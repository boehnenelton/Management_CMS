# Changelog

## Self-Audit Pass
### 2026-07-13 — app.py 4.3.0 -> 4.3.1

Requested audit of the full codebase, not just a recap of prior claims.
Checked: full compile sweep (clean), JS syntax (clean), drift between the
canonical `management_cms` package and this app's embedded copy (none —
all 8 shared library files confirmed byte-identical), version-string
consistency, changelog file integrity (re-verified no recurrence of the
earlier shell-backtick corruption incident — none found), and a fresh
read-through of the most recently touched code for anything missed.

**Found and fixed one real (narrow) bug**: a race condition in the async
build lock. `_BUILD_STATE["running"]` was set to `True` inside the
background thread itself rather than by the route handler that checks
it — leaving a real window between `POST /api/build`'s guard check and
the flag actually being set, during which two near-simultaneous build
requests could both pass the guard and start two concurrent builds
writing to the same shared state and the same `Export/` directory. Fixed
by moving the check-and-set into the route handler under a
`threading.Lock()`, so it happens atomically before the background thread
is even started. Verified by firing 5 genuinely concurrent build requests
at once: exactly one was accepted, the other four correctly rejected with
409.

**Cleanup**: removed a confirmed-dead import (`CmsNav`, aliasing the
CMS-layer Nav module) from `app.py` — checked it was never actually
called anywhere before removing it, only imported.

**Re-verified end-to-end** with a fresh full pipeline: post category +
page category + home page + regular page + post, deleted the page
category mid-flow and confirmed the referencing page's `category_id`
correctly cleared (no dangling reference), built the site, confirmed zero
audit findings across all five taxonomies and a correctly-built home
page.

**Noted but not changed** (real, low-priority, or already covered
elsewhere): there is no `DELETE /api/tags/<id>` route yet, so tags are
currently add-only from the UI — not a bug, just an acknowledged gap;
`lib_bejson_management_cms_nav.py` (the CMS-layer Nav module) remains
scaffolded by `management_cms_init()` for Section V audit coverage but is
otherwise fully unused, as already documented in the previous pass; the
`webframework_scaffold_resync_components()` overwrite-on-restart
consideration flagged in an earlier pass still stands, unresolved, since
no template-customization UI exists yet to actually be at risk from it.

## Auto-Nav Fallback Ignored Page-Type Categories Entirely
### 2026-07-13 — app.py 4.2.0 -> 4.3.0

**Reported: build claimed no categories existed for both Page and Post
categories, even after creating them.** Reproduced directly: created only
a `category_type="page"` category (no post-type ones) and confirmed the
build's automatic navigation fallback (added in the previous pass)
incorrectly reported "no categories exist yet" — it was hardcoded to only
ever query `category_type="post"`, completely ignoring `"page"`-type
categories. Anyone using categories primarily to organize Pages, or using
both types, would see this exact false negative.

Fixed `_management_cms_build_category_sidebar_html()` to build both the
"post" and "page" category trees and combine them — a single labeled
"Categories"/"Pages" split when both types have content, or a plain
unlabeled list in the common single-type case.

**This surfaced a follow-on bug that would have shipped 404s**: nothing
previously built an actual archive page for page-type categories — only
post-type categories ever got one — so once page-type categories started
appearing as real nav links, clicking them would have 404'd. Added a
parallel archive-page generation pass for page-type categories, listing
every Page filed under each (via the existing
`management_cms_content_list_pages(..., category_id_fk=...)` filter — no
new lookup function needed). Written to `/page-category/` rather than
`/category/`, since both category types share one `Category` entity's
`slug` field with no cross-type uniqueness enforced — two categories of
different types could otherwise collide on the same output filename.
`management_cms_static_build()`'s result gained a `page_category_pages`
count for parity with the existing `category_pages`.

**Verified directly**: page-only category case now correctly shows in
nav and its archive page correctly lists the page filed under it; adding
a post-type category alongside it correctly produces the labeled
"Categories" / "Pages" split; the genuine zero-category, zero-nav-item
case still correctly reports that nothing exists (not silently
papered over).

## Two More Real Bugs Found While Reviewing for Further Improvements
### 2026-07-13 — app.py 4.1.0 -> 4.2.0

- **Adding a tag mid-edit silently wiped the entire post form.**
  `quickAddTag()` re-rendered the Post editor with `postForm({})` — an
  empty object — after adding a new tag, discarding every unsaved field
  (title, content, category, status, everything) the person had already
  typed, with no warning. Fixed by capturing the current in-progress form
  state (`_capturePostFormState()`) before re-rendering, so the form now
  correctly preserves whatever was being edited. Verified live: modified a
  post's title and content mid-edit, added a new tag, confirmed both
  modifications were still present afterward.
- **Deleting a category left a dangling reference on any page/post filed
  under it.** `management_cms_taxonomy_delete_category()` correctly
  re-parents child categories but has no way to reach Page/Post's
  manifests (different files; taxonomy.py doesn't import content.py to
  avoid a circular dependency) — so any page/post whose `category_id_fk`
  pointed at the deleted category kept pointing at a category that no
  longer existed. Not a crash (the Static Builder's category lookups
  already degrade gracefully to an empty string), but a real
  data-integrity gap. Fixed in the `delete_category()` route in `app.py`
  — the one place with access to all three manifests — by nulling out
  `category_id_fk` on any page or post that referenced the deleted
  category. Verified directly: created a category, filed a post under it,
  deleted the category, confirmed the post's `category_id` correctly
  became `null` instead of a dangling ID.

## Bare-Minimum Automatic Build Fallbacks (no more required setup)
### 2026-07-13 — app.py 4.0.0 -> 4.1.0

Previous behavior was too strict: a build with no manually-configured
Site Nav items and no page explicitly marked `page_type="home"` produced
a technically-valid but sparse site — no `index.html`, no navigation —
and only *told* you it hadn't, rather than just giving you something
reasonable by default. Reworked both into genuine automatic fallbacks:

- **Navigation**: manual Site Nav items still win if any are configured.
  If none are, `management_cms_static_build()` now auto-generates a
  hierarchical navigation sidebar directly from the Category tree (new
  `_management_cms_build_category_sidebar_html()` /
  `_management_cms_render_category_sidebar_tree()`), nested parent/child
  categories and all, each linking to that category's archive page. Since
  the archive page already lists every post filed under that category,
  "posts and pages automatically populate under their category section"
  falls out of existing behavior rather than needing a second listing
  mechanism.
- **Home page**: an explicit page with Page Type = Home still wins if one
  exists. If none does, the build now auto-generates a real `index.html`
  — a recent-posts feed (reusing the existing "Recent Posts" widget from
  `lib_bejson_management_cms_feed.py`, rendered through the same
  `management_cms_home` template a real custom home page would use, so it
  looks consistent) — instead of skipping `index.html` entirely. Every
  build now always produces a working entry point.
- Both fallbacks add an informational note to the build result rather
  than a build-blocking warning, since the build no longer actually fails
  or produces an incomplete site in either case — just explains what
  default was used and how to replace it (add Site Nav items; mark a page
  as Home). The frontend build log/toast no longer shows these as errors.

**Verified** with the exact reported scenario: a category, a nested
child category, and one published post — nothing else configured. Build
now produces a real `index.html` (site header, working hierarchical
nav showing both categories, a Recent Posts feed listing the post,
footer) and a real `category/news.html` archive page correctly listing
the post filed under it. Confirmed live through the actual Build button
in a browser, zero JS errors.

## Site Nav Was Never Actually Connected to the Static Builder + Drag-and-Drop
### 2026-07-13 — app.py 3.2.0 -> 4.0.0

**Reported: exported pages were "pretty much blank... no website template
or nothing," and no index.html was produced.** Reproduced the exact
scenario (real pages created without explicitly picking a Page Type, a
real build afterward) and found three compounding, real bugs — not one:

1. **No page was marked `page_type="home"`.** This isn't really a "bug"
   in the strict sense (the code does what it's told), but it's a real
   gap: nothing warns you if you forget, and the site silently ships with
   no entry point. Confirmed directly: `home_built: false`, no
   `index.html` at all.

2. **`_management_cms_build_page()` used the page's *slug* for its title
   token, not its actual title** — a leftover from before Page had a real
   `title` field (see the previous pass's fix). Every non-home page's
   `<h1>` showed the ugly slugified text instead of the real title.

3. **The big one: the Static Builder's navigation menu was reading from
   an entirely disconnected data source.** There are two separate nav
   systems in this codebase — the admin one (`lib_bejson_Management_nav.py`,
   backing the "Site Nav" panel, `/api/nav`, everything the UI actually
   lets you manage) and a CMS-layer one
   (`lib_bejson_management_cms_nav.py`, `Content/Nav/MFDB`) that
   `management_cms_init()` scaffolds but that **nothing in this app has
   ever written to or exposed through any route** — no UI, no API
   endpoint, nothing. `_management_cms_get_nav_html()` was calling into
   that second, always-empty system. Every single build rendered a
   completely empty navigation menu, regardless of what was actually
   configured in the Site Nav panel — confirmed by checking whether
   `CmsNav` (the CMS-layer nav module) is called anywhere in `app.py`
   beyond its import statement: it is not. Combined with bug #2's stale
   titles and no shared page chrome at all (see below), a built site
   looked exactly like disconnected fragments with nothing tying them
   together — matching "no website template" precisely.

**All three fixed:**

- `management_cms_static_build()` gained a `warnings` list in its return
  value. A missing home page and an empty/unconfigured nav are now
  surfaced as clear, specific messages — both in the JSON response and in
  the Build panel's log/toast — instead of silently producing an
  incomplete site with no explanation.
- `_management_cms_build_page()` now uses the real `title` field (falling
  back to slug only for pages that predate that fix).
- **`_management_cms_get_nav_html()` rewritten to call the real, connected
  admin Nav module** (`lib_bejson_Management_nav.management_nav_get_tree()`)
  instead of the disconnected CMS-layer one. This is a deliberate new
  cross-family dependency (`Management_CMS` → `Management`), added because
  there is only one real navigation data source in this app and the
  Static Builder needs to render from wherever the admin UI actually
  writes. `management_cms_static_build()` gained a new
  `admin_nav_manifest_path` parameter for this; `app.py`'s build call now
  passes `PAGES_MANIFEST` (where "Site Nav" data actually lives) instead
  of the empty `cms_nav` manifest. `nav_html` is now threaded through
  every page/post/home/archive render.
- **The five default templates were rebuilt from bare `<h1>+content`
  stubs into an actual site shell**: a shared `<header>` (site title,
  links home) + `<nav>{{nav_html}}</nav>` + `<main>` + `<footer>`, with
  real (if minimal) layout CSS inlined directly in each template. Verified
  the rendered output directly: a real header, a real working nav bar
  populated from actual admin Nav data, real page titles, a footer — a
  coherent site instead of isolated fragments.
- **Made this take effect immediately for anyone already running the
  app**: `_ensure_cms_components_registered()` previously only registered
  a template if it was completely missing — meaning an already-running
  instance would have kept the old bare templates forever, even after
  this exact fix. Now always re-registers the 5 canonical defaults on
  every startup. Safe to do since this only touches the *canonical*
  store; any future per-app customization lives in the local root
  manifest, which rendering always checks first regardless.

**A real design tension flagged, not silently ignored**: making the
canonical defaults always-refreshing means `webframework_scaffold_resync_components()`
(which pushes canonical → local on every startup, needed so this exact
fix reaches already-deployed apps) will also overwrite a locally
customized template's content on the next restart, if the local
customization reused the same skeleton_id as its canonical counterpart.
There is no UI for locally customizing these templates yet, so this
causes no visible harm today — but it's a real limitation worth revisiting
before building a "customize your site's look from the dashboard" feature,
which would need this resync step to skip anything the user has
explicitly edited.

## Drag-and-Drop for Categories and Nav (catching the UI up to existing backend support)

Both the Category tree and the Nav tree gained real HTML5 drag-and-drop,
matching exactly what each backend already supported and nothing more:

- **Categories**: backend only supports reparenting (`parent_id` — there's
  no `sort_order`/position field on Category at all), so drag-and-drop
  here is honest about that: drop a category onto another to make it a
  child, or onto a dedicated "top level" drop zone to make it a root
  category again. No fake sibling-ordering implied.
- **Nav**: the backend already had both `parent_id` *and* a dedicated
  `management_nav_reorder()` / `POST /api/nav/reorder` sibling-ordering
  endpoint that the UI never called — so Nav gets the full three-zone
  drag: drop on the top/bottom edge of another item to reorder as its
  sibling (calling the existing reorder endpoint), drop in the middle to
  reparent, or drop on the top-level zone to become a root item.

**Found and fixed one more real bug while testing this**: `GET
/api/nav/tree` returned the raw library field names (`nav_label`,
`nav_url`, `nav_active`) instead of the translated shape (`label`, `url`,
`active`) that `/api/nav` and the frontend both expect — so navigation
tree labels and URLs rendered completely blank in the UI (though the
underlying data was always there and correct). Fixed by recursively
translating the tree through the same `navlink_to_dict()` used elsewhere.

**Verified with real browser tests, not just code review**: dragged a
category onto another and confirmed the backend `parent_id` actually
changed; dragged a nav item to reorder it above a sibling and confirmed
`nav_position` values actually updated correctly afterward. Zero JS
errors in either case.

## Page Save Bug Fix + Media Library Subtabs (Uploads / YouTube / Image Links)
### 2026-07-13 — app.py 3.1.0 -> 3.2.0

**Reported: changing a Page's status (draft to published, or any edit)
"refuses to save."** Reproduced directly and confirmed a genuine,
100%-reproducible bug, not intermittent:

- The **Page entity never had a persisted `title` field** — only `slug`.
  `title` was accepted as a parameter at creation time solely to derive
  the slug, then discarded; it was never actually a column in the
  `PAGE_FIELDS` schema.
- Every save from the UI (`savePageModal()`) sends a `title` value
  regardless, and the server's `update_page()` route whitelist explicitly
  allowed it through. `management_cms_content_update_page()` passed it on
  to `MFDBCore.mfdb_core_update_entity_record_bulk()`, which raises
  `BEJSONCoreError` for any field name that isn't part of the entity's
  real schema — so **every single edit-and-save of an existing Page
  failed with an unhandled 500**, regardless of which field the person
  actually changed. Posts were unaffected since Post's schema genuinely
  does have a `title` field.
- Confirmed by reproducing the exact flow directly against the API before
  fixing anything: create a draft page, then PUT the same payload the UI
  would send — 500 Internal Server Error every time.

**Fixed properly** (not just papered over) by adding a real, persisted
`title` field to `PAGE_FIELDS` in `lib_bejson_management_cms_content.py`
— appended at the *end* of the field list, not inserted in the middle,
since BEJSON rows are positional and an insertion partway through would
misalign every value after it for pages already saved to disk. Existing
pages simply come back without a `title` key (Python's `zip()` truncates
gracefully on a short row) until next saved, which `page_to_dict()`'s
`.get("title") or slug` fallback already handles without any migration
step. Updated `management_cms_content_create_page()` to actually store
the title going forward, `page_to_dict()` in `app.py` to return it, and
the frontend (`editPage()`, `pageForm()`, the page card display) to use
the real title instead of the previous slug-as-a-stand-in workaround.
Re-verified against the exact previously-failing case: the draft →
published save now returns `200 {"ok": true}` and the title round-trips
correctly through create, list, and edit.

## Media Library Subtabs — YouTube and External Image Links

Extended the media picker (previously uploads-only) with three subtabs:
**Uploads** (unchanged), **YouTube**, and **Image Links** — the latter two
register external URLs into the same admin media registry rather than a
separate system, so they appear in the same picker grid without a second
management surface to maintain.

- `lib_bejson_Management_media.py`: added an `external_url` field to
  `MEDIA_FIELDS` (again appended at the end, same backward-compatibility
  reasoning as the Page title fix), a `management_media_add_external()`
  function, and `_extract_youtube_id()` (regex-based, covers
  `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/embed/`, and
  `youtube.com/shorts/` URL forms). YouTube links are normalized to a
  canonical `youtube.com/watch?v=<id>` URL regardless of which form was
  pasted in; thumbnails use YouTube's public, no-API-key-required
  `img.youtube.com/vi/<id>/hqdefault.jpg` pattern. An unrecognized
  YouTube URL is rejected with a clear 400 rather than silently stored
  broken.
- New route `POST /api/media/external` (`media_type`: `"youtube"` or
  `"external_image"`).
- `admin_media_to_dict()` now branches on `file_type` to compute the
  right `url`/`thumbnail_url` pair for each of the three kinds.
- Frontend: the picker overlay gained a tab bar (reusing the existing
  `.becss-filter-bar` component already used elsewhere, not a new
  pattern) and two small add-forms, one per external type. Selecting any
  item in any tab fills the target field the same way real uploads
  already did — no special-casing needed at the call site.

**Verified**: backend tested directly — adding a valid YouTube link,
rejecting an invalid one, adding an image link, and confirming the full
media list returns correct `url`/`thumbnail_url` for all three kinds.
Then a full browser test: opened the picker from the Page editor,
confirmed Uploads is the default active tab, switched to YouTube, added a
link, selected it, confirmed the field populated with the normalized
watch URL; reopened the picker, switched to Image Links, added a link,
selected it, confirmed the field populated with the raw URL. Zero JS
errors throughout.

## Site Preview (Build panel)
### 2026-07-12 — app.py 3.0.0 -> 3.1.0

Added a "👁 Preview" button next to Build. Opens a stacked overlay
(`.becss-preview-overlay`, same z-index-stacking convention as the media
picker and category manager) containing an iframe that shows the built
site.

**Design choice, disclosed rather than silent**: rather than literally
spinning up a second HTTP server process, the preview is served by a new
route (`GET /preview/<path:filename>`) on this same already-running app.
A separate process would need its own port allocation and lifecycle
management — more moving parts than necessary for "serve some static
files back," especially on Android/Termux where spawning extra processes
is more fragile — and a route achieves the identical practical result:
the entire built site, previewable, with working internal navigation.

**The one real technical wrinkle, solved**:
`management_cms_static_build()` writes every internal link as
root-relative (`/about-us.html`, `/feed.xml`, etc.) so the exported site
works correctly once deployed to a real domain root. Serving those same
files back verbatim under `/preview/` would mean every link inside the
iframe resolves against the app's own root instead of staying inside the
preview — clicking anything would jump the whole page out of the overlay
entirely. Fixed by injecting `<base href="/preview/">` into each HTML
page as it's served (first-match, case-insensitive, right after the
opening `<head>` tag) so the browser resolves every root-relative link,
image, and stylesheet reference against `/preview/` instead. Non-HTML
files (images, CSS, feeds) are served unmodified.

Path traversal is guarded the same way as the media-serving route fix
from a previous pass — routed through the already-hardened
`bejson_safe_join()`, returning 404 on any escape attempt.

The Preview button checks for a completed build first
(`fetch("/preview/index.html")`) before opening the overlay — if nothing's
been built yet, it shows a clear toast ("Build the site first") instead
of opening an empty iframe.

**Verified**: the pre-build case correctly 404s; after a real build, the
served HTML correctly carries the injected `<base>` tag; a path-traversal
attempt against `/preview/` correctly 404s; and in a real browser test,
clicking Preview opens the overlay with the actual built homepage content
visible inside the iframe, and the X button correctly closes it. Zero JS
errors.

**Housekeeping note for future deliveries**: going forward, package
zip filenames will include the app's version number
(e.g. `Management_CMS-app-v3.1.0.zip`) rather than a fixed name, per
request.

## Build Reliability — Enabled Threaded Dev Server
### 2026-07-12 — app.py 3.0.0 (no version bump — see note)

Follow-up to the async build rework: `app.run()` did not set
`threaded=True`, meaning Flask's development server handled one request
at a time by default. The background build thread itself runs
independently of that (a real OS thread via `threading.Thread`), but on a
slower device, any contention between the build thread's work (file I/O,
Pillow/WebP processing) and the main process could plausibly delay the
status-polling requests the UI depends on to ever see the build finish —
consistent with a build that says "Building…" and never resolves.

Added `threaded=True` to the `app.run()` call. Verified: triggered a
build and polled `/api/build/status` in rapid succession immediately
afterward — correctly observed `running: true` mid-build, then the
completed result on the next poll, with `/api/build/download` succeeding
right after. Real content (a category, a published page, a published
post) built correctly throughout.

Version note: no bump — this is a one-line server-startup configuration
change, not a behavioral change to any route or library function.

## Build Process Fix — Real Bugs Found and an Async Rework
### 2026-07-12 — app.py 2.9.0 -> 3.0.0

Reported: build failed on a real device; `/api/build/download` correctly
said no export existed, meaning the actual build never completed
server-side, but no specific error message was available to diagnose
from. Studied a reference CMS's own publish flow (a Flask conversion of a
Tkinter-based site publisher) purely for its architecture — not copied,
adapted — since its build route runs asynchronously in a background
thread with a polling log endpoint rather than blocking the request,
which is directly relevant to this app's real deployment target
(low-power Android/Pydroid3/Termux devices where a slow synchronous build
risks exceeding a mobile WebView's request timeout).

**Two real, confirmed bugs found, independent of the async rework:**

1. **`buildPage()` in `templates/index.html` referenced `d.size`** — a
   field from the *old*, now fully-replaced build pipeline
   (`Build.management_build_write_export()` used to return one) that does
   not exist anywhere in `management_cms_static_build()`'s actual response
   shape. `d.size.toLocaleString()` throws `TypeError: Cannot read
   properties of undefined` on every single successful build — meaning
   even when the server-side build worked perfectly, the success feedback
   silently crashed and never reached the user. This alone could produce
   exactly the reported symptom ("errored") on a build that actually
   succeeded. Fixed to reference the real fields (`pages`, `posts`,
   `category_pages`, `tag_pages`, `media_copied`, `auto_published`,
   `audit`).

2. **`/api/build` had no error handling at all** — any exception inside
   `management_cms_static_build()` (most plausibly
   `ManagementCmsMissingComponentError`, if the running app instance's
   components were never seeded — e.g. an app copy that predates the
   component-seeding fix from an earlier pass, or one that's never been
   restarted since a library update) propagated as an unhandled Flask 500
   with no message reaching the UI. Since the reported failure means the
   export genuinely never got created, this — or something like it — is
   the most likely actual root cause, though the exact traceback from the
   user's device wasn't available to confirm which specific exception
   fired.

**Fixed both, plus made the underlying failure mode itself impossible:**

- **`management_cms_render_layout()`** (in
  `lib_bejson_management_cms_static_builder.py`) now self-heals instead of
  hard-failing when a component is missing from *both* the per-app
  manifest and the canonical Web_Framework store: it registers a minimal
  built-in fallback skeleton (`_BUILTIN_FALLBACK_SKELETONS`, bare HTML, no
  BECSS styling — a real app is still expected to register its own richer
  defaults) on the fly and retries once, only raising
  `ManagementCmsMissingComponentError` if the component_id isn't one of
  the 5 this module knows about at all. This directly closes the most
  likely real-world crash: a stale or never-restarted app instance can no
  longer fail a build outright over missing components. **Verified by
  deliberately wiping every `management_cms_*` component from both stores
  and confirming the build still completed successfully**, producing
  valid HTML using the built-in fallback.

- **Reworked `/api/build` to run asynchronously**, adapting the pattern
  from the reference CMS's `r_build()`/`r_log()`: `POST /api/build` now
  starts a background thread and returns immediately
  (`{"ok": true, "started": true}`); a new `GET /api/build/status` reports
  `{"running", "result", "error", "error_type", "log"}`. Every exception
  is now caught, logged with its full traceback (both into the returned
  log and to the server console), and surfaced through `/api/build/status`
  in a form the UI can actually display — no more silent unhandled 500s.
  `templates/index.html`'s `buildPage()` now kicks off the build and polls
  `/api/build/status` every 700ms until it's done, showing live log lines
  and a clear final error (with exception type) or success summary.
  Verified live in a browser: build log updates during the build, final
  summary appears correctly once complete, zero JS errors.

- Version bump 2.9.0 -> 3.0.0: this is a real architectural change to the
  build pipeline (synchronous → asynchronous) plus multiple fixes to the
  specific feature that was reported broken, not a minor patch.

## Media Library Picker + Continued Bug-Scanning Pass
### 2026-07-12 — app.py 2.8.0 -> 2.9.0

- **Added a media library picker** for the Featured Image field on both
  the Page and Post editors — a "🖼 Browse…" button next to the URL input
  opens a stacked overlay (mirroring the existing category-manager
  overlay's z-index-stacking pattern, `.becss-mediapicker-overlay` at
  z-index 350, above the edit modal's 200) showing a thumbnail grid of
  every uploaded image (`GET /api/media`, filtered client-side to
  `mime_type` starting with `image/`). Clicking a thumbnail fills the
  URL field and closes the picker; the underlying Page/Post form stays
  open and unaffected. Also supports uploading a brand-new image directly
  from inside the picker ("⬆ Upload & Use"), which uploads via the
  existing `/api/media/upload` endpoint and auto-selects the result.
  Verified with a real headless-browser test: selecting a pre-existing
  image correctly populated the field and the page saved with it; the
  inline upload-and-use flow correctly uploaded and auto-selected a new
  file. Zero JS errors.

- **Found and fixed three real bugs while building and testing the picker
  and continuing the code audit:**

  1. **Path traversal in the upload handler** (`app.py`'s
     `upload_media()`): used the client-supplied `f.filename` raw, directly
     in a path join, with no sanitization — Flask/Werkzeug does not do
     this automatically. A crafted filename (e.g. containing `../`
     segments) could have written outside `Content/media/uploads/`
     entirely. Fixed with `werkzeug.utils.secure_filename()`. Same
     vulnerability class as the Zip Slip issue fixed in the previous pass.

  2. **Silent overwrite on filename collision**, same function: two
     different uploads sharing an original filename would silently
     overwrite each other on disk (including the WebP sibling), while the
     *old* database row (media_id, file_hash, file_size_bytes, webp_path)
     stayed exactly as it was — now describing content that was no longer
     actually on disk. Fixed by de-duplicating with a `-1`, `-2`, ...
     suffix before the extension when the target path is already taken.
     Verified directly: two different-content files uploaded under the
     same original name now both exist independently on disk with
     distinct, correct file hashes.

  3. **Path traversal in `serve_media_file()`**: the route used
     `<path:filename>` (which permits `/` and `..` segments in the URL)
     joined directly onto `UPLOADS_DIR` with no containment check — a real
     arbitrary-file-read vulnerability (confirmed exploitable:
     `GET /media-files/../../app.py` before the fix). Fixed by routing
     through the already-hardened `bejson_safe_join()` (see the previous
     pass's path-traversal fix) and returning 404 on any escape attempt
     rather than leaking whether a file exists outside the upload
     directory. Verified: the exact same traversal request now correctly
     returns 404 with no content.

- **Continued auditing files not yet fully reviewed** (`mfdb_core.py` in
  full for the 11 functions this app's live code actually calls,
  `bejson_core.py` in full). Found one more real, if not currently
  reachable, bug:

  4. **`bejson_core_sort_by_field()`** (in `lib_bejson_Core_bejson_core.py`)
     used `x[idx] if x[idx] is not None else ""` as its sort key — for any
     non-string field (e.g. `"integer"`), a mix of real `None` and real
     numeric values in the same call raises `TypeError`, since Python 3
     disallows comparing `str` and `int`. Checked whether this is actually
     exercised anywhere in this app first (it is imported by
     `mfdb_core.py` but never called by any of this app's live code
     paths) — fixed anyway since it's a real bug in shared Core code and
     cheap to fix correctly: now sorts on a `(is_none, value)` tuple key,
     so `None` never gets compared against a differently-typed real value.
     Verified directly against the exact scenario that used to crash
     (mixed `None`/int values in an integer field) — now sorts correctly.

- Every fix in this pass verified against a real running server (not just
  read through) — the traversal fixes were tested with actual malicious
  requests, not just code inspection, and the collision fix was tested
  with two genuinely different files sharing a name.

- Version note: unlike the previous pass, this one genuinely changes
  `app.py`'s own route logic (a rewritten `upload_media()`, a rewritten
  `serve_media_file()`, a new import) and adds a new user-facing feature
  (the media picker) — so `VERSION` is bumped this time, 2.8.0 -> 2.9.0,
  matching the header banner comment. Each touched library file also got
  its own version bump per its header (`path_guard.py`, `bejson_core.py`).

## Component Distribution, Editorial Automation, and Final Audit/Bug Fixes
### 2026-07-12 — app.py 2.8.0 (unchanged version — see note)

Verified items 1-3 from this pass's integration directive were already
complete from the earlier Phase 4 UI pass: Category/Nav parent_id
dropdowns (`cf_parent`/`nvf_parent`, recursive indented-option pickers),
the Post editor's 5-state status dropdown + conditional `scheduled_at`
field, and the Page editor's `page_type` selector (including `"home"`).
No rework needed — confirmed by direct inspection, not re-implemented
blind.

- **Item 4 — Component Distribution**: added
  `webframework_scaffold_resync_components(str(SCRIPT_PATH))`, called
  right after `_ensure_cms_components_registered()` on both the normal
  startup path and the factory-reset re-bootstrap path. Previously, the 5
  CMS factory-default skeletons were seeded into Web_Framework's canonical
  library-level store only — the app's own root manifest never actually
  had local copies, so `management_cms_render_layout()`'s "check the app's
  own manifest first" branch always fell through to canonical, silently
  defeating the entire point of manifest-aware rendering. Verified
  directly: the app's own `104a.mfdb.bejson` now carries all 5 CMS
  components (plus `app_shell`) in its `ComponentMap` immediately after a
  fresh startup — they can now be edited locally, in the dashboard,
  without touching library code, which is what "manifest-aware" was
  supposed to mean in the first place.

- **Built `management_cms_content_list_due_for_publish()` and
  `management_cms_content_auto_publish_due()`** (new, in
  `lib_bejson_management_cms_content.py`): the integration directive
  referenced a function, `management_posts_list_due_for_publish()`, to
  back "automated publication triggers" — that function does not exist
  anywhere in this codebase, under that name or any other; checked with a
  direct grep across every file before writing anything. Built the real
  equivalent under this family's actual naming convention instead. Wired
  `management_cms_content_auto_publish_due()` into
  `management_cms_static_build()`'s very first step, so any post whose
  `status == "scheduled"` and `scheduled_at` has already passed gets
  promoted to `"published"` (via the existing
  `management_cms_content_publish_post()`) before the rest of the build
  runs — the build naturally includes it. The list of auto-published post
  ids is returned in the build summary under `"auto_published"`. Verified
  directly with two posts, one scheduled an hour in the past and one a day
  in the future: only the past one flipped to `"published"` during the
  build; the future one correctly stayed `"scheduled"`.

- **Item 5 — Final Audit & Verification, and a real bug found doing it**:
  ran the requested end-to-end check
  (create content → upload a real image → `POST /api/build`) and confirmed
  zero findings across all five taxonomies (Category/Nav/Page/Post/Media)
  — Target State Verification holds. But the second half of the
  requested check — confirming WebP assets land in `Export/media/` — 
  initially FAILED. Investigated and found a real bug:
  **`_generate_webp()` (in both `lib_bejson_management_cms_media.py` and
  the admin `lib_bejson_Management_media.py` — the same bug was
  duplicated into both when the admin module was built by copying the
  CMS-layer one) stored `webp_path` as a path relative to the manifest's
  own directory, while `original_path` on the same entity was stored
  absolute.** Two path fields on the same row with different resolution
  semantics. The real-world effect: `management_cms_static_build()`'s
  `_management_cms_copy_media()` step checks `os.path.exists(webp_path)`
  before copying — but a manifest-relative string resolves against the
  *process's current working directory*, not the manifest's directory, so
  that check silently returned False every time and the WebP variant
  never made it into the exported site, despite generating correctly on
  disk in the first place. **Fixed in both files**: `_generate_webp()` now
  returns `str(out_path.resolve())` — an absolute path, matching
  `original_path`'s existing convention, removing the ambiguity entirely
  rather than teaching the copy step a second path-resolution rule.
  Re-verified end-to-end after the fix: `Export/media/` now correctly
  contains both the original upload and its `.webp` variant.

- **Separately found and fixed a real path-traversal bug** in
  `lib_bejson_Core_bejson_path_guard.py`'s `bejson_safe_join()` — its Zip
  Slip boundary check was a bare string-prefix comparison
  (`str(target_path).startswith(str(base_path))`) with no path-separator
  awareness, meaning a sibling directory that merely *shared* `base_dir`'s
  string prefix (e.g. `base_dir="/srv/app"` and a zip member resolving to
  `/srv/app_evil/payload`) would incorrectly pass the check. Confirmed
  this function is live, load-bearing code — the one and only mitigation
  `lib_bejson_Core_mfdb_core.py`'s archive-extraction loop relies on for
  exactly this class of attack, not dead/unused code. Fixed to require
  `target_path == base_path or target_path` starts with `base_path + os.sep`,
  which correctly rejects the sibling-directory bypass while still
  allowing legitimate paths. Verified directly against the exact bypass
  scenario (before the fix: silently accepted; after: correctly raises
  `ValueError`).

- Version note: `VERSION` in `app.py` was NOT bumped this pass (stays at
  2.8.0) — none of this pass's changes touched `app.py`'s own request-
  handling logic beyond two new import/call lines for the resync wiring;
  the substantive changes are all inside `lib/`. The three touched library
  files (`lib_bejson_management_cms_content.py`,
  `lib_bejson_management_cms_static_builder.py`,
  `lib_bejson_management_cms_media.py`, `lib_bejson_Management_media.py`,
  `lib_bejson_Core_bejson_path_guard.py`) each got their own version bump
  per-file, per the standing policy — see each file's own header for its
  new version number.

## Rebrand to "Management_CMS" + Factory Reset
### 2026-07-11 — app.py 2.6.0 -> 2.8.0
- **Rebranded from "Homepage Builder" to "Management_CMS"** across all
  user-facing surfaces and source comments: `<title>`, sidebar header text,
  `app.py`'s startup console banner and header docstring, the
  `Bootstrap.management_bootstrap_deploy()` app-name string (cosmetic —
  only affects the root manifest's own `db_name`/description metadata, not
  any filename or path), `lib_bejson_Management_bootstrap.py` and
  `lib_bejson_Management_config.py`'s description comments,
  `lib_bejson_management_cms_init.py`'s example-app docstring reference
  (also backported to the standalone `management_cms` package), and the
  orphaned `lib_bejson_Management_build.py`'s exported-page footer credit
  line (`Built with Management_CMS · Elton Boehnen · ...`).
- **Deliberately left unrenamed**: the `HB_Framework/` folder and
  `hb_style.css`/`scaffold_style.css`/`scaffold_template.html` filenames.
  These are internal scaffold-asset names copied verbatim into every new
  page `webframework_scaffold_deploy()`-style tooling stamps out — renaming
  them would mean updating every reference inside
  `lib_bejson_WebFramework_scaffold.py`'s embed logic and could break
  already-deployed site assets that reference `hb_style.css` by that exact
  filename. This is a judgment call, not an oversight — flagging it
  explicitly rather than silently leaving it unmentioned. Only the
  human-readable `Description:` comment text inside those files was
  updated (zero risk, not a path/filename change).
- Deleted the stale `Export/index.html` demo artifact that shipped in the
  original zip — leftover output from the old, now fully-replaced
  Notes/Tasks/Links dashboard-export pipeline, and still displayed the old
  brand name in its content.
- Version bump note: `VERSION` in `app.py` had not actually been bumped
  incrementally during the management_cms integration or Phase-4 UI passes
  in this conversation, despite the standing policy requiring a bump on
  every delivered change — an oversight, now caught up in one jump
  (2.6.0 -> 2.8.0) rather than reconstructed retroactively per-pass.

- **Added Factory Reset** (`Settings → Danger Zone`): a confirm-tab flow,
  not a simple JS `confirm()` dialog — the modal's Save button starts
  disabled and only enables once the user types the exact phrase `RESET`
  into a dedicated confirmation field (`_updateFactoryResetBtn()`,
  real functional gating, not decorative). The server independently
  requires the same exact string in the POST body
  (`POST /api/factory-reset {"confirm": "RESET"}`) as defense-in-depth —
  verified directly: an unconfirmed or wrong-string request is rejected
  with 400 and changes nothing.
- `_factory_reset()` in `app.py`: moves (not deletes) the root manifest,
  all of `Content/` (every admin and CMS-layer MFDB, including uploaded
  media files under `Content/media/uploads/`), `config/`, `Export/`, and
  — importantly — the two legacy `Persist/homepage_data.bejson` /
  `Persist/config.bejson` files, into a timestamped backup folder under
  `Persist/factory_reset_backups/<UTC timestamp>/`, preserving the same
  relative layout. Nothing is permanently destroyed.
- The legacy Persist files are backed up and moved away deliberately, not
  just left alone: leaving them in place would cause
  `_migrate_legacy_data()`/`_migrate_legacy_config()` to silently
  re-import the old pre-migration data the moment the in-process
  re-bootstrap (which happens immediately after the wipe, same request)
  runs — defeating the entire point of a "clean default state" reset.
- After wiping, `_factory_reset()` immediately re-runs the full bootstrap
  sequence in-process (`Bootstrap.management_bootstrap_deploy()` →
  `management_cms_init()` → `_ensure_cms_components_registered()`) — the
  app is fully usable again in the same request/response cycle, no restart
  required.
- Does NOT touch `lib/` (application code) or
  `lib/Web_Framework/ComponentsMFDB` (the canonical Static Builder fallback
  skeletons) — these are factory-shipped code/templates, not user data.
- **Verified end-to-end, live**: created real categories/pages/notes,
  confirmed an unconfirmed reset attempt and a wrong-confirmation attempt
  both correctly no-op with a 400, ran a real reset, confirmed every
  entity count dropped to zero and `site_title` reverted to its true
  default (`"My Homepage"`), confirmed the timestamped backup folder
  actually contains full copies of everything that was wiped, and
  confirmed the app kept serving requests successfully in the same process
  immediately afterward. Also ran a real headless-browser test of the
  confirm-tab UI itself: Save button correctly starts disabled, stays
  disabled after typing the wrong text, enables only after typing `RESET`
  exactly, and the click-through completes with zero JS errors.

## templates/index.html — Phase 4: Pages/Posts/Categories/Nav UI wiring
### 2026-07-11
- Added four new sidebar panels, matching the existing bespoke-per-panel
  style used by Links/Notes/Todos (no shared generic-component abstraction
  introduced — a separate "layers.md" proposal for one was reviewed and
  explicitly declined in favor of consistency with the existing code):
  **Pages** (title/slug/page_type/category/status/meta description/content
  HTML/author/featured image; page_type select is populated from
  /api/page-types, which doubles as the "home page" designation per
  Directive 3 — selecting page_type="home" is how a page becomes the site
  root, no separate toggle needed), **Posts** (title/slug/category/the
  5-state status workflow from /api/post-statuses, with a conditional
  Scheduled-At field that only appears when status="scheduled"/content
  HTML/author/featured image/a tag checklist with an inline "add new tag"
  control backed by two new routes, plus a status filter bar and a
  quick-publish button on non-published cards), **Categories** (indented
  tree view via /api/categories/tree, a Post/Page type filter tab bar
  reusing the same filter-bar pattern as the existing Links category
  filter, and a parent-category picker built from a recursive
  indented-option helper), and **Site Nav** (indented tree view via
  /api/nav/tree, same recursive-indent picker pattern for parent
  selection, target/active fields).
- Added two new routes needed by the Posts editor that didn't exist yet:
  GET/POST /api/tags (list + create) and GET /api/page-types /
  GET /api/post-statuses (expose the taxonomy module's static registries
  to the UI instead of hardcoding the option lists client-side).
- Reused existing generic card/badge/filter-bar CSS classes
  (becss-link-grid, becss-link-card, becss-card__actions,
  becss-note-card__badge, becss-filter-bar) rather than introducing new
  near-duplicate BEM blocks — these are already visually generic despite
  their block names, and the existing Links panel itself already reuses
  becss-note-card__badge for its own category badges, so this follows
  established practice rather than a new one.
- **Verified with a real headless-browser test (Playwright/Chromium), not
  just curl** — clicked through every new panel, opened every Add modal,
  filled in real form fields, saved, and confirmed the records were
  actually created server-side. Zero JavaScript console errors or page
  exceptions; the one console warning that did appear (a 403 on a Google
  Fonts CDN request) is a sandbox network-policy artifact unrelated to any
  app code, confirmed by checking the failing request URL directly.
- Not built: drag-and-drop reordering for Categories/Nav trees (manual
  sort_order/position fields exist server-side but no UI control for
  them beyond the parent-picker) and a dedicated Media library browser
  panel (upload endpoint exists and is used by nothing in the UI yet) —
  both reasonable next steps, not attempted here since neither was asked
  for and both are separable, sizeable pieces of work on their own.

## templates/index.html — BECSS/BEM CSS conversion (merged from a separate upload)
### 2026-07-10
- Converted all CSS class names in templates/index.html to the BECSS-BEM
  convention (e.g. .nav-btn -> .becss-nav-item, .tbtn -> .becss-toolbar__btn,
  .app-header -> .becss-header), and introduced OKLCH color tokens for
  --primary/--primary-hover alongside renamed CSS custom properties
  (--bg -> --bg-page, --text -> --text-main, etc.). This was delivered as a
  separate upload against the pre-integration app.py; merged here on top of
  the management_cms integration above rather than replacing it, since the
  two changes touch different files (templates/index.html only, vs.
  app.py + lib/Management_CMS + lib/Management/nav+media).
- Verified: no old (non-BECSS) class names remain in the file; confirmed
  the JS (go(), toggleSidebar(), closeSidebar()) was already updated
  consistently to reference the new class names, not just the CSS — no
  breakage. Re-ran a live server test after merging: page serves correctly
  (299 becss- class references, 0 old-style class names), and a fresh API
  call (category create) still works normally alongside the new frontend.
- HB_Framework/hb_style.css, assets/scaffold_style.css, assets/scaffold_template.html,
  HB_Framework/template.html were all confirmed byte-identical to the
  pre-conversion versions — this pass touched templates/index.html only.

## app.py + lib/Management_CMS (new family) — management_cms public-hosting layer integration
### 2.6.0 -> 2.7.0 — 2026-07-10
- Added `lib/Management_CMS/` (new family, 8 files): `lib_bejson_management_cms_content.py`
  (Page/Post/PageSeo CRUD, `category_id_fk`, `page_type`), `_taxonomy.py` (shared
  hierarchical Category + flat Tag), `_nav.py` (id/parent_id Nav, `management_cms_nav_get_tree`),
  `_feed.py` (RSS/Atom/JSON, pagination, widgets), `_media.py` (SHA-256 + WebP),
  `_init.py` (`management_cms_init` scaffolds all 5 Content/ manifests, `management_cms_audit`),
  `_static_builder.py` (de-classed static site orchestrator, manifest-aware rendering),
  `_shared.py` (UUID/timestamp/slugify/esc).
- Copied `lib_bejson_Core_bejson_list_validator.py` into `lib/Core/` — this app's Core
  library predated that file entirely; the new nav/taxonomy hierarchy code depends on it.
- Replaced stale `lib/Management/lib_bejson_Management_nav.py` (flat, position-only,
  unused by any route) with the hierarchical id/parent_id rebuild (`management_nav_get_tree`,
  delete-with-reparent, `validate_list()` wired via a field-name translation shim
  since this entity's key is `nav_id`, not `id`).
- Replaced stale `lib/Management/lib_bejson_Management_media.py` (10-field, unused by
  any route) with the SHA-256 + WebP version (12 fields — schema change, no existing
  data affected since neither file was wired into any route before this change).
- **Bug fixed in `management_cms_init()`** (also backported to the standalone
  `management_cms` package): it unconditionally called
  `webframework_taxonomy_register_type()` on every invocation, even for manifests that
  already existed — since this app calls `management_cms_init()` on every startup
  (it needs to, to populate `CMS_MANIFESTS` even when the guarded Bootstrap block
  above it is skipped), every restart would have appended duplicate `TaxonomyType`
  rows forever. Fixed: only registers a taxonomy if it isn't already present.
- **Taxonomy naming collision found and avoided**: `Bootstrap.management_bootstrap_deploy()`
  already registers a bare `"page"` taxonomy pointing at the OLD admin Pages MFDB
  (`Content/Pages/MFDB`, plural, flat category, no hierarchy — deployed via
  `lib_bejson_Management_pages.py`, still fully intact and untouched). Calling
  `management_cms_init()` with no prefix would register a SECOND, different manifest
  (`Content/Page/MFDB`, singular) under the same `"page"` key. Fixed by calling
  `management_cms_init(..., taxonomy_prefix="cms_")` — the five new manifests register
  as `cms_category`/`cms_nav`/`cms_page`/`cms_post`/`cms_media`. No path collision either
  way (`Pages` vs `Page` are different folders) — this was a registry-naming collision,
  not a filesystem one. **The old admin Pages MFDB (with its own Page/PageCategory
  entities and secondary LandingSection/PageSeo/Media/NavLink entities from Bootstrap)
  now coexists, unused by the new public routes, alongside the new five-manifest
  management_cms layer.** Flagging this plainly: nothing forced a choice between the
  two, so both exist on disk. `/api/nav` and the media-upload routes deliberately use
  the OLD Pages MFDB's NavLink/Media secondary entities (matching what
  `lib_bejson_Management_nav.py`/`lib_bejson_Management_media.py` — the ADMIN functions
  the integration plan named — actually operate on), while `/api/pages` and `/api/posts`
  use the NEW management_cms Content/Page and Content/Post manifests. `lib_bejson_Management_pages.py`
  itself is not called by any route (same as before this change) and not removed.
- Added routes: `/api/pages` (GET/POST), `/api/pages/<id>` (PUT/DELETE); `/api/posts`
  (GET/POST), `/api/posts/<id>` (PUT/DELETE), `/api/posts/<id>/publish`,
  `/api/posts/<id>/archive`; `/api/categories` (GET/POST), `/api/categories/<id>`
  (PUT/DELETE), `/api/categories/tree`; `/api/nav` (GET/POST), `/api/nav/<id>`
  (PUT/DELETE), `/api/nav/tree`, `/api/nav/reorder`; `/api/media/upload` (dual-writes
  into both the admin Pages-MFDB Media entity AND the new `cms_media` manifest — see
  code comment on why both, since the Static Builder's media-copy step reads only from
  the CMS one), `/api/media` (GET), `/api/media/<id>` (DELETE); `/media-files/<name>`
  (static file serving for uploaded originals).
- **`/api/build` fully replaced** (not additive) with `management_cms_static_build()`,
  per the plan's Phase 3 and its Q5 addendum. `Build.management_build_render_homepage`/
  `management_build_write_export` in `lib_bejson_Management_build.py` are no longer
  called by any route — left in place as orphaned, harmless dead code rather than
  deleted (not asked to remove the file).
- Added `_ensure_cms_components_registered()`, called once from `ensure_scaffold_deployed()`:
  registers 5 factory-default BECSS-styled HTML skeletons (`management_cms_home/page/post/
  category_archive/tag_archive`) canonically, since nothing in the integration plan
  actually seeded any — without this, `/api/build` would fail immediately on every fresh
  install (`management_cms_render_layout()` fails loudly by design when a component isn't
  registered anywhere, which is correct; it just means *something* has to register them
  once). Apps can still override any one locally later.
- **Verified end-to-end, live, against a running server** (not just unit-tested):
  category create + tree, page create (including `page_type="home"`) + list, post
  create + list, nav create (2-level) + tree resolution, media upload (real SHA-256
  hash + admin/CMS dual-write), and a full `/api/build` run producing a real static
  site: `index.html`, `about-us.html`, `hello-world.html`, `category/tutorials.html`,
  `feed.xml`/`atom.xml`/`feed.json`, `sitemap.xml`, `robots.txt`, and copied media —
  all inspected and correct. 5-way audit (`category`/`nav`/`page`/`post`/`media`)
  returned zero `verify` findings in the same run.
- **Not done this pass** (Phase 4 — UI/workflow): tree-based Category/Nav pickers, the
  5-state Post status workflow UI, and the Page-editor home-page toggle are backend-ready
  (every API route above supports them) but `templates/index.html`'s JS was not touched —
  flagged as the natural next step rather than attempted in the same pass.

## lib/Management (new — Family: Management)
### 1.0.0 — 2026-07-01
- `lib_bejson_Management_notes.py` — Note + NoteCategory CRUD.
- `lib_bejson_Management_tasks.py` — TodoItem CRUD (incl. toggle-done).
- `lib_bejson_Management_links.py` — Link CRUD.
- `lib_bejson_Management_bootstrap.py` — deploys all three sections as
  atomically-separated MFDBs under `<app_root>/Content/` via
  Web_Framework's per-taxonomy scaffold deploy, and registers each in the
  root TaxonomyType registry. This is the only file that ties Web_Framework
  and Management together; the two libraries otherwise never reference
  each other.
- Tested end-to-end: deploy -> add/list/update/delete on all three sections.
  Full run confirmed at /tmp/full_app_test during build.
- NOTE: this is the new library, built and verified standalone. app.py's
  live Flask routes still read/write the original single
  Persist/homepage_data.bejson (104db) — I have not rewired app.py to use
  these new per-section MFDBs. That's a further integration step I didn't
  do without being asked, since it touches your working app's live routes.

## lib/Web_Framework (Family: Web_Framework)
### 1.1.0 — 2026-07-01
- Renamed `lib_webframework_*.py` -> `lib_bejson_WebFramework_*.py` to match
  the ecosystem-wide `lib_bejson_<Family>_<name>` convention already used
  across every existing family (Core, CMS, Gaming, HTML, AI, Chunker, MD,
  System, Utility, Core_Nesting).
- Scaffold HTML/CSS are exact verbatim copies of the real
  `HB_Framework/template.html` / `hb_style.css` design (sizing, sidebar,
  toolbar, modal, toast — unchanged). `HB_Framework/` itself untouched.
- `webframework_scaffold_deploy_taxonomy_mfdb()` — deploys a per-taxonomy
  templated MFDB under `/Content/<taxonomy>/<mfdb_subfolder>` (subfolder
  name caller-supplied — original spec sketch itself used "MFDB"/"MFDB1"/
  "DB" inconsistently) plus that taxonomy's own HTML/CSS.

### 1.0.0 — 2026-07-01
- `webframework_scaffold_deploy()` — root MFDB (manifest + TaxonomyType
  entity) + scaffold template/CSS.
- `lib_bejson_WebFramework_taxonomy.py` — TaxonomyType schema/CRUD.
- Deliberately does not import or reference any Lib_PY/HTML (HTML3) module.

## lib/Core (verbatim copies, unmodified — Library Immutability 5.5)
- lib_bejson_Core_bejson_core.py
- lib_bejson_Core_bejson_env.py
- lib_bejson_Core_bejson_errors.py
- lib_bejson_Core_bejson_validator.py
- lib_bejson_Core_bejson_path_guard.py
- lib_bejson_Core_mfdb_core.py
- lib_bejson_Core_mfdb_validator.py

## app.py — rewired to Management persistence
### 1.3.0 — 2026-07-01
- Replaced the single 104db (Persist/homepage_data.bejson) persistence
  layer with the three Management-section MFDBs (Content/Notes,
  Content/Tasks, Content/Links), deployed via
  `lib_bejson_Management_bootstrap.management_bootstrap_deploy()` on first
  run.
- One-time legacy migration pulls every row out of the old file into the
  new MFDBs, preserving original ids/timestamps, then leaves the old file
  untouched as a backup (not deleted, not written to again).
- BUG FOUND AND WORKED AROUND (in the old app, not introduced by this
  change): app.py never re-derived field positions from the on-disk
  "Fields" array of the loaded 104db — it always used the hardcoded
  SCHEMA_FIELDS order in its own source. Migrations over time appended new
  field declarations to the on-disk Fields metadata without reordering it
  to match, so the file's declared Fields list was stale/decorative and
  did not reflect actual value positions (e.g. on-disk metadata labeled
  position 17 as "todo_created_at" while the value actually stored there
  was the todo_id). The migration function replicates the OLD app's
  hardcoded runtime order, not the on-disk metadata, and was verified
  against the live 14-row dataset — all 7 notes, 3 categories, 3 tasks,
  and 1 link came through with correct titles/ids/timestamps.
- All 15 API routes smoke-tested against the migrated data: GET/POST/PUT/
  DELETE on links, notes, note-categories, todos, plus build/download.
  All pass.
- Response JSON shapes are unchanged from v1.2.0 — the frontend
  (templates/index.html) needs no changes.

## lib/Web_Framework (Family: Web_Framework)
### 1.2.0 — 2026-07-02
- Added `COMMON_TAXONOMY_FIELDS` — the baseline fields most taxonomies will
  share (`entity_id`, `category`, `label`, `created_at`).
- Added `webframework_scaffold_deploy_template_mfdb()` — distributes a
  standalone, pre-built template MFDB containing only the common fields,
  as a distributable starting point/reference.
- `webframework_scaffold_deploy_taxonomy_mfdb()` gained
  `prepend_common_fields` (default `False`). When `True`, the common
  fields are placed first in a new taxonomy's schema, ahead of its own
  fields. Default is `False` so the already-deployed Notes/Tasks/Links
  sections are unaffected — tested, still returning identical data
  (7 notes, 3 categories, 3 tasks, 1 link) after this change.
- The global MFDB's TaxonomyType registry entity (root manifest) was
  already in place from 1.0.0 — confirmed still intact, no change needed.
- NOTE: Notes/Tasks/Links were NOT retrofitted with the common fields —
  that would mean adding entity_id/category/label/created_at onto schemas
  that already have their own id/category-ish/timestamp fields under
  different names, which touches the live, working app. Didn't do that
  without being asked; flagging it as a separate decision.

## lib/Web_Framework — Templates MFDB (new)
### 1.3.0 — 2026-07-02
- `lib_bejson_WebFramework_templates.py` (new) — manages a separate global
  MFDB (`lib/Web_Framework/TemplatesMFDB/`) that is distributed WITH the
  library itself, not deployed per-app. Holds HTML/CSS template content as
  data records (Template entity: template_id, template_name,
  template_type, category, content, created_at). Other libraries now pull
  template content through this module instead of copying loose asset
  files directly.
- Seeded with the real `HB_Framework/template.html` /
  `hb_style.css` content, verified byte-for-byte identical to source.
- `lib_bejson_WebFramework_scaffold.py` rewired: both
  `webframework_scaffold_deploy()` and
  `webframework_scaffold_deploy_taxonomy_mfdb()` now write template
  content pulled from the Templates MFDB instead of `shutil.copyfile`-ing
  the loose `assets/scaffold_template.html` / `scaffold_style.css` files.
  Regression-tested: deployed output is still byte-identical to the real
  design, and the live app (Notes/Tasks/Links) is unaffected — 7 notes,
  3 categories, 3 tasks, 1 link, all correct after the change.
- `assets/scaffold_template.html` / `scaffold_style.css` are left in place
  as the original source files (that's what seeded the Templates MFDB) but
  are no longer read at deploy time — the Templates MFDB is now the single
  distribution point.

## lib/Web_Framework — templates now embedded in the distributed root MFDB
### 1.4.0 — 2026-07-02
- Corrected the previous approach: the Templates MFDB was staying inside
  the library and never actually being distributed. Now:
  - `webframework_scaffold_deploy()` creates the root MFDB with TWO
    entities: `TaxonomyType` (global registry) AND `Template` (the
    pre-built HTML/CSS scaffolds, embedded directly into this distributed
    root MFDB, copied in from the library's canonical TemplatesMFDB at
    deploy time). The root MFDB is now self-contained once distributed.
  - `webframework_scaffold_deploy_taxonomy_mfdb()` now takes
    `root_manifest_path` as its first argument and pulls template content
    OUT of that already-distributed root MFDB — not from the library's
    internal TemplatesMFDB. (Call-site change — updates
    `lib_bejson_Management_bootstrap.py` 1.1.0 to pass `root["manifest_path"]`.)
  - Added `lib_bejson_WebFramework_templates.webframework_templates_get_from_manifest()`
    — generic getter that reads Template content from any manifest (root
    or library), used by both flows.
- Regression-tested: fresh deploy confirms the root MFDB carries the
  embedded `Template` entity with both templates; taxonomy deploy pulled
  from that distributed root is byte-identical to the real design; live
  app (Notes/Tasks/Links, build, index) all still correct.

## Common taxonomy schema rebuild + resync
### 2.0.0 — 2026-07-02
- Notes/Tasks/Links entities rebuilt on the literal COMMON MFDB ENTITY
  TAXONOMY SCHEMA from the spec note: taxonomy, type, category, id, label,
  idx_position, idx_sorting, active, hidden, created_at — first in every
  schema, entity-specific fields after (Note: content,color;
  TodoItem: done,priority,detail; Link: url,icon,description).
- Bootstrap now deploys all three with prepend_common_fields=True.
- app.py rewired: response conversion + update routes use the new generic
  field names (id/label/category) mapped back to the unchanged public API
  JSON shape.
- Legacy migration bug found and fixed: older notes (pre note_category
  field) have their created_at sitting where the current schema's
  "category" slot is — no category was ever recorded for them. Fixed with
  per-row detection (timestamp-shaped value -> old shape). All 7 notes now
  migrate with correct category/created_at.
- Added `webframework_scaffold_resync_templates()` to Web_Framework —
  pushes updated library template content out to an already-deployed
  root MFDB and cascades to every registered taxonomy. Tested: simulated
  a template edit, resynced, confirmed root + Notes/Tasks/Links all
  updated, then restored canonical content.
- Full regression: all API routes, round-trip CRUD, build/download, index
  page — all pass.

### lib_bejson_WebFramework_scaffold.py 1.5.0 — 2026-07-02
- `prepend_common_fields` now defaults to True on
  webframework_scaffold_deploy_taxonomy_mfdb — every new taxonomy
  automatically gets the common schema, no flag needed. Pass False
  explicitly only for a deliberate non-taxonomy lookup table.
- Verified: brand-new "Bookmarks" taxonomy created with zero flags gets
  the full common schema automatically; existing Notes/Tasks/Links
  unaffected (7 notes, 3 tasks, 1 link, all correct).

## app.py — rewired onto merged libraries
### 2.0.0 — 2026-07-04
- Replaced inline config load/save with `lib_bejson_Management_config.py`.
  One-time migration copies the real, already-customized
  Persist/config.bejson (site_title "BoehnenElton2024", etc.) into the new
  location the library expects; old file untouched.
- Replaced the inline static-page renderer with
  `lib_bejson_Management_build.py` — now uses `html.escape` instead of the
  old hand-rolled replace chain. XSS-tested through the real route with a
  live `<script>` payload — confirmed neutralized in the exported HTML.
- Added Link Categories: `/api/link-categories` (GET/POST/PUT/DELETE),
  mirroring Note Categories. Delete is self-healing (nulls out `category`
  on affected links) — implemented inside the library itself this time,
  not in app.py.
- `/api/links` now also returns `link_categories` alongside the existing
  `categories` (grouped-by-name) key — additive, not a breaking change.
- Web_Framework side rebuilt on component_map/skeleton_store — opaque to
  app.py, no route changes needed there.
- Full regression against the REAL existing data (7 notes, 3 tasks, 1
  link, real config) — all correct, all routes pass, build/download/XSS
  all verified.

## Links subfolder consistency fix
### 2.1.0 — 2026-07-04
- Links now deploys under "MFDB" like Notes/Tasks (was "DB") for full
  consistency across all three taxonomies — schema, registry, templates,
  AND now folder naming all identical.
- Backward-compatible: app.py checks for an existing "DB" folder first;
  if found (an already-deployed instance), keeps using it untouched — no
  forced migration, no data loss. Only fresh installs get the new
  consistent "MFDB" name.
- Found and fixed a real bug this surfaced: an already-deployed instance
  from before LinkCategory existed has no LinkCategory entity in its Links
  manifest — calling the category routes on it threw. Added
  `_ensure_link_category_entity()` — self-healing backfill, runs on every
  startup, only acts if the entity is actually missing. Tested: simulated
  an old DB-style deployment with a real link and no LinkCategory entity,
  confirmed it now self-heals and works, while a fresh install gets the
  consistent MFDB naming from the start. Real production data (7 notes,
  3 tasks, 1 link) re-verified unaffected.

## Simplification — no existing deployments, so no fallback needed
### 2.2.0 — 2026-07-04
- Simplified: removed the DB/MFDB dual-path fallback and the LinkCategory
  backfill logic added in 2.1.0 — no existing deployment exists, so that
  compatibility layer was unnecessary complexity. LINKS_MANIFEST is now
  hardcoded to "MFDB", identical in form to NOTES_MANIFEST/TASKS_MANIFEST.
- Directory cleaned: removed the empty, unused `instructions.md` and
  stray `__pycache__`. Kept `Export/index.html` (a real prior export,
  not test output).
- Full regression re-confirmed on the simplified tree: 7 notes, 3 tasks,
  1 link, real config, link-category add, build — all correct.

## Category framework fully synced across all three sections
### 2.3.0 — 2026-07-04
- Added TaskCategory (lib_bejson_Management_tasks.py 3.0.0), mirroring
  NoteCategory/LinkCategory exactly: same fields (cat_id, cat_name,
  cat_created_at), same self-healing FK-null-out on delete.
- bootstrap.py (2.1.0) now deploys TaskCategory as a secondary entity in
  the Tasks MFDB, same pattern as NoteCategory/LinkCategory.
- New /api/task-categories routes (GET/POST/PUT/DELETE), identical shape
  to /api/note-categories and /api/link-categories.
- todo_to_dict now exposes todo_category; add_todo/update_todo accept it.
- get_todos response now includes task_categories alongside todos, for
  parity with notes (categories) and links (link_categories).
- Verified: all three sections now expose identical
  management_<section>_category_add/list/delete function names and
  behavior. Full regression: real data (7 notes, 3 tasks, 1 link)
  untouched, category add/assign/self-heal-delete tested on Tasks,
  build/export still correct.

## Category framework wired front-to-back
### 2.4.0 — 2026-07-04
- Frontend (templates/index.html) now has full category UI for ALL three
  sections, not just Notes:
  - Generic category manager (openCatMgr(kind), addCat, saveEditCat,
    deleteCat) — one implementation, works for notes/links/todos via
    CAT_ENDPOINTS mapping.
  - Links: replaced free-text category input with a proper dropdown
    sourced from LinkCategory, added filter bar + badge, matching Notes'
    UI pattern exactly (previously had zero real category management in
    the UI — it was a raw string field).
  - Todos: added category filter bar, badge, and dropdown in the task
    form — previously had NO category UI at all.
- Backend fix: add_link/update_link no longer force a "General" string
  default — category can be null (Uncategorized), consistent with how
  Notes and Tasks already worked. This was a real inconsistency between
  sections, now resolved.
- Real bug found and fixed: legacy links carry a plain free-text category
  string ("PERSONAL") from before LinkCategory existed. Without a fix,
  the new cat_id-based UI would have silently shown it as "Uncategorized."
  Added a one-time migration step that promotes each distinct legacy
  string into a real LinkCategory, remapping the link to the new cat_id.
  Verified: the real existing link now correctly shows "PERSONAL" as a
  proper category, not lost.
- Full regression: real data (7 notes, 3 tasks, 1 link, real config)
  intact; task-category assign/self-heal tested through the live routes;
  build/export still correct.

## Category framework is now automatic — the ecosystem standard
### 2.5.0 — 2026-07-04
- lib_bejson_WebFramework_scaffold.py (2.1.0): added
  CATEGORY_LOOKUP_FIELDS and made webframework_scaffold_deploy_taxonomy_mfdb()
  automatically deploy a paired Category lookup entity for every new
  taxonomy — deploy_category_lookup=True by default, this is now the
  standard. Pass False to opt out. category_entity_name defaults to
  f"{entity_name}Category", overridable (needed for Tasks: entity_name
  "TodoItem" -> category name "TaskCategory").
- lib_bejson_Management_bootstrap.py (3.0.0): simplified — no longer
  manually creates NoteCategory/TaskCategory/LinkCategory via
  _add_secondary_entity. Web_Framework does it automatically now; Tasks
  passes category_entity_name="TaskCategory" as the one necessary override.
- Verified: fresh deploy produces IDENTICAL entity names/schemas as
  before (NoteCategory, TaskCategory, LinkCategory) — Management's
  existing CRUD functions needed zero changes.
- Verified opt-out: deploy_category_lookup=False on a test taxonomy
  correctly creates no category entity.
- Verified default-on: a brand-new taxonomy with zero extra arguments
  automatically gets a correctly-named Category entity
  (e.g. "Bookmark" -> "BookmarkCategory").
- Full regression against real data: 7 notes, 3 tasks, 1 link, task
  category assign/self-heal through live routes, build/export all correct.

## CMS Pages + Landing Page builder — new publishing layer
### 2.6.0 (libraries) — 2026-07-05
- New taxonomy: Pages — the CMS/publishing side of the app, deliberately
  separate from the personal-management taxonomies (Notes/Tasks/Links).
  Deployed the exact same way as any other taxonomy, via Web_Framework's
  scaffold (webframework_scaffold_deploy_taxonomy_mfdb) — no different
  foundation needed. Gets an automatic PageCategory, same as the standard.
- lib_bejson_Management_pages.py (new) — Page CRUD: slug (auto-generated
  from title if not given), status (draft/published/archived),
  meta_description, layout. Publish/archive helpers.
- lib_bejson_Management_landing.py (new) — reorderable landing-page
  sections (hero, features, pricing, testimonials, CTA, FAQ, content,
  gallery, stats, newsletter). LandingSection stored as a proper MFDB
  secondary entity in the Pages MFDB (page_id_fk), NOT a loose JSON file
  per page — a real improvement over the reference source this was
  adapted from, which stored sections in flat JSON files bypassing its
  own MFDB entirely.
- Section renderers adapted from an external reference CMS someone
  shared for evaluation — kept because they were already sound
  (correct html.escape usage throughout, matches our own build.py fix).
  Rebuilt as pure functions on lib_bejson_Core_mfdb_core, full UUIDs
  (source used truncated 12-char hex IDs; ours uses full uuid4()).
- bootstrap.py (4.0.0): now deploys Pages + LandingSection alongside the
  three existing sections; returns "pages" in its result dict.
- Tested end-to-end: deploy -> create page -> add all 10 section types
  -> render (XSS-tested with a live payload in a hero headline, escaped
  correctly) -> reorder -> publish. All passed. Regression-tested against
  existing real data: 7 notes, 3 tasks, 1 link, build/export all still
  correct — Pages addition did not disturb the existing app.
- NOT done: no Flask routes or frontend UI for Pages/Landing yet — this
  round was libraries only, per the "build the CMS architecture, adapt
  the concepts to fit our framework" scope. Routes/UI are a clear next
  step if wanted.

## Third-party CLI tool evaluated and merged in — CMS family renamed to Management
### 2.9.0 — 2026-07-06
- Evaluated a third-party CLI tool (built independently on top of an
  earlier snapshot of these exact libraries). Genuinely valuable — merged
  in rather than kept as a separate conflicting "CMS" family (per your
  flag that the name would collide with an existing ExpCMS elsewhere).
- Page schema merged: added content_html, content_markdown, author,
  featured_image, parent_page_id_fk (hierarchy), sort_order to the
  existing Page fields (slug, status, meta_description, layout).
- New: PageSeo (meta_title, meta_keywords, OG tags, canonical_url,
  robots_directive) — secondary entity, one row per page.
- New: lib_bejson_Management_media.py — Media registry (filename, mime
  type, dimensions, alt text).
- New: lib_bejson_Management_nav.py — site navigation (NavLink: label,
  url, target, position, active, reorderable).
- Added PageCategory CRUD to pages.py — full symmetry with Note/Task/
  LinkCategory, something the source tool didn't have (it used a
  separate, non-standard Category entity).
- New: lib_bejson_Management_cli.py — ManagementCLIProject, a stateful
  wrapper around the stateless library functions for CLI/script use.
  Adopted the source's manifest-resolution pattern (looks up each
  section's MFDB path through the TaxonomyType registry rather than
  hardcoding paths) — a genuine improvement worth considering for app.py
  too.
- New: `cms` — a Click-based terminal CLI (init, page create/list/show/
  edit/publish/archive/delete, category create/list/delete, seo set, nav
  add/list, link add/list/audit, build). No web admin needed.
- Fixed: source's invalid RELATIONAL_ID header replaced with real UUIDs
  throughout.
- Tested end-to-end via the actual CLI (not just library calls): init ->
  page create -> category create -> nav add -> link add -> link audit
  (real HTTP request, got a genuine response back) -> build. All passed.
- Full regression: existing live Flask app (7 notes, 3 tasks, 1 link,
  build/export) completely unaffected by this addition.

## Audit remediation — MANAGEMENT_CMS5_AUDIT.txt
### app.py 5.1.0 — 2026-08-13

Full remediation pass against `MANAGEMENT_CMS5_AUDIT.txt` (scoped to
Package 13 / Project v4.18.0 / app.py v4.17.0 — this project was already
at `VERSION="5.0.0"` in `app.py` with the header comment left stale at
4.17.0; that drift is fixed as part of this pass too, and the deliverable
is repackaged as PKG1/v5.1.0 to reflect the changes below).

**HIGH**
- **H-1 / M-7 — unauthenticated destructive API, no CSRF, bound to
  0.0.0.0.** Added a shared `X-Admin-Token` bearer-token gate
  (`app.before_request`), token generated on first run and persisted to
  `config/admin_token.txt` (or pinned via `MANAGEMENT_CMS_TOKEN` env var;
  disable entirely — not recommended — via `MANAGEMENT_CMS_NO_AUTH=1`).
  Exempts only `/` (so the browser can load the shell that then attaches
  the token to every call), `/static/`, and `/media-files/` (read-only
  assets referenced from plain `<img src>`, which can't set headers).
  `templates/index.html`'s `api()` helper, the media-upload `fetch()`, the
  preview iframe, and the download link all now send the token (header for
  fetch/XHR, `?token=` query param for GET-only navigations via a new
  `withToken()` helper). Default bind host changed from `0.0.0.0` to
  `127.0.0.1`; override with `MANAGEMENT_CMS_HOST=0.0.0.0` as an informed
  opt-in.
- **H-2 — category silently dropped on Page/Post create.** `create_page()`
  / `create_post()` read `d.get("category_id")`, but the frontend sends
  `category_id_fk` — picking a category in the create dialog was silently
  ignored. Now reads `d.get("category_id_fk", d.get("category_id"))` in
  both routes.
- **H-3 — stale 4-char `esc()` in scaffold/skeleton blobs.** Both
  `skeleton_store.bejson` copies (`data/` and
  `lib/Management/ComponentsMFDB/data/`) and all 12 live scaffold HTML
  copies (`scaffold_template.html`, `HB_Framework/template.html`,
  `assets/scaffold_template.html`, every `Content/*_template.html`) had
  the old `esc()` that only encodes `& < > "`. Brought in line with
  `templates/index.html`'s hardened version (also encodes `'` and `` ` ``).
- **H-4 — trust-based upload validation.** Added `MAX_CONTENT_LENGTH`
  (64 MB) to cap request-body size; added an extension allow-list
  (`_ALLOWED_UPLOAD_EXTENSIONS`) and magic-byte content sniffing
  (`_sniff_file_type()`) so `file_type` is derived from the file's actual
  bytes, not the client-supplied `f.mimetype` — a claimed extension whose
  sniffed category disagrees with its extension's category is rejected
  outright.

**MEDIUM**
- **M-1 — `quickAddTag()` broke saving a new post.** Was forcing
  `editTarget = editTarget || {type:"post"}` unconditionally, which — for
  a genuinely new post (`editTarget === null`) — made `savePostModal()`
  take the edit branch and `PUT /api/posts/undefined` (404), silently
  losing the save. Now mirrors `deleteTag()`'s already-correct pattern:
  re-render the open form without touching `editTarget`.
- **M-2 — `note_color` interpolated into a CSS context unchecked.**
  `esc()` blocks HTML breakout but doesn't validate CSS syntax. The note
  card background now checks `note_color` against the known `NOTE_COLS`
  swatch allow-list before use, falling back to the default swatch for
  anything else.
- **M-3 — unscoped filter-bar `querySelectorAll`.** `setLinkFilter` /
  `setNoteFilter` / `setTodoFilter` queried `.becss-filter-bar__tab`
  document-wide, so filtering links/notes/todos also stripped the active
  state off the media picker's `mpTab-*` tabs (same class, different
  component). Scoped each to its own output container
  (`#linksOut`/`#notesOut`/`#todosOut`), matching
  `setPostStatusFilter`/`setCatTypeFilter`'s existing correct pattern.
- **M-4 — `_navLinkPickerCache` never invalidated.** Reset to
  `{page:null, post:null}` every time the Nav Item form opens (both add
  and edit), so pages/posts created after the picker's first use show up
  without a full page reload.
- **M-5 — `_BUILD_STATE` read/written outside the lock.** Added
  `_build_log()` / `_build_set()` helpers so every mutation in
  `_run_build_in_background()` goes through `_BUILD_LOCK`; `GET
  /api/build/status` now takes one locked snapshot instead of reading each
  field unsynchronized.
- **M-6 — relative/empty exported OG & canonical URLs.**
  `management_cms_static_build()` (in
  `lib_bejson_Management_static_builder.py`) now appends a build warning
  when `site_url` is empty, surfacing the gap in the build log instead of
  only being discoverable by reading the exported HTML afterward.
- **M-8 — `AUDIT.txt` contained the entire report twice.** De-duplicated;
  kept the first copy (196 -> 97 lines).

**LOW**
- **L-1** — `threading`/`traceback` imports moved from mid-file (BUILD
  section) to the top import block, alongside new `logging`, `secrets`,
  `hmac` imports needed for the H-1/H-4/L-2 fixes.
- **L-2** — replaced the one remaining `print()` (startup banner) and the
  build-failure `print(tb)` with the stdlib `logging` module
  (`logging.basicConfig` + a named `Management_CMS` logger).
- **L-3** — Python version floor was undocumented. `app.py` now checks
  `sys.version_info < (3, 8)` at startup and exits with a clear message
  instead of failing later with a confusing `TypeError` (the floor is set
  by `Path.unlink(missing_ok=True)`, used in the legacy-file archive
  step, which is 3.8+ only).
- **L-6** — "Homepage Builder" rebrand drift fixed in all scaffold/
  template header comments and both `skeleton_store.bejson` blobs — the
  v2.8.0 rebrand now reaches every deployed scaffold, not just
  `HB_Framework`/`assets`.
- **L-7** — `.becss-catmgr__item input` (descendant selector, never
  matched because `startEditCat()` applies both classes flatly on the
  same `<input>`) changed to `.becss-catmgr__item.input` (compound
  selector on one element).
- **L-8** — added hex fallback (`#DE2626`/`#c01f1f`) declared before the
  `oklch()` values for `--primary`/`--primary-hover`, so a browser that
  can't parse `oklch()` falls back to the hex declaration instead of an
  unparseable custom property.
- **L-11** — confirmed not an issue in this delivered zip: `Export/`
  already ships `feed.xml`/`atom.xml`/`sitemap.xml` alongside the page/
  post/category output (10 files total) — the audit's concern applied to
  an older chunk.
- **L-10** — added `requirements.txt`, pinned (`Flask`, `Werkzeug`,
  `Pillow`). Round-2 audit flagged this as possibly missing `click`
  (assuming `lib_bejson_Management_cli.py` is Click-based) — checked:
  it isn't. That file has zero `click`/`argparse` imports; it's a plain
  Python class (`ManagementCMS`) meant to be imported and driven
  programmatically, not a Click CLI. No `click` dependency exists to pin.
  Also verified the WebP-on-upload path actually works with Pillow
  installed from this file (round-2 audit noted `webp_path: ""` on the
  package's two media rows, correctly reading that as "Pillow wasn't
  present when that package was built" rather than a bug — the media
  library already degrades gracefully by design, leaving `webp_path`
  empty when Pillow is unavailable rather than failing the upload).

**Not addressed this pass:** L-4's durable fix (content_html validation
at the create/update routes — the seed data was fixed, but nothing
stopped a fresh instance of the same bug; closed in 5.2.0, see below),
L-5 (non-portable absolute paths — confirmed only present in the archived
`Persist/factory_reset_backups/` snapshot, correctly left untouched
rather than "fixed"), M-2's durable fix (full `onclick`-string-context ->
`addEventListener`+`dataset` migration, CHECKLIST item 1b — structural
rewrite, correctly deferred), and the Direction-1 naming decision /
Layer 2 formalization (blocked on Elton per CHECKLIST). No
`docs/variable_naming_issues.md` findings were logged this pass (no
variable-naming audit was run) — removed the dangling reference to that
file below; it did not exist and nothing in this pass warranted creating
it.

## Audit remediation, round 2 — review of the 5.1.0 fixes themselves
### app.py 5.2.0 — 2026-08-13

Elton had the 5.1.0 remediation pass itself independently reviewed
("Management_CMS — Audit Pass 2"). It found the pass was substantial and
mostly correct, but shipped one critical self-defeating flaw and three
inaccurate claims. All fixed here. Full item-by-item detail also in
`CHECKLIST.md` section 15.

**Critical**
- **§3.1 — the 5.1.0 auth gate was fully bypassable.** `/` was (correctly)
  exempt from the token check — the browser has to load something first —
  but `index()` then rendered `ADMIN_TOKEN` directly into that same
  unauthenticated page. `GET /`, read the token out of the HTML, use it
  on every other route: the whole gate was a no-op, worst in exactly the
  scenario it was built for (`MANAGEMENT_CMS_HOST=0.0.0.0` LAN exposure).
  Fixed: `/` no longer receives the token at all. A new client-side login
  prompt (shown on first load, or after any 401) collects it from the
  person running the app — printed to the console/log at startup, or read
  from `config/admin_token.txt` — verifies it against new route
  `GET /api/auth/check`, and holds it only in `sessionStorage` (cleared
  when the tab closes). That route also sets a `SameSite=Strict`
  `admin_token` cookie — the one channel accepted for **GET** requests
  without the header, used by the two navigations that can't set a custom
  header (the preview iframe's `src`, the ZIP download link). The 5.1.0
  `?token=` query-string fallback for those same two cases is removed
  entirely (it leaked into server logs and browser history). Every
  state-changing route (POST/PUT/DELETE) still requires the header, so a
  cross-site page relying on the cookie alone still can't perform a write
  — CSRF stays closed. Verified live against a running instance: token
  absent from `/`'s response body; unauthenticated calls 401; wrong token
  401; correct token returns 200 and sets the cookie; a GET succeeds on
  cookie alone; a **POST with cookie-only (no header) still 401s**,
  confirming the CSRF property actually holds and isn't just assumed.

**High**
- **§3.2 — L-4 recurred.** The `<H2O>Post Title Test</h2>` seed content
  was fixed as *data* in 5.1.0, but nothing in the four
  create/update Page/Post routes validated `content_html` on the way in
  — so the exact same bug class (an unbalanced/mismatched tag) could be,
  and was, saved again. Added `_lint_content_html()`: a balanced-tag
  check via `html.parser` that rejects a genuine start/end mismatch
  (exactly what `<H2O>...</h2>` is — an opening `h2o` tag closed by `h2`)
  or a tag left unclosed at the end of the content, wired into
  `create_page`/`update_page`/`create_post`/`update_post` as a 400 on
  violation. Deliberately lenient about legal HTML5 tag-omission patterns
  (`<li>` without `</li>`, etc.) so it doesn't reject normal content —
  unit-tested against 7 cases (including the exact historical bug) before
  wiring it in. Also rebuilt `Export/` from the already-corrected source
  data and confirmed the malformed markup is gone from the live output
  (`Export/post/Test-Blog-Post.html`, `Export/feed.json`).

**Medium**
- **§4.2 — L-6 (rebrand drift) was only half-finished.** 5.1.0 fixed
  "Homepage Builder" -> "Management_CMS" in the HTML scaffold copies and
  both `skeleton_store.bejson` blobs, but missed the 9
  `Content/*_style.css` header comments, which carry the identical drift
  one directory level down. Swept and fixed all 9; the corresponding
  backup copies under `Persist/factory_reset_backups/` are correctly
  left untouched (backup-never-delete discipline).
- **§4.6 — M-2's fix was render-only.** 5.1.0 validated `note_color`
  against the `NOTE_COLS` swatch palette only on the render path (the
  note card's `background` style) — the save path (`POST`/`PUT
  /api/notes`) still round-tripped whatever value was sent, so a raw API
  call bypassing the swatch-only UI could still persist an out-of-palette
  value. Added `_clean_note_color()`, applied at both routes.
- **§4.7 — residual bad data from the pre-fix H-2 bug.** "Test Blog
  Post" still had `category_id_fk: null` (assigned before H-2 was fixed),
  so its category archive page rendered "No posts in this category yet"
  despite the post existing and appearing elsewhere. Reassigned via the
  app's own `management_cms_content_update_post()` — not a raw data
  edit — and rebuilt `Export/`; confirmed the category page now lists
  the post correctly.

**Documentation corrections (§4.4, §4.5)**
- `docs/security-notes.md` claimed L-4 "was fixed as data" without
  qualification — misleading, since that's exactly the claim the
  recurrence disproved. Corrected and expanded with the real fix and its
  actual limits (structural-only, not a full sanitizer).
- The 5.1.0 changelog entry's own "Not addressed this pass" list
  referenced `docs/variable_naming_issues.md`, which was never created —
  removed the dangling reference rather than leaving it unresolved for a
  future reader.
- The 5.1.0 changelog entry silently omitted **L-3** (Python 3.8+ floor)
  and **L-10** (`requirements.txt`) from its own "fixed" bullets, even
  though both were genuinely done in that same pass — an underclaim,
  in the round-2 audit's own words. Added as proper bullets to the 5.1.0
  section above instead of leaving them unlisted.
- The round-2 audit inferred `lib_bejson_Management_cli.py` is
  Click-based and flagged `requirements.txt` as missing `click`. Checked
  the actual file rather than trusting the inference: zero
  `click`/`argparse` imports anywhere in it — it's a plain importable
  Python class (`ManagementCMS`), not a Click CLI. Nothing to add.
  Separately, functionally verified (not just re-read the code) that the
  WebP-on-upload path works correctly with Pillow installed — the
  round-2 audit's `webp_path: ""` observation was itself already
  correctly read as "Pillow wasn't present when that package was built,"
  not a bug; the media library already degrades gracefully by design.

**Not resolved — genuinely blocked, not guessed at**
- **§4.1 — `bejson_project.json` provenance.** The round-2 audit
  describes a prior `.bejson_project.json` (dot-prefixed,
  `Schema_Version` 2.0.0, a different `Project_GUID`) that this project
  supposedly evolved from. The zip actually delivered to build the 5.1.0
  pass contained no file of that name at all — checked directly. The
  5.1.0 file (no dot, `Schema_Version` 1.6.0 per Elton's own policy
  template) is the first `bejson_project.json` that has ever shipped in
  a package received here; there is no local history to reconcile
  against. `Package_Version` bumped 100 -> 101 for this pass regardless.

## Exported-site redesign — BEJSON-vanilla design system
### ComponentsMFDB skeleton store — 2026-08-13

Elton uploaded three reference templates (vanilla_blog.html,
vanilla_article.html, vanilla_landing.html) and asked for the exported
public site to be designed around them. Rewrote the shared HTML/CSS shell
for all 5 registered layout components (management_cms_home/page/post/
category_archive/tag_archive) to adopt that design language: fixed 18rem
sidebar app-shell with mobile hamburger + slide-in overlay, Syncopate/
Inter/Fira Code fonts, red/black/white BEJSON palette, checkerboard
background texture, card-hover-lift feed cards, pill-style pagination,
and article typography (h2 with red underline, red-square list bullets,
code/pre blocks) for Page/Post content.

This was a shell-only change: every existing `{{token}}` in each
component skeleton was preserved exactly, so nothing in
`lib_bejson_Management_static_builder.py` or `lib_bejson_Management_shared.py`
needed to change — `_management_cms_render_layout()`'s token substitution,
the feed-card/pagination/nav-tree renderers, and every builder function's
token_map are all untouched. Applied to both ComponentsMFDB copies (the
project-root override at `data/skeleton_store.bejson` and the canonical
library default at `lib/Management/ComponentsMFDB/data/skeleton_store.bejson`),
matching how the H-3 esc() fix was applied to both copies previously.

Verified via a real `management_cms_static_build()` run (not just visual
inspection): all rebuilt page types pass a balanced-tag HTML check, zero
leaked `{{token}}` placeholders in output, and a headless-rendered
screenshot of the homepage, a post, a category archive, and a plain page
all confirmed the sidebar/nav/breadcrumbs/feed-cards/typography render as
designed. Note for the record: this environment's only available
screenshot renderer (`wkhtmltoimage`, an old Qt-WebKit engine) has a
genuine bug with `position:fixed -> relative` + `transition` inside a
media query — reproduced it in a 6-line isolated test case unrelated to
this project, confirmed Elton's own `vanilla_landing.html` already uses
the identical `transform: translateX(0) !important` override pattern, and
worked around it for screenshot purposes only (a transition-stripped copy)
without changing any shipped file.

**Not done, flagged for follow-up:** `vanilla_landing.html`'s
hero-section/version-cards/CTA-banner marketing layout was not wired in
for the case where a Page is marked `page_type == "home"` — a custom home
page currently renders with the same article-content styling as any other
Page, not the landing template's distinct hero treatment. That would need
page-type-aware branching in `_management_cms_build_home_page()`
(currently untouched) and a decision on how much of the landing
template's fixed marketing copy (version cards, MFDB banner) is meant to
be literal vs. replaced with CMS-driven content — deferred pending
Elton's direction rather than guessed at.

## Audit remediation, round 3
### app.py 5.3.0 — 2026-08-14

A third-round audit reviewed the state after the redesign work above.
Full detail also in `app.py`'s own 5.3.0 header changelog entry.

**Findings that did NOT reproduce (checked directly, not assumed):**
H-1 ("lib/ directory entirely absent") — the delivered zip has 37 `lib/`
entries. H-3 ("Export/ has 8 files, missing feed.xml/atom.xml/
sitemap.xml") — confirmed present, 11 files. Half of H-4 ("no media
binaries shipped") — both real image files (PNG + WebP, non-zero,
`file`-verified) are in the delivered zip. This is the third audit round
in a row with this exact pattern (same dispute as L-11 in round 2) —
worth Elton checking what tool is producing these audit inputs, since it
appears to systematically drop `lib/`, binaries, and large files.

**Real findings, fixed:**
- **H-2** — `app.py`'s comment claimed Notes/Tasks/Links/Nav/Media come
  from a separate `lib/Management_Live/` directory that doesn't exist.
  Traced what actually happened: the by-name MFDB-call migration landed
  in place in `lib/Management/*.py`, confirmed via those files' own
  changelogs and by grepping for the by-name calls, which are present and
  execute. Corrected the comment; also resolved the audit's own open
  question (checked, not left open: `lib_bejson_Management_cli.py` only
  imports these files' public functions, so it inherits the fix
  automatically).
- **H-4** — absolute Termux device paths (`/data/data/com.termux/...`)
  in `data/taxonomytype.bejson` and both `media.bejson` files, confirmed
  genuinely consumed as real filesystem paths (traced into
  `lib_bejson_Management_scaffold.py`'s taxonomy-resync `isdir()` check
  and `app.py`'s delete-media route's `Path().unlink()`). Fixed at the
  write sites (`lib_bejson_Management_bootstrap.py`,
  `lib_bejson_Management_init.py` now store paths relative to project
  root), the read sites (`lib_bejson_Management_scaffold.py`,
  `lib_bejson_Management_cli.py`, `app.py`'s delete-media route all
  resolve relative-or-absolute correctly), and the current data itself.
- **H-5** — `selectUrl` in the media picker's `onclick` was the one value
  skipped by `esc()` while `title=`/`src=`/`alt=` right next to it were
  escaped. Fixed, with an honest comment about what `esc()` does and
  doesn't close here (blocks the more serious HTML-attribute-boundary
  breakout via a raw `"`; doesn't fully close the JS-string-context issue,
  which is the same already-documented, file-wide, deferred item as
  `docs/security-notes.md`'s `esc()` note).
- **M-2** — category-archive empty-state message was hardcoded to "No
  posts in this category yet." even for Page-type categories. Now reads
  "No pages..." vs "No posts..." based on `category_type`, which the
  function already had in scope. Verified live: a real rebuild of the
  (currently-empty) page category shows the corrected wording.
- **M-3** — post byline showed the category **slug**
  ("Developer-Post-Category") instead of its **title** ("Developer Post
  Category") — `_management_cms_build_post()`/`_build_page()` were wired
  to `management_cms_taxonomy_get_category_slug_map()`, a `{id: slug}`
  map, for what's purely a display token. Added
  `management_cms_taxonomy_get_category_title_map()` (kept the slug map
  function itself unchanged, in case anything else depends on its actual
  return shape) and switched the byline/meta code to it. Verified live: a
  real rebuild's byline now reads "Developer Post Category".
- **M-4** — `admin_token` cookie's `HttpOnly` was `False` with nothing in
  the codebase reading `document.cookie` (checked via grep, not assumed)
  — no reason to leave it script-readable. Now `True`. `Secure` is
  conditional on `request.is_secure` rather than hardcoded `True`, since
  this app's default bind is loopback-HTTP by design (the H-1 round-2
  fix) and a hardcoded `Secure` flag would make the cookie silently never
  get set on that default path.
- **M-6** — the download button only ever served `Export/index.html` —
  a real multi-page build (posts, category archives, feeds, sitemap,
  robots.txt, media) was silently truncated to just the homepage, with no
  error. Now zips the entire `Export/` tree in memory and serves that.
  Verified live against a running instance: a real download came back as
  a 692KB, 13-file zip (every page, both media binaries, all three feed
  formats), not a single HTML file.
- **LOW items** — removed a duplicated `_TOKEN_FILE` definition;
  corrected login-gate and code-comment text that said the token itself
  gets printed to the console (it's the *file path* that's printed, not
  the token value); fixed `openPreview()` conflating a 401 (needs
  re-auth) with a 404 (no build yet) into the same misleading "build the
  site first" message; fixed the `hb_style.css` filename mismatch across
  all 11 `Content/*_template.html`/`scaffold_template.html` copies.

  That last one turned out to have its actual root cause in **two**
  scaffold-generation functions in `lib_bejson_Management_scaffold.py`
  (`webframework_scaffold_deploy_taxonomy_mfdb()` — used when a NEW
  taxonomy is deployed — and `webframework_scaffold_resync_components()`
  — used to refresh EXISTING deployments), not just the 11 stale files
  themselves. The shared `app_shell` component's master HTML has
  `href="hb_style.css"` hardcoded, while both write paths always name the
  actual stylesheet file per-taxonomy (`f"{label}_style.css"`) — a
  guaranteed mismatch on every future taxonomy or resync, silently
  undoing a file-by-file fix. Fixed at both call sites with a
  post-fetch string substitution to the real per-deployment filename.
  Verified live, not just read: ran the actual resync function against
  this project and confirmed it regenerates all 11 template.html files
  with correct links and — critically — does NOT reintroduce the bug or
  clobber the earlier H-3 (`esc()` hardening) / L-6 (rebrand) fixes,
  which live in `SkeletonStore` and correctly survive a resync.

## Audit remediation, round 3 (continued) — M-1/M-5/M-7/M-8
### app.py 5.4.0 — 2026-08-14

Finished the round-3 audit's remaining findings. Full detail also in
`app.py`'s own 5.4.0 header changelog entry and `CHECKLIST.md` section 16.

- **M-1** — Post's `featured_image` field has been settable in the admin
  editor since it existed, but nothing on the export side ever read it —
  silently dead past the admin form. `management_cms_shared_render_feed_card()`
  gained an optional `thumbnail` param (empty-safe: no `<img>` at all
  when a caller doesn't pass one), wired through
  `management_cms_shared_render_feed()` into all 4 places that build feed
  items: category archive, tag archive, the homepage feed, and the
  Recent Posts sidebar widget. Individual post pages also gained a
  `featured_image_html` hero image above the post meta line. Verified
  live: the real WebP file serves correctly through `/media-files/`
  (200, exact byte match, correct content-type) and appears at both the
  feed-card and post-hero call sites in a fresh build.
- **M-5** — checked every config setting for actual consumers (grepped,
  not assumed) rather than trusting the audit's list. `debug` had zero
  references anywhere — removed from both the default schema
  (`lib_bejson_Management_config.py`) and the live `config/config.bejson`,
  logged in new `docs/dead_code.md` per the dead-code policy.
  `show_clock`/`show_greeting`/`accent_color`/`bg_color` are genuinely
  NOT dead — `lib_bejson_Management_build.py` reads all four, consumed by
  `lib_bejson_Management_cli.py`'s Termux export path — but they have
  zero effect on this web app's own "Build" button, which calls
  `lib_bejson_Management_static_builder.py` instead. Rather than wiring
  them into the (deliberately fixed, BEJSON-vanilla) web-build design
  system as a scope-creep feature change, added an inline warning next to
  those 4 settings in the admin Settings panel so this scope gap is
  visible instead of a silent trap.
- **M-7** — category drag-and-drop only blocked direct self-parenting
  (dropping a category onto itself), not indirect cycles (dropping a
  category onto one of its own descendants). Added real ancestor-chain
  walking both server-side (`update_category()` in `app.py` — the actual
  enforcement, reachable regardless of entry point) and client-side (a
  `_catWouldCycle()` pre-check in the drag handlers, for immediate visual
  feedback). Verified live against a running instance: created a real
  child category, attempted to make its parent a child of it (an actual
  cycle), got back a 400 with a clear error message, cleaned up after.
- **M-8** — the `scheduled_at` field's `<input type="datetime-local">`
  produces a bare local-time string with no timezone marker at all, which
  used to be sent straight to the server and string-compared against
  `management_cms_shared_now_iso()`'s UTC timestamps in
  `management_cms_content_list_due_for_publish()`. Verified the practical
  impact with Node (simulating a US-Eastern-timezone browser): a post
  scheduled for "2:00 PM local" would have auto-published ~2.5 hours
  early under the old code. Added `_localDatetimeInputToIso()` /
  `_isoToLocalDatetimeInput()` conversion helpers at the UI boundary
  (`templates/index.html`) so the stored value is always real UTC and the
  displayed value is always correctly converted back to local time for
  editing — verified the round-trip is exact. No server-side code needed
  to change; the fix is entirely at the boundary where local time enters
  and leaves the browser.

**Self-caught regression, fixed:** while live-testing the round-3
`hb_style.css` scaffold fix (M-7's neighbor, LOW #6/#7) earlier in this
session, actually running `webframework_scaffold_resync_components()`
against the live project to confirm it worked also silently reverted the
exported-site redesign in both ComponentsMFDB skeleton stores — those 5
rows were never flagged `user_customized`, so the resync's "pull
canonical defaults back in" step overwrote them. Caught while wiring in
M-1, not before anything shipped with it — the v5.3.0/PKG102 zip already
delivered predates this accident. Restored the redesign, re-applied
M-1's CSS/tokens on top of it, and — the actual fix, not just a
restoration — marked the 5 redesigned components `user_customized: true`
in the project's own store, so a future resync can never silently
clobber this again.

## CRITICAL HOTFIX — JS SyntaxError broke the entire admin dashboard
### app.py 5.4.1 — 2026-08-15

Elton reported "only header shows" and asked for Playwright tests to be
run. This is the real thing — full detail also in `app.py`'s own 5.4.1
header changelog entry.

**Root cause.** Playwright + a real Chromium browser (this session's
earlier verification used `wkhtmltoimage`, an old Qt-WebKit-based tool —
switched to Playwright here specifically because it's a real, current
browser engine) traced this to a genuine JavaScript `SyntaxError` in
`templates/index.html`. The LOW #3 fix from the round-3 audit pass
(correcting the login-gate's message about where the admin token is
actually printed) wrote an apostrophe escape as `\\'`
(backslash-backslash-quote) instead of `\'` (backslash-quote) inside a
single-quoted JS string literal. The double backslash renders as one
literal backslash character in the resulting string, leaving the
following `'` unescaped — which prematurely closes the string literal
mid-sentence. The parser then hits the bare word immediately after
(`s path at startup...`) and throws `Unexpected identifier 's'`,
aborting the parse of the **entire** inline `<script>` block.

With the whole script failing to parse, zero JavaScript on the page
executes — not just the login gate, everything: no panel loading, no
Build button, no Preview, nothing wired up at all. Only the static HTML
shell (the header/sidebar markup that doesn't depend on JS) renders,
which is exactly "only header shows."

**Scope of impact.** This landed before either of the last two
deliveries were packaged — **both v5.3.0/PKG102 and v5.4.0/PKG103 shipped
with a completely non-functional admin dashboard.** The exported public
site itself (`Export/`) was unaffected — that's a separate, independent
HTML/CSS/JS pipeline built by `lib_bejson_Management_static_builder.py`,
not touched by this bug.

**Fix and verification.**
1. Extracted the actual `<script>` block from the shipped file and ran
   `node --check` against it — reproduced the exact `SyntaxError` cold,
   confirming the diagnosis before touching anything.
2. Fixed the one character (`\\'` → `\'`).
3. `node --check` again — clean.
4. Grepped the entire file for the same `\\'` pattern elsewhere — none
   found, so this was the only instance.
5. Syntax-checked every `<script>` block in the file individually (one
   block total, clean).
6. Full real-browser Playwright pass against a running instance of the
   actual app, not a static analysis: loaded `/`, confirmed the login
   gate is now visible and accepts the real token, clicked through to
   the Build panel, clicked the real Preview button, confirmed the
   modal opens and the iframe's `content_frame()` shows real rendered
   content (sidebar nav present, feed card present, footer present) —
   checked via `inner_text()` and DOM element queries, not a screenshot
   that could hide a blank-but-visually-similar page.
7. Along the way, also caught and cleaned up a leftover "Cycle Test
   Child" category from earlier M-7 cycle-protection testing that a
   stale `Export/` build was still displaying — deleted the test data
   properly and rebuilt `Export/` fresh.

**Not a bug, for the record:** two `403` console errors remain in every
Playwright run — both are `fonts.googleapis.com` requests blocked by
this development sandbox's network egress allowlist, not something that
will occur for Elton on a normal internet connection. Confirmed by URL,
not assumed.

## Audit remediation, round 4
### app.py 5.5.0 — 2026-08-15

Fourth external audit pass, run against v5.4.1/PKG104. Full detail also
in `app.py`'s own 5.5.0 header changelog entry.

**N-1 (HIGH, claimed) did NOT reproduce.** The audit reported the live
admin bearer token shipped inside the package
(`config/admin_token.txt`, plaintext, visible in the chunk). Checked
directly: `unzip -l | grep -i token` against every zip actually
delivered this project so far — zero hits in every one, including
PKG104 itself. No stray copy exists anywhere in the working directory or
the original upload either. This is the fourth finding across four audit
rounds that doesn't reproduce against the real files (after H-1, H-3,
and half of H-4 in round 3) — flagged plainly rather than silently
"fixed" a finding that isn't actually present.

Closed the underlying hygiene gap anyway, since it costs nothing and the
audit's point about the *convention* being undocumented was fair: added
a `.gitignore` (never existed before, despite `app.py`'s own
`ADMIN_TOKEN` comment claiming "gitignored-by-convention" since the H-1
round-2 fix) with `config/admin_token.txt` as its first entry, and a
packaging-exclusion note in `docs/security-notes.md`.

**Real findings, fixed:**
- **N-2** — a loopback `site_url` passed the existing M-6 empty-string
  check completely silently. Verified live that this is the *normal*
  case, not an edge case: triggering a real build through the actual
  running app (`POST /api/build`, the button anyone clicks) captures
  `request.host_url` verbatim, and with the default loopback bind that
  produced `canonical="http://127.0.0.1:5030/"` in the real exported
  HTML with zero warning. Added a second warning specifically for
  `127.0.0.1`/`localhost`/`::1`, verified live that it now fires
  correctly on a real triggered build.
- **N-3** — `Persist/factory_reset_backups/`/`Persist/_migrated_archive/`
  snapshots accumulate indefinitely by design (backup-never-delete is
  deliberate policy, not a bug) with no operator-visible signal of how
  much space they're using. Added a soft, startup-time size advisory
  (500 MB threshold, log line only, never auto-deletes) — verified the
  size-calculation logic against the real `Persist/` directory (found
  both actual snapshot dirs, computed size correctly).
- **N-5** — `config/config.bejson`'s `accent_color`
  (`#ff0000`)/`bg_color` (`#ffffff`) had drifted from the design
  system's actual palette (`#DE2626`/`#0a0a0a`). Aligned both — cosmetic
  (M-5 already established these settings don't affect the web build),
  but confusing for the next person who assumes they do.

**N-4 (hash-pinned requirements.txt) — considered, deliberately not
done.** Attempted it (downloaded the three pinned packages to compute
hashes), then caught a real problem before shipping it: Pillow ships
platform-specific wheels, and the wheel resolved in this x86_64 dev
sandbox is not the wheel this project needs on its actual deployment
target (Android/Termux, normally aarch64). Shipping those hashes would
make `pip install --require-hashes` fail on-device — strictly worse than
the current unhashed-but-working state. Documented the reasoning and the
correct on-device generation command in `requirements.txt` instead.

**N-6/N-7** — N-6 (old `esc()` persisting in backup snapshots) correctly
left untouched; backups are immutable by design and these files never
execute. N-7 (maintainability observations — large single-file frontend,
skeleton blobs as strings, device-specific `Drive_Path`) is informational
only, no action taken.

**Phase 2/3 (structural XSS migration, deferred-by-design items)** —
both explicitly gated on Elton's scope approval per the audit's own
pacing rule. Not started; not appropriate to start without that
confirmation.

## Sidebar bug fixes — broken images/links + nav-group styling
### app.py 5.6.0 — 2026-08-17

Elton reported: "broken images and links on the sidebar and the
categories font look the same exact as the titles... should be like
some font separation for the categories or like expanding collapse
feature or something." All three are real, verified bugs. Full detail
also in `app.py`'s own 5.6.0 header changelog entry.

**1) Broken images.** `featured_image` stores an admin-app-only
`/media-files/<name>` path — that route only exists on the running Flask
app and only serves `Content/media/uploads/`, never the exported
`Export/media/` copy. The M-1 feature (5.4.0) embedded that raw path
directly into exported HTML. It happened to *look* like it worked
through this app's own preview (since `/media-files/` coincidentally is
a real top-level route here, serving byte-identical content), which is
almost certainly why this wasn't caught earlier — but it 404s on any
genuine static hosting the export gets deployed to, which is the entire
point of a static export.

Added `management_cms_shared_export_media_url()` to
`lib_bejson_Management_shared.py`: rewrites `/media-files/<name>` to
`/media/<name>` (what `Export/media/` actually contains), applied at all
4 places that read `featured_image` (post hero, category archive, tag
archive, homepage feed, Recent Posts widget). Verified live via
Playwright: the thumbnail's `naturalWidth`/`naturalHeight` went from
`0x0` (failed to load) to the real image's actual `1376x768`.

**2) Broken links — pre-existing, reproduced independently, not
introduced by fix #1.** `serve_preview()`'s `<base href="/preview/">`
only rewrites *relative* URLs per the HTML spec — every link this app's
static builder generates (post/page/category/tag/media, all of it) is
*absolute* by deliberate, consistent design (the site is meant to be
deployed at a real domain's root), which a `<base>` tag can't touch at
all. Clicking a real sidebar nav link inside the preview iframe
navigated to `http://host:port/post/...` — a genuine top-level route
that doesn't exist. Reproduced with Playwright before fixing (clicked a
real link, landed on Flask's actual 404 page) rather than assumed.

Fixed generally, not just for the one media path that also happened to
break: `serve_preview()` now runs a regex rewrite over every previewed
HTML page, prefixing any `href="/…"`/`src="/…"` that isn't already under
`/preview/` and isn't protocol-relative (`//other-host/...`) with
`/preview/`. Unit-tested the regex against 6 cases (absolute path,
protocol-relative, external `https://`, already-prefixed, relative,
plus the `<base>` tag itself) before wiring it in — all handled
correctly. Verified live: the same nav-link click now lands on the real
post page with real rendered content, still inside the `/preview/`
sandbox.

**3) Nav-group section labels indistinguishable from links, no
collapse.** `.becss-c-nav-group__label` (the "Categories"/"Pages"/
"Recent Posts" headers) has carried that class since the redesign was
first built, but the class was never actually given CSS — it fell back
to identical styling as the `.becss-c-nav__link` items underneath it,
exactly matching "the categories font look the same exact as the
titles." Added real visual differentiation (uppercase, monospace,
smaller size, muted color — standard sidebar section-heading treatment)
plus genuine collapse/expand behavior: a chevron indicator, a new
`_navGroupToggle()` function wired to each label's click, and a CSS
`max-height` transition on the group's `<ul>`. Verified live: computed
styles differ from nav-link styles on every checked property
(font-size, font-family, text-transform, color), and clicking a label
correctly toggles the collapsed state back and forth (confirmed both
directions, not just collapse).

**Process note.** While reapplying these fixes, caught a *second*
instance of the "canonical ComponentsMFDB copy silently reverted"
problem from earlier this session — this time to a genuinely hybrid,
worse state (old pre-redesign HTML shell with the newest CSS patch
bolted onto it, because an incremental patch script trusted its own
idempotency guard without re-checking the file's actual current state
first). Did a full clean re-restoration of both skeleton stores in the
correct dependency order this time (base redesign, then M-1, then
nav-group), and explicitly re-verified every expected marker string is
present in both files before moving on, rather than trusting a patch
script's guard blindly again.

## Root cause of the recurring skeleton-store reversion
### app.py 5.6.1 — 2026-08-17

The "canonical ComponentsMFDB copy silently reverts" problem noted in
both the 5.4.0 and 5.6.0 changelog entries as a self-caught regression
had recurred a THIRD time while verifying the sidebar fixes above.
Rather than re-patch it a third time and move on, actually root-caused
it this time.

**Root cause.** `_ensure_cms_components_registered()` (`app.py`) has a
docstring that opens with "One-time seed," but its loop called
`webframework_components_register()` unconditionally for all 5
`management_cms_*` components on every single invocation — and this
function runs on **every app startup**, via `ensure_scaffold_deployed()`,
which has no guard around calling it (the comment right above the call
even says it's "safe to call on every startup"). `webframework_components_register()`
itself unconditionally overwrites an existing skeleton's `skeleton_content`
(see `_upsert_skeleton()` in `lib_bejson_Management_components.py` —
no diff-check, just an unconditional update). The net effect: every
single app restart silently clobbered the canonical `SkeletonStore` back
to the hardcoded factory-default HTML — including the exported-site
redesign, the M-1 feature, and the nav-group work — because none of
that customization was protected by a `user_customized` flag on the
*canonical* copy (only this app's own root-manifest copy has that
protection, added as part of the first self-caught regression back in
5.4.0).

This explains all three prior "regression" incidents this session as
the same underlying bug recurring, not three unrelated flukes.

**Fix.** Added the one-line existence guard the docstring already
implied should be there: skip `webframework_components_register()` for
a component if `webframework_components_get_record(component_id)`
already returns a record. Restores genuine one-time-seed behavior.

**Verification, not assertion.** Restarted the live app three separate
times (not once) and confirmed after each restart — reading the actual
file, not trusting the fix — that the canonical store's sidebar
redesign, M-1 CSS, and nav-group CSS were all still intact. Only after
three clean restarts in a row was this considered actually fixed.

## Feature: YouTube link embedding for featured_image
### app.py 5.7.0 — 2026-08-17

Elton asked for a YouTube link category in the media picker that "work[s]
the same way as images but embed[s] differently." Full detail also in
`app.py`'s own 5.7.0 header changelog entry.

**What already existed.** The media picker already has a dedicated
YouTube tab, and `management_media_add_external()` already normalizes a
pasted YouTube link to a canonical `youtube.com/watch?v=<id>` URL and
stores it in the exact same `featured_image` field that image uploads
use. So "the same way as images" was already true on the data-model
side — same field, same picker, one workflow.

**The actual gap.** The render side only ever knew how to do
`<img src="...">`. A YouTube watch-page URL isn't an image — using it as
an `<img src>` is simply broken (shows nothing). This was the missing
half of "embed differently."

**Fix.** Added to `lib_bejson_Management_shared.py`:
- `management_cms_shared_youtube_id()` — detects a YouTube URL and
  extracts its video ID. Deliberately kept in exact parity with
  `lib_bejson_Management_media.py`'s own `_extract_youtube_id()` rather
  than importing that module (static_builder.py/feed.py are export-time
  readers and shouldn't need the admin write-side media library's
  uuid/datetime/upload surface just to recognize a URL shape). Unit-
  tested both functions against the same 7 inputs (all 4 accepted
  YouTube URL formats, a non-YouTube URL, a plain media path, an empty
  string) before wiring in — every result matched exactly.
- `management_cms_shared_youtube_embed_html()` — a responsive 16:9
  `<iframe>` player, used for the post page hero (a real embed makes
  sense in that full-width context).
- `management_cms_shared_export_thumbnail()` — resolves a YouTube URL to
  its real static thumbnail JPG (`img.youtube.com/vi/<id>/hqdefault.jpg`)
  for feed-card listings instead — an iframe doesn't belong in a small
  card (autoplay/sizing problems), so listings get an image with a new
  play-icon badge overlay (`is_video` flag threaded through
  `management_cms_shared_render_feed_card()`) so a video is visually
  distinguishable from a plain image at a glance, addressing the
  "categorize" half of the request without needing a schema change or a
  brand-new admin panel.

Wired into all 4 existing feed-thumbnail call sites (home, category
archive, tag archive, Recent Posts widget) plus the post hero (the one
call site that was image-only before). Added CSS for the video container
and play badge to both ComponentsMFDB skeleton stores. Updated the
Featured Image field's label in the admin editor
("image or YouTube link — embeds automatically") so this capability
isn't undiscoverable.

**Verified live end-to-end**, not just unit-tested in isolation: set a
real YouTube URL on the actual test post, ran a genuine
`management_cms_static_build()`, confirmed the post page's real exported
HTML contains a correct `<iframe src="https://www.youtube.com/embed/...">`
and every feed card shows the real `img.youtube.com` thumbnail plus the
play badge — then loaded it in a real Playwright/Chromium browser and
confirmed the iframe element and its 16:9 container render at the
correct size and position (the video itself doesn't play inside this
sandbox, since `youtube.com` isn't in its network egress allowlist —
same category of environment limitation as the earlier Google Fonts
block, not a defect in the implementation). Restored the test post's
original image and rebuilt clean before packaging.

## Features: global footer, related posts, auto-TOC, custom 404 + critical content-desync fix
### app.py 5.8.0 — 2026-08-19

Four feature requests, plus a serious data-integrity bug found and fixed
while testing them. Full detail also in `app.py`'s own 5.8.0 header
changelog entry and `docs/data-integrity-notes.md`.

**Critical fix found during this work, not part of the original ask:**
`management_cms_content_update_post()`/`update_page()` wrote edited
`content_html` only to the separate content file, never back to the
entity record itself — and `management_cms_static_build()` reads
content exclusively from the entity (via `list_posts()`/`list_pages()`),
never the file. Net effect: **every edit to an existing post or page's
content silently never appeared on the published site**, from the
moment it was first edited onward, no matter how many times it was
rebuilt. The admin editor's own display never revealed this (it reads
the content file correctly), so an edit always looked successful when
checked the obvious way. Found by testing the TOC feature — a real edit
didn't show up in a real build — not assumed. Grepped every `update_*`
function in `lib/Management/*.py` for the same pop-then-file-only
pattern (only these two matched). Fixed by leaving `content_html` in the
`updates` dict so the bulk entity write covers it too, matching what
`create_post()`/`create_page()` already did correctly. Verified live
against the actual function the builder calls. Checked every real
post/page in the project for existing desync before and after — none
found, nothing needed repair.

**Global footer.** New `footer_text` config setting (freeform — a
tagline, "All rights reserved.", whatever). `management_cms_shared_build_footer_html()`
computes "© \<year\> \<site_title\>[ · footer_text]" once per build,
threaded through all 5 page-type builders (home/page/post/category/tag)
via a `{{footer_html}}` token, replacing the old hardcoded
`{{site_title}}`-only footer.

**Related posts.** 2-3 posts sharing the current post's category,
newest first, rendered at the bottom of the post page using the exact
same feed-card component every other listing on the site already uses
— no new visual language. Empty-safe: confirmed via a real build that
the section is completely absent when there's nothing to relate to,
not just hidden by CSS.

**Auto-generated table of contents.** `management_cms_shared_inject_toc()`
finds every `h2`/`h3` in `content_html`, injects a stable slug `id=` on
each (skipping ones that already have one, so hand-authored anchors
aren't touched), and builds a linked contents box shown above the
article — only when there are at least 2 headings, so a short post
doesn't get a pointless one-item list. Regex-based rather than a full
HTML parser deliberately: `content_html` is already balanced-tag-checked
at save time (the L-4/round-3 `_lint_content_html()` fix), so this only
needs to find heading open/close pairs, not handle arbitrary malformed
nesting. Unit-tested against 6 cases (too few headings, normal case,
duplicate heading text needing unique ids, a heading with a
hand-authored `id=` already present, no headings at all, nested inline
tags inside a heading) before wiring in — all correct.

**Custom 404 page.** `Export/404.html` — the filename every major static
host (GitHub Pages, Cloudflare Pages, Netlify) auto-detects by
convention, so no hosting configuration is needed for it to take effect
on deployment. Derived from the live, currently-shipping "page" skeleton
rather than built from scratch, so it automatically inherits every
sidebar/nav/CSS fix already tested this session instead of risking a
stale copy. Registered as a proper 6th component (both a `ComponentMap`
row and a `SkeletonStore` row, in both the project's own manifest and
the canonical library copy) through the same data structures the
existing 5 components use, rather than hacking around them — deliberate,
given this session's earlier skeleton-reversion incidents were caused by
exactly that kind of raw-JSON shortcut. Verified live through the real
`management_cms_render_layout()` lookup path before wiring into the
build, not just checked that the file parses.

Also wired into `serve_preview()`: a broken link inside the in-app
preview now shows the real 404 page instead of a generic JSON error.
While doing this, caught that a copy-paste would have applied the
`<base href>`/absolute-path rewrite (the 5.6.0 fix for "broken links")
to real pages but not to the 404 fallback — factored the rewrite into a
shared `_rewrite_preview_html()` helper instead so both paths can't
drift apart.

**Bug caught before shipping, not after:** the 404 page's "Back to Home"
button was styled white-text-on-red by design, but a more specific
pre-existing rule (`.becss-c-main a`) was silently overriding it to
red-on-red — invisible. Caught via a Playwright screenshot that showed
an empty-looking button (the markup and CSS both read correctly in
isolation; only an actual rendered check surfaced the specificity
conflict), fixed by scoping the button's selector more specifically,
verified via computed styles that the text is now genuinely white
against the red background.

## Audit remediation pass — PKG111/PKG112/PKG113
### bejson_project.json change_log — 2026-09-09

(Appended PKG117: these three package entries existed only in the
bejson_project.json `change_log` field and were not yet mirrored here.
Moved into structured form as part of the PKG116 change_log trim/rolling-window
cleanup, per audit instruction §4, before truncating the field to its
last-3-entries window.)

**PKG111** — Audit remediation pass (Full Sweep Audit v5.9.0/PKG110): C-1 fixed leaked {{meta_description}} token in 404 builder token_map (also patched already-exported Export/404.html); H-1 corrected stale ComponentMap record_count (6->7) in root 104a.mfdb.bejson; H-2 deduped tripled Google Fonts <link> blocks in both skeleton_store.bejson files and all 7 already-exported HTML pages; H-3 normalized empty-string parent_id to null in category.bejson; M-1 fixed File: header/filename mismatches in scaffold_style.css and scaffold_template.html (root + assets/ copies); M-2 moved the unlocked _BUILD_STATE._site_url read in _run_build_in_background() under _BUILD_LOCK; M-3 fixed handleSave() cross-panel modal dispatch bug by calling closeModal() inside go(); M-6 404 builder canonical_url now degrades to site root ("/") instead of a hardcoded blank, matching other page builders, and patched the already-exported Export/404.html og:url/canonical to match; M-5 verified no CRLF present in Post content (already clean); cleared stale Persist/factory_reset_backups/2026-07-31T11-17-43Z per explicit user instruction (not a factory reset).

**PKG112** — Added docs/variable_naming_issues.md per policy S1.2: flagged global P (templates/index.html, current-panel state) as confusing-but-valid — no rename applied, flagged as the underlying naming ambiguity behind the M-3 modal-dispatch bug fixed in PKG111. Noted (not flagged) the file's pervasive local single-letter scratch vars (d/n/t/l/el/r/m) as ordinary JS convention, not genuine confusion.

**PKG113** — Added Reports/2026-09-09_Management_CMS_Audit_Remediation_Report.md (technical-drafter format): detailed writeup of the PKG111/PKG112 audit remediation pass — Executive Summary, per-finding Deep Analysis with root-cause tracing for C-1/H-1/H-2/H-3/M-1/M-2/M-3/M-5/M-6, MFDB integrity table, a token-substitution architecture note explaining the shared root-cause shape behind C-1 and M-6, 8 Actionable Suggestions, and a 5-phase Implementation Roadmap. No source files changed in this delivery.

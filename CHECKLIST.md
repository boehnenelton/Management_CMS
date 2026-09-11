# Management_CMS v4.5.0 Audit — Fix Checklist

Goal: address the 5 liabilities from the v4.5.0 audit. Order was left to
Claude's discretion per instruction. Checked items were implemented AND
smoke-tested this pass; unchecked items are analyzed but not yet built,
each with the specific reason it was held back.

## 1. XSS — weak `esc()` sanitizer
- [x] Hardened `esc()` in `templates/index.html` and `scaffold_template.html`
      to also encode `'` and `` ` ``, not just `& < > "`. Closes the
      breakout vector where user data containing a single quote or backtick
      escapes an `onclick="fn('...')"` single-quoted JS-string argument.
      Verified in Node against a string containing all six characters.
- [ ] **1b — not done.** This is still character-substitution, not a
      context-aware DOM sanitizer. The durable fix is migrating
      `onclick="fn('"+esc(x)+"')"` call sites to `addEventListener` +
      `dataset` attributes so untrusted data never enters a JS-string
      context at all. That's a structural rewrite touching most of
      `templates/index.html`'s render functions — held back pending
      confirmation, per the pacing rule against large unconfirmed leaps.
- [x] The identical starter-template `esc()` embedded as a data blob inside
      `data/skeleton_store.bejson` and
      `lib/Management/ComponentsMFDB/data/skeleton_store.bejson` (this
      project's actual skeleton-blob locations — the path above was from
      an earlier `Web_Framework`-era layout) **was patched, 2026-08-13**,
      as part of the external-audit remediation pass (H-3) — see section
      15 below. Same fix, applied to both JSON-embedded copies plus all
      12 live scaffold HTML copies that had drifted out of sync with
      `templates/index.html`'s hardened version.

## 2. Hardcoded field indices (`LEGACY_RUNTIME_FIELD_ORDER`)
- [x] **Investigated, not a live bug (as originally framed).** The current
      MFDB read/write path (`bejson_core_get_field_index`,
      `bejson_core_update_field`, `bejson_core_filter_rows`,
      `bejson_core_sort_by_field` in `lib_bejson_Core_bejson_core.py`)
      already does real Field Map Indexing off the on-disk `Fields` array —
      it is NOT positionally hardcoded. `LEGACY_RUNTIME_FIELD_ORDER` only
      exists inside `_migrate_legacy_data()` in `app.py`, a one-time
      importer for the old pre-MFDB `Persist/homepage_data.bejson` format,
      which never had trustworthy `Fields` metadata to begin with — that's
      a deliberate, documented exception, not an ongoing schema-evolution
      risk.
- [x] **The real residual risk — fixed at the Core level, and tested.**
      Every `*_add_*()` function across `lib/Management/*` and
      `lib/Management_CMS/*` (~20 call sites) still builds its `values`
      list as a raw positional literal (`[cat_id, name, created_at]` etc.)
      matching the *current* `Fields` order by convention, not by lookup.
      Added `mfdb_core_add_entity_record_by_name()` to
      `lib_bejson_Core_mfdb_core.py` — additive only, no existing function
      touched — which resolves each value's position from
      `bejson_core_get_field_map()` instead. Smoke-tested including a
      simulated mid-`Fields`-insertion (the new function lands the value
      correctly; a positional literal would have silently misaligned) and
      unknown-field-name rejection (raises instead of silently misplacing).
- [x] **2b — done for `lib/Management_CMS/*` (2026-07-25).** Migrated all 7
      positional call sites in that family:
      `management_cms_content_create_page()`, `create_post()`, `seo_set()`
      (`content.py`); `management_cms_media_add()` (`media.py`);
      `management_cms_nav_create_menu()` (`nav.py`);
      `management_cms_taxonomy_add_category()`, `add_tag()` (`taxonomy.py`).
      Each retested with a real create-then-read-back after migration, and
      a full `management_cms_static_build()` run confirmed nothing broke
      end-to-end.
- [x] **2b — done for the entities the live app actually touches from
      `lib/Management/*`, via a copy strategy (2026-07-25).** Rather than
      editing `lib/Management/*.py` in place — still directly depended on
      by `lib_bejson_Management_cli.py`, so protected under Library
      Immutability — created a new `lib/Management_Live/` family:
      byte-for-byte copies of `notes.py`, `tasks.py`, `links.py`, `nav.py`,
      `media.py` with only the `mfdb_core_add_entity_record()` calls
      migrated to `mfdb_core_add_entity_record_by_name()` (9 call sites:
      Note, NoteCategory, TodoItem, TaskCategory, Link, LinkCategory,
      NavLink, Media upload path, Media external/YouTube path). `app.py`'s
      imports repointed to the new copies; the originals are untouched —
      verified by confirming the positional-call count in each original is
      unchanged. Verified `app.py` actually loads the new copies at
      runtime (checked `NotesLib.__file__`), then functionally exercised
      all 9 migrated call sites through the real app-created manifests.
- [ ] **2b — still genuinely out of scope: `landing.py` and `pages.py`.**
      `app.py` never imports either — they're CLI/bootstrap-only. Not
      copied, not touched.
- [x] **Real bug found and actually fixed while doing this pass** (not
      part of the original audit, but caught along the way): both
      `management_cms_content_list_pages()` and
      `management_cms_nav_get_tree()` sorted by
      `.get("sort_order", 0)` — which only applies that default when the
      key is *absent*, not when it's present with value `null` (the
      correct representation for "no value set"). Any Page or NavLink with
      a null `sort_order` crashed the entire static build site-wide via
      `sorted()` comparing `None < int`. Fixed both with `or 0`. Reproduced
      the exact crash, confirmed the fix stops it, and reran a full build
      with that data present.

## 3. Naming drift + Layer 2 formalization
- [ ] **Blocked, not guessed.** `big picture.txt` in the uploaded zip poses
      an open fork: "Direction 1" wants `Management` libs renamed to
      `Management_CMS_Frontend` and `Web_Framework` renamed to
      `Management_CMS_Framework`, tied to merging in the `Other_Half/`
      folder from the same zip. Whether that rename/merge is still wanted
      directly determines what "fix the naming drift" even means, so this
      was left for Elton to confirm rather than assumed either way.
- [ ] Layer 2 formalization (moving the Action Toolbar / Tabular Grid /
      Form Schema Injector out of the `app_shell` script payload into a
      real `skeleton_store.bejson` component entry) is a separate large
      restructure — not started, same reasoning.

## 4. Scaffold overwrite loop + obsolete migration artifacts
- [x] **4a — scaffold overwrite loop, fixed and tested.** Added a
      `user_customized` boolean field to `SkeletonStore`
      (`lib_bejson_WebFramework_components.py`) plus
      `webframework_skeletons_set_customized()`.
      `webframework_scaffold_resync_components()`
      (`lib_bejson_WebFramework_scaffold.py`) now skips overwriting a
      skeleton's `skeleton_content` on an app's own manifest when that
      row is flagged customized. Smoke-tested: a customized row survives
      resync unchanged; non-customized rows still process without error.
      The loose `scaffold_template.html`/`scaffold_style.css` file rewrite
      needed no separate fix — it reads back from this same (now
      protected) entity, not from canonical, so it stays consistent.
- [ ] **4b — no UI wires the flag yet.** `webframework_skeletons_set_customized()`
      is callable but there's no dashboard toggle for Elton (or an end
      user) to actually flag "this is customized, don't touch it" from
      the app itself. Building that toggle is a distinct, if small,
      feature addition — held back for confirmation since it wasn't part
      of the original 5-item audit list itself, it's a consequence of
      fixing item 4a properly.
- [x] **4c — obsolete `Persist/homepage_data.bejson` and
      `Persist/config.bejson`, fixed and applied.** Added
      `_archive_legacy_file()` to `app.py` —
      `_migrate_legacy_config()`/`_migrate_legacy_data()` now move (never
      delete) their source file into
      `Persist/_migrated_archive/<UTC timestamp>/` once migration
      succeeds, instead of leaving it in the root forever. Confirmed
      (didn't assume) both legacy files in *this* project snapshot were
      already consumed — the current-format manifests
      (`Content/Notes/MFDB/104a.mfdb.bejson` etc.) and the migrated
      `config/config.bejson` already existed — then archived them as part
      of this delivery. Nothing was deleted; both files are still on disk
      under `Persist/_migrated_archive/`.

## 5. Tags add-only / no DELETE route
- [x] Added `DELETE /api/tags/<tag_id>` route in `app.py`.
- [x] Fixed `management_cms_taxonomy_delete_tag()`
      (`lib_bejson_management_cms_taxonomy.py`) to strip the deleted
      `tag_id` out of every Post's `tag_ids` array first — mirrors the
      existing category re-parenting orphan-prevention pattern. Previously
      it would have left dangling references the moment a route called it.
      Smoke-tested: orphan cleanup confirmed, unrelated tags untouched,
      unknown tag_id returns `False` cleanly instead of raising.
- [x] Wired a delete ("✕") button into each tag chip in the Post editor
      (`templates/index.html`) so the new route is actually reachable.
- [ ] Template-customization dashboard (letting a non-technical user
      customize public site skeletons from inside the app) — separate,
      large, net-new UI feature. Not started; needs its own scope
      discussion, not assumed as part of an "audit fix" pass.

## 6. Self-discovery / naming clarity / professionalism (this request)
- [x] **Nav auto-population fix.** `management_cms_static_build()`
      (`lib_bejson_management_cms_static_builder.py`) previously treated
      manual Site Nav and auto-generated navigation as either/or — the
      moment an admin added even one manual link, the auto-generated
      category (and now posts) navigation was silenced completely, even
      though categories/posts still existed and were still being built.
      Changed to always merge: manual links, then an always-on
      "Categories" block, then an always-on new "Recent Posts" block.
      Smoke-tested the new posts block: published-only, newest-first,
      empty-safe.
- [x] **Posts previously had no direct nav path at all.** They only
      surfaced indirectly via a category archive page link. Added
      `_management_cms_build_recent_posts_html()` — a "Recent Posts" nav
      block, same rendering pattern as the category sidebar.
- [x] **Category vs. Post naming review.** Field-level naming is already
      clear — `PAGE_FIELDS`/`POST_FIELDS` are separate constants, every
      function name says `_pages`/`_posts`/`_categories` explicitly, and
      category type (`post` vs `page`) already routes to distinct URL
      prefixes (`/category/` vs `/page-category/`) specifically to avoid
      slug collision between the two category types. Nothing changed here
      — it checked out.
- [x] **Found the real distinction problem instead, and fixed it.** Pages
      and Posts are BOTH written flatly as `/{slug}.html` with no
      distinguishing prefix at all — unlike Category. If a Page and a Post
      ever share a slug, one silently overwrites the other's output file.
      Added a pre-build collision guard comparing all published Page slugs
      against all published Post slugs; a collision is now reported as a
      build warning before any file is written, instead of silently
      clobbering later.
- [ ] **Not fixed: the URL scheme itself.** Giving Posts their own prefix
      (e.g. `/post/{slug}.html`, matching how Category already works)
      would eliminate the collision risk structurally instead of just
      warning about it — but that changes every post-referencing URL
      across the site (sitemap, feeds, category/tag archive listings, nav,
      in-post links), a genuinely large, breaking restructure. Held back
      per the pacing rule; flagging for a confirmed follow-up rather than
      guessing Elton wants URLs changing under him.
- [x] **Dead code sweep.** Ran `vulture` at 90%+ confidence across
      `app.py` and `lib/`. Removed `app.py`'s unused
      `import lib_bejson_Management_build as Build` and corrected a stale
      comment that incorrectly implied the whole build library was
      orphaned — it's still actively used by
      `lib_bejson_Management_cli.py` (the Termux CLI menu), so the library
      file itself was left untouched.
- [ ] **Found but not touched:** `check_bidirectional` — an unused
      parameter on `validate_mfdb_entity_file()` in
      `lib_bejson_Core_mfdb_validator.py` (100% vulture confidence). This
      is a Core library; altering a public function's signature needs a
      verified-bug justification, not just an unused-parameter
      observation, per Library Immutability. Flagged for Elton's own call.
      A handful of `E_MFDB_*`/`E_...` error-constant imports also flagged
      by vulture as "unused" across Core files were left alone — these
      look like intentional re-exports for callers, not dead code, and
      touching them risks breaking an external import contract for a
      cosmetic gain.
- [ ] **"Professional" exported output — partially verified, not fully.**
      The default `app_shell` skeleton's embedded CSS is a substantial
      (~8KB) BECSS-styled theme already following the white/black/red
      design system. A real browser render/visual check was NOT performed
      — there's no browser available in this build environment — so this
      is a code-level check, not a "does it actually look good rendered"
      check. If you want that verified, the honest path is you (or a
      future session with browser access) opening a built site's actual
      output HTML.

## 7. Category URL symmetry + follow-up polish (2026-07-22)
Elton correctly flagged: post categories output at `/category/` while page
categories output at `/page-category/` — asymmetric, with the "post-"
qualifier on the more common one silently dropped, easy to mistake for the
only category concept that exists.
- [x] **Renamed post categories to `/post-category/`**, exactly symmetric
      with `/page-category/`. Updated all 3 places that hardcoded the old
      path: the static-build output directory + sidebar nav
      (`lib_bejson_management_cms_static_builder.py`), the unused-but-still-
      present `management_cms_nav_auto_generate_from_categories()`
      (`lib_bejson_management_cms_nav.py`), and the Recent-Categories widget
      (`lib_bejson_management_cms_feed.py`). **BREAKING for any
      already-published site** — old `/category/{slug}.html` links will
      404 after a rebuild. No way to avoid that with a rename; flagging
      loudly rather than burying it.
- [x] **Found and fixed a latent bug while touching those two files:**
      both `nav.py`'s and `feed.py`'s category-URL builders hardcoded the
      post-style prefix regardless of the `category_type` argument they
      were given — so calling either with `category_type="page"` would
      have silently generated links to a path that was never actually
      built. Now both pick the correct prefix based on the type.
- [x] **Re-applied the export-polish fixes** (found reviewing the *other*,
      wrong-lineage upload last turn, now correctly applied here): added
      `lang="en"` and a viewport meta tag to `page_shell()` (both were
      missing entirely), turned the nav into a real collapsible hamburger
      menu below 640px (previously a plain inline list with nowhere to go
      on a phone), and fixed the post byline/tags line's dangling-`"· "`/
      orphaned-`"Tags:"` bug — this time reusing the project's existing
      `management_cms_shared_fmt_date()` helper instead of writing a
      duplicate date formatter.
- [x] **Verified with a real end-to-end build**, not just isolated unit
      tests: ran `management_cms_static_build()` against this project's
      actual data in a throwaway copy and confirmed the generated
      `Export/index.html` and `Export/post-category/*.html` actually
      contain the new `/post-category/` links, `lang="en"`, the viewport
      tag, and the hamburger CSS — not just that the token-substitution
      logic looked right in isolation.

## 8. Shared feed component, from Elton's reference skeletons (2026-07-25)
Elton provided two full BECSS reference HTML/CSS documents (a card-based
feed with pagination, and a dashboard-style homepage with widgets) and
asked for a homepage skeleton, a general feed skeleton shared across
pages/posts/categories/tags, and page/post skeletons — all built off each
other.
- [x] **Built one shared feed-card component**, not three separate ones:
      `management_cms_shared_excerpt()` / `_render_feed_card()` /
      `_render_feed()` in `lib_bejson_management_cms_shared.py`. Used by:
      the homepage recent-posts feed (`lib_bejson_management_cms_feed.py`),
      category archives, and tag archives (both in
      `lib_bejson_management_cms_static_builder.py`). Each card shows
      title, date (author too, elsewhere), and a real excerpt derived by
      stripping tags from `content_html` and truncating at a word
      boundary — there's no dedicated excerpt field on Post/Page.
- [x] **Fixed a real bug this surfaced:** the category/tag archive default
      templates wrapped `{{post_list_html}}` in `<ul>...</ul>` — valid
      when it was a list of `<li>`, invalid now that it's a self-contained
      `<div class="becss-c-feed">`. Removed the wrapper.
- [x] **Deliberately did NOT copy the reference docs verbatim**, two
      specific choices:
      - Kept the existing black/white/`#DE2626` hex token palette instead
        of switching to the reference docs' OKLCH color functions — same
        palette your own dev policy already specifies; no reason to
        introduce a second color system for this.
      - Did not adopt the reference docs' collapsible tree-nav sidebar
        (the "Content / Categories / Posts / Pages" expandable admin
        tree) for the public-facing site. That's an *admin dashboard*
        pattern — a public visitor doesn't need a collapsible tree of
        every page/post/category, they need to read the site. Kept the
        existing flat nav + hamburger menu, now with feed cards for
        actual content browsing.
- [x] **Verified with a real build**, not just isolated tests: added an
      actual published post with real content to a throwaway copy, ran
      `management_cms_static_build()`, and confirmed the generated
      `index.html` contains a real feed card (title, date, truncated
      excerpt) — then separately unit-tested
      `_management_cms_build_category_page()` directly with fabricated
      posts to confirm no invalid `<ul>` remains and the empty-state
      message ("No posts in this category yet.") renders cleanly when a
      category has zero posts.
- [ ] **Not implemented: real pagination.** Elton's reference feed doc
      included working pagination UI (page 1/2/3/.../12). Building that
      for real means splitting a feed into multiple output files
      (`/category/news/page/2.html` etc.), tracking page counts, and
      wiring "next/prev" links — a genuinely separate feature, not
      something to improvise inside this pass. Currently every feed (home,
      category, tag) renders as one unpaginated list; flagging rather than
      building fake pagination buttons that don't go anywhere.
- [ ] **Page and Post templates themselves were not visually reworked**
      this pass — they already got the byline/tags conditional-rendering
      fix and the shared token palette in the prior session. If you want
      them redesigned to match the new card-feed visual language more
      directly (e.g. a hero/featured-image treatment), that's a distinct,
      focused pass rather than folded into this one.

## 9. Nav sidebar restyle (2026-07-25, from a live preview screenshot)
Elton previewed a real build on his phone and said the nav sidebar looked
"kind of goofy" and asked for the visual style from the two reference docs.
- [x] **Restyled `.becss-c-nav__link`/`.becss-c-nav-group`** from plain
      inline text with no padding (and a group label crammed inline next
      to a horizontally-wrapping link list) into proper tree-row-style
      rows: padding, border-radius, a hover background, and — in the
      mobile flyout specifically — a red left-accent border on hover,
      matching the reference docs' `.becss-tree__row` treatment.
- [x] **Deliberately did not copy** the reference docs' JS expand/collapse
      behavior or admin-style icons — just the row/hover visual language,
      applied to the nav structure that already exists (manual links +
      Categories + Pages + Recent Posts groups).
- [x] **Verified with a real build**: ran `management_cms_static_build()`
      and confirmed the new CSS classes and updated hover/padding rules
      actually appear in the generated `index.html`, not just written and
      assumed correct.
- [x] **Confirmed, not assumed:** the "Test_Category"/"Test-Page-Category"
      items Elton saw in his screenshot are the same test data already
      accounted for, not a separate mystery "news template" bug — he
      confirmed this himself, no code change was needed.

## 10. Full codebase audit (2026-07-26)
Requested directly: "audit code base." Full sweep, not scoped to any one
feature.
- [x] **Compile-swept all 34 `.py` files** — all clean.
- [x] **Swept every `sorted()`/`.sort(key=lambda...get(...))` call site**
      for the None-vs-default-value class of bug already found twice this
      project (Page `sort_order`, NavLink `sort_order` in the CMS family).
      Found 3 more instances — in my own
      `lib/Management_Live/lib_bejson_Management_Live_nav.py`, missed when
      that file was created because the write-side fix (item 2b) doesn't
      cover the read side. Fixed all 3 with `or 0`. Everywhere else that
      matched the grep already had a safe `or ""`/`or 0` fallback in
      place.
- [x] **Swept for mutable default arguments, bare `except:`,
      `== None`/`!= None`, and duplicate `RELATIONAL_ID`s** across the
      whole codebase — all clean.
- [x] **Reviewed the security-critical code directly** (path-traversal
      guard, `secure_filename()`, upload de-duplication) rather than
      trusting the earlier report a second time — confirmed correctly
      implemented and properly wired into real call sites with correct
      error handling in both places it's used.
- [x] **Found and fixed two real "delete doesn't clean up its
      dependents" bugs:**
      - `delete_media()` in `app.py` only ever removed the database row.
        `management_media_delete()` never deleted the physical file (or
        its WebP sibling) from disk — a permanent storage leak on every
        delete — and never touched the separately-created CmsMedia
        record for the same upload (the two Media bookkeeping systems
        share no foreign key at all, only the same `original_path` by
        coincidence of both being created from the same upload). Fixed:
        looks up the record first (so its paths are still available),
        deletes both files if present, then finds and deletes the
        matching CmsMedia record by path. Tested a full
        upload-simulate-then-delete cycle: file, webp, admin record, and
        linked CMS record all confirmed gone; unknown-id delete still
        404s cleanly instead of crashing.
      - `management_cms_content_delete_page()` left the page's `PageSeo`
        row behind as a permanent orphan pointing at a `page_id_fk` that
        no longer exists. Fixed and tested: create page + set SEO,
        delete page, confirm the SEO record is gone too.
- [x] **Vulture at 100% confidence** found nothing new beyond the
      already-flagged, deliberately-untouched `check_bidirectional`
      parameter in `lib_bejson_Core_mfdb_validator.py` (Core library,
      needs a verified-bug justification for a signature change, not just
      an unused-parameter observation — same reasoning as before).
- [x] **Full regression pass**: reran `management_cms_static_build()` end
      to end (still builds clean) and exercised the admin NavLink
      add+tree path specifically, since that's exactly what the
      `nav_position` sort fix touches — confirmed still correct.
- [ ] **Not audited this pass:** `lib/Management/*.py` originals (the
      CLI-only family — `landing.py`, `pages.py`, and the untouched
      halves of `notes.py`/`tasks.py`/`links.py`/`nav.py`/`media.py`),
      since they're out of scope for the live Flask app and protected
      under Library Immutability. If Elton wants the CLI tool itself
      audited, that's a distinct pass.
- [ ] **Not audited this pass:** JavaScript in `templates/index.html` and
      the exported-site skeleton templates in `app.py` — this audit was a
      Python-focused sweep (compile, dead code, common bug patterns,
      delete/orphan-cleanup consistency). A frontend-specific audit would
      need its own pass.

## 11. Dead code / dead library sweep (2026-07-26)
Requested directly: "remove dead code and libs."
- [x] **Checked for fully orphaned files** (never imported by anything,
      anywhere) across all 34 `.py` files — none found. Every file is
      referenced by `app.py`, another lib file, or
      `lib_bejson_Management_cli.py`. No dead libraries to remove.
- [x] **`vulture` at 80% confidence, each hit manually verified before
      touching anything** (not just acted on blind):
      - Removed a genuinely unused `Set` import from `typing`
        (`lib_bejson_Core_bejson_validator.py`).
      - Removed two genuinely unused re-imported functions,
        `bejson_core_filter_rows`/`bejson_core_sort_by_field`
        (`lib_bejson_Core_mfdb_core.py`) — confirmed never called in that
        file and never re-exported for anything else to import from
        there either.
      - Removed 3 unused imports from `lib_bejson_Management_cli.py`:
        `management_tasks_toggle_done`,
        `management_landing_update_section`,
        `management_landing_remove_section` — confirmed no CLI menu path
        calls any of them. The underlying functions themselves are
        untouched in their source libraries — only the redundant import
        names in the CLI's own file were removed.
- [x] **Deliberately left alone, not misidentified as dead:** the
      `E_MFDB_CORE_*`/`E_MFDB_*` error-constant imports vulture also
      flagged in `mfdb_core.py`/`mfdb_validator.py` — that's a fail-loud
      registry-completeness check (the whole module refuses to import if
      any expected error constant is missing from the registry), not
      unused code; and `check_bidirectional` in `mfdb_validator.py`,
      already flagged in item 5 above — Core library, needs a
      verified-bug justification for a signature change, not just an
      unused-parameter observation.
- [x] **Checked the admin dashboard JS** (`templates/index.html`) for
      unused functions. Initial scan (function name appears only once,
      at its own declaration, within the `<script>` block) found 5
      candidates; every one turned out to be a false positive once
      checked against the *whole file* — each is actually called via an
      `onclick="..."` attribute in the static HTML markup outside the
      scanned script block. No dead JS found.
- [x] **Full regression after all removals**: app still deploys cleanly,
      static build still completes, and `lib_bejson_Management_cli.py`
      still imports cleanly with the 3 names removed.

## 12. Favicon/OG tags + Post URL restructure (2026-07-27)
Requested directly ("get to work on whatever is not done") — two of the
open items from the last review.
- [x] **Favicon + Open Graph tags.** Added a self-contained inline SVG
      favicon (red circle on black, no asset to generate or ship) and a
      full OG meta block (`og:type`, `og:title`, `og:description`,
      `og:url`, `og:site_name`, canonical link, `twitter:card`) to
      `page_shell()` in `app.py`. New `og_title`/`og_description`/
      `canonical_url` tokens populated in all 5 builder functions (home,
      page, post, category archive, tag archive) in
      `lib_bejson_management_cms_static_builder.py` — post's
      `og:description` reuses `management_cms_shared_excerpt()` rather
      than dumping raw `content_html` into a meta attribute. Verified
      with a real build: favicon present and OG tags correctly populated
      (not leftover `{{tokens}}`) on home/post/category pages, with
      correct canonical URLs on each.
- [x] **Post URL restructure — the collision fix that was previously just
      a warning.** Posts now write to `/post/{slug}.html` instead of flat
      `/{slug}.html`, matching the existing `/post-category/`/
      `/page-category/` symmetry. This makes a Page/Post slug collision
      structurally impossible instead of merely detecting it after the
      fact — the old warning-only guard (item 12 in an earlier section)
      was removed as dead code, since the collision it checked for can no
      longer happen. **Breaking** for any already-published site: old
      flat post URLs are no longer produced.
- [x] **Every internal post-URL reference updated to match** —
      `canonical_url`, category/tag archive feed-card links (the category
      archive's link is conditional, since that builder is reused for
      page-type categories too, which correctly stay flat), and
      `feed.py`'s RSS/Atom/JSON feeds and recent-posts widget.
- [x] **Found and fixed a 4th missed reference during the audit crawl,
      not just trusted the first 3 fixes.** A full link-crawl of a real
      build initially found 20 broken links, all pointing at the nav
      sidebar's own "Recent Posts" block
      (`_management_cms_build_recent_posts_html()` — a *different*
      function from `feed.py`'s recent-posts widget, easy to miss since
      they sound almost identical). It still had the old flat URL, and
      since that block renders in the nav on every page, it broke links
      site-wide. Fixed and re-crawled.
- [x] **Verified with a full link-crawl of a real multi-content build**
      (posts, pages, both category types, tags, home fallback): 0 broken
      links across 83 checked on the second pass. Separately confirmed
      `sitemap.xml`, `feed.xml`, `atom.xml`, and `feed.json` all emit the
      correct `/post/` URL.
- [x] **Homepage hero, real feed pagination, and stale-output cleanup —
      done 2026-07-28** (see section 13 below).
- [ ] **Still not done:** an audit pass on `lib/Management/*` (the
      CLI-only originals, out of scope for the live app but not yet
      reviewed on their own terms).

## 13. Homepage hero, real pagination, stale-output fix (2026-07-28)
Requested directly ("get to work on whatever is not done" / after seeing
a stale-looking preview, "clean up any old broken unused files").
- [x] **Homepage hero.** The auto-generated homepage now shows the site
      title/tagline in a distinct block above the feed instead of
      dropping straight into the feed with no front-page treatment at
      all. Only renders if there's a title or tagline configured — no
      empty hero shell. Verified on a real build; separately confirmed
      (by inspecting the actual `<main>` content directly) that it
      correctly does *not* render when both are empty — an earlier
      shortcut assertion checking the whole document instead of just
      `<main>` gave a false negative here, caught and re-verified
      properly before trusting it.
- [x] **Real feed pagination.** Added
      `management_cms_shared_paginate()`/`render_pagination_nav()`
      (`lib_bejson_management_cms_shared.py`) and
      `_management_cms_write_paginated_feed()`
      (`lib_bejson_management_cms_static_builder.py`), wired into the
      homepage fallback, both category-archive loops (post-type and
      page-type), and the tag-archive loop. Page size 10. Page 1 stays at
      the original URL (`/index.html`, `/post-category/{slug}.html`,
      etc.); page 2+ goes to `.../page/{n}.html`. Tested with 25 posts in
      one category/tag — correctly produced 3 pages everywhere, with 0
      broken links across the whole crawl.
- [x] **Caught my own bug before it shipped.** While adding the
      pagination helpers to `shared.py`, an edit accidentally dropped the
      `def management_cms_shared_render_feed(...)` signature line
      entirely, leaving its body orphaned with no function — the very
      next import-and-build test failed immediately with an
      `ImportError`, not left for Elton to discover. Fixed and re-tested.
- [x] **Stale-output fix — the real bug behind "the exported site looks
      like nothing's changed."** A crawl of this project's own `Export/`
      folder found `Export/category/test-category.html` — a genuine
      leftover from *before* the `/category/` → `/post-category/` rename,
      still being shipped in every delivered zip since, because nothing
      ever cleared old output before writing new output. Same story for
      an orphaned `Export/management_cms_Export.zip` that nothing in the
      codebase creates or references. Root cause: the build only ever
      added files, never removed any — so any renamed or deleted content
      (category URLs, individual posts/pages, whatever) accumulates dead
      weight forever. Fixed by wiping the output directory clean before
      every build. Confirmed safe first: media is already re-copied from
      its original source path on every build, not from `Export/` itself,
      so nothing is lost by clearing it. Verified: the actual stale files
      in this project are confirmed gone after a real rebuild, and two
      consecutive builds both succeed without error.
- [x] **This delivery's `Export/` folder is the output of a real rebuild
      of this actual project** — not carried-over stale content, per the
      explicit request to send the site "pre-built."

## 14. Nav item link picker (2026-07-29)
Requested directly: "radio box Pages or Posts and then combo box the
specific page or post and then click add."
- [x] **Added a Link Type radio (Custom URL / Page / Post)** to the Site
      Nav admin form (`templates/index.html`), plus a combo box that's
      populated by fetching the real Pages/Posts lists from the existing
      `GET /api/pages`/`GET /api/posts` routes — no new backend routes
      needed, just wired the admin UI to data that was already there.
- [x] **Picking an item auto-fills the URL field** with the correct real
      output path — `/{slug}.html` for pages, `/post/{slug}.html` for
      posts, matching the actual static-build URL scheme exactly (not a
      guessed-at format) — and auto-fills the Label field with the
      item's title if the label is still empty.
- [x] **Defaults to Custom URL** for both new items and when editing an
      existing one. Reverse-matching an arbitrary already-saved URL back
      to a specific page/post isn't reliable enough to guess at silently,
      so existing nav items and the plain-URL workflow are completely
      unchanged unless the new picker is actually used.
- [x] **Verified end-to-end, not just that the JS parses.** Created a
      real page and post through the actual API routes, confirmed both
      are findable through the exact same data source the picker calls,
      and confirmed the computed URLs save correctly as real nav items
      pointing at the exact real output paths (`/contact-us.html`,
      `/post/launch-announcement.html`).

## 15. External audit remediation — two passes (2026-08-13)
Elton had an outside audit run against Package 13/v4.18.0
(`MANAGEMENT_CMS5_AUDIT.txt`), then a second-pass review of the fixes
themselves. Full detail for both lives in `data/changelog.md`'s two
"Audit remediation" entries (app.py 5.1.0, then 5.2.0) — this section is
the checklist-style summary, since neither pass fit the "5 liabilities"
framing sections 1–14 were built around.

**Pass 1 (5.1.0) — 19 findings from the original audit.**
- [x] 14 fixed outright: H-2 (`category_id_fk` dropped on Page/Post
      create), H-3 (stale `esc()`, see item 1 above), H-4 (upload
      MAX_CONTENT_LENGTH + extension allow-list + magic-byte sniffing),
      M-1 (`quickAddTag()` breaking new-post saves), M-3 (unscoped
      filter-bar queries), M-4 (nav-link-picker cache never invalidating),
      M-5 (`_BUILD_STATE` mutated outside its lock), M-8 (`AUDIT.txt`
      duplicated verbatim), L-1 (mid-file imports), L-2 (`print()` ->
      `logging`), L-3 (Python 3.8+ floor enforced), L-6 (rebrand drift —
      partial, see pass 2), L-7 (dead CSS selector), L-8 (`oklch()` hex
      fallback), L-10 (`requirements.txt` added).
- [x] H-1/M-7 — attempted (shared `X-Admin-Token` gate + CSRF closure +
      loopback-default bind) but shipped with a critical flaw — see pass
      2 below.
- [~] M-2, M-6 — partial: render-path-only validation, warning-only
      build gap respectively. Full-scoped in pass 2 (M-2) / left
      warning-only by design (M-6, see `security-notes.md`).
- [ ] Correctly deferred, unchanged from before: CHECKLIST item 1b
      (`onclick` -> `addEventListener`+`dataset` structural rewrite),
      Direction-1 naming / Layer 2 formalization (section 3 above).

**Pass 2 (5.2.0) — review of pass 1's own fixes found 3 real problems.**
- [x] **§3.1, critical — the auth gate was fully bypassable.** Pass 1
      exempted `/` from the token check (necessary — the browser has to
      load *something* first) but then rendered `ADMIN_TOKEN` straight
      into that unauthenticated page. `GET /` -> read the token out of
      the HTML -> use it on every other route, no auth actually required.
      Fixed properly this time: `/` ships with no token; a login prompt
      (new, client-side only) collects it from the person running the
      app (who reads it off the console/log or `config/admin_token.txt`
      at startup, same as any CLI "here's your API key" flow), verifies
      it via new route `GET /api/auth/check`, and holds it only in
      `sessionStorage` — never written into any HTML response again. The
      round-1 `?token=` query-string fallback for GET-only navigations
      (preview iframe, download link) is gone too (it leaked into server
      logs/browser history) — replaced with a `SameSite=Strict` cookie,
      accepted only for GET requests, so state-changing routes still
      require the header and CSRF stays closed. Verified live against a
      running instance, not just read: confirmed the token is absent from
      `/`'s response body, unauthenticated calls 401, the cookie alone
      authenticates a GET but is correctly rejected on a POST.
- [x] **§3.2 — L-4 recurred.** The `<H2O>Post Title Test</h2>` seed was
      fixed as *data* in pass 1, but nothing validated new saves, so the
      exact same bug class came back (a fresh malformed seed) and was
      caught in the pass-2 audit. Added `_lint_content_html()` — a
      balanced-tag check via `html.parser` — to all four
      create/update Page/Post routes; rejects a genuine mismatch (exactly
      what `<H2O>...</h2>` is) with a 400, while correctly not flagging
      legal HTML5 tag-omission patterns (`<li>` without `</li>`, etc.).
      Unit-tested against 7 cases before wiring in.
- [x] **§3.3 — L-11 claim disputed.** Pass 2's audit reported the
      delivered `Export/` had 8 files with no `feed.xml`/`atom.xml`/
      `sitemap.xml`. Rebuilt `Export/` from this project's actual source
      data and confirmed all three files ARE produced (11 files total);
      also confirmed via `unzip -l` that the zip actually delivered for
      pass 1 already contained them. Noted the discrepancy rather than
      guessing at a fix for a problem that doesn't reproduce here — worth
      Elton double-checking what he actually received if this comes up
      again.
- [x] **§4.2 — L-6 was only half-finished.** Pass 1 fixed the rebrand
      drift ("Homepage Builder" -> "Management_CMS") in the HTML scaffold
      copies and the `skeleton_store.bejson` blobs, but missed all 9
      `Content/*_style.css` header comments, which carry the same drift
      one directory level down. Swept and fixed; backup copies under
      `Persist/factory_reset_backups/` correctly left untouched.
- [x] **§4.4 — three real documentation inconsistencies**, all fixed:
      `security-notes.md` claimed L-4 "was fixed as data" (contradicted
      by the pass-2 audit's own evidence, since the recurrence proved it
      wasn't durably fixed) — corrected and expanded with the actual
      fix. `data/changelog.md` referenced a `docs/variable_naming_issues.md`
      that was never created — reference removed rather than left
      dangling. Pass 1's changelog entry silently omitted L-3 and L-10
      from its own fixed-items list even though both were genuinely done
      in that same pass (an *under*claim, the audit's words) — added as
      proper bullets instead of leaving them unlisted.
- [x] **§4.5 — `click` dependency claim checked, not assumed.** The
      pass-2 audit inferred `lib_bejson_Management_cli.py` is
      Click-based and flagged `requirements.txt` as missing `click`.
      Checked the actual file: zero `click`/`argparse` imports — it's a
      plain importable Python class, not a Click CLI. Nothing to add.
      Also functionally verified the WebP-on-upload path works with
      Pillow installed (the pass-2 audit's `webp_path: ""` observation
      was itself correctly read as "Pillow wasn't present when that
      package was built," not a bug — confirmed rather than just agreed
      with).
- [x] **§4.6 — M-2's render-only scope closed.** `note_color` is now
      validated against the same swatch allow-list at the `/api/notes`
      POST/PUT routes (`_clean_note_color()`), not just at render — a
      raw API call bypassing the swatch-only UI can no longer store an
      out-of-palette value at all.
- [x] **§4.7 — residual bad data from the pre-fix H-2 bug, cleaned up.**
      "Test Blog Post" had `category_id_fk: null` from before H-2 was
      fixed, so its category archive page rendered "No posts in this
      category yet" despite the post existing. Reassigned via the app's
      own `management_cms_content_update_post()` (not a raw data edit)
      and rebuilt `Export/` — confirmed the category page now lists the
      post.
- [ ] **§4.1 — `bejson_project.json` provenance question, not resolved,
      not guessed at.** The pass-2 audit describes a prior
      `.bejson_project.json` (dot-prefixed, `Schema_Version` 2.0.0,
      GUID `c372e44e…`) that this project supposedly "went from." The
      zip actually delivered to build pass 1 contained no
      `bejson_project.json` of any name — checked directly, not assumed.
      The file created in pass 1 (no dot, `Schema_Version` 1.6.0, per
      Elton's own policy template) is the first one that's ever shipped
      in a package I received; there's no prior-history file on this end
      to reconcile against. If that dot-prefixed file exists somewhere
      outside what's been uploaded here, send it over and the history
      can be merged properly instead of orphaned.

## 16. Exported-site redesign + external audit remediation, round 3 (2026-08-14)

**Redesign.** Elton uploaded three reference templates (vanilla_blog.html,
vanilla_article.html, vanilla_landing.html) and asked for the exported
public site to be built around them. Rewrote the shared HTML/CSS shell
for all 5 registered ComponentsMFDB layout components
(management_cms_home/page/post/category_archive/tag_archive): fixed
18rem sidebar app-shell, mobile hamburger + slide-in overlay, Syncopate/
Inter/Fira Code fonts, red/black/white palette, checkerboard texture,
card-hover-lift feed cards, pill pagination, article typography. Shell
only — every `{{token}}` preserved exactly, so
`lib_bejson_Management_static_builder.py`/`lib_bejson_Management_shared.py`
needed zero changes. Applied to both ComponentsMFDB copies. Verified via
a real build (balanced-tag check on every output page, zero leaked
tokens) and a headless-rendered screenshot of 4 page types. Full detail
in `data/changelog.md`.

**Round-3 audit.** A third external audit pass reviewed the state after
the redesign.
- [x] Three findings did NOT reproduce, checked directly rather than
      assumed: H-1 (lib/ "entirely absent" — delivered zip has 37 lib/
      entries), H-3 (Export/ "8 files, no XML feeds" — confirmed 11 files
      present), half of H-4 ("no media binaries shipped" — both real
      image files confirmed present and valid). Third audit round in a
      row with this exact pattern (same dispute as round 2's L-11) —
      flagged prominently rather than re-"fixed" a third time.
- [x] **H-2** — the `lib/Management_Live/` comment in app.py was stale
      and wrong. Traced what actually happened (the by-name MFDB
      migration landed in place in `lib/Management/*.py`) and corrected
      the comment; also resolved the audit's own open question about
      whether `lib_bejson_Management_cli.py` inherits the fix (it does —
      confirmed via import analysis, not assumed).
- [x] **H-4 (real half)** — absolute Termux device paths in
      `taxonomytype.bejson` and both `media.bejson` files, confirmed
      genuinely consumed as filesystem paths (traced into
      `scaffold.py`'s resync `isdir()` check and `app.py`'s delete-media
      route). Fixed at the write sites (`bootstrap.py`/`init.py` now
      store project-relative paths), the read sites (`scaffold.py`/
      `cli.py`/`app.py` resolve either format), and the current data.
- [x] **H-5** — `selectUrl` was the one value skipped by `esc()` in the
      media picker's `onclick`, unlike its neighbors. Fixed, with an
      honest comment about the fix's actual (partial) scope.
- [x] **M-2** — category-archive empty-state message hardcoded to
      "posts" even for Page categories. Now type-aware; verified live.
- [x] **M-3** — post byline showed category *slug* instead of *title* —
      wired to the slug-map lookup where a title map belonged. Added
      `management_cms_taxonomy_get_category_title_map()`, verified live
      (byline now reads "Developer Post Category", not the slug).
- [x] **M-4** — `admin_token` cookie's `HttpOnly` was `False` with
      nothing reading `document.cookie` (checked, not assumed). Now
      `True`; `Secure` conditional on `request.is_secure` rather than
      hardcoded (which would've silently broken the default HTTP-loopback
      bind).
- [x] **M-6** — download button only served `Export/index.html`, not
      the full multi-page build. Now zips the entire `Export/` tree.
      Verified live: real download came back as 692KB/13 files.
- [x] **LOW #1** — duplicate `_TOKEN_FILE` definition removed.
- [x] **LOW #3** — login-gate/comment text corrected: it's the token
      *file's path* that's printed at startup, not the token value.
- [x] **LOW #4** — `openPreview()` no longer conflates a 401 (needs
      re-auth) with a 404 (no build yet) into the same message.
- [x] **LOW #6/#7** — `hb_style.css` filename mismatch, root-caused (not
      just patched at the symptom): both scaffold-generation functions in
      `lib_bejson_Management_scaffold.py`
      (`webframework_scaffold_deploy_taxonomy_mfdb()` and
      `webframework_scaffold_resync_components()`) hardcode
      `href="hb_style.css"` from the shared `app_shell` component while
      always naming the actual file per-taxonomy — guaranteed mismatch on
      every future taxonomy/resync. Fixed at both call sites; verified
      live by re-running the actual resync function and confirming
      correct output with no regression to the earlier H-3/L-6 fixes
      (which live in `SkeletonStore` and correctly survive a resync).

**Round-3 audit, continued (M-1/M-5/M-7/M-8) — same day.**
- [x] **M-1** — `featured_image` settable in the admin editor since it
      existed, never read on the export side. Added an optional
      `thumbnail` param through `management_cms_shared_render_feed_card()`/
      `render_feed()`, wired into all 4 feed-item builders (category
      archive, tag archive, homepage feed, Recent Posts widget) plus a
      hero image on individual posts. Verified live: real WebP file
      serves correctly (200, byte-exact, correct content-type),
      thumbnail/hero both present in a fresh build.
- [x] **M-5** — checked every setting for actual consumers rather than
      trusting the audit's list. `debug` had zero references anywhere —
      removed (`docs/dead_code.md`). The other 4 flagged settings
      (`show_clock`/`show_greeting`/`accent_color`/`bg_color`) are NOT
      dead — `lib_bejson_Management_build.py`/the Termux CLI path uses
      them — just scoped narrower (no effect on this app's own Build
      button) than the Settings panel implied. Flagged inline instead of
      wiring them into the deliberately-fixed redesign as a scope-creep
      feature change.
- [x] **M-7** — category drag-drop only blocked direct self-parenting,
      not indirect cycles. Added real ancestor-chain checking server-side
      (the actual enforcement, in `update_category()`) and client-side
      (immediate drag feedback). Verified live: created a real child
      category, attempted an actual cycle, got a 400 with a clear error.
- [x] **M-8** — `scheduled_at`'s `datetime-local` input sent a bare
      local-time string straight to the server, compared against UTC.
      Verified the practical impact with Node (US-Eastern simulation): a
      "2pm local" schedule would have auto-published ~2.5 hours early.
      Added local<->UTC conversion at the UI boundary in both directions;
      verified the round-trip is exact. No server-side changes needed.

**Self-caught regression, fixed same session.** Live-testing the
`hb_style.css` scaffold fix above (actually running
`webframework_scaffold_resync_components()` to confirm it worked)
silently reverted the exported-site redesign in both ComponentsMFDB
skeleton stores — those rows were never flagged `user_customized`.
Caught while wiring in M-1, before the next delivery — the already-
delivered v5.3.0/PKG102 zip predates this accident and doesn't carry it.
Restored the redesign, re-applied M-1's CSS/tokens on top of it, and
marked the 5 redesigned components `user_customized: true` in the
project's own store so a future resync can't silently clobber this again.

## Versioning
- `app.py`: 4.3.1 → 4.6.0 → 4.7.0 → 4.8.0 → 4.9.0 → 4.10.0 → 4.11.0 →
  4.13.0 → 4.14.0 → 4.16.0 → 4.17.0 → 5.0.0 (packaged as delivered) →
  5.1.0 (pass 1, external audit remediation) → 5.2.0 (pass 2) →
  5.3.0 (redesign + pass 3, section 16) → 5.4.0 (pass 3 continued —
  M-1/M-5/M-7/M-8, section 16) (header + `VERSION` const + fresh
  `RELATIONAL_ID` each bump; 4.12.0/4.15.0 were used for standalone
  `.bejson_project.json` bumps and skipped in app.py to avoid duplicate
  version numbers)
- `lib_bejson_management_cms_taxonomy.py`: 2.0.0 → 2.1.0 → 2.2.0
- `lib_bejson_WebFramework_components.py`: 1.0.0 → 1.1.0
- `lib_bejson_WebFramework_scaffold.py`: 2.1.0 → 2.2.0
- `lib_bejson_Core_mfdb_core.py`: 2.0.1 → 2.1.0 → 2.1.1
- `lib_bejson_Core_bejson_validator.py`: 2.0.2 → 2.0.3
- `lib_bejson_Management_cli.py`: 1.0.0 → 1.0.1
- `lib_bejson_management_cms_static_builder.py`: 3.1.0 → 3.2.0 → 3.3.0 →
  3.4.0 → 3.5.0 → 3.6.0
- `lib_bejson_management_cms_content.py`: 1.3.0 → 1.4.0 → 1.5.0
- `lib_bejson_management_cms_media.py`: 1.1.0 → 1.2.0
- `lib_bejson_management_cms_nav.py`: 2.1.0 → 2.2.0
- `lib_bejson_management_cms_feed.py`: 1.0.0 → 1.1.0 → 1.2.0 → 1.3.0
- `lib_bejson_management_cms_shared.py`: 1.1.0 → 1.2.0 → 1.3.0
- `lib_bejson_Management_Live_nav.py`: 2.1.0 → 2.2.0
- **New files (`lib/Management_Live/`, copies of the CLI-facing
  originals — see item 2b above):** `lib_bejson_Management_Live_notes.py`
  (2.1.0), `_tasks.py` (3.1.0), `_links.py` (3.1.0), `_nav.py` (2.2.0),
  `_media.py` (2.3.0) — version numbers carried forward from each
  original's own version at copy time, then bumped for each subsequent
  migration/fix.
- `templates/index.html`: not under the strict `lib_bejson_*` version-
  header convention (it's a template, not a library file), so this
  change is tracked in `.bejson_project.json` and this checklist only
- `.bejson_project.json`: Project_Version 4.18.0, Package_Version 13
  (last known state before this file was — per §4.1 above — absent from
  the zip these two audit-remediation passes were run against). Recreated
  fresh at Project_Version 5.1.0/Package_Version 100, now bumped to
  5.2.0/Package_Version 101.
- **Version drift, resolved:** file's own header said 4.3.1 at the start of
  this session; Elton confirmed v4.5.0 was the correct prior version.
- `lib_bejson_Management_static_builder.py`: `Library_Version` 012 → 013
  for the M-6 (site_url-empty build warning) fix in pass 1.

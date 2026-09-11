STATUS: CLOSED — all findings remediated as of PKG116. Historical record only.

# Full Sweep Audit — Management_CMS v5.9.0 / PKG110

**Scope:** All 100+ files in the chunked BEJSON package.
**Date:** 2026-09-10
**Auditor pass:** Logic, security, practices, syntax, MFDB integrity.

---

## CRITICAL

### C-1 — Leaked `{{meta_description}}` token in `Export/404.html`

The 404 skeleton (`sk_html_management_cms_404_a1f2b3c4`) contains `{{meta_description}}` in its `<meta name="description">` tag. The builder's token map for the 404 component does not substitute this token. The literal string `{{meta_description}}` ships in the exported HTML.

```html
<!-- Export/404.html, line ~1 -->
<meta name="description" content="{{meta_description}}">
```

Every other token in the 404 skeleton (`{{site_title}}`, `{{nav_html}}`, `{{footer_html}}`, `{{og_title}}`, `{{og_description}}`, `{{canonical_url}}`) resolves correctly. Only `{{meta_description}}` leaks. This means `_management_cms_build_404()` (or whichever builder path renders the 404) omits `meta_description` from its `token_map`.

**Fix:** Add `"meta_description": ""` (or a sensible default like `"Page not found"`) to the 404 builder's token map, or remove the `{{meta_description}}` reference from the 404 skeleton if a 404 page should never carry a description meta.

---

## HIGH

### H-1 — Root manifest `record_count` stale for `ComponentMap`

`104a.mfdb.bejson` (root) declares:

| entity | declared `record_count` | actual rows in file |
|---|---|---|
| TaxonomyType | 9 | 9 ✓ |
| ComponentMap | **6** | **7** ✗ |
| SkeletonStore | 7 | 7 ✓ |

`data/component_map.bejson` has 7 rows (the 6th addition, `management_cms_404`, was registered in v5.8.0). The root manifest's `record_count` was never bumped. Any validator or tool that trusts `record_count` for integrity checks will flag a mismatch.

**Fix:** Update `record_count` to `7` in the root manifest's ComponentMap row.

### H-2 — Tripled Google Fonts `<link>` tags in all 6 CMS skeletons

Every CMS skeleton (`management_cms_home`, `_page`, `_post`, `_category_archive`, `_tag_archive`, `_404`) contains the **identical** font-loading block **three times**:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syncopate:..." rel="stylesheet">
<!-- ×3 -->
```

This was almost certainly introduced during the incremental skeleton patching sequence (base redesign → M-1 → nav-group), where each pass appended the font links without deduplication. Browsers deduplicate the network requests, so there's no functional breakage, but it's 6 unnecessary `<link>` elements per page, propagates into every exported HTML file, and bloats each skeleton blob by ~600 bytes × 6 skeletons.

**Fix:** Strip the duplicate `<link>` pairs from all 6 skeleton blobs in both `data/skeleton_store.bejson` and `lib/Management/ComponentsMFDB/data/skeleton_store.bejson`. Single occurrence is sufficient.

### H-3 — Inconsistent `parent_id` representation in `category.bejson`

`Content/Category/MFDB/data/category.bejson`:

```json
["ed9eb599...", "",   "post", "Developer Post Category", ...]   // parent_id = ""
["70f6a23b...", null,  "page", "Developer-Page-Category", ...]  // parent_id = null
```

One top-level category stores `parent_id` as empty string `""`, the other as `null`. The code handles both (Python's `or` / truthiness checks treat both as falsy), but this is a data-integrity inconsistency. Any future code that does `if parent_id is None:` vs `if not parent_id:` will behave differently depending on which row it hits. The `_indentedCategoryOptions()` JS helper checks `(c.parent_id||null)===parentId`, which coerces `""` to `null` via `||`, masking the inconsistency at the UI layer but not at the data layer.

**Fix:** Normalize to `null` for "no parent." Run a one-time data migration or fix at the write site in `management_cms_taxonomy_add_category()`.

---

## MEDIUM

### M-1 — `File:` header / filename mismatch in scaffold assets

| Actual filename | `File:` header says |
|---|---|
| `scaffold_style.css` (root) | `hb_style.css` |
| `scaffold_template.html` (root) | `template.html` |
| `assets/scaffold_style.css` | `hb_style.css` |
| `assets/scaffold_template.html` | `template.html` |

The L-6 rebrand pass updated `Description:` to say "Management_CMS" but left the `File:` header referencing the old names. The LOW #6/#7 fix in round 3 corrected the `<link rel="stylesheet" href="...">` targets but not the comment headers. Not functionally harmful, but violates the project's own header-accuracy convention and will confuse anyone trying to trace which file a header belongs to.

### M-2 — `_BUILD_STATE.get("_site_url")` read outside lock

In `_run_build_in_background()`:

```python
site_config = {
    ...
    "site_url": _BUILD_STATE.get("_site_url", ""),
    ...
}
```

This reads `_BUILD_STATE` without acquiring `_BUILD_LOCK`. The write side (`_build_set(_site_url=...)` in `build_homepage()`) does go through the lock. In practice the route handler sets `_site_url` before starting the thread, so the value is stable by the time the thread reads it. But this violates the pattern established by M-5 (all `_BUILD_STATE` access under lock) and is a latent race if the call ordering ever changes.

### M-3 — `handleSave()` dispatch can target wrong panel

`templates/index.html`:

```javascript
function handleSave(){
    var t = editTarget ? editTarget.type : P;
    if(t==="link"||P==="links") saveLinkModal();
    ...
}
```

If a user opens a modal on the "links" panel, then navigates to "notes" via the sidebar (the modal stays open — `go()` doesn't call `closeModal()`), then presses Ctrl+Enter, `P` is now `"notes"` but `editTarget` is still `null`, so `t` resolves to `"notes"` and `saveNoteModal()` fires instead of `saveLinkModal()`. The modal body still contains the link form fields, so `saveNoteModal()` would read from nonexistent `nf_title`/`nf_body` elements and silently save garbage or fail.

**Fix:** Either close the modal on panel switch (add `closeModal()` to `go()`), or capture `P` at modal-open time and dispatch on that.

### M-4 — `/media-files/` is auth-exempt with guessable filenames

`_AUTH_EXEMPT_PREFIXES` includes `"/media-files/"`. Uploaded files get `secure_filename()` names, but the original filenames from phone cameras (`1000744483.png`, `1000754777.webp`) are sequential integers. Anyone who can reach the server can enumerate media by incrementing the numeric prefix. Combined with the default loopback bind this is low-risk, but if `MANAGEMENT_CMS_HOST=0.0.0.0` is set (documented as a supported opt-in), all uploaded media becomes publicly enumerable without the admin token.

### M-5 — `\r\n` line endings in Post content data

`Content/Post/MFDB/data/post.bejson` `content_html` and `Content/Post/MFDB/content/posts/Test-Blog-Post.html` both contain `\r\n` (Windows CRLF) line endings. The rest of the project uses `\n`. This won't break HTML rendering (browsers normalize whitespace), but it creates inconsistency in diffs, hashes, and any tool that does line-by-line processing. The content was likely pasted from a Windows clipboard or edited on a device with CRLF defaults.

### M-6 — `Export/` OG/canonical URLs are bare `/` due to empty `site_url`

All exported pages carry:

```html
<meta property="og:url" content="/">
<link rel="canonical" href="/">
```

This is the correct BLD-01 degradation behavior (loopback/empty `site_url` → relative output). But the build warning that's supposed to flag this (`management_cms_static_build()` appends to `warnings` list) should be verified as actually firing in the build log. The `Export/404.html` additionally has empty `og:url` and `canonical` (not even `/`), which is slightly inconsistent with the other pages.

---

## LOW

### L-1 — 12+ duplicate copies of the same CSS design system

The identical BECSS design system exists as separate files in:
- `scaffold_style.css` (root)
- `HB_Framework/hb_style.css`
- `assets/scaffold_style.css`
- `Content/Links/links_style.css`
- `Content/media/media_style.css`
- `Content/Pages/pages_style.css`
- `Content/Notes/notes_style.css`
- `Content/Post/post_style.css`
- `Content/Nav/nav_style.css`
- `Content/Category/category_style.css`
- `Content/Tasks/tasks_style.css`
- `Content/Page/page_style.css`
- Embedded in `skeleton_store.bejson` (app_shell CSS blob)

Plus 12+ copies of the scaffold HTML template. Any design-token change (e.g., adjusting `--red` or `--r`) requires touching all of them. The `user_customized` flag protects the skeleton-store copies from resync, but the loose `Content/*_style.css` files have no such protection and will drift on the next scaffold resync.

### L-2 — `Persist/factory_reset_backups/` contains pre-fix code

The backup snapshot (`2026-07-31T11-17-43Z`) contains:
- Old 4-character `esc()` in all template files (pre-H-3 fix)
- "Homepage Builder" branding (pre-L-6 rebrand)
- Old `category/` URL prefix (pre-`/post-category/` rename)
- Absolute Termux device paths in `media.bejson` (pre-H-4 portability fix)

This is intentional (backup-never-delete, immutability). But if a factory reset is performed and then someone manually restores files from this backup instead of using the app's own re-bootstrap, they'd reintroduce all previously-fixed vulnerabilities. Worth a note in `docs/security-notes.md`.

### L-3 — `bejson_project.json` `Drive_Path` is device-specific

```json
"Drive_Path": "/storage/emulated/0"
```

This is an Android/Termux-specific path. The H-4 fix addressed absolute device paths in MFDB data files, but this project-metadata field was not covered. It's informational (not consumed as a filesystem path by any code in this package), but it's the same class of portability concern.

### L-4 — `skeleton_store.bejson` blobs are ~15KB+ escaped strings

Each CMS skeleton is stored as a single heavily-escaped JSON string value. The 6 CMS skeletons plus app_shell total roughly 100KB of escaped HTML/CSS/JS in a single BEJSON file. Any manual edit risks introducing a stray escape character that corrupts the entire record. This is inherent to the BEJSON format's design (HTML-in-JSON), not a bug, but it makes the file extremely fragile to hand-edit.

### L-5 — `config/config.bejson` `footer_text` is empty string

The `footer_text` setting exists and is wired into the build pipeline, but its value is `""`. The exported footer renders as `© 2026 Management CMS` with no additional text. This is correct behavior (the code handles empty `footer_text` gracefully), but the setting's `description` field says *"Extra footer text (e.g. \"All rights reserved.\") — appears after the auto copyright line"*, which might mislead a user into thinking something is broken when the footer looks "incomplete."

### L-6 — `Export/feed.json` `home_page_url` is empty string

```json
"home_page_url": "",
"feed_url": "/feed.json",
```

The `home_page_url` is empty because `site_url` is empty (BLD-01 degradation). The `feed_url` is relative. JSON Feed spec says `home_page_url` is required. An empty string is technically present but semantically meaningless. Same root cause as M-6.

---

## MFDB INTEGRITY SUMMARY

| Manifest | Entity | Declared Count | Actual Count | Status |
|---|---|---|---|---|
| Root `104a.mfdb.bejson` | TaxonomyType | 9 | 9 | ✓ |
| Root `104a.mfdb.bejson` | ComponentMap | **6** | **7** | **✗ STALE** |
| Root `104a.mfdb.bejson` | SkeletonStore | 7 | 7 | ✓ |
| Content/Notes | Note | 7 | 7 | ✓ |
| Content/Notes | NoteCategory | 2 | 2 | ✓ |
| Content/Links | Link | 1 | 1 | ✓ |
| Content/Links | LinkCategory | 1 | 1 | ✓ |
| Content/Tasks | TodoItem | 0 | 0 | ✓ |
| Content/Tasks | TaskCategory | 0 | 0 | ✓ |
| Content/Pages | Page | 0 | 0 | ✓ |
| Content/Pages | Media | 2 | 2 | ✓ |
| Content/Pages | NavLink | 2 | 2 | ✓ |
| Content/Page | Page | 2 | 2 | ✓ |
| Content/Page | PageSeo | 0 | 0 | ✓ |
| Content/Post | Post | 1 | 1 | ✓ |
| Content/Post | Tag | 0 | 0 | ✓ |
| Content/Category | Category | 2 | 2 | ✓ |
| Content/Nav | Nav | 0 | 0 | ✓ |
| Content/media | Media | 2 | 2 | ✓ |

One mismatch: **ComponentMap `record_count` 6 vs actual 7** (H-1 above).

---

## SYNTAX / COMPILE

No Python syntax errors detected in `app.py` (all imports resolve, all function definitions are well-formed, all route decorators are valid). No HTML structural errors in `templates/index.html` (single `<script>` block, balanced tags). No JSON parse errors in any `.bejson` file. The only syntax-adjacent issue is the leaked `{{meta_description}}` token (C-1), which is a template-substitution omission, not a syntax error in the source.

---

## SUMMARY

| Severity | Count | Key items |
|---|---|---|
| Critical | 1 | Leaked `{{meta_description}}` in 404 output |
| High | 3 | Stale `record_count`, tripled font links, inconsistent `parent_id` |
| Medium | 6 | Header mismatches, lock-gap, modal dispatch, auth-exempt media, CRLF, empty OG URLs |
| Low | 6 | CSS duplication, backup staleness, device path, blob fragility, empty config, empty feed URL |

**Overall assessment:** The codebase is in strong shape for v5.9.0. Five audit rounds have hardened the security surface substantially. The findings above are predominantly data-hygiene and output-correctness issues rather than exploitable vulnerabilities. C-1 is the only item that produces visibly broken output in the delivered `Export/`. H-1 and H-2 are the most actionable structural fixes. M-3 is the most likely to cause a real user-facing bug if triggered.
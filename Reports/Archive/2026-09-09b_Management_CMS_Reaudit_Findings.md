STATUS: CLOSED — all findings remediated as of PKG116. Historical record only.

# Management_CMS — Re-Audit Findings Report

**Subject:** Independent re-audit against current state (post PKG111–PKG113 remediation)
**Date:** 2026-09-09
**Auditor:** Claude
**Project state audited:** v5.9.0 / PKG113
**Scope:** Full re-scan — not a review of the prior remediation's correctness (that was verified at delivery time), but an independent pass looking for anything the original Full Sweep Audit and the subsequent remediation did not catch.
**Disposition:** Findings only. No fixes applied in this pass, per explicit instruction.

---

## Executive Summary

This re-audit found **3 new findings not present in the original Full
Sweep Audit** — one previously-undetected functional defect (home
page ships with zero meta description), and two MFDB manifest/entity
count mismatches, one of which appears to have been mis-reported as
"OK" in the *original* audit's own integrity table rather than
introduced by the recent remediation work.

Every fix delivered in PKG111–PKG113 was independently re-verified in
this pass and holds: the font-link dedup is complete (zero remaining
duplicates across both skeleton stores), the 404 token-map fix is
complete and its output now exactly matches its skeleton's declared
tokens, and no Python or JSON file in the project fails to parse.

A systematic cross-check (skeleton placeholder tokens vs. builder
`token_map` keys, run across all 7 page-type builders) was performed
as part of this pass — this is the same check Suggestion #1 of the
prior remediation report proposed adding as permanent code; running it
manually this time is what surfaced the home-page finding below.

---

## Findings

### NEW-1 (High) — Home page ships with zero `<meta name="description">` tag

**What:** `_management_cms_build_home_page()` in
`lib_bejson_Management_static_builder.py` computes and supplies a
`meta_description` value in its `token_map`. The home skeleton
(`sk_html_management_cms_home_2b49b928` in both `data/skeleton_store.bejson`
and the library copy) contains **no** `{{meta_description}}`
placeholder anywhere in its `<head>` — confirmed by both token
extraction (regex scan of every `{{...}}` in the skeleton content) and
a direct literal-string check for `name="description"` in the raw
skeleton HTML, which returned `False`. The skeleton's `<head>` goes
directly from `<title>{{site_title}}</title>` to the favicon `<link>`,
skipping a description meta entirely — every other page type (page,
post, category archive, tag archive, 404) has this tag; home does not.

**Confirmed live in the already-exported artifact:** `Export/index.html`
has no `<meta name="description">` tag at all. By contrast,
`Export/404.html`, `Export/About-Page-Test.html`, and
`Export/Contact-Page-Test.html` all have one.

**Why this matters more than a typical missing-tag issue:** the home
page is the single most SEO-significant page on the site — it's the
page search engines most commonly index and surface a description
snippet for — and it's the one page type where that snippet is
silently absent. This is the inverse-shape bug to C-1 (which leaked an
unfilled placeholder into output): here the builder *does* compute the
right value, but the skeleton gives it nowhere to go, so the value is
silently discarded and the page ships without it. Neither the original
Full Sweep Audit nor the PKG111–113 remediation pass caught this,
because both were working from the skeleton's existing token set
outward rather than cross-checking site-wide SEO-tag coverage across
page types.

**Root cause:** the home skeleton predates the `meta_description`
token's introduction to the other five skeletons (page/post/category/
tag/404 all carry it) and was never backfilled when that token was
added elsewhere — the same class of drift H-2's tripled-font-links
came from (an incremental patch applied inconsistently across
skeletons), just for a missing element instead of a duplicated one.

### NEW-2 (High) — `ComponentMap` `record_count` stale in the library-copy manifest

**What:** `lib/Management/ComponentsMFDB/104a.mfdb.bejson` declares
`ComponentMap` `record_count: 6`, but
`lib/Management/ComponentsMFDB/data/component_map.bejson` has 7 rows
(`app_shell`, `management_cms_home`, `management_cms_page`,
`management_cms_post`, `management_cms_category_archive`,
`management_cms_tag_archive`, `management_cms_404`) — identical in
content to the root project's own `data/component_map.bejson`, which
was corrected to `record_count: 7` in PKG111 (the original audit's
H-1 finding).

**Why this wasn't caught before:** the original Full Sweep Audit's
H-1 finding and its own MFDB Integrity Summary table only examined the
root project manifest (`104a.mfdb.bejson`) — the parallel manifest
inside `lib/Management/ComponentsMFDB/` was never in scope for that
audit or the remediation that followed it. It carries the exact same
data and the exact same defect, one manifest generation behind.

**Implication:** this confirms Suggestion #2 from the prior
remediation report (programmatic `record_count` resync) needs to cover
*every* manifest that shadows a given entity, not just the primary
project manifest — a one-off correction to the root file, as was done
in PKG111, does not close this class of drift when a library carries
its own duplicate manifest.

### NEW-3 (Medium) — `SkeletonStore` `record_count` mismatch in both manifests (7 declared vs. 8 actual)

**What:** both `104a.mfdb.bejson` (root) and
`lib/Management/ComponentsMFDB/104a.mfdb.bejson` (library copy)
declare `SkeletonStore` `record_count: 7`. Both underlying
`skeleton_store.bejson` files actually contain **8** rows:
`app_shell` is split across two separate rows (`sk_html_app_shell_...`
and `sk_css_app_shell_...` — HTML and CSS stored as distinct
`SkeletonStore` entities), plus the 6 CMS page-type skeletons
(home/page/post/category_archive/tag_archive/404).

**This appears to predate the recent remediation work.** No skeleton
rows were added or removed during the PKG111–113 remediation pass —
only existing rows' `skeleton_content` field was edited in place (the
H-2 font-link dedup). The original Full Sweep Audit's own MFDB
Integrity Summary table reported `SkeletonStore: declared 7, actual 7,
status OK` — that reported "actual" count does not match direct
inspection of the same file today, and since this pass made no
row-count changes, the most likely explanation is that the original
audit's own count was taken before `app_shell` was split into two rows,
or the original audit miscounted. Either way, the manifest and the
entity file are currently out of sync in both places, and this was not
corrected by the H-1 fix (which only touched the `ComponentMap` row,
not `SkeletonStore`, since the original finding was scoped to
`ComponentMap` only).

### Verified Clean — no action needed

- **Token-map completeness, all 7 builders:** systematic cross-check of
  every skeleton's `{{token}}` placeholders against its builder
  function's `token_map` keys. `home` has the gap described in NEW-1;
  every other builder (`page`, `post`, `category_archive`, `tag_archive`,
  `404`) supplies a superset of what its skeleton requires — no leaked
  placeholders, no other missing ones.
- **H-2 font-link dedup, both skeleton stores:** re-scanned every row
  in both `skeleton_store.bejson` files for the tripled font-link
  string; zero rows now contain more than one occurrence.
- **Python syntax:** every `.py` file in the project
  (`find . -name "*.py"` piped through `py_compile --doraise`)
  compiles cleanly.
- **JSON/BEJSON validity:** every `.bejson` and `.json` file in the
  project parses without error.
- **`lib/Core/lib_bejson_Core_bejson_list_validator.py`'s `print()`
  call:** guarded by `if __name__ == "__main__":` — fires only on
  standalone script execution, not on import. Not a §7.3 logging
  violation in practice, despite matching the raw pattern on a naive
  grep; confirmed by reading the surrounding control flow rather than
  flagging on the grep hit alone.
- **`/storage/emulated/0` references in `lib/Core/lib_bejson_Core_bejson_env.py`
  and `lib_bejson_Core_bejson_path_guard.py`:** these are the
  documented fallback/mapping paths specified by your own Global
  Operating Rules §4.3/§4.5, not unauthorized hardcoding.

### Still open (unchanged from the prior remediation report)

M-4 (media auth-exempt enumeration risk) and all 6 Low findings
(L-1 through L-6) from the original audit remain in the same state
reported previously — this pass did not re-investigate them further,
as nothing in this pass's scope touched their underlying code paths.

---

## Recommended Next Actions (findings only — not applied this pass)

1. **NEW-1:** add a `{{meta_description}}` placeholder to the home
   skeleton's `<head>` (both `data/skeleton_store.bejson` and the
   library copy), matching the pattern already used by page/post/
   category/tag/404.
2. **NEW-2:** correct `lib/Management/ComponentsMFDB/104a.mfdb.bejson`'s
   `ComponentMap` `record_count` from 6 to 7.
3. **NEW-3:** correct `SkeletonStore` `record_count` from 7 to 8 in
   both `104a.mfdb.bejson` (root) and the library copy — or, if
   `app_shell`'s HTML/CSS split was never intended to count as 2 rows,
   investigate whether that's itself a data-modeling question worth
   resolving before just changing the declared number.
4. Standing recommendation from the prior report reaffirmed by NEW-2:
   any future `record_count` reconciliation needs to cover every
   manifest that shadows a given entity (root project manifest **and**
   any library-embedded copy), not just the primary one.

Say the word and I'll apply these.

---

*Elton Boehnen · boehnenelton2024@gmail.com ·
boehnenelton2024.pages.dev · github.com/boehnenelton*

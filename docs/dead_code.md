# Dead Code Log

Verified-dead code removed from this project, per policy: confirmed zero
references before removal, logged here with what was removed and why.

## `debug` config setting — removed 2026-08-14 (M-5, round-3 audit)

**What:** the `debug` row in `MANAGEMENT_CONFIG_DEFAULT_VALUES`
(`lib_bejson_Management_config.py`) and the matching row in the live
`config/config.bejson`.

**Why removed:** grepped `app.py`, every file in `lib/Management/*.py`,
and `templates/index.html` for any reference to the `"debug"` config key
— zero consumers anywhere. It rendered in the Settings panel as an
editable text field a person could toggle believing it did something,
with no code path reading it back. Confirmed dead, not assumed.

**Not removed (related, but genuinely still used):** `show_clock`,
`show_greeting`, `accent_color`, `bg_color` — these DO have real code
behind them in `lib_bejson_Management_build.py`, consumed by
`lib_bejson_Management_cli.py`'s Termux export path. They have zero
effect on this web app's own "Build" button (which calls
`lib_bejson_Management_static_builder.py` instead), which was
misleading enough to flag — see the M-5 note added inline in the
Settings panel (`templates/index.html`) — but they are not dead code,
just scoped narrower than a glance at the Settings UI would suggest.

## `Content/Nav/` (CMS-layer Nav entity) — removed 2026-09-09

**What:** the entire `Content/Nav/` directory — `MFDB/104a.mfdb.bejson`,
`MFDB/data/nav.bejson` (0 records), `nav_template.html`, `nav_style.css`
— plus the `cms_nav` row in `data/taxonomytype.bejson` that registered
it (`TaxonomyType` `record_count` corrected 9 → 8 in the root manifest
to match).

**Why removed — three independent confirmations, not one:**
1. `lib_bejson_Management_init.py`'s own `_MFDB_LAYOUT` dict (what
   `management_cms_init()` actually scaffolds/registers today) has no
   `"nav"` entry at all, with an inline comment dated 2026-08-02:
   "Nav entity removed ... library consolidation — was deployed on
   every new site but never actually used for real navigation (the
   real Site Nav has always flowed through
   `lib_bejson_Management_nav.py`'s NavLink entity instead).
   `lib_bejson_management_cms_nav.py` deleted." — i.e. the management
   library for this entity was already deleted in a prior session;
   only the scaffolded data/manifest files from before that change
   were left behind in this specific project.
2. `app.py`'s own comment at the static-build call site confirms the
   same thing from the read side: `Content/Nav` ("cms_nav") is "which
   nothing in this app ever [writes to]" — the actual site nav is
   built from `PAGES_MANIFEST`'s `NavLink` entity, a completely
   separate structure that was NOT touched.
3. Direct grep across every `.py` file and `templates/index.html`:
   zero reads or writes against `Content/Nav`'s `Nav` entity anywhere,
   and `CMS_MANIFESTS["cms_nav"]` (which the taxonomy row would have
   populated) is never accessed as a dict key anywhere in `app.py`.

**Not touched:** `lib_bejson_Management_nav.py` and `PAGES_MANIFEST`'s
`NavLink` entity — this is the *live* Site Nav feature (the admin
"Site Nav" panel, `/nav` routes) and is unrelated to the dead
`Content/Nav`/`cms_nav` structure removed here, despite the similar
naming.

## `AUDIT.txt` (project root) — relocated, not deleted, 2026-09-09

Not dead code, but a stray root-level document: the original Full
Sweep Audit (v5.9.0/PKG110), fully superseded in content by
`Reports/2026-09-09_Management_CMS_Audit_Remediation_Report.md` and
`Reports/2026-09-09b_Management_CMS_Reaudit_Findings.md`. Moved to
`Reports/2026-09-10_Management_CMS_Full_Sweep_Audit_Original.md`
(CRLF normalized to LF in the process) rather than deleted, preserving
it as the primary source those two reports were built from — cleared
out of the project root, not out of the record.

## `__pycache__/` directories — cleared, 2026-09-09

Three stale compiled-bytecode caches (`__pycache__` under the project
root, `lib/Management/`, and `lib/Core/`) removed. Pure build
artifacts — regenerated automatically on next Python invocation, zero
source content, not part of any deliverable.

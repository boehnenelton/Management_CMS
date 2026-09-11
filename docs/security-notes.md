# Security Notes — deferred / partially-mitigated items

Written during the 5.1.0 audit-remediation pass against
`MANAGEMENT_CMS5_AUDIT.txt`, updated during the 5.2.0 pass against the
round-2 review (`Management_CMS — Audit Pass 2`). See `data/changelog.md`
for everything that WAS fixed in each pass. This file tracks what's still
open.

## Auth is single-token, not multi-user
The `X-Admin-Token` gate (H-1/M-7, hardened again in round 2 — see
below) closes the "anyone-on-the-LAN-can-wipe-the-app" gap, but it's
still one shared secret for the whole app — no per-user accounts, no
session expiry, no rate limiting on failed `/api/auth/check` attempts.
Adequate for a solo-admin tool; not a substitute for real auth if this
ever needs multiple admins or a public-facing deployment.

## Round-2 fix: the round-1 auth gate was fully bypassable
The round-1 pass gated every route except `/` — then rendered
`ADMIN_TOKEN` directly into `/`'s HTML (`var ADMIN_TOKEN = {{ admin_token
| tojson }}`). Since `/` itself required no token, that made the whole
gate a no-op: `GET /`, read the token out of the page source, use it on
everything else. Caught in the round-2 audit (§3.1). Fixed by no longer
handing `/` the token at all — it's read by the person running the app
from the console/log at startup or `config/admin_token.txt`, entered
once into a login prompt, verified via `GET /api/auth/check`, and held
only in `sessionStorage` (cleared when the tab closes, never written
into any HTML response). `/api/auth/check` also sets a `SameSite=Strict`
`admin_token` cookie, which is the only channel accepted for **GET**
requests without the header (used by the preview iframe and the ZIP
download link, neither of which can set a custom header) — state-changing
requests (POST/PUT/DELETE) still require the header, so a cross-site page
that can rely on the cookie being sent automatically still can't perform
a CSRF write. The round-1 `?token=` query-string fallback is gone
entirely (it leaked into server logs and browser history — also flagged
in the round-2 audit).

## `esc()` is still character-substitution, not context-aware (M-2, open)
The hardened `esc()` closes the `'`/`` ` `` breakout vectors, but every
`onclick="fn('"+esc(x)+"')"` call site in `templates/index.html` still
routes untrusted data through a JS-string context. The durable fix —
migrating those call sites to `addEventListener` + `dataset` — is
CHECKLIST.md item 1b, a deliberate structural rewrite, not done here.

## Content-HTML validation in the publish pipeline (L-4) — now enforced
`create_post()`/`update_post()`/`create_page()`/`update_page()` now run
`content_html` through `_lint_content_html()` (a balanced-tag check via
`html.parser`) before saving, rejecting mismatched/unclosed tags with a
400. This closes the actual failure mode — the `<H2O>Post Title
Test</h2>` seed content that shipped in the 5.1.0 round-1 audit pass was
fixed as *data* but nothing validated new saves, so the same bug class
recurred and was caught in the round-2 audit. Still true and worth
noting: the linter only catches structurally-broken tags (mismatched
open/close, unclosed at EOF) — it is not a full HTML sanitizer and
doesn't evaluate attribute content, inline `<script>`, or CSS in `style=`
attributes. Nothing changed on that front; see the `esc()` note above.

## Upload MIME sniffing covers common types only
`_sniff_file_type()` (H-4) recognizes JPEG/PNG/GIF/WebP/WAV/MP3/PDF/MP4/
MOV/WebM by magic bytes. `.svg` and `.ogg` have no fixed magic number
handled here, so a file with either of those extensions is trusted on
extension alone (still allow-listed, still under `MAX_CONTENT_LENGTH`,
just not content-verified). SVG in particular can carry embedded
`<script>` — if SVG uploads become untrusted-user-facing rather than
admin-only, that needs its own sanitization pass before this is safe.

## Packaging exclusion: `config/admin_token.txt` (N-1)
This file holds the live admin bearer token in plaintext and must never
be included in a delivered/distributed package — same class as an
`.env` file. `app.py`'s own comment on `ADMIN_TOKEN` has claimed this is
"gitignored-by-convention" since the auth gate was added, but no actual
`.gitignore` backed that claim up until this note — added one, with
`config/admin_token.txt` as its first entry.

Checked, not assumed: grepped every zip actually delivered so far this
project (`unzip -l | grep -i token`, on the real files) — zero hits in
every one. The token was never in fact shipped; the gap was the missing
*mechanism* to guarantee that stays true, not an active leak. If you
maintain your own packaging/chunking pipeline outside what's done in
this chat, make sure it also excludes `config/admin_token.txt`
explicitly — a `.gitignore` alone won't stop a chunker or zip command
that doesn't consult it.

If a token is ever suspected to have leaked (shared publicly, committed,
etc.): delete `config/admin_token.txt` and restart the app — a fresh one
generates automatically, and the old value stops working immediately
(compared via `hmac.compare_digest` against whatever's currently on
disk, so there's no grace period).



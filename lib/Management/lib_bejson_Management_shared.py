"""
Library:         lib_bejson_Management_shared
Family:          management_cms
Description:     Shared private helpers for the management_cms family — ID
                  generation, ISO timestamps, slugify, HTML escaping. Ports
                  and collapses the 8 duplicate private copies of these
                  functions found across the KIMI-CMS source (_gen_id,
                  _now_iso, _slugify, _esc) into one shared module, per
                  OFFICIAL_PLAN.MD Sec. I (36-char canonical UUIDs, not
                  KIMI's 12-char hex pattern).
Version:         1.3.0
Library_Version: 004
Date:            2026-07-28
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   8f3a6c9e-4b1d-4e7a-9c2f-6d8b3a4e9f57

CHANGELOG (1.3.0, 2026-07-28): Added management_cms_shared_paginate() and
management_cms_shared_render_pagination_nav() for real feed pagination
(homepage, category archives, tag archives — see
lib_bejson_Management_static_builder.py's changelog). Both unit-tested
in isolation (multi-page split, empty-list edge case, single-page-shows-
no-nav case) before being wired into the builders.

CHANGELOG (1.2.0, 2026-07-22): Added management_cms_shared_excerpt(),
management_cms_shared_render_feed_card(), and
management_cms_shared_render_feed() — a shared feed-card component so the
homepage recent-posts feed, category archives, and tag archives can all be
built off the same base instead of three separate bare <li><a> lists, per
Elton's request.
"""

import html as _html_mod
import re
import uuid
from datetime import datetime, timezone


def management_cms_shared_gen_id() -> str:
    """36-character canonical UUID string, per OFFICIAL_PLAN.MD Sec. I."""
    return str(uuid.uuid4())


def management_cms_shared_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def management_cms_shared_now_rfc822() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")


def management_cms_shared_to_rfc822(iso_str: str) -> str:
    if not iso_str:
        return management_cms_shared_now_rfc822()
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
    except (ValueError, TypeError):
        return iso_str


def management_cms_shared_fmt_date(iso_str: str, fmt: str) -> str:
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime(fmt)
    except (ValueError, TypeError):
        return iso_str


def management_cms_shared_slugify(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or management_cms_shared_gen_id()[:8]


def management_cms_shared_esc(text) -> str:
    return _html_mod.escape(str(text or ""), quote=True)


def management_cms_shared_export_media_url(url: str) -> str:
    """
    Rewrites an admin-app-only /media-files/<name> reference (what the
    media picker's URL field and the "featured_image" input actually
    store — that route only exists on the running Flask app, per
    app.py's own @app.route("/media-files/<path:filename>")) to the
    equivalent /media/<name> path that management_cms_static_build()
    actually copies uploaded files to in Export/.

    BUG FIX: this didn't exist when featured_image support (M-1) was
    added — the raw stored value was embedded straight into exported
    HTML unchanged. Confirmed broken: `src="/media-files/<name>"` in a
    real build's index.html/post page, a path that resolves through the
    live app but 404s on any real static hosting (or a locally-opened
    file) the export gets deployed to, which is the entire point of a
    static export. Only rewrites the one prefix this app itself
    generates (via the media picker) — leaves any other value (a
    external_url the user pasted directly, an already-relative /media/
    path, empty string) untouched.
    """
    url = url or ""
    if url.startswith("/media-files/"):
        return "/media/" + url[len("/media-files/"):]
    return url


# YouTube link support for featured_image / feed thumbnails. Mirrors
# lib_bejson_Management_media.py's own _YOUTUBE_ID_PATTERNS/_extract_youtube_id
# exactly (same patterns, same behavior) rather than importing that
# module here — static_builder.py and feed.py are export-time/read-only
# consumers and shouldn't need to pull in the admin-write-side media
# library (with its uuid/datetime/upload-handling surface) just to
# recognize a URL shape. Kept in sync manually; if the accepted URL
# formats change, update both copies.
_YOUTUBE_ID_PATTERNS = (
    r"(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
)


def management_cms_shared_youtube_id(url: str) -> str:
    """Returns the 11-char video ID if url is a recognized YouTube link, else ''."""
    url = url or ""
    for pattern in _YOUTUBE_ID_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return ""


def management_cms_shared_youtube_thumbnail_url(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def management_cms_shared_youtube_embed_html(video_id: str) -> str:
    """
    Responsive 16:9 iframe embed, wrapped in a ratio-locked container so
    it doesn't need a fixed pixel height (which would look wrong across
    the range of screen widths a post page has to support). No inline
    <style> needed at the call site — .becss-c-video-embed/__frame are
    defined once in the shared skeleton CSS.
    """
    return (
        '<div class="becss-c-video-embed">'
        f'<iframe src="https://www.youtube.com/embed/{video_id}" '
        'title="YouTube video" frameborder="0" loading="lazy" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" '
        'allowfullscreen class="becss-c-video-embed__frame"></iframe>'
        '</div>'
    )


def management_cms_shared_export_thumbnail(url: str):
    """
    Resolves a stored featured_image/thumbnail value for use as a feed
    card's small preview <img> — used by all 4 feed-item builders (home,
    category archive, tag archive, Recent Posts widget). Returns
    (thumbnail_url, is_video): a YouTube URL becomes its real static JPG
    thumbnail (an iframe embed doesn't belong in a small listing card —
    too heavy, autoplay/sizing issues), with is_video=True so the caller
    can flag it visually (a play-icon overlay); anything else goes
    through the existing /media-files/ rewrite unchanged, is_video=False.
    """
    video_id = management_cms_shared_youtube_id(url)
    if video_id:
        return management_cms_shared_youtube_thumbnail_url(video_id), True
    return management_cms_shared_export_media_url(url), False


def management_cms_shared_export_site_url(site_config) -> str:
    """
    AUDIT FIX (BLD-01): every canonical_url/og:url construction site
    across the 5 page-type builders independently read
    site_config.get("site_url"), so the loopback problem the N-2 warning
    already detects and warns about (a build triggered through the
    running app captures request.host_url verbatim, and the default
    bind is 127.0.0.1) was still silently baked into every absolute URL
    the build actually emitted — the warning told the operator about the
    problem without the output itself doing anything differently. An
    empty site_url already degrades gracefully (a relative URL, not
    ideal for Open Graph's absolute-URL requirement but at least not
    WRONG) — a POPULATED loopback site_url is worse: it produces a
    confident-looking absolute URL (http://127.0.0.1:5030/post/x.html)
    that's unreachable for literally everyone but whoever's running the
    admin app on that exact machine, and that's the value that gets
    baked into a search index or a social-media unfurl preview if the
    build is published as-is. Treating a loopback site_url the same as
    an empty one (fall back to relative output) closes that gap; the N-2
    warning stays as the one place this is actually explained to the
    operator, so this only needed to change what gets baked into the
    output, not add a second warning.
    """
    site_url = (site_config.get("site_url") or "").strip().rstrip("/")
    if not site_url:
        return ""
    host = site_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    if host in ("127.0.0.1", "localhost", "::1"):
        return ""
    return site_url


def management_cms_shared_current_year() -> int:
    return datetime.now(timezone.utc).year


def management_cms_shared_build_footer_html(site_config) -> str:
    """
    Feature request (Elton): a real global footer, not just the site
    title repeated. Builds "© <year> <site_title>[ · <footer_text>]" —
    footer_text is a new, optional config.bejson setting (freeform: a
    tagline, a company name, an "All rights reserved", whatever). Pure
    function of site_config so every one of the 5 page-type builders can
    call it identically without needing a shared token-assembly pass.
    """
    year = management_cms_shared_current_year()
    site_title = site_config.get("site_title", "")
    footer_text = (site_config.get("footer_text") or "").strip()
    parts = [f"\u00a9 {year} {management_cms_shared_esc(site_title)}"]
    if footer_text:
        parts.append(management_cms_shared_esc(footer_text))
    return " · ".join(parts)


_HEADING_PATTERN = re.compile(r"<h([23])(\s[^>]*)?>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
_TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")


def management_cms_shared_inject_toc(content_html: str, min_headings: int = 2):
    """
    Feature request (Elton): auto-generated table of contents for longer
    posts, built from h2/h3 in content_html. Returns
    (content_html_with_ids, toc_html): content_html_with_ids is the input
    with a unique id="..." added to every h2/h3 that doesn't already have
    one (skips ones that already have an id, so this is safe to run on
    content someone hand-authored with anchors already); toc_html is a
    nested list linking to them, or "" if there are fewer than
    min_headings headings (a 1-heading "table of contents" is just
    noise) or content_html has no headings at all.

    Regex-based rather than a full HTML parser deliberately: content_html
    is admin-authored (already passed through _lint_content_html() at
    save time — see app.py — so it's balanced tag-wise), and the only
    thing this needs to do is find h2/h3 open/close pairs and read their
    inner text, not handle arbitrary nested malformed markup.
    """
    headings = []  # [(level, text, id, full_match_span)]
    seen_ids = set()

    def slugify_heading(text: str) -> str:
        text = _TAG_STRIP_PATTERN.sub("", text)
        # Not reusing management_cms_shared_slugify() here on purpose: its
        # empty-input fallback is a random 8-char id (fine for
        # never-repeated things like category slugs), but a heading
        # anchor should be STABLE across rebuilds of the same content —
        # a random suffix would silently break any bookmarked/shared
        # #anchor link on every single build.
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"

    matches = list(_HEADING_PATTERN.finditer(content_html))
    if len(matches) < min_headings:
        return content_html, ""

    result_parts = []
    last_end = 0
    for m in matches:
        level, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        result_parts.append(content_html[last_end:m.start()])
        if re.search(r'\bid\s*=\s*"', attrs, re.IGNORECASE):
            # Already has an id — use it as-is for the TOC link, don't touch the tag.
            existing_id = re.search(r'\bid\s*=\s*"([^"]*)"', attrs, re.IGNORECASE).group(1)
            heading_id = existing_id
            result_parts.append(m.group(0))
        else:
            base_id = slugify_heading(inner)
            heading_id = base_id
            n = 2
            while heading_id in seen_ids:
                heading_id = f"{base_id}-{n}"
                n += 1
            result_parts.append(f'<h{level}{attrs} id="{heading_id}">{inner}</h{level}>')
        seen_ids.add(heading_id)
        headings.append((int(level), _TAG_STRIP_PATTERN.sub("", inner).strip(), heading_id))
        last_end = m.end()
    result_parts.append(content_html[last_end:])
    content_with_ids = "".join(result_parts)

    if not headings:
        return content_html, ""

    items = []
    for level, text, heading_id in headings:
        indent_class = " becss-c-toc__item--sub" if level == 3 else ""
        items.append(
            f'<li class="becss-c-toc__item{indent_class}">'
            f'<a href="#{heading_id}">{management_cms_shared_esc(text)}</a></li>'
        )
    toc_html = (
        '<nav class="becss-c-toc"><span class="becss-c-toc__label">Contents</span>'
        f'<ul class="becss-c-toc__list">{"".join(items)}</ul></nav>'
    )
    return content_with_ids, toc_html


def management_cms_shared_excerpt(html_content: str, max_chars: int = 160) -> str:
    """
    Strips tags from content_html and truncates to a clean word boundary —
    there's no dedicated excerpt field on Post/Page, so feed cards need
    something short to show instead of dumping full content_html into a
    list item. Added 2026-07-22 as part of building shared feed-card
    rendering (see management_cms_shared_render_feed_card()/_render_feed())
    for the homepage recent-posts feed, category archives, and tag
    archives — all requested to be built off the same base rather than
    each having its own bespoke bare <li><a> list.
    """
    text = re.sub(r"<[^>]+>", " ", html_content or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated + "…"


def management_cms_shared_render_feed_card(title: str, url: str, meta: str = "", excerpt: str = "", thumbnail: str = "", is_video: bool = False) -> str:
    """
    One feed-card's HTML — the shared unit used by
    management_cms_shared_render_feed() below. Kept separate in case a
    caller ever needs to render a single card outside a full feed list.

    AUDIT FIX (M-1): thumbnail is new. Post's featured_image has been
    settable in the admin editor since it was added, but nothing on the
    export side ever read it — the field silently did nothing past the
    admin form. Optional and empty-safe: no img at all when a caller
    doesn't pass one, so this is a pure addition for every existing call
    site that doesn't opt in.

    is_video: set when the resolved thumbnail came from a YouTube link
    (see management_cms_shared_export_thumbnail()) — adds a play-icon
    overlay so a video is visually distinguishable from a plain image in
    a feed listing, since the thumbnail image itself looks identical
    either way.
    """
    meta_html = f'<div class="becss-c-feed__meta">{meta}</div>' if meta else ""
    excerpt_html = f'<p class="becss-c-feed__excerpt">{management_cms_shared_esc(excerpt)}</p>' if excerpt else ""
    play_badge = '<span class="becss-c-feed__play-badge" aria-hidden="true"></span>' if (thumbnail and is_video) else ""
    thumb_html = (
        f'<a href="{url}" class="becss-c-feed__thumb-link">'
        f'<img class="becss-c-feed__thumb" src="{management_cms_shared_esc(thumbnail)}" alt="" loading="lazy">'
        f'{play_badge}</a>'
    ) if thumbnail else ""
    return (
        f'<article class="becss-c-feed__card{" becss-c-feed__card--with-thumb" if thumbnail else ""}">'
        f'{thumb_html}'
        f'<div class="becss-c-feed__card-body">'
        f'<h2 class="becss-c-feed__title"><a href="{url}">{management_cms_shared_esc(title)}</a></h2>'
        f'{meta_html}{excerpt_html}'
        f'</div>'
        f'</article>'
    )


def management_cms_shared_paginate(items: list, page_size: int = 10) -> list:
    """
    Splits items into pages of page_size. Always returns at least one
    (possibly empty) page, so callers don't need a separate empty-list
    branch. Added 2026-07-28 as part of building real feed pagination for
    the homepage, category archives, and tag archives — previously every
    feed rendered as a single unpaginated list no matter how many posts
    existed.
    """
    if not items:
        return [[]]
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]


def management_cms_shared_render_pagination_nav(current_page: int, total_pages: int, page_url_fn) -> str:
    """
    page_url_fn(n) -> the URL for page n (1-indexed, int in). Keeps the
    actual output-path scheme (which differs between the homepage,
    category archives, and tag archives) in the caller, which already
    knows its own conventions, rather than trying to encode every scheme
    here. Returns "" when there's only one page — no dead pagination UI
    on a feed that doesn't need it.
    """
    if total_pages <= 1:
        return ""
    parts = ['<nav class="becss-c-pagination" aria-label="Pagination">']
    if current_page > 1:
        parts.append(f'<a class="becss-c-pagination__link" href="{page_url_fn(current_page - 1)}">&laquo; Prev</a>')
    for n in range(1, total_pages + 1):
        cls = "becss-c-pagination__link becss-c-pagination__link--active" if n == current_page else "becss-c-pagination__link"
        parts.append(f'<a class="{cls}" href="{page_url_fn(n)}">{n}</a>')
    if current_page < total_pages:
        parts.append(f'<a class="becss-c-pagination__link" href="{page_url_fn(current_page + 1)}">Next &raquo;</a>')
    parts.append('</nav>')
    return "".join(parts)


def management_cms_shared_render_feed(items: list, empty_message: str = "Nothing here yet.") -> str:
    """
    items: list of {"title", "url", "meta" (optional), "excerpt" (optional)}
    dicts. Shared by the homepage recent-posts feed
    (lib_bejson_Management_feed.py), category archives, and tag
    archives (both lib_bejson_Management_static_builder.py) — one
    feed-card layout and CSS (.becss-c-feed* in app.py's shared_style) for
    all three instead of three separately-maintained bare-list markups.
    """
    if not items:
        return f'<p class="becss-c-feed__empty">{management_cms_shared_esc(empty_message)}</p>'
    cards = "".join(
        management_cms_shared_render_feed_card(
            it.get("title", ""), it.get("url", ""), it.get("meta", ""), it.get("excerpt", ""),
            it.get("thumbnail", ""), it.get("is_video", False)
        )
        for it in items
    )
    return f'<div class="becss-c-feed">{cards}</div>'

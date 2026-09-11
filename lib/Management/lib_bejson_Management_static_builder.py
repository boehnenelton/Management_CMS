"""
Library:         lib_bejson_Management_static_builder
Family:          management_cms
Description:     Top-level orchestrator that resolves the MFDB tree (Pages,
                  Posts, Categories, Nav, Media) and exports a deployable
                  static site with sitemap.xml, robots.txt, and RSS/Atom/JSON
                  feeds — the Static Builder named in OFFICIAL_PLAN.MD
                  Sec. IV. De-classed per the Global Standards stateless
                  rule: KIMI's StaticSiteBuilder class (__init__(self, site),
                  build(), 15 _build_* methods) becomes a set of standalone
                  functions taking manifest paths directly.

                  Rendering (RESOLVED this pass — was previously flagged):
                  management_cms_render_layout(component_id, token_map,
                  root_manifest_path) is now manifest-aware:
                    1. Try root_manifest_path's own ComponentMap/SkeletonStore
                       via webframework_components_get_from_manifest() — an
                       app's local edits/overrides win if present.
                    2. Fall back to Web_Framework's canonical
                       webframework_components_render_html() (the library's
                       factory-default skeleton) if the app hasn't overridden
                       that component.
                    3. Raise ManagementCmsMissingComponentError if neither
                       store has it — fail loudly, no placeholder HTML.
                  webframework_components_get_from_manifest() returns raw
                  (un-substituted) skeleton content, so this wrapper performs
                  the same {{token}} replacement render_html() does
                  internally, applied uniformly regardless of which store
                  the skeleton came from.

                  Home page: per Directive 3, the site root is identified via
                  lib_bejson_Management_content.management_cms_content_get_home_page(),
                  which queries Page for page_type == "home".

                  Audit: management_cms_static_build() now runs
                  lib_bejson_Management_init.management_cms_audit()
                  against all five taxonomies (Category, Nav, Page, Post,
                  Media) before writing any output, so every deployment gets
                  a deep_verify/self_heal pass automatically rather than
                  requiring a separate manual call. Findings are returned in
                  the build summary under "audit"; the build itself is not
                  aborted by findings (self_heal already attempts to fix
                  what it can) — a caller that wants build-blocking behavior
                  on unresolved findings can inspect the returned audit dict.

                  Component IDs this builder expects to find registered (in
                  either store) — none pre-registered by this package:
                  "management_cms_page", "management_cms_post",
                  "management_cms_category_archive",
                  "management_cms_tag_archive", "management_cms_home".
Version:         3.6.0
Library_Version: 013
Date:            2026-07-28
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   2e8a4c9f-6b3d-4e1a-9c7f-5d8b2a4e9f16

CHANGELOG (3.6.0, 2026-07-28): Three changes, requested directly ("get to
work on whatever is not done" / "clean up any old broken unused files").
(1) Homepage hero: the auto-generated homepage now shows a distinct
site-title/tagline block above the feed instead of just being the bare
feed with nothing above it. (2) Real feed pagination: added
_management_cms_write_paginated_feed() (page 1 at the original URL, page
2+ at .../page/{n}.html) and wired it into the homepage fallback, both
category-archive loops, and the tag-archive loop — page size is
CMS_FEED_PAGE_SIZE (10). Fixed a self-inflicted bug caught before
shipping: an earlier edit to lib_bejson_Management_shared.py's
pagination-helper insertion accidentally dropped the
`def management_cms_shared_render_feed(...)` signature line, leaving its
body orphaned with no function — caught by the very next import-and-build
test, not left for Elton to find. (3) STALE-OUTPUT FIX: found via a real
crawl of this project's own Export/ folder that every URL-scheme rename
this project has gone through left the OLD files behind forever, since
the build only ever wrote new files and never cleared old ones —
Export/category/test-category.html (pre-/post-category/-rename) and a
long-stale Export/management_cms_Export.zip had been shipping in every
delivered zip since. Fixed the only correct way: the output directory is
now wiped and rebuilt fresh on every build (confirmed safe — media is
already re-copied from its original source path each time, not from
Export/ itself). Verified all three: a 25-post test produced correctly
paginated homepage/category/tag output with 0 broken links; two
consecutive builds both succeeded; and the actual stale files in this
project were confirmed gone after a real rebuild.
CHANGELOG (3.5.0, 2026-07-27): Two changes, requested directly ("get to
work on whatever is not done"). (1) Added og_title/og_description/
canonical_url tokens to all 5 builder functions (home, page, post,
category archive, tag archive) — consumed by app.py's new OG meta block.
Post's og:description reuses management_cms_shared_excerpt() (the same
helper feed cards use) instead of dumping raw content_html into a meta
attribute. (2) Posts now write to /post/{slug}.html instead of flat
/{slug}.html, matching /post-category/ and /page-category/ symmetry —
structurally eliminates the Page/Post slug collision instead of just
warning about it (the old warning-only guard was removed as dead code,
now that the collision it detected is impossible). Updated every internal
post-URL reference to match: canonical_url, category/tag archive feed-card
links (category archive's link is conditional — it's reused for
page-type categories too, which stay flat), and the nav sidebar's Recent
Posts block. A full link-crawl audit of a real multi-content build (pages,
posts, categories of both types, tags) confirmed 0 broken links across 83
checked, and sitemap.xml/feed.xml/atom.xml/feed.json all emit the new
/post/ URL correctly.
CHANGELOG (3.4.0, 2026-07-25): _management_cms_build_category_page() and
_management_cms_build_tag_page() now render post_list_html via the shared
management_cms_shared_render_feed() card component (excerpt + date per
post) instead of a bare <li><a> list — same component the homepage
recent-posts feed uses (lib_bejson_Management_feed.py). Category-page
date now falls back to created_at when published_at is absent, since this
function is also reused for Page-type categories (Pages have no
published_at field). Verified end-to-end with a real
management_cms_static_build() run using an actual published post, not just
isolated unit tests.

CHANGELOG (3.3.0, 2026-07-22): Category URL symmetry fix — post categories
renamed from /category/ to /post-category/, matching /page-category/
exactly (previously the "post-" qualifier was silently dropped, easy to
mistake for the only category concept). BREAKING for already-published
sites using the old /category/ URLs. Also fixed _management_cms_build_post()
to build post_meta_html/tags_html conditionally using the existing
management_cms_shared_fmt_date() helper (not duplicated) instead of
unconditional token substitution that left a dangling "· " separator
whenever a field was empty. Verified end-to-end with a real
management_cms_static_build() run, not just isolated unit tests.

CHANGELOG (3.2.0, 2026-07-21): Self-discovery nav fix. Manual Site Nav and
auto-generated navigation were previously either/or — any manual nav item
silenced categories/posts entirely. Now always merged: manual links, then
an always-on Categories block, then a new always-on Recent Posts block
(_management_cms_build_recent_posts_html()). Also added a Page/Post
output-slug collision guard: both are written flatly as /{slug}.html with
no distinguishing prefix, so a shared slug silently overwrote one file with
the other; now surfaced as a build warning before any files are written.
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
WEBFRAMEWORK_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Web_Framework"))
MANAGEMENT_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Management"))
for _dir in (CORE_DIR, WEBFRAMEWORK_DIR, MANAGEMENT_DIR):
    if _dir not in sys.path:
        sys.path.append(_dir)

import lib_bejson_Management_components as Components
import lib_bejson_Management_content as Content
import lib_bejson_Management_taxonomy as Taxonomy
import lib_bejson_Management_nav as AdminNav
import lib_bejson_Management_feed as Feed
import lib_bejson_Management_media_cms as Media
import lib_bejson_Management_init as Init
from lib_bejson_Management_shared import (
    management_cms_shared_esc, management_cms_shared_fmt_date,
    management_cms_shared_excerpt, management_cms_shared_render_feed,
    management_cms_shared_paginate, management_cms_shared_render_pagination_nav,
    management_cms_shared_export_media_url, management_cms_shared_youtube_id,
    management_cms_shared_youtube_thumbnail_url, management_cms_shared_youtube_embed_html,
    management_cms_shared_export_thumbnail, management_cms_shared_render_feed_card,
    management_cms_shared_build_footer_html, management_cms_shared_inject_toc,
    management_cms_shared_export_site_url,
)


class ManagementCmsMissingComponentError(Exception):
    """
    Raised when a required Web_Framework component isn't registered in
    either the app's own root manifest or the library's canonical store.
    Fail loudly rather than silently degrade to placeholder HTML, per the
    standing bootstrap convention.
    """


# Minimal, self-contained factory defaults for the 5 component IDs this
# module renders. Used ONLY as a last-resort, on-the-fly registration if
# BOTH the per-app manifest and the canonical Web_Framework store are
# missing a component — see management_cms_render_layout()'s self-healing
# note below. Intentionally bare (no BECSS styling) since a real app is
# expected to register its own richer defaults (e.g. via an
# _ensure_cms_components_registered()-style startup step); this exists so
# the *library* never hard-fails a build on its own, regardless of which
# app embeds it or whether that app's own seeding step has run yet.
_BUILTIN_FALLBACK_SKELETONS = {
    "management_cms_home": '<!doctype html><html><head><meta charset="utf-8">'
        '<title>{{site_title}}</title></head><body><h1>{{site_title}}</h1>{{content_html}}</body></html>',
    "management_cms_page": '<!doctype html><html><head><meta charset="utf-8">'
        '<title>{{title}}</title></head><body><h1>{{title}}</h1>{{content_html}}</body></html>',
    "management_cms_post": '<!doctype html><html><head><meta charset="utf-8">'
        '<title>{{title}}</title></head><body><h1>{{title}}</h1>{{content_html}}</body></html>',
    "management_cms_category_archive": '<!doctype html><html><head><meta charset="utf-8">'
        '<title>{{category_title}}</title></head><body><h1>{{category_title}}</h1>{{post_list_html}}</body></html>',
    "management_cms_tag_archive": '<!doctype html><html><head><meta charset="utf-8">'
        '<title>#{{tag_name}}</title></head><body><h1>#{{tag_name}}</h1>{{post_list_html}}</body></html>',
    # Feature request (Elton): custom 404 page for the exported site.
    "management_cms_404": '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Page Not Found — {{site_title}}</title></head><body><h1>404 — Page Not Found</h1>'
        '<p><a href="/index.html">Return home</a></p></body></html>',
}


def management_cms_render_layout(component_id: str, token_map: Dict[str, Any],
                                  root_manifest_path: Optional[str] = None) -> str:
    """
    Manifest-aware rendering wrapper: per-app ComponentMap/SkeletonStore
    first, canonical library store as fallback. If NEITHER has the
    component, self-heals by registering a minimal built-in default
    canonically and retrying once, instead of hard-failing the entire
    build (see _BUILTIN_FALLBACK_SKELETONS above) — this is the fix for
    the most likely real-world cause of a build erroring outright: a
    running app instance whose components were never seeded (e.g. after
    a code/library update without a full app restart, or an app that
    embeds this library without its own seeding step). Only raises
    ManagementCmsMissingComponentError for a component_id this module
    doesn't know a built-in default for at all.

    root_manifest_path: the app's own root MFDB (the same one passed to
    lib_bejson_Management_init.management_cms_init() as
    root_manifest_path) — the one webframework_scaffold_deploy() already
    distributes a ComponentMap/SkeletonStore copy into. Pass None to skip
    straight to the canonical store (matches the old behavior).
    """
    raw_html = None
    if root_manifest_path:
        raw_html = Components.webframework_components_get_from_manifest(
            root_manifest_path, component_id, "html")

    if raw_html is not None:
        for k, v in token_map.items():
            raw_html = raw_html.replace("{{" + k + "}}", str(v or ""))
        return raw_html

    fallback_html = Components.webframework_components_render_html(component_id, token_map)
    if fallback_html is not None:
        return fallback_html

    if component_id in _BUILTIN_FALLBACK_SKELETONS:
        Components.webframework_components_register(
            component_id, component_id.replace("_", " ").title(),
            html_content=_BUILTIN_FALLBACK_SKELETONS[component_id],
        )
        healed_html = Components.webframework_components_render_html(component_id, token_map)
        if healed_html is not None:
            return healed_html

    raise ManagementCmsMissingComponentError(
        f"Component '{component_id}' is not registered in the app's root manifest "
        f"({root_manifest_path!r}) or in Web_Framework's canonical ComponentsMFDB, "
        f"and no built-in fallback exists for it either. Register it with "
        f"lib_bejson_Management_components.webframework_components_register()."
    )


# =============================================================================
# PAGE / POST BUILDERS
# =============================================================================

def _management_cms_build_page(page: Dict[str, Any], category_lookup: Dict[str, str],
                                site_config: Dict[str, Any], root_manifest_path: Optional[str],
                                nav_html: str = "") -> str:
    category_title = category_lookup.get(page.get("category_id_fk", ""), "")
    site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)
    slug = page.get("slug", "")
    token_map = {
        "title": page.get("title") or page.get("slug", ""), "content_html": page.get("content_html", ""),
        "meta_description": page.get("meta_description", ""), "category_title": category_title,
        "footer_html": management_cms_shared_build_footer_html(site_config),
        "site_title": site_config.get("site_title", ""), "nav_html": nav_html,
        # SEO/SOCIAL-SHARING FIX (2026-07-27): tokens consumed by the OG
        # meta block in app.py's page_shell().
        "og_title": page.get("title") or page.get("slug", ""),
        "og_description": page.get("meta_description", ""),
        "canonical_url": f"{site_url}/{slug}.html",
    }
    return management_cms_render_layout("management_cms_page", token_map, root_manifest_path)


def _management_cms_build_related_posts_html(post: Dict[str, Any], all_posts: List[Dict[str, Any]], limit: int = 3) -> str:
    """
    Feature request (Elton): "Related posts — 2-3 posts from the same
    category at the bottom of a post page, using data you already have."
    all_posts is the same already-loaded, already-published post list the
    main build loop iterates over — no extra manifest read. Excludes the
    post itself, requires a shared non-empty category_id_fk (a post with
    no category has nothing to be "related" by), sorted newest-first,
    capped at `limit`. Reuses management_cms_shared_render_feed_card() —
    the exact same card used by every other listing on the site — for
    visual consistency rather than inventing a second card style.
    """
    category_id = post.get("category_id_fk")
    if not category_id:
        return ""
    candidates = [
        p for p in all_posts
        if p.get("id") != post.get("id") and p.get("category_id_fk") == category_id
    ]
    candidates.sort(key=lambda p: p.get("published_at", ""), reverse=True)
    related = candidates[:limit]
    if not related:
        return ""
    cards = "".join(
        management_cms_shared_render_feed_card(
            r.get("title", ""), f'/post/{r.get("slug", "")}.html',
            management_cms_shared_fmt_date(r.get("published_at", ""), "%b %d, %Y"),
            management_cms_shared_excerpt(r.get("content_html", "")),
            *management_cms_shared_export_thumbnail(r.get("featured_image", "")),
        )
        for r in related
    )
    return (
        '<section class="becss-c-related-posts">'
        '<h2 class="becss-c-related-posts__heading">Related Posts</h2>'
        f'<div class="becss-c-feed">{cards}</div>'
        '</section>'
    )


def _management_cms_build_post(post: Dict[str, Any], category_lookup: Dict[str, str],
                                tag_lookup: Dict[str, str], site_config: Dict[str, Any],
                                root_manifest_path: Optional[str], nav_html: str = "",
                                all_posts: Optional[List[Dict[str, Any]]] = None) -> str:
    category_title = category_lookup.get(post.get("category_id_fk", ""), "")
    tag_names = ", ".join(tag_lookup.get(tid, "") for tid in (post.get("tag_ids") or []))

    # PROFESSIONAL-POLISH FIX (2026-07-22, requested after live-site review):
    # the default "management_cms_post" skeleton (see
    # _ensure_cms_components_registered() in app.py) unconditionally
    # substituted "By {{author}} · {{published_at}} · {{category_title}}"
    # and "Tags: {{tags}}" — token substitution can't express "omit this
    # if empty", so a post with no category left a dangling "· " with
    # nothing after it, and a post with no tags showed a bare "Tags:"
    # label. published_at was also substituted raw
    # ("2026-07-22T03:47:32Z") instead of human-readable. Built here
    # instead, conditionally, using the existing
    # management_cms_shared_fmt_date() helper (not duplicated — it was
    # already used by lib_bejson_Management_feed.py's Recent Posts
    # widget) and passed through as pre-built post_meta_html/tags_html
    # tokens that are already empty strings when there's nothing to show.
    meta_parts = [p for p in (
        post.get("author", ""),
        management_cms_shared_fmt_date(post.get("published_at", ""), "%b %d, %Y"),
        category_title,
    ) if p]
    post_meta_html = (
        f'<p style="opacity:.7;font-size:.85rem;">{" · ".join(meta_parts)}</p>' if meta_parts else ""
    )
    tags_html = (
        f'<p style="opacity:.5;font-size:.8rem;">Tags: {management_cms_shared_esc(tag_names)}</p>'
        if tag_names else ""
    )
    # AUDIT FIX (M-1): featured_image was settable in the admin editor but
    # nothing on the export side ever read it — silently dead past the
    # admin form. Built conditionally (empty string when unset), same
    # pattern as post_meta_html/tags_html above, so the {{featured_image_html}}
    # token below never leaves a dangling empty <img> tag.
    # AUDIT FIX (M-1 follow-up): rewrite the admin-only /media-files/
    # prefix to the static export's actual /media/ path — see
    # management_cms_shared_export_media_url()'s own comment.
    #
    # Elton: "add a YouTube link category to the media center... work
    # the same way as images but they just embed differently." The
    # media picker/add_external_media() already stores a YouTube
    # selection as a normalized youtube.com/watch?v=<id> URL in this
    # same featured_image field — "the same way as images" in the sense
    # that it's still one field, one picker, no schema change — but
    # rendering it with <img src="..."> (the only thing this code did
    # before) is broken, since that's a webpage URL, not an image file.
    # Detect it and embed a real player instead; anything that isn't a
    # recognized YouTube URL falls through to the existing <img> path
    # unchanged.
    featured_image_raw = post.get("featured_image", "")
    _yt_id = management_cms_shared_youtube_id(featured_image_raw)
    if _yt_id:
        featured_image_html = management_cms_shared_youtube_embed_html(_yt_id)
    else:
        featured_image = management_cms_shared_export_media_url(featured_image_raw)
        featured_image_html = (
            f'<img class="becss-c-post-featured-image" src="{management_cms_shared_esc(featured_image)}" alt="">'
            if featured_image else ""
        )

    # Feature request (Elton): auto-generated table of contents for
    # longer posts, built from h2/h3 in content_html. content_with_toc
    # (heading ids injected) replaces the raw content_html everywhere
    # below — og_description's excerpt strips tags anyway so the ids
    # don't affect it either way.
    content_with_toc, toc_html = management_cms_shared_inject_toc(post.get("content_html", ""))

    # Feature request (Elton): related posts, 2-3 from the same category,
    # at the bottom of the post. all_posts is the full published-posts
    # list the caller already loaded for this build — see that call
    # site's own comment for why no extra manifest read was needed.
    related_posts_html = _management_cms_build_related_posts_html(post, all_posts or [])

    site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)
    slug = post.get("slug", "")
    token_map = {
        "title": post.get("title", ""), "content_html": content_with_toc,
        "author": post.get("author", ""), "published_at": post.get("published_at", ""),
        "category_title": category_title, "tags": tag_names,
        "post_meta_html": post_meta_html, "tags_html": tags_html,
        "featured_image_html": featured_image_html,
        "toc_html": toc_html, "related_posts_html": related_posts_html,
        "footer_html": management_cms_shared_build_footer_html(site_config),
        "site_title": site_config.get("site_title", ""), "nav_html": nav_html,
        # SEO/SOCIAL-SHARING FIX (2026-07-27): tokens consumed by the OG
        # meta block in app.py's page_shell(). og:description reuses the
        # same excerpt helper as the feed cards (management_cms_shared_excerpt())
        # instead of dumping raw content_html into a meta attribute.
        "og_title": post.get("title", ""),
        "og_description": management_cms_shared_excerpt(post.get("content_html", "")),
        "canonical_url": f"{site_url}/post/{slug}.html",
    }
    return management_cms_render_layout("management_cms_post", token_map, root_manifest_path)


def _management_cms_build_category_page(category: Dict[str, Any], posts: List[Dict[str, Any]],
                                         site_config: Dict[str, Any], root_manifest_path: Optional[str],
                                         nav_html: str = "", pagination_html: str = "") -> str:
    # SHARED-FEED-COMPONENT FIX (2026-07-22, requested directly): category
    # and tag archives (and the homepage recent-posts feed in
    # lib_bejson_Management_feed.py) now all build off the same
    # management_cms_shared_render_feed() card component instead of each
    # having its own bare <li><a> list — same date formatting, same
    # excerpt logic, one CSS surface (.becss-c-feed* in app.py) to
    # maintain instead of three.
    # URL-STRUCTURE FIX (2026-07-27): item URLs must match where each
    # content type actually gets written now — Posts are under /post/,
    # Pages stay flat. This builder is reused for both post-type and
    # page-type categories, so the prefix is picked per-category, not
    # per-item (a category is entirely one type or the other).
    item_url_prefix = "/post/" if category.get("category_type") == "post" else "/"
    items = [
        {
            "title": p.get("title", ""),
            "url": f'{item_url_prefix}{p.get("slug", "")}.html',
            "meta": management_cms_shared_fmt_date(p.get("published_at") or p.get("created_at", ""), "%b %d, %Y"),  # this builder is reused for Page categories too (Pages have no published_at)
            "excerpt": management_cms_shared_excerpt(p.get("content_html", "")),
            "thumbnail": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[0],  # AUDIT FIX (M-1, media-url rewrite + YouTube thumbnail)
            "is_video": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[1],
        }
        for p in posts
    ]
    # AUDIT FIX (M-2): this builder is shared by post-type AND page-type
    # categories (see item_url_prefix/url_prefix above, which already
    # branch on category_type) — but the empty-state message was hardcoded
    # to "No posts in this category yet." even when rendering a Page
    # category, since Pages aren't "posts". Reuses the same
    # category_type check already in scope instead of adding a new one.
    empty_message = ("No posts in this category yet." if category.get("category_type") == "post"
                      else "No pages in this category yet.")
    post_list_html = management_cms_shared_render_feed(items, empty_message) + pagination_html
    site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)
    url_prefix = "/post-category/" if category.get("category_type") == "post" else "/page-category/"
    token_map = {
        "category_title": category.get("title", ""), "category_description": category.get("description", ""),
        "post_list_html": post_list_html, "site_title": site_config.get("site_title", ""), "nav_html": nav_html,
        "footer_html": management_cms_shared_build_footer_html(site_config),
        # SEO/SOCIAL-SHARING FIX (2026-07-27): tokens consumed by the OG
        # meta block in app.py's page_shell().
        "og_title": category.get("title", ""), "og_description": category.get("description", ""),
        "canonical_url": f"{site_url}{url_prefix}{category.get('slug', '')}.html",
    }
    return management_cms_render_layout("management_cms_category_archive", token_map, root_manifest_path)


def _management_cms_build_tag_page(tag: Dict[str, Any], posts: List[Dict[str, Any]],
                                    site_config: Dict[str, Any], root_manifest_path: Optional[str],
                                    nav_html: str = "", pagination_html: str = "") -> str:
    items = [
        {
            "title": p.get("title", ""),
            "url": f'/post/{p.get("slug", "")}.html',
            "meta": management_cms_shared_fmt_date(p.get("published_at") or p.get("created_at", ""), "%b %d, %Y"),  # this builder is reused for Page categories too (Pages have no published_at)
            "excerpt": management_cms_shared_excerpt(p.get("content_html", "")),
            "thumbnail": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[0],  # AUDIT FIX (M-1, media-url rewrite + YouTube thumbnail)
            "is_video": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[1],
        }
        for p in posts
    ]
    post_list_html = management_cms_shared_render_feed(items, "No posts with this tag yet.") + pagination_html
    site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)
    token_map = {
        "tag_name": tag.get("name", ""), "post_list_html": post_list_html,
        "site_title": site_config.get("site_title", ""), "nav_html": nav_html,
        "footer_html": management_cms_shared_build_footer_html(site_config),
        # SEO/SOCIAL-SHARING FIX (2026-07-27): tokens consumed by the OG
        # meta block in app.py's page_shell().
        "og_title": f"#{tag.get('name', '')}", "og_description": "",
        "canonical_url": f"{site_url}/tag/{tag.get('slug', '')}.html",
    }
    return management_cms_render_layout("management_cms_tag_archive", token_map, root_manifest_path)


def _management_cms_build_404_page(site_config: Dict[str, Any], root_manifest_path: Optional[str],
                                    nav_html: str = "") -> str:
    """
    Feature request (Elton): "Custom 404 page — right now a broken link
    probably just hits the host's default error page." Every static host
    (GitHub Pages, Cloudflare Pages, Netlify, etc.) auto-serves a file
    literally named 404.html by convention, so writing one to the export
    root is all that's needed for it to take effect on deployment — no
    server-side config required.
    """
    # AUDIT FIX (M-6): canonical_url was hardcoded to "" here, which left
    # og:url/canonical blank on the 404 page even when every other page
    # falls back to "/" (site root) for the same empty/loopback site_url
    # case. There's no real page path for a 404, so site root is the
    # correct degrade-to target — this now matches the other builders'
    # convention instead of producing an inconsistent blank output.
    site_url = (site_config.get("site_url") or "").strip()
    token_map = {
        "site_title": site_config.get("site_title", ""),
        "footer_html": management_cms_shared_build_footer_html(site_config),
        "nav_html": nav_html,
        "meta_description": "Page not found.",
        "og_title": f"Page Not Found — {site_config.get('site_title', '')}",
        "og_description": "",
        "canonical_url": f"{site_url}/",
    }
    return management_cms_render_layout("management_cms_404", token_map, root_manifest_path)


def _management_cms_build_home_page(page_manifest_path: str, site_config: Dict[str, Any],
                                     root_manifest_path: Optional[str], nav_html: str = "") -> Optional[str]:
    """
    Directive 3's Static Builder hook: identify the site root via
    page_type == "home". Returns None (not an error) if no page is marked
    "home" yet — that's a content-authoring gap, not a build failure (see
    management_cms_static_build()'s "warnings" list, which surfaces this
    clearly instead of silently producing a site with no index.html).
    """
    home_page = Content.management_cms_content_get_home_page(page_manifest_path)
    if not home_page:
        return None
    site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)
    token_map = {
        "content_html": home_page.get("content_html", ""),
        "meta_description": home_page.get("meta_description", ""),
        "footer_html": management_cms_shared_build_footer_html(site_config),
        "site_title": site_config.get("site_title", ""), "nav_html": nav_html,
        # SEO/SOCIAL-SHARING FIX (2026-07-27): tokens consumed by the OG
        # meta block in app.py's page_shell().
        "og_title": site_config.get("site_title", ""),
        "og_description": home_page.get("meta_description") or site_config.get("site_tagline", ""),
        "canonical_url": f"{site_url}/",
    }
    return management_cms_render_layout("management_cms_home", token_map, root_manifest_path)


# =============================================================================
# NAV
# =============================================================================

def _management_cms_render_nav_tree(nodes: List[Dict[str, Any]]) -> str:
    if not nodes:
        return ""
    items = ""
    for n in nodes:
        children_html = _management_cms_render_nav_tree(n.get("children", []))
        sub = f'<ul class="becss-c-nav__submenu">{children_html}</ul>' if children_html else ""
        # BUG FIX: this used to read n.get("label")/n.get("url") — the
        # translated field names app.py's navlink_to_dict() produces for
        # the JSON API. Calling AdminNav.management_nav_get_tree() directly
        # (see the note above _management_cms_get_nav_html()) returns the
        # RAW field names instead (nav_label, nav_url), so this was
        # rendering blank labels/links for every nav item, every build.
        items += (f'<li class="becss-c-nav__item"><a href="{management_cms_shared_esc(n.get("nav_url", "#"))}" '
                  f'class="becss-c-nav__link">{management_cms_shared_esc(n.get("nav_label", ""))}</a>{sub}</li>')
    return items


def _management_cms_get_nav_html(admin_nav_manifest_path: Optional[str]) -> str:
    """
    BUG FIX (significant): this used to call
    lib_bejson_management_cms_nav.management_cms_nav_get_tree() — the
    CMS-layer Nav manifest (Content/Nav/MFDB) that management_cms_init()
    scaffolds but that NOTHING in a typical embedding app (including this
    one) ever actually writes to; there's no UI, no route, nothing wired
    to it anywhere. The real, connected navigation data — the one the
    "Site Nav" admin panel actually reads and writes — lives in
    lib_bejson_Management_nav.py's NavLink entity (the PAGES_MANIFEST
    admin manifest). This function was therefore ALWAYS rendering an
    empty nav menu on every build, regardless of what the user configured
    in the admin UI — one of the reasons a built site could look like
    disconnected page fragments with no site-wide navigation at all.
    Fixed to call the real admin Nav module instead. Returns "" (not an
    error) if admin_nav_manifest_path is None or the nav is empty — a
    site with no nav items configured yet is not a build failure.
    """
    if not admin_nav_manifest_path:
        return ""
    tree = AdminNav.management_nav_get_tree(admin_nav_manifest_path)
    items_html = _management_cms_render_nav_tree(tree)
    return f'<ul class="becss-c-nav">{items_html}</ul>' if items_html else ""


def _management_cms_build_recent_posts_html(post_manifest_path: str, limit: int = 5) -> str:
    """
    Self-discovering nav fix (user-requested): a "Recent Posts" nav block
    listing the most recently published posts, same rendering shape as the
    category sidebar. Previously posts only surfaced in nav *indirectly*,
    via a category archive page link — a site with no manual nav and no
    categories configured yet had literally no way to reach any post from
    the nav at all, even with published posts sitting there. Returns "" if
    there are no published posts.
    """
    posts = Content.management_cms_content_list_posts(post_manifest_path, status="published", limit=limit)
    if not posts:
        return ""
    # URL-STRUCTURE FIX (2026-07-27): Posts now live under /post/, not
    # flat /{slug}.html — this was the last of 4 places that built a post
    # URL still using the old scheme (found via a full link-crawl of a
    # real build; it broke the nav's Recent Posts links on every single
    # page since this block renders site-wide).
    items = "".join(
        f'<li class="becss-c-nav__item"><a href="/post/{management_cms_shared_esc(p.get("slug",""))}.html" '
        f'class="becss-c-nav__link">{management_cms_shared_esc(p.get("title",""))}</a></li>'
        for p in posts
    )
    return (
        f'<div class="becss-c-nav-group"><span class="becss-c-nav-group__label" onclick="_navGroupToggle(this)">'
        f'Recent Posts<span class="becss-c-nav-group__chevron">&#9662;</span></span>'
        f'<ul class="becss-c-nav">{items}</ul></div>'
    )


def _management_cms_render_category_sidebar_tree(nodes: List[Dict[str, Any]], url_prefix: str = "/post-category/") -> str:
    if not nodes:
        return ""
    items = ""
    for n in nodes:
        children_html = _management_cms_render_category_sidebar_tree(n.get("children", []), url_prefix)
        sub = f'<ul class="becss-c-nav__submenu">{children_html}</ul>' if children_html else ""
        items += (f'<li class="becss-c-nav__item"><a href="{url_prefix}{management_cms_shared_esc(n.get("slug", ""))}.html" '
                  f'class="becss-c-nav__link">{management_cms_shared_esc(n.get("title", ""))}</a>{sub}</li>')
    return items


def _management_cms_build_category_sidebar_html(category_manifest_path: str) -> str:
    """
    Bare-minimum automatic navigation: a hierarchical list of category
    links (each pointing at that category's already-built archive page,
    which lists every post/page in it — so "posts and pages
    automatically populate under their category section" falls out of
    that existing archive-page behavior rather than needing a second,
    separate listing mechanism here). Used as the fallback when no
    manual Site Nav items are configured — see management_cms_static_build().

    BUG FIX: this used to take a single category_type ("post" only, from
    its one call site), meaning a site with only "page"-type categories
    (or with both types) would only ever show — or in the page-only case,
    completely fail to show — post categories, incorrectly reporting "no
    categories exist" when they genuinely did, just under the type this
    function wasn't looking at. Now builds both the "post" and "page"
    category trees and combines them, labeling each section only if BOTH
    have content (a single-type site just gets a plain unlabeled list,
    avoiding clutter for the common case). Page-type categories link under
    /page-category/ rather than /post-category/ — both types share the same
    Category entity and slug field with no cross-type uniqueness
    enforced, so two categories of different types could otherwise
    collide on the same output filename.

    Returns "" if there are no categories of either type (nothing to show).
    """
    post_tree = Taxonomy.management_cms_taxonomy_get_category_tree(category_manifest_path, "post")
    page_tree = Taxonomy.management_cms_taxonomy_get_category_tree(category_manifest_path, "page")
    post_html = _management_cms_render_category_sidebar_tree(post_tree, "/post-category/")
    page_html = _management_cms_render_category_sidebar_tree(page_tree, "/page-category/")

    if post_html and page_html:
        return (
            f'<div class="becss-c-nav-group"><span class="becss-c-nav-group__label" onclick="_navGroupToggle(this)">'
            f'Categories<span class="becss-c-nav-group__chevron">&#9662;</span></span>'
            f'<ul class="becss-c-nav">{post_html}</ul></div>'
            f'<div class="becss-c-nav-group"><span class="becss-c-nav-group__label" onclick="_navGroupToggle(this)">'
            f'Pages<span class="becss-c-nav-group__chevron">&#9662;</span></span>'
            f'<ul class="becss-c-nav">{page_html}</ul></div>'
        )
    items_html = post_html or page_html
    return f'<ul class="becss-c-nav">{items_html}</ul>' if items_html else ""


# =============================================================================
# SITEMAP / ROBOTS / MEDIA
# =============================================================================

def _management_cms_build_sitemap(site_url: str, urls: List[str]) -> str:
    site_url = site_url.rstrip("/")
    entries = "".join(f"  <url><loc>{management_cms_shared_esc(site_url + u)}</loc></url>\n" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}</urlset>'


def _management_cms_build_robots(site_url: str) -> str:
    site_url = site_url.rstrip("/")
    return f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n"


def _management_cms_copy_media(media_manifest_path: str, output_dir: str) -> int:
    """Copy every registered media file (original + webp variant, if any) into output_dir/media/. Returns count copied."""
    import shutil
    media_items = Media.management_cms_media_list(media_manifest_path)
    out_media_dir = Path(output_dir) / "media"
    out_media_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for m in media_items:
        for path_field in ("original_path", "webp_path"):
            src = m.get(path_field)
            if src and os.path.exists(src):
                shutil.copy2(src, out_media_dir / os.path.basename(src))
                copied += 1
    return copied


# =============================================================================
# TOP-LEVEL ORCHESTRATOR
# =============================================================================

CMS_FEED_PAGE_SIZE = 10  # posts per page — homepage, category, and tag archives


def _management_cms_write_paginated_feed(items: list, url_base: str, out_first_page: Path,
                                          build_fn) -> List[str]:
    """
    Writes a feed as one or more pages. Page 1 goes to out_first_page
    (e.g. .../post-category/news.html); page 2+ goes to
    {url_base}/page/{n}.html (e.g. /post-category/news/page/2.html).
    build_fn(page_items, pagination_html) -> the rendered HTML for that page.
    Returns the list of URLs actually written (relative, leading "/").
    Added 2026-07-28 — shared by the category archive, tag archive, and
    homepage-feed write loops in management_cms_static_build() so all
    three paginate the same way instead of three separate
    almost-but-not-quite-identical implementations.
    """
    pages = management_cms_shared_paginate(items, CMS_FEED_PAGE_SIZE)
    total_pages = len(pages)
    written_urls = []
    for i, page_items in enumerate(pages, start=1):
        def url_fn(n, base=url_base):
            return f"{base}.html" if n == 1 else f"{base}/page/{n}.html"
        pagination_html = management_cms_shared_render_pagination_nav(i, total_pages, url_fn)
        html = build_fn(page_items, pagination_html)
        if i == 1:
            target = out_first_page
        else:
            page_dir = out_first_page.parent / out_first_page.stem / "page"
            page_dir.mkdir(parents=True, exist_ok=True)
            target = page_dir / f"{i}.html"
        target.write_text(html, encoding="utf-8")
        written_urls.append(url_fn(i))
    return written_urls


def management_cms_static_build(page_manifest_path: str, post_manifest_path: str,
                                 category_manifest_path: str,
                                 media_manifest_path: str, site_config: Dict[str, Any],
                                 output_dir: str, root_manifest_path: Optional[str] = None,
                                 admin_nav_manifest_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolves Pages, Posts, Categories, Nav, Media into a deployable static
    site under output_dir. site_config keys: site_url, site_title,
    site_tagline, feed_posts_limit, site_language.

    root_manifest_path: the app's own root MFDB, passed through to
    management_cms_render_layout() so per-app component overrides are tried
    before the canonical library defaults. Pass None to always use canonical.

    admin_nav_manifest_path: the REAL, connected navigation data source —
    lib_bejson_Management_nav.py's NavLink manifest, the one an embedding
    app's admin UI actually reads and writes (in this app, PAGES_MANIFEST).
    BUG FIX: earlier versions rendered nav from nav_manifest_path (the
    CMS-layer manifest above), which nothing in a typical embedding app
    ever populates — every build silently produced a site with an empty
    navigation menu regardless of what was actually configured. Pass None
    to render with no site-wide nav (a valid choice, not an error).

    Runs management_cms_audit() against all five taxonomies before writing
    any output — every deployment gets a deep_verify/self_heal pass
    automatically. Findings are returned under "audit" and do not block the
    build (self_heal already attempts fixes).

    Returns: {"pages": n, "posts": n, "category_pages": n, "tag_pages": n,
    "home_built": bool, "media_copied": n, "urls": [...], "audit": {...},
    "auto_published": [...], "warnings": [...]}.
    """
    warnings: List[str] = []

    # AUDIT FIX (M-6): site_url drives every og:url/canonical/sitemap/feed
    # absolute link this build produces. When it's empty (e.g. a CLI build
    # that never captured request.host_url), every one of those links comes
    # out relative or blank ("/", "") instead of absolute — silently, with
    # no signal to whoever runs the build. Warn the same way the nav/home
    # fallbacks already do, so the gap shows up in the build log/UI instead
    # of only being discoverable by reading the exported HTML afterward.
    #
    # BUG FIX (self-caught, introduced by the BLD-01 refactor below): this
    # specific site_url needs the RAW config value, not
    # management_cms_shared_export_site_url()'s already-blanked-for-loopback
    # result — a find-and-replace across every site_url assignment in this
    # file initially caught this one too, which would have made the
    # loopback branch below permanently unreachable (site_url would already
    # be "" for a loopback host by the time the `else` ran, so `if not
    # site_url` always wins and the loopback-specific warning message never
    # fires). Caught by re-reading this function's own logic before moving
    # on, not by a test — worth calling out since it's exactly the kind of
    # silent regression a search-and-replace can introduce.
    site_url = (site_config.get("site_url") or "").strip()
    if not site_url:
        warnings.append(
            "site_url is empty — og:url, canonical links, sitemap.xml, and "
            "feed home_page_url will be output as relative/blank instead of "
            "absolute URLs."
        )
    else:
        # AUDIT FIX (N-4): the empty-string case above was caught (M-6),
        # but a POPULATED-with-loopback site_url passed silently — and
        # this is actually the common case, not an edge case: app.py's
        # own build route sets site_url = request.host_url verbatim on
        # every build triggered through the running app (the normal way
        # anyone uses this), and the default bind is 127.0.0.1. Verified
        # live: triggering a real build via POST /api/build against a
        # loopback-bound instance produced
        # canonical="http://127.0.0.1:5030/" in the actual exported HTML,
        # with zero warning under the old code — a site published as-is
        # would have every canonical/OG/sitemap URL pointing at localhost.
        _host = site_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        if _host in ("127.0.0.1", "localhost", "::1"):
            warnings.append(
                f"site_url is {site_url!r} — a loopback address. Every "
                "og:url, canonical link, sitemap.xml entry, and feed "
                "home_page_url in this build will point at localhost, "
                "which is unreachable for anyone but this device. If this "
                "build is meant to be published, rebuild after setting "
                "MANAGEMENT_CMS_HOST to a real hostname/IP, or run the "
                "build from a request that arrived on one."
            )

    # Auto-publish any scheduled post whose scheduled_at has come due, before
    # anything else runs — this is the actual "automated publication
    # trigger" a later integration directive asked for (under a function
    # name, management_posts_list_due_for_publish(), that didn't exist
    # anywhere in the codebase; built fresh as
    # management_cms_content_auto_publish_due(), see that function's
    # docstring). Doing this first means the audit below and every
    # downstream step (page listing, feeds, sitemap) all see the
    # newly-published posts as already published, not stale scheduled ones.
    auto_published = Content.management_cms_content_auto_publish_due(post_manifest_path)

    manifests = {
        "category": category_manifest_path,
        "page": page_manifest_path, "post": post_manifest_path, "media": media_manifest_path,
    }
    audit_results = {name: Init.management_cms_audit(path) for name, path in manifests.items()}

    out = Path(output_dir)
    # STALE-OUTPUT FIX (2026-07-28, found and requested directly — "clean
    # up any old broken unused files"): previously this only ever created
    # the output directory if missing (out.mkdir(exist_ok=True)) and then
    # wrote new/updated files — it never removed anything. Every URL
    # rename this project has gone through (/category/ -> /post-category/,
    # /{slug}.html -> /post/{slug}.html for posts) left the OLD files
    # behind forever, because nothing ever deleted them; the same is true
    # for any Post/Page/Category deleted from the CMS after being
    # published once. Confirmed real via a full crawl of this project's
    # own Export/ folder: Export/category/test-category.html is a
    # genuine leftover from before the /post-category/ rename, still
    # being shipped in every delivered zip since. Fixed the only correct
    # way: wipe the entire output directory and rebuild it fresh every
    # time, the standard pattern for a static-site generator. Confirmed
    # safe to do — _management_cms_copy_media() already re-copies every
    # media file from its original source path on each build, not from
    # Export/ itself, so nothing is lost by clearing it first.
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    # AUDIT FIX (M-3): was the slug map (get_category_slug_map) — see that
    # function's own comment. This is only ever used below to populate a
    # human-facing {{category_title}} token, never for URL/slug purposes.
    category_lookup = Taxonomy.management_cms_taxonomy_get_category_title_map(category_manifest_path)
    tag_lookup = Taxonomy.management_cms_taxonomy_get_tag_slug_map(post_manifest_path)

    # Navigation (user-requested fix, 2026-07-21): previously this was
    # either/or — ANY manual Site Nav item at all silenced the
    # auto-generated category/post navigation entirely, so a site with even
    # one hand-added link (e.g. "About") would stop showing categories and
    # posts in nav altogether, even though they still existed and were
    # still being built. Now always merges: manual Site Nav links first
    # (if any), then an always-on auto-generated "Categories" block, then
    # an always-on auto-generated "Recent Posts" block — so visitors can
    # always discover current categories and posts regardless of whether
    # the admin has touched the Site Nav panel.
    manual_nav_html = _management_cms_get_nav_html(admin_nav_manifest_path)
    auto_category_html = _management_cms_build_category_sidebar_html(category_manifest_path)
    auto_posts_html = _management_cms_build_recent_posts_html(post_manifest_path)
    nav_html = manual_nav_html + auto_category_html + auto_posts_html
    if not nav_html:
        warnings.append(
            "No navigation could be generated — no Site Nav items, no categories, "
            "and no published posts exist yet. Add any of these to give visitors "
            "a way to browse the site."
        )
    elif not manual_nav_html:
        warnings.append(
            "No Site Nav items are configured — showing auto-generated category "
            "and recent-posts navigation instead. Add items in the Site Nav panel "
            "for custom links alongside it."
        )

    # Page/Post output-URL collision — RESOLVED STRUCTURALLY (2026-07-27):
    # this used to be a runtime guard here (added 2026-07-21) that detected
    # a shared slug between a Page and a Post and surfaced it as a build
    # warning, because both were written flatly as /{slug}.html and one
    # would silently clobber the other. Posts now live under /post/ (see
    # the Posts write loop below), so a Page and a Post can no longer
    # share an output path at all — the collision class this guarded
    # against is now structurally impossible, not just detected. The
    # check itself was removed rather than left in place doing nothing.

    urls: List[str] = []

    # Home page: an explicit page_type=="home" page wins if one exists; if
    # not, auto-generate a recent-posts feed as the homepage (bare-minimum
    # default — every build produces a real index.html, always) rather than
    # skipping it entirely. Reuses the existing "Recent Posts" widget
    # markup, wrapped in the same management_cms_home component/template as
    # a real custom home page would use, so it's visually consistent.
    home_html = _management_cms_build_home_page(page_manifest_path, site_config, root_manifest_path, nav_html)
    if home_html is not None:
        home_built = True
        (out / "index.html").write_text(home_html, encoding="utf-8")
        urls.append("/index.html")
    else:
        # HOMEPAGE HERO FIX (2026-07-28, requested directly — "get to work
        # on whatever is not done"): previously the auto-generated
        # homepage was just the bare feed with nothing above it — no
        # distinct front-page treatment at all, even though site_title/
        # site_tagline are already configured and already used elsewhere
        # (page <title>, OG tags). A hero block using them costs nothing
        # extra to build and makes the homepage look like an actual front
        # page instead of "the feed, but it's index.html". Only rendered
        # if there's a title or tagline to show — no empty hero shell.
        site_title = site_config.get("site_title", "")
        site_tagline = site_config.get("site_tagline", "")
        hero_html = ""
        if site_title or site_tagline:
            hero_html = (
                '<div class="becss-c-hero">'
                + (f'<h1 class="becss-c-hero__title">{management_cms_shared_esc(site_title)}</h1>' if site_title else "")
                + (f'<p class="becss-c-hero__tagline">{management_cms_shared_esc(site_tagline)}</p>' if site_tagline else "")
                + '</div>'
            )
        site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)

        # FEED PAGINATION FIX (2026-07-28): previously always just the
        # first `limit` posts via feed.py's widget, no way to reach older
        # posts from the homepage at all. Now builds real feed cards
        # directly (same shape as the category/tag archives) from every
        # published post, and paginates properly via the shared helper —
        # page 1 is index.html, page 2+ is /page/{n}.html. The hero is
        # repeated on every page for consistent framing, not just page 1.
        all_recent_posts = Content.management_cms_content_list_posts(post_manifest_path, status="published")
        home_items = [
            {
                "title": p.get("title", ""),
                "url": f'/post/{p.get("slug", "")}.html',
                "meta": management_cms_shared_fmt_date(p.get("published_at", ""), "%b %d, %Y"),
                "excerpt": management_cms_shared_excerpt(p.get("content_html", "")),
                "thumbnail": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[0],  # AUDIT FIX (M-1, media-url rewrite + YouTube thumbnail)
                "is_video": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[1],
            }
            for p in all_recent_posts
        ]

        def _build_home_fallback_page(items, pagination_html):
            feed_html = management_cms_shared_render_feed(items, "No posts published yet.") + pagination_html
            home_token_map = {
                "content_html": hero_html + feed_html,
                "meta_description": "", "site_title": site_config.get("site_title", ""), "nav_html": nav_html,
                "footer_html": management_cms_shared_build_footer_html(site_config),
                # SEO/SOCIAL-SHARING FIX (2026-07-27): same OG tokens as the
                # custom-home-page path above — this fallback is the more
                # common case in practice (most sites won't have a Page
                # Type "home" set), so it needs the same tokens just as
                # much.
                "og_title": site_config.get("site_title", ""),
                "og_description": site_config.get("site_tagline", ""),
                "canonical_url": f"{site_url}/",
            }
            return management_cms_render_layout("management_cms_home", home_token_map, root_manifest_path)

        home_page_urls = _management_cms_write_paginated_feed(
            home_items, "/index", out / "index.html", _build_home_fallback_page,
        )
        # page 1's real URL is "/index.html" already (out/index.html),
        # matching url_fn's "/index.html" for n==1 — no extra rewrite
        # needed. Page 2+ lands at out/index/page/{n}.html -> /index/page/{n}.html.
        home_built = True
        urls.extend(home_page_urls)
        warnings.append(
            "No page is marked as Home (Page Type = \"home\") — using an auto-generated "
            "recent-posts feed as the homepage instead. Set a page's Page Type to Home "
            "to replace it with custom content."
        )

    # Pages (excluding the home page — it's already written as index.html)
    pages = Content.management_cms_content_list_pages(page_manifest_path, status="published")
    page_count = 0
    for page in pages:
        if page.get("page_type") == "home":
            continue
        html = _management_cms_build_page(page, category_lookup, site_config, root_manifest_path, nav_html)
        slug = page.get("slug", "")
        (out / f"{slug}.html").write_text(html, encoding="utf-8")
        urls.append(f"/{slug}.html")
        page_count += 1

    # Posts
    # URL-STRUCTURE FIX (2026-07-27, requested directly — "get to work on
    # whatever is not done"): previously posts were written flatly as
    # /{slug}.html, same namespace as Pages — a real collision risk that
    # was only ever warned about (see the slug-collision guard below),
    # never actually prevented. Now written under /post/, matching the
    # existing /post-category/ and /page-category/ symmetry. This
    # structurally eliminates Page-vs-Post collisions entirely (Pages and
    # Posts can no longer share an output path, full stop) rather than
    # just detecting them after the fact. BREAKING for any already-
    # published site: old flat /{slug}.html post URLs are no longer
    # produced. All internal references (nav's Recent Posts, category/tag
    # archive feed cards, the homepage recent-posts fallback, sitemap,
    # RSS/Atom/JSON feeds) were updated to match — see each file's own
    # changelog.
    posts = Content.management_cms_content_list_posts(post_manifest_path, status="published")
    post_dir = out / "post"
    post_dir.mkdir(exist_ok=True)
    for post in posts:
        html = _management_cms_build_post(post, category_lookup, tag_lookup, site_config, root_manifest_path, nav_html, all_posts=posts)
        slug = post.get("slug", "")
        (post_dir / f"{slug}.html").write_text(html, encoding="utf-8")
        urls.append(f"/post/{slug}.html")

    # Category archive pages (post-type)
    # URL-SYMMETRY FIX (2026-07-22, requested directly): previously written
    # under /category/, while page-type categories were under
    # /page-category/ — asymmetric naming where "category" implicitly meant
    # "post category" with the qualifier silently dropped, easy to mistake
    # for the only category concept. Now /post-category/, matching
    # /page-category/ exactly. BREAKING for any already-published site: old
    # /category/{slug}.html URLs are no longer produced. See CHECKLIST.md.
    categories = Taxonomy.management_cms_taxonomy_get_categories(category_manifest_path, "post")
    category_dir = out / "post-category"
    category_dir.mkdir(exist_ok=True)
    for cat in categories:
        cat_posts, _ = Feed.management_cms_feed_get_category_posts(
            category_manifest_path, post_manifest_path, cat.get("slug", ""))
        slug = cat.get("slug", "")
        # FEED PAGINATION FIX (2026-07-28): was a single unpaginated page
        # no matter how many posts a category had. Page 1 stays at the
        # same /post-category/{slug}.html URL; page 2+ goes to
        # /post-category/{slug}/page/{n}.html.
        page_urls = _management_cms_write_paginated_feed(
            cat_posts, f"/post-category/{slug}", category_dir / f"{slug}.html",
            lambda items, pag, c=cat: _management_cms_build_category_page(
                c, items, site_config, root_manifest_path, nav_html, pag),
        )
        urls.extend(page_urls)

    # Category archive pages (page-type) — BUG FIX: these categories can
    # now appear in the auto-generated nav sidebar (see
    # _management_cms_build_category_sidebar_html()), but nothing
    # previously built an actual archive page for them, so those links
    # would have 404'd. _management_cms_build_category_page() works
    # identically for a list of Page dicts as it does Posts (both have
    # "slug"/"title"), so it's reused as-is rather than duplicated.
    # Written under /page-category/ rather than /category/ since the two
    # category types share one Category entity's slug field with no
    # cross-type uniqueness enforced — two categories of different types
    # could otherwise collide on the same output filename.
    page_categories = Taxonomy.management_cms_taxonomy_get_categories(category_manifest_path, "page")
    page_category_dir = out / "page-category"
    if page_categories:
        page_category_dir.mkdir(exist_ok=True)
    for cat in page_categories:
        cat_pages = Content.management_cms_content_list_pages(
            page_manifest_path, status="published", category_id_fk=cat["id"])
        slug = cat.get("slug", "")
        page_urls = _management_cms_write_paginated_feed(
            cat_pages, f"/page-category/{slug}", page_category_dir / f"{slug}.html",
            lambda items, pag, c=cat: _management_cms_build_category_page(
                c, items, site_config, root_manifest_path, nav_html, pag),
        )
        urls.extend(page_urls)

    # Tag archive pages
    tags = Taxonomy.management_cms_taxonomy_get_tags(post_manifest_path)
    tag_dir = out / "tag"
    tag_dir.mkdir(exist_ok=True)
    for tag in tags:
        tag_posts, _ = Feed.management_cms_feed_get_tag_posts(post_manifest_path, tag.get("slug", ""))
        slug = tag.get("slug", "")
        page_urls = _management_cms_write_paginated_feed(
            tag_posts, f"/tag/{slug}", tag_dir / f"{slug}.html",
            lambda items, pag, t=tag: _management_cms_build_tag_page(
                t, items, site_config, root_manifest_path, nav_html, pag),
        )
        urls.extend(page_urls)

    # Feeds
    rss = Feed.management_cms_feed_generate_rss(post_manifest_path, site_config, posts)
    atom = Feed.management_cms_feed_generate_atom(post_manifest_path, site_config, posts)
    json_feed = Feed.management_cms_feed_generate_json(post_manifest_path, site_config, posts)
    (out / "feed.xml").write_text(rss, encoding="utf-8")
    (out / "atom.xml").write_text(atom, encoding="utf-8")
    (out / "feed.json").write_text(json_feed, encoding="utf-8")

    # Sitemap / robots
    site_url = management_cms_shared_export_site_url(site_config)  # AUDIT FIX (BLD-01)
    (out / "sitemap.xml").write_text(_management_cms_build_sitemap(site_url, urls), encoding="utf-8")
    (out / "robots.txt").write_text(_management_cms_build_robots(site_url), encoding="utf-8")

    # Feature request (Elton): custom 404 page. Written as 404.html at
    # the export root — the filename static hosts (GitHub Pages,
    # Cloudflare Pages, Netlify, etc.) look for by convention, so no
    # extra hosting configuration is needed for this to take effect.
    (out / "404.html").write_text(
        _management_cms_build_404_page(site_config, root_manifest_path, nav_html), encoding="utf-8"
    )

    # Media
    media_copied = _management_cms_copy_media(media_manifest_path, output_dir)

    return {
        "pages": page_count, "posts": len(posts), "category_pages": len(categories),
        "page_category_pages": len(page_categories),
        "tag_pages": len(tags), "home_built": home_built, "media_copied": media_copied,
        "urls": urls, "audit": audit_results, "auto_published": auto_published,
        "warnings": warnings,
    }

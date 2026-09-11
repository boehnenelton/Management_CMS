"""
Library:         lib_bejson_Management_feed
Family:          management_cms
Description:     RSS/Atom/JSON feed generation, category/tag feed pagination,
                  and content widgets. Ported from KIMI-CMS's
                  lib_bejson_Web_CMS_Feed.py (10 functions) — the lowest-risk
                  file in the merge, per the merge report's risk section,
                  since this is pure output formatting with no schema change.

                  KIMI's version read site config via site.get_config() on
                  the now-discarded WebCMSSite. Since there is no class to
                  hold that config anymore, every function that needs it
                  takes an explicit site_config: dict argument instead
                  (keys: site_url, site_title, site_tagline,
                  feed_posts_limit, site_language) — the caller supplies it
                  from wherever the app keeps its own configuration.
Version:         1.3.0
Library_Version: 004
Date:            2026-07-27
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   3f8a6c2e-9b4d-4e1a-8c7f-5d3b9a2e4f76

CHANGELOG (1.3.0, 2026-07-27): Posts now live under /post/{slug}.html
instead of flat /{slug}.html (see
lib_bejson_Management_static_builder.py's changelog). Updated all 4
post-URL references in this file to match: RSS feed, Atom feed, JSON feed,
and the recent-posts widget. Verified each format emits the correct
/post/ URL in a real build.
CHANGELOG (1.2.0, 2026-07-25): management_cms_feed_recent_posts_widget() now
renders via the shared management_cms_shared_render_feed() card component
(with a real excerpt via management_cms_shared_excerpt()) instead of its
own bare <li><a> list — same component the category/tag archives use.

CHANGELOG (1.1.0, 2026-07-22): management_cms_feed_categories_widget() now
emits /post-category/ or /page-category/ depending on category_type,
matching the URL-symmetry rename. Previously hardcoded /category/
regardless of category_type — harmless while the only caller passed
category_type="post" by default, but would have produced dead links the
moment anyone passed "page".
"""

import json as _json
from typing import Any, Dict, List, Optional, Tuple

import os
import sys

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore
from lib_bejson_Management_shared import (
    management_cms_shared_now_iso,
    management_cms_shared_now_rfc822,
    management_cms_shared_to_rfc822,
    management_cms_shared_fmt_date,
    management_cms_shared_esc,
    management_cms_shared_excerpt,
    management_cms_shared_export_media_url,
    management_cms_shared_export_thumbnail,
    management_cms_shared_render_feed,
)


def _published_posts(post_manifest_path: str) -> List[Dict[str, Any]]:
    posts = MFDBCore.mfdb_core_load_entity(post_manifest_path, "Post")
    posts = [p for p in posts if p.get("status") == "published"]
    posts.sort(key=lambda p: p.get("published_at", "") or "", reverse=True)
    return posts


# =============================================================================
# FEED GENERATION
# =============================================================================

def management_cms_feed_generate_rss(post_manifest_path: str, site_config: Dict[str, Any],
                                      posts: Optional[list] = None) -> str:
    """Generate an RSS 2.0 feed XML string."""
    site_url = (site_config.get("site_url") or "").rstrip("/")
    site_title = site_config.get("site_title", "My Site")
    site_desc = site_config.get("site_tagline", "")

    if posts is None:
        posts = _published_posts(post_manifest_path)
    limit = int(site_config.get("feed_posts_limit", 20))
    posts = posts[:limit]

    now = management_cms_shared_now_rfc822()
    items = ""
    for p in posts:
        url = f"{site_url}/post/{p.get('slug', '')}.html"
        pub = management_cms_shared_to_rfc822(p.get("published_at", ""))
        items += f"""    <item>
      <title>{management_cms_shared_esc(p.get('title', ''))}</title>
      <link>{management_cms_shared_esc(url)}</link>
      <guid>{management_cms_shared_esc(url)}</guid>
      <pubDate>{pub}</pubDate>
    </item>
"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{management_cms_shared_esc(site_title)}</title>
    <link>{management_cms_shared_esc(site_url)}</link>
    <description>{management_cms_shared_esc(site_desc)}</description>
    <lastBuildDate>{now}</lastBuildDate>
    <language>en</language>
{items}  </channel>
</rss>"""


def management_cms_feed_generate_atom(post_manifest_path: str, site_config: Dict[str, Any],
                                       posts: Optional[list] = None) -> str:
    """Generate an Atom 1.0 feed XML string."""
    site_url = (site_config.get("site_url") or "").rstrip("/")
    site_title = site_config.get("site_title", "My Site")
    site_desc = site_config.get("site_tagline", "")

    if posts is None:
        posts = _published_posts(post_manifest_path)
    limit = int(site_config.get("feed_posts_limit", 20))
    posts = posts[:limit]

    now = management_cms_shared_now_iso()
    feed_id = f"{site_url}/atom.xml"
    entries = ""
    for p in posts:
        url = f"{site_url}/post/{p.get('slug', '')}.html"
        updated = p.get("updated_at") or p.get("published_at", now)
        entries += f"""  <entry>
    <title>{management_cms_shared_esc(p.get('title', ''))}</title>
    <link href="{management_cms_shared_esc(url)}"/>
    <id>{management_cms_shared_esc(url)}</id>
    <updated>{updated}</updated>
  </entry>
"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{management_cms_shared_esc(site_title)}</title>
  <link href="{management_cms_shared_esc(site_url)}"/>
  <id>{management_cms_shared_esc(feed_id)}</id>
  <updated>{now}</updated>
  <subtitle>{management_cms_shared_esc(site_desc)}</subtitle>
{entries}</feed>"""


def management_cms_feed_generate_json(post_manifest_path: str, site_config: Dict[str, Any],
                                       posts: Optional[list] = None) -> str:
    """Generate a JSON Feed v1 (jsonfeed.org)."""
    site_url = (site_config.get("site_url") or "").rstrip("/")
    site_title = site_config.get("site_title", "My Site")
    site_desc = site_config.get("site_tagline", "")

    if posts is None:
        posts = _published_posts(post_manifest_path)
    limit = int(site_config.get("feed_posts_limit", 20))
    posts = posts[:limit]

    items = [{
        "id": p.get("slug", ""),
        "url": f"{site_url}/post/{p.get('slug', '')}.html",
        "title": p.get("title", ""),
        "content_html": p.get("content_html", ""),
        "date_published": p.get("published_at", ""),
        "date_modified": p.get("updated_at", ""),
        "author": {"name": p.get("author", "")},
    } for p in posts]

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": site_title,
        "description": site_desc,
        "home_page_url": site_url,
        "feed_url": f"{site_url}/feed.json",
        "language": site_config.get("site_language", "en"),
        "items": items,
    }
    return _json.dumps(feed, ensure_ascii=False, indent=2)


# =============================================================================
# CATEGORY / TAG FEED PAGES
# =============================================================================

def management_cms_feed_get_category_posts(category_manifest_path: str, post_manifest_path: str,
                                            category_slug: str, status: str = "published",
                                            limit: Optional[int] = None, offset: int = 0) -> Tuple[List[Dict], int]:
    import lib_bejson_Management_taxonomy as Taxonomy
    cat = Taxonomy.management_cms_taxonomy_get_category_by_slug(category_manifest_path, category_slug)
    if not cat:
        return [], 0
    posts = MFDBCore.mfdb_core_load_entity(post_manifest_path, "Post")
    matched = [p for p in posts if p.get("status") == status and p.get("category_id_fk") == cat["id"]]
    matched.sort(key=lambda p: p.get("published_at", "") or "", reverse=True)
    total = len(matched)
    if limit is not None:
        matched = matched[offset:offset + limit]
    return matched, total


def management_cms_feed_get_tag_posts(post_manifest_path: str, tag_slug: str, status: str = "published",
                                       limit: Optional[int] = None, offset: int = 0) -> Tuple[List[Dict], int]:
    import lib_bejson_Management_taxonomy as Taxonomy
    tag = Taxonomy.management_cms_taxonomy_get_tag_by_slug(post_manifest_path, tag_slug)
    if not tag:
        return [], 0
    posts = MFDBCore.mfdb_core_load_entity(post_manifest_path, "Post")
    matched = [p for p in posts if p.get("status") == status and tag["id"] in (p.get("tag_ids") or [])]
    matched.sort(key=lambda p: p.get("published_at", "") or "", reverse=True)
    total = len(matched)
    if limit is not None:
        matched = matched[offset:offset + limit]
    return matched, total


# =============================================================================
# PAGINATION
# =============================================================================

def management_cms_feed_paginate(items: list, page: int, per_page: int) -> Dict[str, Any]:
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    return {
        "items": items[offset:offset + per_page],
        "page": page, "per_page": per_page, "total": total, "total_pages": total_pages,
        "has_prev": page > 1, "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
    }


def management_cms_feed_pagination_html(pagination: dict, base_url: str) -> str:
    if pagination["total_pages"] <= 1:
        return ""
    parts = ['<div class="becss-c-pagination">']
    if pagination["has_prev"]:
        parts.append(f'<a href="{base_url}?page={pagination["prev_page"]}" class="becss-c-pagination__btn">&larr; Previous</a>')
    else:
        parts.append('<span class="becss-c-pagination__btn becss-c-pagination__btn--disabled">&larr; Previous</span>')
    for p in range(1, pagination["total_pages"] + 1):
        cls = "becss-c-pagination__btn becss-c-pagination__btn--active" if p == pagination["page"] else "becss-c-pagination__btn"
        if p == pagination["page"]:
            parts.append(f'<span class="{cls}">{p}</span>')
        else:
            parts.append(f'<a href="{base_url}?page={p}" class="{cls}">{p}</a>')
    if pagination["has_next"]:
        parts.append(f'<a href="{base_url}?page={pagination["next_page"]}" class="becss-c-pagination__btn">Next &rarr;</a>')
    else:
        parts.append('<span class="becss-c-pagination__btn becss-c-pagination__btn--disabled">Next &rarr;</span>')
    parts.append("</div>")
    return "\n".join(parts)


# =============================================================================
# WIDGETS
# =============================================================================

def management_cms_feed_recent_posts_widget(post_manifest_path: str, limit: int = 5) -> str:
    """
    SHARED-FEED-COMPONENT FIX (2026-07-22, requested directly): now built
    on management_cms_shared_render_feed() — the same card component used
    by category and tag archives — instead of its own bare <li><a> list.
    Each card gets a real excerpt (management_cms_shared_excerpt()) and a
    date, matching what the archive pages show.
    """
    posts = _published_posts(post_manifest_path)[:limit]
    items = [
        {
            "title": p.get("title", ""),
            "url": f'/post/{p.get("slug", "")}.html',
            "meta": management_cms_shared_fmt_date(p.get("published_at", ""), "%b %d, %Y"),
            "excerpt": management_cms_shared_excerpt(p.get("content_html", "")),
            "thumbnail": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[0],  # AUDIT FIX (M-1, media-url rewrite + YouTube thumbnail)
            "is_video": management_cms_shared_export_thumbnail(p.get("featured_image", ""))[1],
        }
        for p in posts
    ]
    heading = '<h4 class="becss-c-widget__heading">Recent Posts</h4>' if items else ""
    return f'<div class="becss-c-widget">{heading}{management_cms_shared_render_feed(items, "No posts published yet.")}</div>'


def management_cms_feed_categories_widget(category_manifest_path: str, category_type: str = "post") -> str:
    """
    URL-SYMMETRY FIX (2026-07-22): now emits /post-category/ or
    /page-category/ depending on category_type, matching the rename in
    lib_bejson_Management_static_builder.py. Previously hardcoded
    /category/ regardless of category_type — harmless while this
    function's only caller passed category_type="post" by default, but
    would have generated dead links the moment anyone passed "page".
    """
    import lib_bejson_Management_taxonomy as Taxonomy
    cats = Taxonomy.management_cms_taxonomy_get_categories(category_manifest_path, category_type)
    url_prefix = "/post-category/" if category_type == "post" else "/page-category/"
    items = "".join(
        f'<li class="becss-c-widget__item"><a href="{url_prefix}{c.get("slug", "")}.html" '
        f'class="becss-c-widget__link">{management_cms_shared_esc(c.get("title", ""))}</a></li>'
        for c in cats
    )
    return (f'<div class="becss-c-widget"><h4 class="becss-c-widget__heading">Categories</h4>'
            f'<ul class="becss-c-widget__list">{items}</ul></div>')


def management_cms_feed_tag_cloud_widget(post_manifest_path: str, min_size: int = 12, max_size: int = 24) -> str:
    import lib_bejson_Management_taxonomy as Taxonomy
    tags = Taxonomy.management_cms_taxonomy_get_tags(post_manifest_path)
    if not tags:
        return ""
    posts = MFDBCore.mfdb_core_load_entity(post_manifest_path, "Post")
    tag_counts: Dict[str, int] = {}
    for p in posts:
        for tid in (p.get("tag_ids") or []):
            tag_counts[tid] = tag_counts.get(tid, 0) + 1
    max_count = max(tag_counts.values()) if tag_counts else 1
    tags_html = ""
    for t in tags:
        count = tag_counts.get(t.get("id", ""), 0)
        if count == 0:
            continue
        size = min_size + (max_size - min_size) * (count / max_count)
        tags_html += (f'<a href="/tag/{t.get("slug", "")}.html" style="font-size:{size:.0f}px" '
                      f'class="becss-c-tagcloud__tag">{management_cms_shared_esc(t.get("name", ""))}</a>')
    return f'<div class="becss-c-widget"><h4 class="becss-c-widget__heading">Tags</h4><div class="becss-c-tagcloud">{tags_html}</div></div>'

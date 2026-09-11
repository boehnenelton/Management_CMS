"""
Library:         lib_bejson_Management_content
Family:          management_cms
Description:     Page and Post CRUD. Ported from KIMI-CMS's
                  lib_bejson_Web_CMS_Content.py (12 functions), re-pointed
                  from WebCMSSite's private JSON I/O onto MFDBCore, per
                  OFFICIAL_PLAN.MD Sec. I/III. Every page/post foreign-keys
                  into the shared Category entity (category_id_fk) rather
                  than carrying a flat category string, per Sec. IV's
                  relational-integrity rule. Content bodies for large
                  HTML/Markdown bodies are still written to separate files
                  under the entity's content folder rather than stored
                  inline in the MFDB row, exactly as KIMI already did —
                  only the call site moved off WebCMSSite's private writer.
                  page_type restored to PAGE_FIELDS and management_cms_content_get_home_page()
                  added per Directive 3 (Static Builder's site-root hook).
Version:         1.5.0
Library_Version: 006
Date:            2026-07-26
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   9c4f7a2e-5b8d-4e1c-9a3f-6d2b8c4e9f57

CHANGELOG (1.5.0, 2026-07-26): Full codebase audit fix.
management_cms_content_delete_page() previously left the page's PageSeo
row behind — an orphan pointing at a page_id_fk that no longer exists,
forever. Same "delete doesn't clean up its dependents" pattern as the
media-delete bug fixed the same pass in app.py. Now finds and removes the
matching PageSeo row too. Functionally tested: create page + set SEO,
delete page, confirm SEO record is gone.
CHANGELOG (1.4.0, 2026-07-25): Two fixes. (1) Checklist item 2b:
management_cms_content_create_page()/create_post()/seo_set() migrated from
raw positional lists to mfdb_core_add_entity_record_by_name() — resolves
each value's slot from *_FIELDS' own on-disk order instead of the call site
staying in lockstep with it by convention. All three functionally
retested (create + read-back) after migration. (2) Real bug found during
a full build/link-audit pass: management_cms_content_list_pages()'s sort
crashed (None < int) the moment any Page had sort_order stored as null —
site-wide build failure, not contained to one page. Fixed with `or 0`.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore
from lib_bejson_Management_shared import (
    management_cms_shared_gen_id,
    management_cms_shared_now_iso,
    management_cms_shared_slugify,
)

# ---------------------------------------------------------------------------
# Schema — Page (+ PageSeo secondary entity), Content/Page/MFDB/104a.mfdb.bejson
# ---------------------------------------------------------------------------

PAGE_FIELDS = [
    {"name": "id",                 "type": "string"},
    {"name": "category_id_fk",     "type": "string"},
    {"name": "slug",               "type": "string"},
    {"name": "status",             "type": "string"},   # draft | published | archived
    {"name": "page_type",          "type": "string"},   # per taxonomy.PAGE_TYPES: home | landing | content | ...
    {"name": "meta_description",   "type": "string"},
    {"name": "layout",             "type": "string"},
    {"name": "content_html",       "type": "string"},
    {"name": "content_markdown",   "type": "string"},
    {"name": "author",             "type": "string"},
    {"name": "featured_image",     "type": "string"},
    {"name": "parent_page_id_fk",  "type": "string"},
    {"name": "sort_order",         "type": "integer"},
    {"name": "created_at",         "type": "string"},
    {"name": "updated_at",         "type": "string"},
    # BUG FIX: title was never a real field — only ever used transiently
    # to derive a slug at creation time, then discarded. Every save from
    # the UI includes a title value, and management_cms_content_update_page()
    # would try to write it via MFDBCore.mfdb_core_update_entity_record_bulk(),
    # which raises BEJSONCoreError for any field name not in this list —
    # meaning every single edit-and-save of an existing page failed with an
    # unhandled 500. Appended at the END of the field list (not inserted
    # earlier) so existing on-disk Page rows — which have one fewer value
    # than this new Fields list — aren't corrupted: BEJSON rows are
    # positional, and Python's zip() truncates gracefully on a short row,
    # so old pages just come back without a "title" key until next saved,
    # which page_to_dict()'s .get("title", "") default already handles.
    {"name": "title",              "type": "string"},
]

PAGE_SEO_FIELDS = [
    {"name": "seo_id",           "type": "string"},
    {"name": "page_id_fk",       "type": "string"},
    {"name": "meta_title",       "type": "string"},
    {"name": "meta_keywords",    "type": "string"},
    {"name": "og_title",         "type": "string"},
    {"name": "og_description",   "type": "string"},
    {"name": "og_image",         "type": "string"},
    {"name": "canonical_url",    "type": "string"},
    {"name": "robots_directive", "type": "string"},
    {"name": "created_at",       "type": "string"},
]

# ---------------------------------------------------------------------------
# Schema — Post (+ Tag secondary entity — see lib_bejson_Management_taxonomy.py)
# Content/Post/MFDB/104a.mfdb.bejson
# ---------------------------------------------------------------------------

POST_FIELDS = [
    {"name": "id",               "type": "string"},
    {"name": "category_id_fk",   "type": "string"},
    {"name": "title",            "type": "string"},
    {"name": "slug",             "type": "string"},
    {"name": "status",           "type": "string"},   # draft | review | scheduled | published | archived
    {"name": "content_html",     "type": "string"},
    {"name": "content_markdown", "type": "string"},
    {"name": "author",           "type": "string"},
    {"name": "featured_image",   "type": "string"},
    {"name": "published_at",     "type": "string"},
    {"name": "scheduled_at",     "type": "string"},
    {"name": "tag_ids",          "type": "array"},
    {"name": "created_at",       "type": "string"},
    {"name": "updated_at",       "type": "string"},
]

PAGE_STATUSES = ("draft", "published", "archived")


# ---------------------------------------------------------------------------
# Content file I/O — large bodies kept out of the MFDB row, per Job B
# ---------------------------------------------------------------------------

def _content_dir(manifest_path: str, content_type: str) -> Path:
    return Path(os.path.dirname(os.path.abspath(manifest_path))) / "content" / content_type


def _write_content_file(manifest_path: str, content_type: str, slug: str, html_content: str) -> None:
    directory = _content_dir(manifest_path, content_type)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{slug}.html").write_text(html_content, encoding="utf-8")


def _read_content_file(manifest_path: str, content_type: str, slug: str) -> str:
    file_path = _content_dir(manifest_path, content_type) / f"{slug}.html"
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return ""


def _delete_content_file(manifest_path: str, content_type: str, slug: str) -> None:
    file_path = _content_dir(manifest_path, content_type) / f"{slug}.html"
    if file_path.exists():
        file_path.unlink()


# =============================================================================
# PAGE OPERATIONS
# =============================================================================

def management_cms_content_create_page(manifest_path: str, title: str, slug: str = "",
                                        category_id_fk: Optional[str] = None,
                                        page_type: str = "content",
                                        meta_description: str = "", layout: str = "default",
                                        author: str = "", featured_image: str = "",
                                        parent_page_id_fk: Optional[str] = None, sort_order: int = 0,
                                        status: str = "draft", content_html: str = "",
                                        content_markdown: str = "") -> str:
    """
    page_type: must match a key in lib_bejson_Management_taxonomy.PAGE_TYPES
    (e.g. "home", "landing", "content", "blog_index", ...), per Directive 3.
    Not validated against that registry here to avoid a circular import
    (taxonomy.py doesn't depend on content.py); callers building an admin UI
    should offer management_cms_taxonomy_list_page_types() as the choice list.
    """
    resolved_slug = slug or management_cms_shared_slugify(title)
    now = management_cms_shared_now_iso()
    page_id = management_cms_shared_gen_id()
    # CHECKLIST ITEM 2b FIX (2026-07-25): migrated from a raw positional
    # list to mfdb_core_add_entity_record_by_name() — resolves each value's
    # slot from PAGE_FIELDS' own on-disk order instead of this call site
    # having to stay in lockstep with it by convention. See
    # lib_bejson_Core_mfdb_core.py's changelog for why the positional
    # version was a real (if not yet triggered) corruption risk.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Page", {
        "id": page_id, "category_id_fk": category_id_fk, "slug": resolved_slug,
        "status": status if status in PAGE_STATUSES else "draft",
        "page_type": page_type, "meta_description": meta_description, "layout": layout,
        "content_html": content_html, "content_markdown": content_markdown, "author": author,
        "featured_image": featured_image, "parent_page_id_fk": parent_page_id_fk,
        "sort_order": sort_order, "created_at": now, "updated_at": now, "title": title,
    })
    if content_html:
        _write_content_file(manifest_path, "pages", resolved_slug, content_html)
    return page_id


def management_cms_content_update_page(manifest_path: str, page_id: str, **updates) -> bool:
    # BUG FIX (found while testing the TOC feature, 2026-08-19):
    # content_html used to be popped out of `updates` before the bulk
    # entity update — written to the content file (via _write_content_file
    # below) but NEVER back into the Page entity's own content_html
    # field. management_cms_content_create_page() writes to BOTH on
    # creation; this function only wrote to one on every edit after that,
    # silently desyncing them. management_cms_static_build() (the actual
    # published-site generator) reads content_html from the entity via
    # management_cms_content_list_pages() — never the content file — so
    # every edit to an existing page's content_html was silently invisible
    # on the built site from that point on, even though re-opening the
    # page in the admin editor (which reads via
    # management_cms_content_get_page(), which DOES read the content
    # file) looked like the edit had worked. content_html now stays in
    # `updates` so the bulk call writes it to the entity too, in addition
    # to the existing content-file write below.
    content_html = updates.get("content_html", None)
    pages = MFDBCore.mfdb_core_load_entity(manifest_path, "Page")
    for i, p in enumerate(pages):
        if p.get("id") == page_id:
            updates["updated_at"] = management_cms_shared_now_iso()
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Page", i, updates)
            if content_html is not None:
                slug = updates.get("slug", p.get("slug", page_id))
                _write_content_file(manifest_path, "pages", slug, content_html)
            return True
    return False


def management_cms_content_get_page(manifest_path: str, page_id: Optional[str] = None,
                                     slug: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for p in MFDBCore.mfdb_core_load_entity(manifest_path, "Page"):
        if page_id and p.get("id") == page_id:
            match = p
            break
        if slug and p.get("slug") == slug:
            match = p
            break
    else:
        return None
    match = dict(match)
    match["content_html"] = _read_content_file(manifest_path, "pages", match.get("slug", ""))
    return match


def management_cms_content_list_pages(manifest_path: str, status: Optional[str] = None,
                                       category_id_fk: Optional[str] = None) -> List[Dict[str, Any]]:
    pages = MFDBCore.mfdb_core_load_entity(manifest_path, "Page")
    if status:
        pages = [p for p in pages if p.get("status") == status]
    if category_id_fk:
        pages = [p for p in pages if p.get("category_id_fk") == category_id_fk]
    # BUG FIX (2026-07-25, found during a full build/link-audit pass):
    # `.get("sort_order", 0)` only applies the 0 default when the key is
    # entirely absent — a record where sort_order is legitimately stored
    # as null (the correct representation for "no value set", per the
    # project's own data-integrity standard) still returns None, not 0,
    # and `sorted()` then crashes comparing None < int the moment ANY
    # page has a null sort_order — which took the entire static build
    # down site-wide, not just that one page. `or 0` handles None safely
    # while still sorting explicit 0 and negative values correctly.
    return sorted(pages, key=lambda p: p.get("sort_order") or 0)


def management_cms_content_delete_page(manifest_path: str, page_id: str) -> bool:
    pages = MFDBCore.mfdb_core_load_entity(manifest_path, "Page")
    for i, p in enumerate(pages):
        if p.get("id") == page_id:
            if p.get("slug"):
                _delete_content_file(manifest_path, "pages", p["slug"])
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Page", i)
            # AUDIT FIX (2026-07-26): previously left the page's PageSeo
            # row behind — an orphan pointing at a page_id_fk that no
            # longer exists, forever, the same "delete doesn't clean up
            # its dependents" pattern as the media-delete bug fixed in
            # app.py's delete_media() this same pass.
            for j, s in enumerate(MFDBCore.mfdb_core_load_entity(manifest_path, "PageSeo")):
                if s.get("page_id_fk") == page_id:
                    MFDBCore.mfdb_core_remove_entity_record(manifest_path, "PageSeo", j)
                    break
            return True
    return False


def management_cms_content_get_home_page(manifest_path: str) -> Optional[Dict[str, Any]]:
    """
    Directive 3 / Static Builder hook: identify the site root by querying
    Page for page_type == "home". If more than one page is marked "home"
    (a data-entry mistake, not something this function silently resolves),
    the first published one found is returned; callers that care about that
    ambiguity should check management_cms_content_list_pages(..., ) for
    duplicates themselves.
    """
    pages = MFDBCore.mfdb_core_load_entity(manifest_path, "Page")
    home_pages = [p for p in pages if p.get("page_type") == "home"]
    published = [p for p in home_pages if p.get("status") == "published"]
    candidates = published or home_pages
    if not candidates:
        return None
    match = dict(candidates[0])
    match["content_html"] = _read_content_file(manifest_path, "pages", match.get("slug", ""))
    return match


# =============================================================================
# POST OPERATIONS
# =============================================================================

def management_cms_content_create_post(manifest_path: str, title: str, slug: str = "",
                                        category_id_fk: Optional[str] = None,
                                        tag_ids: Optional[list] = None,
                                        author: str = "", featured_image: str = "",
                                        status: str = "draft", content_html: str = "",
                                        content_markdown: str = "",
                                        scheduled_at: str = "") -> str:
    resolved_slug = slug or management_cms_shared_slugify(title)
    now = management_cms_shared_now_iso()
    post_id = management_cms_shared_gen_id()
    # CHECKLIST ITEM 2b FIX (2026-07-25): migrated to
    # mfdb_core_add_entity_record_by_name() — see the matching fix on
    # management_cms_content_create_page() above for rationale.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Post", {
        "id": post_id, "category_id_fk": category_id_fk, "title": title, "slug": resolved_slug,
        "status": status, "content_html": content_html, "content_markdown": content_markdown,
        "author": author, "featured_image": featured_image,
        "published_at": now if status == "published" else "", "scheduled_at": scheduled_at,
        "tag_ids": tag_ids or [], "created_at": now, "updated_at": now,
    })
    if content_html:
        _write_content_file(manifest_path, "posts", resolved_slug, content_html)
    return post_id


def management_cms_content_update_post(manifest_path: str, post_id: str, **updates) -> bool:
    # BUG FIX (found while testing the TOC feature, 2026-08-19): same
    # bug as management_cms_content_update_page() above — content_html
    # was popped out of `updates` before the bulk entity update, written
    # only to the content file, never back into the Post entity's own
    # content_html field. management_cms_static_build() reads
    # content_html from the entity via management_cms_content_list_posts()
    # (never the content file), so every content edit to an existing
    # post silently never appeared on the built site. Left in `updates`
    # now so the bulk write covers the entity too.
    content_html = updates.get("content_html", None)
    posts = MFDBCore.mfdb_core_load_entity(manifest_path, "Post")
    for i, p in enumerate(posts):
        if p.get("id") == post_id:
            updates["updated_at"] = management_cms_shared_now_iso()
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Post", i, updates)
            if content_html is not None:
                slug = updates.get("slug", p.get("slug", post_id))
                _write_content_file(manifest_path, "posts", slug, content_html)
            return True
    return False


def management_cms_content_get_post(manifest_path: str, post_id: Optional[str] = None,
                                     slug: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for p in MFDBCore.mfdb_core_load_entity(manifest_path, "Post"):
        if post_id and p.get("id") == post_id:
            match = p
            break
        if slug and p.get("slug") == slug:
            match = p
            break
    else:
        return None
    match = dict(match)
    match["content_html"] = _read_content_file(manifest_path, "posts", match.get("slug", ""))
    return match


def management_cms_content_list_posts(manifest_path: str, category_id_fk: Optional[str] = None,
                                       tag_id: Optional[str] = None, status: str = "published",
                                       limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
    posts = MFDBCore.mfdb_core_load_entity(manifest_path, "Post")
    if status:
        posts = [p for p in posts if p.get("status") == status]
    if category_id_fk:
        posts = [p for p in posts if p.get("category_id_fk") == category_id_fk]
    if tag_id:
        posts = [p for p in posts if tag_id in (p.get("tag_ids") or [])]
    posts.sort(key=lambda p: p.get("published_at", "") or "", reverse=True)
    if limit is not None:
        posts = posts[offset:offset + limit]
    return posts


def management_cms_content_delete_post(manifest_path: str, post_id: str) -> bool:
    posts = MFDBCore.mfdb_core_load_entity(manifest_path, "Post")
    for i, p in enumerate(posts):
        if p.get("id") == post_id:
            if p.get("slug"):
                _delete_content_file(manifest_path, "posts", p["slug"])
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Post", i)
            return True
    return False


def management_cms_content_publish_post(manifest_path: str, post_id: str) -> bool:
    return management_cms_content_update_post(manifest_path, post_id, status="published",
                                               published_at=management_cms_shared_now_iso())


def management_cms_content_archive_post(manifest_path: str, post_id: str) -> bool:
    return management_cms_content_update_post(manifest_path, post_id, status="archived")


def management_cms_content_list_due_for_publish(manifest_path: str) -> List[Dict[str, Any]]:
    """
    Scans Post for status=="scheduled" rows whose scheduled_at has already
    passed (UTC, compared as ISO 8601 strings — safe since
    management_cms_shared_now_iso()'s "%Y-%m-%dT%H:%M:%SZ" format sorts
    lexicographically the same as chronologically). Malformed/empty
    scheduled_at values are skipped rather than treated as always-due.

    This is the real function backing the "automated publication triggers"
    capability referenced (under a different, nonexistent function name,
    management_posts_list_due_for_publish()) in a later integration
    directive — built fresh under this family's actual naming convention
    since no such function existed anywhere in the codebase.
    """
    now = management_cms_shared_now_iso()
    posts = MFDBCore.mfdb_core_load_entity(manifest_path, "Post")
    due = []
    for p in posts:
        if p.get("status") != "scheduled":
            continue
        scheduled_at = p.get("scheduled_at") or ""
        if not scheduled_at:
            continue
        try:
            if scheduled_at <= now:
                due.append(p)
        except TypeError:
            continue
    return due


def management_cms_content_auto_publish_due(manifest_path: str) -> List[str]:
    """
    Publishes every post management_cms_content_list_due_for_publish()
    reports as due (via the existing management_cms_content_publish_post(),
    which stamps published_at to "now"). Returns the list of post ids that
    were promoted. Intended to be called at the top of a build so a static
    export naturally includes anything that just came due — see
    lib_bejson_Management_static_builder.management_cms_static_build().
    """
    due = management_cms_content_list_due_for_publish(manifest_path)
    published_ids = []
    for p in due:
        if management_cms_content_publish_post(manifest_path, p["id"]):
            published_ids.append(p["id"])
    return published_ids


# =============================================================================
# PageSeo (secondary entity — unchanged pattern from Management_pages.py v2.0.0)
# =============================================================================

def management_cms_content_seo_set(manifest_path: str, page_id: str, **seo_fields) -> str:
    all_seo = MFDBCore.mfdb_core_load_entity(manifest_path, "PageSeo")
    for i, s in enumerate(all_seo):
        if s.get("page_id_fk") == page_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "PageSeo", i, seo_fields)
            return s["seo_id"]
    seo_id = management_cms_shared_gen_id()
    created_at = management_cms_shared_now_iso()
    # CHECKLIST ITEM 2b FIX (2026-07-25): migrated to
    # mfdb_core_add_entity_record_by_name().
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "PageSeo", {
        "seo_id": seo_id, "page_id_fk": page_id,
        "meta_title": seo_fields.get("meta_title"), "meta_keywords": seo_fields.get("meta_keywords"),
        "og_title": seo_fields.get("og_title"), "og_description": seo_fields.get("og_description"),
        "og_image": seo_fields.get("og_image"), "canonical_url": seo_fields.get("canonical_url"),
        "robots_directive": seo_fields.get("robots_directive"), "created_at": created_at,
    })
    return seo_id


def management_cms_content_seo_get(manifest_path: str, page_id: str) -> Optional[Dict[str, Any]]:
    for s in MFDBCore.mfdb_core_load_entity(manifest_path, "PageSeo"):
        if s.get("page_id_fk") == page_id:
            return s
    return None

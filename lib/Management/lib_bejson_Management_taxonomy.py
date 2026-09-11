"""
Library:         lib_bejson_Management_taxonomy
Family:          management_cms
Description:     Category (shared, hierarchical, public-hosting taxonomy for
                  Pages and Posts) and Tag (flat, Post-only). Ported from
                  KIMI-CMS's lib_bejson_Web_CMS_Taxonomy.py (17 functions),
                  re-pointed from WebCMSSite's private JSON I/O onto
                  MFDBCore, per OFFICIAL_PLAN.MD Sec. I/III/IV.

                  Category is promoted out of the per-row flat "category"
                  field pattern used by Management's admin taxonomies
                  (Notes/Tasks/Links keep that pattern unchanged) and is
                  instead a top-level shared MFDB entity at
                  Content/Category/MFDB/104a.mfdb.bejson, following the
                  identical MFDBCore manifest+entity split used by Page,
                  Post, and Media (per Directive 2 — the standalone flat
                  104a workaround was retired once validate_list() was
                  decoupled from file I/O). Every write is validated via
                  lib_bejson_Core_bejson_list_validator.validate_list(),
                  called against the entity's raw doc dict fetched with
                  MFDBCore.mfdb_core_get_entity_doc(), per SCHEMA_LIST_MANAGER_v100
                  (id, parent_id, title, description).
Version:         2.2.0
Library_Version: 004
Date:            2026-07-25
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   8b3e6a9f-4d1c-4e7a-9f2b-5c8d3a9e4f67

CHANGELOG (2.2.0, 2026-07-25): Checklist item 2b:
management_cms_taxonomy_add_category()/add_tag() migrated from raw
positional lists to mfdb_core_add_entity_record_by_name(). Retested
functionally (create + read-back) after migration.

CHANGELOG (2.1.0, 2026-07-21): management_cms_taxonomy_delete_tag now nullifies
the deleted tag_id out of every Post's tag_ids array before removing the Tag
record itself, mirroring the existing category re-parenting orphan-prevention
pattern in management_cms_taxonomy_delete_category. Previously tags were
add-only from the UI (no DELETE route existed in app.py); now that a route
calls this function directly, a naive delete would have left dangling
tag_ids referencing a Tag that no longer exists. See CHECKLIST.md item 5.
"""

import os
import sys
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore
from lib_bejson_Core_bejson_list_validator import validate_list
from lib_bejson_Management_shared import (
    management_cms_shared_gen_id,
    management_cms_shared_now_iso,
    management_cms_shared_slugify,
)

# ---------------------------------------------------------------------------
# Schema — Category (Content/Category/MFDB/104a.mfdb.bejson)
# SCHEMA_LIST_MANAGER_v100 baseline: id, parent_id, title, description.
#
# Standard MFDBCore manifest+entity split, identical pattern to Page, Post,
# Media, and Nav — manifest_path is the 104a manifest; "Category" is the
# entity name within it.
# ---------------------------------------------------------------------------

CATEGORY_FIELDS = [
    {"name": "id",              "type": "string"},
    {"name": "parent_id",       "type": "string"},
    {"name": "category_type",   "type": "string"},   # page | post
    {"name": "title",           "type": "string"},
    {"name": "description",     "type": "string"},
    {"name": "slug",            "type": "string"},
    {"name": "created_at",      "type": "string"},
]

# Tag lives as a secondary entity in the Post manifest (flat, non-hierarchical,
# no validate_list() requirement — standard MFDBCore pattern).
TAG_FIELDS = [
    {"name": "id",         "type": "string"},
    {"name": "name",       "type": "string"},
    {"name": "slug",       "type": "string"},
    {"name": "created_at", "type": "string"},
]


class ManagementCmsHierarchyError(Exception):
    """Raised when a Category write would fail validate_list()'s hierarchy check."""


def _validate_hierarchy_or_raise(manifest_path: str, entity_name: str = "Category") -> None:
    """
    Per Directive 1, validate_list() now takes an already-loaded doc dict
    rather than a path, and its structural-validation failure branch no
    longer calls the removed StandardValidator.bejson_validator_get_errors().
    """
    doc_data = MFDBCore.mfdb_core_get_entity_doc(manifest_path, entity_name)
    result = validate_list(doc_data)
    if not result.get("is_valid", False):
        raise ManagementCmsHierarchyError(
            f"{entity_name} hierarchy validation failed: {result.get('errors')}"
        )


# =============================================================================
# CATEGORY OPERATIONS
# =============================================================================

def management_cms_taxonomy_add_category(manifest_path: str, title: str, slug: str = "",
                                          category_type: str = "post", description: str = "",
                                          parent_id: Optional[str] = None) -> str:
    """
    category_type: 'post' | 'page' — discriminator on the single shared
    Category entity, per OFFICIAL_PLAN.MD Sec. IV.
    """
    resolved_slug = slug or management_cms_shared_slugify(title)
    category_id = management_cms_shared_gen_id()
    created_at = management_cms_shared_now_iso()
    # CHECKLIST ITEM 2b FIX (2026-07-25): migrated to
    # mfdb_core_add_entity_record_by_name().
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Category", {
        "id": category_id, "parent_id": parent_id, "category_type": category_type,
        "title": title, "description": description, "slug": resolved_slug, "created_at": created_at,
    })
    _validate_hierarchy_or_raise(manifest_path)
    return category_id


def management_cms_taxonomy_get_categories(manifest_path: str,
                                            category_type: Optional[str] = None) -> List[Dict[str, Any]]:
    cats = MFDBCore.mfdb_core_load_entity(manifest_path, "Category")
    if category_type:
        cats = [c for c in cats if c.get("category_type") == category_type]
    return cats


def management_cms_taxonomy_get_category_by_slug(manifest_path: str, slug: str) -> Optional[Dict[str, Any]]:
    for c in MFDBCore.mfdb_core_load_entity(manifest_path, "Category"):
        if c.get("slug") == slug:
            return c
    return None


def management_cms_taxonomy_get_category_tree(manifest_path: str,
                                               category_type: str = "post") -> List[Dict[str, Any]]:
    """Build a hierarchical tree of categories via id/parent_id (validate_list()'s own model)."""
    cats = management_cms_taxonomy_get_categories(manifest_path, category_type)
    cat_map = {c["id"]: dict(c, children=[]) for c in cats}
    roots = []
    for c in cats:
        node = cat_map[c["id"]]
        pid = c.get("parent_id")
        if pid and pid in cat_map:
            cat_map[pid]["children"].append(node)
        else:
            roots.append(node)
    return roots


def management_cms_taxonomy_update_category(manifest_path: str, category_id: str, **updates) -> bool:
    cats = MFDBCore.mfdb_core_load_entity(manifest_path, "Category")
    for i, c in enumerate(cats):
        if c.get("id") == category_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Category", i, updates)
            _validate_hierarchy_or_raise(manifest_path)
            return True
    return False


def management_cms_taxonomy_delete_category(manifest_path: str, category_id: str) -> bool:
    """
    Delete a category. Per Job B's orphan-prevention rule, any child category
    (parent_id == category_id) is re-parented to None (promoted to root)
    rather than left orphaned, before the hierarchy is re-validated.
    """
    cats = MFDBCore.mfdb_core_load_entity(manifest_path, "Category")
    found_index = None
    for i, c in enumerate(cats):
        if c.get("id") == category_id:
            found_index = i
            break
    if found_index is None:
        return False

    MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Category", found_index)

    remaining = MFDBCore.mfdb_core_load_entity(manifest_path, "Category")
    for i, c in enumerate(remaining):
        if c.get("parent_id") == category_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "Category", i, "parent_id", None)

    _validate_hierarchy_or_raise(manifest_path)
    return True


# =============================================================================
# TAG OPERATIONS (flat, non-hierarchical, lives in the Post manifest)
# =============================================================================

def management_cms_taxonomy_add_tag(manifest_path: str, name: str, slug: str = "") -> str:
    resolved_slug = slug or management_cms_shared_slugify(name)
    tag_id = management_cms_shared_gen_id()
    created_at = management_cms_shared_now_iso()
    # CHECKLIST ITEM 2b FIX (2026-07-25): migrated to
    # mfdb_core_add_entity_record_by_name().
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Tag", {
        "id": tag_id, "name": name, "slug": resolved_slug, "created_at": created_at,
    })
    return tag_id


def management_cms_taxonomy_get_tags(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "Tag")


def management_cms_taxonomy_get_tag_by_slug(manifest_path: str, slug: str) -> Optional[Dict[str, Any]]:
    for t in MFDBCore.mfdb_core_load_entity(manifest_path, "Tag"):
        if t.get("slug") == slug:
            return t
    return None


def management_cms_taxonomy_delete_tag(manifest_path: str, tag_id: str) -> bool:
    """
    Delete a tag. Same manifest holds both Tag and Post entities (cms_post),
    so before removing the Tag record itself, strip tag_id out of every
    Post's tag_ids array — otherwise posts are left holding a dangling
    reference to a Tag that no longer exists (the same orphan-FK risk
    already handled for Category via re-parenting in
    management_cms_taxonomy_delete_category).
    """
    tags = MFDBCore.mfdb_core_load_entity(manifest_path, "Tag")
    found_index = None
    for i, t in enumerate(tags):
        if t.get("id") == tag_id:
            found_index = i
            break
    if found_index is None:
        return False

    posts = MFDBCore.mfdb_core_load_entity(manifest_path, "Post")
    for i, p in enumerate(posts):
        current_tag_ids = p.get("tag_ids") or []
        if tag_id in current_tag_ids:
            MFDBCore.mfdb_core_update_entity_record(
                manifest_path, "Post", i, "tag_ids",
                [t for t in current_tag_ids if t != tag_id],
            )

    MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Tag", found_index)
    return True


# =============================================================================
# PAGE TYPE REGISTRY (unchanged from KIMI — static reference data, no MFDB access)
# =============================================================================

PAGE_TYPES = {
    "landing":    {"label": "Landing Page",    "description": "Marketing/splash page with sections"},
    "content":    {"label": "Content Page",    "description": "Standard informational page"},
    "blog_index": {"label": "Blog Index",      "description": "Listing of blog posts"},
    "contact":    {"label": "Contact Page",    "description": "Contact form and info"},
    "about":      {"label": "About Page",      "description": "About/bio page"},
    "home":       {"label": "Home Page",       "description": "Site homepage"},
    "feed":       {"label": "Feed Page",       "description": "Category/tag feed listing"},
    "legal":      {"label": "Legal Page",      "description": "Privacy policy, terms, etc."},
    "custom":     {"label": "Custom Page",     "description": "User-defined page type"},
}


def management_cms_taxonomy_list_page_types() -> Dict[str, Dict[str, str]]:
    return PAGE_TYPES.copy()


def management_cms_taxonomy_is_valid_page_type(page_type: str) -> bool:
    return page_type in PAGE_TYPES


# =============================================================================
# POST STATUS WORKFLOW (draft/review/scheduled/published, kept from KIMI per
# OFFICIAL_PLAN.MD Sec. IV — richer than Management's current 3-state Page workflow)
# =============================================================================

POST_STATUSES = {
    "draft":     {"label": "Draft",     "public": False, "description": "Work in progress"},
    "review":    {"label": "Review",    "public": False, "description": "Pending review"},
    "scheduled": {"label": "Scheduled", "public": False, "description": "Scheduled for future"},
    "published": {"label": "Published", "public": True,  "description": "Live and visible"},
    "archived":  {"label": "Archived",  "public": False, "description": "No longer visible"},
}


def management_cms_taxonomy_list_post_statuses() -> Dict[str, Dict[str, Any]]:
    return POST_STATUSES.copy()


def management_cms_taxonomy_is_public_status(status: str) -> bool:
    return POST_STATUSES.get(status, {}).get("public", False)


# =============================================================================
# TAXONOMY RELATIONSHIP HELPERS
# =============================================================================

def management_cms_taxonomy_get_posts_by_category(category_manifest_path: str, post_manifest_path: str,
                                                   category_slug: str, status: str = "published") -> List[Dict[str, Any]]:
    cat = management_cms_taxonomy_get_category_by_slug(category_manifest_path, category_slug)
    if not cat:
        return []
    posts = MFDBCore.mfdb_core_load_entity(post_manifest_path, "Post")
    return [p for p in posts if p.get("category_id_fk") == cat["id"]
            and (not status or p.get("status") == status)]


def management_cms_taxonomy_get_posts_by_tag(post_manifest_path: str, tag_slug: str,
                                              status: str = "published") -> List[Dict[str, Any]]:
    tag = management_cms_taxonomy_get_tag_by_slug(post_manifest_path, tag_slug)
    if not tag:
        return []
    posts = MFDBCore.mfdb_core_load_entity(post_manifest_path, "Post")
    return [p for p in posts
            if tag["id"] in (p.get("tag_ids") or [])
            and (not status or p.get("status") == status)]


def management_cms_taxonomy_get_category_slug_map(manifest_path: str) -> Dict[str, str]:
    return {c["id"]: c.get("slug", "") for c in MFDBCore.mfdb_core_load_entity(manifest_path, "Category")}


# AUDIT FIX (M-3): static_builder.py's _management_cms_build_page/_post()
# call this "category_lookup" and use it to populate the {{category_title}}
# token in the post byline / page meta — but it was wired to
# management_cms_taxonomy_get_category_slug_map() (returns {id: slug}),
# not a title map. Verified live: Export/post/Test-Blog-Post.html's byline
# rendered the category's slug ("Developer-Post-Category") where the
# sidebar nav, built from the same category record, correctly showed the
# title ("Developer Post Category") — same data, two different lookups,
# only one right for a human-facing byline. Added this function rather
# than repurposing the slug map, since slug maps are presumably still
# needed elsewhere (URL generation) and conflating the two by changing
# what the existing function returns would be a silent behavior change
# for any other caller.
def management_cms_taxonomy_get_category_title_map(manifest_path: str) -> Dict[str, str]:
    return {c["id"]: c.get("title", "") for c in MFDBCore.mfdb_core_load_entity(manifest_path, "Category")}


def management_cms_taxonomy_get_tag_slug_map(manifest_path: str) -> Dict[str, str]:
    return {t["id"]: t.get("name", "") for t in MFDBCore.mfdb_core_load_entity(manifest_path, "Tag")}

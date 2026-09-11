"""
Library:        lib_bejson_Management_pages.py
Family:         Management
Description:    CMS Pages — the publishing side of this app, distinct from
                 the personal-management taxonomies (Notes/Tasks/Links).
                 Entity schema is built on the common taxonomy baseline
                 (taxonomy, type, category, id, label, idx_position,
                 idx_sorting, active, hidden, created_at) plus its own
                 fields — merged from an evaluated CLI tool someone built
                 on top of these libraries: slug, status, meta_description,
                 layout, content_html, content_markdown, author,
                 featured_image, parent_page_id_fk (page hierarchy),
                 sort_order. PageSeo is a secondary entity (not a
                 taxonomy) for the fuller SEO metadata set. Deployed the
                 same way as any other taxonomy — via Web_Framework's
                 scaffold, on the same MFDBCore backbone.
Version:        2.0.0
Date:           2026-07-06
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  7d2e9f4a-1c6b-4e8d-a3f7-9b5c2d8e1f42
"""

import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore

PAGE_FIELDS = [
    {"name": "slug",               "type": "string"},
    {"name": "status",             "type": "string"},   # draft | published | archived
    {"name": "meta_description",   "type": "string"},
    {"name": "layout",             "type": "string"},    # e.g. "default", "landing"
    {"name": "content_html",       "type": "string"},
    {"name": "content_markdown",   "type": "string"},
    {"name": "author",             "type": "string"},
    {"name": "featured_image",     "type": "string"},
    {"name": "parent_page_id_fk",  "type": "string"},    # page hierarchy
    {"name": "sort_order",         "type": "integer"},
]

PAGE_STATUSES = ("draft", "published", "archived")

# SEO metadata, one row per page — secondary entity, not a taxonomy.
PAGE_SEO_FIELDS = [
    {"name": "seo_id",            "type": "string"},
    {"name": "page_id_fk",        "type": "string"},
    {"name": "meta_title",        "type": "string"},
    {"name": "meta_keywords",     "type": "string"},
    {"name": "og_title",          "type": "string"},
    {"name": "og_description",   "type": "string"},
    {"name": "og_image",          "type": "string"},
    {"name": "canonical_url",     "type": "string"},
    {"name": "robots_directive",  "type": "string"},
    {"name": "created_at",        "type": "string"},
]


def management_pages_slugify(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or str(uuid.uuid4())[:8]


def management_pages_add(manifest_path: str, title: str, slug: Optional[str] = None,
                          status: str = "draft", meta_description: Optional[str] = None,
                          layout: str = "default", category: Optional[str] = None,
                          content_html: Optional[str] = None, content_markdown: Optional[str] = None,
                          author: Optional[str] = None, featured_image: Optional[str] = None,
                          parent_page_id: Optional[str] = None, sort_order: int = 0) -> str:
    page_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resolved_slug = slug or management_pages_slugify(title)
    row = ["page", None, category, page_id, title, 0, "default", True, False, created_at,
           resolved_slug, status if status in PAGE_STATUSES else "draft", meta_description, layout,
           content_html, content_markdown, author, featured_image, parent_page_id, sort_order]
    MFDBCore.mfdb_core_add_entity_record(manifest_path, "Page", row)
    return page_id


def management_pages_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "Page")


def management_pages_get(manifest_path: str, page_id: Optional[str] = None,
                          slug: Optional[str] = None) -> Optional[Dict[str, Any]]:
    for p in management_pages_list(manifest_path):
        if page_id and p.get("id") == page_id:
            return p
        if slug and p.get("slug") == slug:
            return p
    return None


def management_pages_update(manifest_path: str, page_id: str, **fields) -> bool:
    pages = management_pages_list(manifest_path)
    for i, p in enumerate(pages):
        if p.get("id") == page_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Page", i, fields)
            return True
    return False


def management_pages_delete(manifest_path: str, page_id: str) -> bool:
    pages = management_pages_list(manifest_path)
    for i, p in enumerate(pages):
        if p.get("id") == page_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Page", i)
            return True
    return False


def management_pages_publish(manifest_path: str, page_id: str) -> bool:
    return management_pages_update(manifest_path, page_id, status="published")


def management_pages_archive(manifest_path: str, page_id: str) -> bool:
    return management_pages_update(manifest_path, page_id, status="archived")

# ---------------------------------------------------------------------------
# PageSeo (secondary entity, one row per page — not a taxonomy)
# ---------------------------------------------------------------------------

def management_pages_seo_set(manifest_path: str, page_id: str, **seo_fields) -> str:
    """Creates or updates the SEO row for a page. Returns the seo_id."""
    all_seo = MFDBCore.mfdb_core_load_entity(manifest_path, "PageSeo")
    for i, s in enumerate(all_seo):
        if s.get("page_id_fk") == page_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "PageSeo", i, seo_fields)
            return s["seo_id"]
    seo_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = [seo_id, page_id,
           seo_fields.get("meta_title"), seo_fields.get("meta_keywords"),
           seo_fields.get("og_title"), seo_fields.get("og_description"), seo_fields.get("og_image"),
           seo_fields.get("canonical_url"), seo_fields.get("robots_directive"), created_at]
    MFDBCore.mfdb_core_add_entity_record(manifest_path, "PageSeo", row)
    return seo_id


def management_pages_seo_get(manifest_path: str, page_id: str) -> Optional[Dict[str, Any]]:
    for s in MFDBCore.mfdb_core_load_entity(manifest_path, "PageSeo"):
        if s.get("page_id_fk") == page_id:
            return s
    return None

# ---------------------------------------------------------------------------
# PageCategory (lookup table, not a taxonomy — mirrors NoteCategory/TaskCategory/LinkCategory)
# ---------------------------------------------------------------------------

def management_pages_category_add(manifest_path: str, name: str) -> str:
    cat_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    MFDBCore.mfdb_core_add_entity_record(manifest_path, "PageCategory", [cat_id, name, created_at])
    return cat_id


def management_pages_category_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "PageCategory")


def management_pages_category_delete(manifest_path: str, cat_id: str) -> bool:
    """Deletes a page category. Self-healing: nulls out category on any pages that referenced it."""
    cats = management_pages_category_list(manifest_path)
    found = False
    for i, c in enumerate(cats):
        if c.get("cat_id") == cat_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "PageCategory", i)
            found = True
            break
    if not found:
        return False

    for i, p in enumerate(management_pages_list(manifest_path)):
        if p.get("category") == cat_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "Page", i, "category", None)
    return True

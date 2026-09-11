"""
Library:        lib_bejson_Management_links
Family:         Management
Description:    Links section — Link + LinkCategory CRUD against a
                 dedicated, atomically-separated MFDB. Link's entity schema
                 is built on the common taxonomy baseline (taxonomy, type,
                 category, id, label, idx_position, idx_sorting, active,
                 hidden, created_at) plus its own fields (url, icon,
                 description). LinkCategory is a lookup table, not itself a
                 taxonomy, mirroring NoteCategory's structure and
                 self-healing FK-null-out behavior on delete — per the
                 in-progress link/note category structural alignment.
                 Independent of the Web_Framework library; Web_Framework
                 only provisions the MFDB shell.
Version:        3.1.0
Date:           2026-07-03
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  ceaf9353-1625-49bc-82ec-59e676213335

CHANGELOG (3.1.0, 2026-07-25): New file — a live-app-only copy of the
original lib_bejson_Management_links.py, created because Elton asked to fix
the positional-add-call fragility without risking the original (still used
by lib_bejson_Management_cli.py). All mfdb_core_add_entity_record() calls
migrated to mfdb_core_add_entity_record_by_name(). Functionally retested
through the real app.py import path, not just in isolation. The original
file is untouched.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore

# Entity-specific fields only — COMMON_TAXONOMY_FIELDS is prepended by
# Web_Framework's deploy (prepend_common_fields=True).
LINK_FIELDS = [
    {"name": "url",         "type": "string"},
    {"name": "icon",        "type": "string"},
    {"name": "description", "type": "string"},
]

LINK_CATEGORY_FIELDS = [
    {"name": "cat_id",         "type": "string"},
    {"name": "cat_name",       "type": "string"},
    {"name": "cat_created_at", "type": "string"},
]

# ---------------------------------------------------------------------------
# Link (taxonomy = "link")
# ---------------------------------------------------------------------------

def management_links_add(manifest_path: str, title: str, url: str,
                          category: Optional[str] = None, icon: Optional[str] = None,
                          description: Optional[str] = None) -> str:
    link_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # LIVE-COPY FIX (2026-07-25): same pattern as
    # lib_bejson_Management_notes.py — migrated to
    # mfdb_core_add_entity_record_by_name() (COMMON_TAXONOMY_FIELDS +
    # LINK_FIELDS). Original lib_bejson_Management_links.py untouched.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Link", {
        "taxonomy": "link", "type": None, "category": category, "id": link_id,
        "label": title, "idx_position": 0, "idx_sorting": "default",
        "active": True, "hidden": False, "created_at": created_at,
        "url": url, "icon": icon, "description": description,
    })
    return link_id


def management_links_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "Link")


def management_links_update(manifest_path: str, link_id: str, **fields) -> bool:
    links = management_links_list(manifest_path)
    for i, l in enumerate(links):
        if l.get("id") == link_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Link", i, fields)
            return True
    return False


def management_links_delete(manifest_path: str, link_id: str) -> bool:
    links = management_links_list(manifest_path)
    for i, l in enumerate(links):
        if l.get("id") == link_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Link", i)
            return True
    return False

# ---------------------------------------------------------------------------
# LinkCategory (lookup table, not a taxonomy — mirrors NoteCategory)
# ---------------------------------------------------------------------------

def management_links_category_add(manifest_path: str, name: str) -> str:
    cat_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "LinkCategory", {
        "cat_id": cat_id, "cat_name": name, "cat_created_at": created_at,
    })
    return cat_id


def management_links_category_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "LinkCategory")


def management_links_category_delete(manifest_path: str, cat_id: str) -> bool:
    """
    Deletes a link category. Self-healing: nulls out the `category` field
    on any links that referenced this category, mirroring
    management_notes_delete's FK cascade behavior for NoteCategory.
    """
    cats = management_links_category_list(manifest_path)
    found = False
    for i, c in enumerate(cats):
        if c.get("cat_id") == cat_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "LinkCategory", i)
            found = True
            break
    if not found:
        return False

    for i, l in enumerate(management_links_list(manifest_path)):
        if l.get("category") == cat_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "Link", i, "category", None)
    return True

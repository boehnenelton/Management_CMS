"""
Library:        lib_bejson_Management_scaffold_taxonomy.py
Family:         Web_Framework
Description:    Generic taxonomy-type registry for the Web_Framework scaffold.
                 Registers content types (note, task, link, page, etc.) so a
                 deployed app knows what taxonomies exist and where their
                 individual MFDBs live. Entirely separate from HTML3 — must
                 never import or reference any Lib_PY/HTML module.
Version:        1.0.0
Date:           2026-07-01
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  8f1c2e4a-3b6d-4a7f-9c1e-2d5f7a8b9c01
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

# ---------------------------------------------------------------------------
# COMMON MFDB ENTITY TAXONOMY SCHEMA
# (per Elton's rough-draft spec — TAXONOMY, TYPE, CATEGORY, ID, LABEL,
#  IDX_POSITION, IDX_SORTING, Active, Hidden)
# ---------------------------------------------------------------------------

TAXONOMY_TYPE_SCHEMA = [
    {"name": "taxonomy_id",     "type": "string"},
    {"name": "taxonomy",        "type": "string"},   # note, task, link, page, etc.
    {"name": "type",            "type": "string"},   # optional sub-type
    {"name": "category",        "type": "string"},
    {"name": "label",           "type": "string"},
    {"name": "idx_position",    "type": "integer"},
    {"name": "idx_sorting",     "type": "string"},    # default / date / optional
    {"name": "active",          "type": "boolean"},
    {"name": "hidden",          "type": "boolean"},
    {"name": "mfdb_path",       "type": "string"},    # where this taxonomy's own MFDB manifest lives
    {"name": "created_at",      "type": "string"},
]


def webframework_taxonomy_register_type(
    manifest_path: str,
    taxonomy: str,
    mfdb_path: str,
    type_: Optional[str] = None,
    category: Optional[str] = None,
    label: Optional[str] = None,
    idx_position: int = 0,
    idx_sorting: str = "default",
    active: bool = True,
    hidden: bool = False,
) -> str:
    """Registers a taxonomy type (note, task, link, page, etc.) in the root manifest's TaxonomyType entity."""
    taxonomy_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = [
        taxonomy_id, taxonomy, type_, category, label or taxonomy,
        idx_position, idx_sorting, active, hidden, mfdb_path, created_at,
    ]
    MFDBCore.mfdb_core_add_entity_record(manifest_path, "TaxonomyType", row)
    return taxonomy_id


def webframework_taxonomy_list_types(manifest_path: str) -> List[Dict[str, Any]]:
    """Returns all registered taxonomy types."""
    return MFDBCore.mfdb_core_load_entity(manifest_path, "TaxonomyType")


def webframework_taxonomy_get_type(manifest_path: str, taxonomy_id: str) -> Optional[Dict[str, Any]]:
    """Returns a single taxonomy type record by id, or None."""
    for row in webframework_taxonomy_list_types(manifest_path):
        if row.get("taxonomy_id") == taxonomy_id:
            return row
    return None


def webframework_taxonomy_delete_type(manifest_path: str, taxonomy_id: str) -> bool:
    """Removes a taxonomy type registration by id."""
    rows = webframework_taxonomy_list_types(manifest_path)
    for i, row in enumerate(rows):
        if row.get("taxonomy_id") == taxonomy_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "TaxonomyType", i)
            return True
    return False

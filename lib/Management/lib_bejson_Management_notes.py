"""
Library:        lib_bejson_Management_notes
Family:         Management
Description:    Notes section — Note + NoteCategory CRUD against a
                 dedicated, atomically-separated MFDB. Note's entity
                 schema is built on the common taxonomy baseline (taxonomy,
                 type, category, id, label, idx_position, idx_sorting,
                 active, hidden, created_at) plus its own fields
                 (content, color), per the original spec note's COMMON
                 MFDB ENTITY TAXONOMY SCHEMA. NoteCategory is a lookup
                 table, not itself a taxonomy, and keeps its own simple
                 schema. Independent of the Web_Framework library;
                 Web_Framework only provisions the MFDB shell.
Version:        2.1.0
Date:           2026-07-02
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  4a118e02-362f-470c-84a2-25a1f9127039

CHANGELOG (2.1.0, 2026-07-25): New file — a live-app-only copy of the
original lib_bejson_Management_notes.py, created because Elton asked to fix
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
NOTE_FIELDS = [
    {"name": "content", "type": "string"},
    {"name": "color",   "type": "string"},
]

NOTE_CATEGORY_FIELDS = [
    {"name": "cat_id",         "type": "string"},
    {"name": "cat_name",       "type": "string"},
    {"name": "cat_created_at", "type": "string"},
]

# ---------------------------------------------------------------------------
# Note (taxonomy = "note")
# ---------------------------------------------------------------------------

def management_notes_add(manifest_path: str, title: str, content: str,
                          color: Optional[str] = None, category: Optional[str] = None) -> str:
    note_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # LIVE-COPY FIX (2026-07-25): migrated from a raw positional list to
    # mfdb_core_add_entity_record_by_name(), matching the on-disk Fields
    # order (COMMON_TAXONOMY_FIELDS in lib_bejson_Management_scaffold.py
    # + NOTE_FIELDS, per prepend_common_fields=True in
    # management_bootstrap_deploy()). This file is a live-app-only copy of
    # the original lib_bejson_Management_notes.py — the original is left
    # byte-for-byte untouched since lib_bejson_Management_cli.py still
    # depends on it (Library Immutability), per Elton's instruction to
    # copy rather than modify when in doubt.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Note", {
        "taxonomy": "note", "type": None, "category": category, "id": note_id,
        "label": title, "idx_position": 0, "idx_sorting": "default",
        "active": True, "hidden": False, "created_at": created_at,
        "content": content, "color": color,
    })
    return note_id


def management_notes_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "Note")


def management_notes_update(manifest_path: str, note_id: str, **fields) -> bool:
    notes = management_notes_list(manifest_path)
    for i, n in enumerate(notes):
        if n.get("id") == note_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Note", i, fields)
            return True
    return False


def management_notes_delete(manifest_path: str, note_id: str) -> bool:
    notes = management_notes_list(manifest_path)
    for i, n in enumerate(notes):
        if n.get("id") == note_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Note", i)
            return True
    return False

# ---------------------------------------------------------------------------
# NoteCategory (lookup table, not a taxonomy)
# ---------------------------------------------------------------------------

def management_notes_category_add(manifest_path: str, name: str) -> str:
    cat_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "NoteCategory", {
        "cat_id": cat_id, "cat_name": name, "cat_created_at": created_at,
    })
    return cat_id


def management_notes_category_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "NoteCategory")


def management_notes_category_delete(manifest_path: str, cat_id: str) -> bool:
    cats = management_notes_category_list(manifest_path)
    for i, c in enumerate(cats):
        if c.get("cat_id") == cat_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "NoteCategory", i)
            return True
    return False

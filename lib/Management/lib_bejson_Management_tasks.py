"""
Library:        lib_bejson_Management_tasks
Family:         Management
Description:    Tasks section — TodoItem + TaskCategory CRUD against a
                 dedicated, atomically-separated MFDB. TodoItem's entity
                 schema is built on the common taxonomy baseline (taxonomy,
                 type, category, id, label, idx_position, idx_sorting,
                 active, hidden, created_at) plus its own fields (done,
                 priority, detail). TaskCategory is a lookup table, not
                 itself a taxonomy, mirroring NoteCategory/LinkCategory's
                 structure and self-healing FK-null-out behavior on
                 delete — all three sections now share the identical
                 category framework. Independent of the Web_Framework
                 library; Web_Framework only provisions the MFDB shell.
Version:        3.1.0
Date:           2026-07-04
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  3175a930-6119-4e37-ae5a-43c9de39cbd9

CHANGELOG (3.1.0, 2026-07-25): New file — a live-app-only copy of the
original lib_bejson_Management_tasks.py, created because Elton asked to fix
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

TODO_ITEM_FIELDS = [
    {"name": "done",     "type": "boolean"},
    {"name": "priority", "type": "string"},
    {"name": "detail",   "type": "string"},
]

TASK_CATEGORY_FIELDS = [
    {"name": "cat_id",         "type": "string"},
    {"name": "cat_name",       "type": "string"},
    {"name": "cat_created_at", "type": "string"},
]


def management_tasks_add(manifest_path: str, text: str, priority: Optional[str] = None,
                          detail: Optional[str] = None, category: Optional[str] = None) -> str:
    todo_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # LIVE-COPY FIX (2026-07-25): same pattern as
    # lib_bejson_Management_notes.py — migrated to
    # mfdb_core_add_entity_record_by_name() (COMMON_TAXONOMY_FIELDS +
    # TODO_ITEM_FIELDS). Original lib_bejson_Management_tasks.py untouched.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "TodoItem", {
        "taxonomy": "task", "type": None, "category": category, "id": todo_id,
        "label": text, "idx_position": 0, "idx_sorting": "default",
        "active": True, "hidden": False, "created_at": created_at,
        "done": False, "priority": priority, "detail": detail,
    })
    return todo_id


def management_tasks_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "TodoItem")


def management_tasks_update(manifest_path: str, todo_id: str, **fields) -> bool:
    todos = management_tasks_list(manifest_path)
    for i, t in enumerate(todos):
        if t.get("id") == todo_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "TodoItem", i, fields)
            return True
    return False


def management_tasks_toggle_done(manifest_path: str, todo_id: str) -> bool:
    todos = management_tasks_list(manifest_path)
    for i, t in enumerate(todos):
        if t.get("id") == todo_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "TodoItem", i, "done", not t.get("done"))
            return True
    return False


def management_tasks_delete(manifest_path: str, todo_id: str) -> bool:
    todos = management_tasks_list(manifest_path)
    for i, t in enumerate(todos):
        if t.get("id") == todo_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "TodoItem", i)
            return True
    return False

# ---------------------------------------------------------------------------
# TaskCategory (lookup table, not a taxonomy — mirrors NoteCategory/LinkCategory)
# ---------------------------------------------------------------------------

def management_tasks_category_add(manifest_path: str, name: str) -> str:
    cat_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "TaskCategory", {
        "cat_id": cat_id, "cat_name": name, "cat_created_at": created_at,
    })
    return cat_id


def management_tasks_category_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "TaskCategory")


def management_tasks_category_delete(manifest_path: str, cat_id: str) -> bool:
    """
    Deletes a task category. Self-healing: nulls out the `category` field
    on any tasks that referenced this category, mirroring
    management_links_category_delete / NoteCategory's FK cascade behavior.
    """
    cats = management_tasks_category_list(manifest_path)
    found = False
    for i, c in enumerate(cats):
        if c.get("cat_id") == cat_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "TaskCategory", i)
            found = True
            break
    if not found:
        return False

    for i, t in enumerate(management_tasks_list(manifest_path)):
        if t.get("category") == cat_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "TodoItem", i, "category", None)
    return True

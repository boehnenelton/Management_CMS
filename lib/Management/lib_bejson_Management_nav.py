"""
Library:        lib_bejson_Management_nav
Family:         Management
Description:    Site navigation menu — separate from personal Links.
                 NavLink entries (label, url, target, active toggle) for
                 building a site's nav bar. Not a taxonomy itself; deployed
                 as a secondary entity in the Pages MFDB.

                 Rebuilt from a flat, position-only list ("Option 4") into
                 a true hierarchical tree: parent_id added, sub-menus
                 (dropdowns) now representable, management_nav_get_tree()
                 resolves the flat rows into the nested JSON shape frontend
                 templates expect.

                 Hierarchy validation: every write is checked with
                 lib_bejson_Core_bejson_list_validator.validate_list(),
                 which requires literal "id"/"parent_id" field names in its
                 target doc. This entity's primary key is named "nav_id"
                 (per the System Development Policy's Relational Signalling
                 convention — every field prefixed with its family/group
                 identity), not "id", so a real rename would break every
                 existing caller of management_nav_add/list/update/delete
                 that reads n["nav_id"]. Rather than choose between two bad
                 options (break the API, or skip hierarchy validation
                 entirely), this file builds a small translation view of
                 the loaded entity doc — Fields renamed nav_id->id for
                 validate_list()'s benefit only — before calling it. The
                 real stored file and this module's public API keep using
                 "nav_id" throughout; nothing external sees the rename.
Version:        2.2.0
Date:            2026-07-26
Author:          Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  7a4e9c2f-3d8b-4c1e-9a6f-5b7d2c9e4a83

CHANGELOG (2.2.0, 2026-07-26): Full codebase audit fix. The write-side
positional-list migration in v2.1.0 didn't cover the read side —
management_nav_list() and management_nav_get_tree() still sorted by
n.get("nav_position", 0), the exact same None-vs-int crash class already
fixed in management_cms_content_list_pages()/nav_get_tree() (CMS family).
Fixed with `or 0` in all 3 sort call sites.

CHANGELOG (2.1.0, 2026-07-25): New file — a live-app-only copy of the
original lib_bejson_Management_nav.py, created because Elton asked to fix
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
from lib_bejson_Core_bejson_list_validator import validate_list

NAV_LINK_FIELDS = [
    {"name": "nav_id",       "type": "string"},
    {"name": "parent_id",    "type": "string"},
    {"name": "nav_label",    "type": "string"},
    {"name": "nav_url",      "type": "string"},
    {"name": "nav_target",   "type": "string"},   # _self | _blank
    {"name": "nav_position", "type": "integer"},
    {"name": "nav_active",   "type": "boolean"},
    {"name": "created_at",   "type": "string"},
]


def _validate_hierarchy(manifest_path: str) -> Dict[str, Any]:
    """
    Translation shim: validate_list() needs literal "id"/"parent_id" field
    names. This entity's primary key is "nav_id" (see module docstring for
    why it stays that way in the real stored file and public API). Build a
    shallow-copied doc with just the Fields list's name renamed for this
    call only — Values (positional rows) are untouched, so the row shape
    validate_list() reads is identical either way.
    """
    doc = MFDBCore.mfdb_core_get_entity_doc(manifest_path, "NavLink")
    translated = dict(doc)
    translated["Fields"] = [
        (dict(f, name="id") if f["name"] == "nav_id" else f) for f in doc.get("Fields", [])
    ]
    return validate_list(translated)


def management_nav_add(manifest_path: str, label: str, url: str, target: str = "_self",
                        parent_id: Optional[str] = None, position: Optional[int] = None,
                        active: bool = True) -> str:
    nav_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if position is None:
        position = len(management_nav_list(manifest_path))
    # LIVE-COPY FIX (2026-07-25): migrated from a raw positional list to
    # mfdb_core_add_entity_record_by_name() — NAV_LINK_FIELDS maps 1:1, no
    # common-fields prepend involved for this entity. Original
    # lib_bejson_Management_nav.py untouched (still used by
    # lib_bejson_Management_cli.py).
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "NavLink", {
        "nav_id": nav_id, "parent_id": parent_id, "nav_label": label, "nav_url": url,
        "nav_target": target, "nav_position": position, "nav_active": active,
        "created_at": created_at,
    })
    result = _validate_hierarchy(manifest_path)
    if not result.get("is_valid", False):
        raise ValueError(f"NavLink hierarchy validation failed: {result.get('errors')}")
    return nav_id


def management_nav_list(manifest_path: str, active_only: bool = False) -> List[Dict[str, Any]]:
    items = MFDBCore.mfdb_core_load_entity(manifest_path, "NavLink")
    if active_only:
        items = [n for n in items if n.get("nav_active")]
    # AUDIT FIX (2026-07-26): found during a full-codebase sweep for the
    # same class of bug fixed in management_cms_content_list_pages() and
    # management_cms_nav_get_tree() — .get("nav_position", 0) only
    # defaults when the key is absent, not when it's present with value
    # null. `or 0` handles both.
    items.sort(key=lambda n: n.get("nav_position") or 0)
    return items


def management_nav_update(manifest_path: str, nav_id: str, **fields) -> bool:
    items = MFDBCore.mfdb_core_load_entity(manifest_path, "NavLink")
    for i, n in enumerate(items):
        if n.get("nav_id") == nav_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "NavLink", i, fields)
            if "parent_id" in fields:
                result = _validate_hierarchy(manifest_path)
                if not result.get("is_valid", False):
                    raise ValueError(f"NavLink hierarchy validation failed: {result.get('errors')}")
            return True
    return False


def management_nav_delete(manifest_path: str, nav_id: str) -> bool:
    """
    Per the same re-parenting convention used by management_cms_taxonomy's
    Category delete: any child link (parent_id == nav_id) is promoted to
    root (parent_id -> None) rather than left orphaned.
    """
    items = MFDBCore.mfdb_core_load_entity(manifest_path, "NavLink")
    found_index = None
    for i, n in enumerate(items):
        if n.get("nav_id") == nav_id:
            found_index = i
            break
    if found_index is None:
        return False

    MFDBCore.mfdb_core_remove_entity_record(manifest_path, "NavLink", found_index)

    remaining = MFDBCore.mfdb_core_load_entity(manifest_path, "NavLink")
    for i, n in enumerate(remaining):
        if n.get("parent_id") == nav_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "NavLink", i, "parent_id", None)

    result = _validate_hierarchy(manifest_path)
    if not result.get("is_valid", False):
        raise ValueError(f"NavLink hierarchy validation failed: {result.get('errors')}")
    return True


def management_nav_reorder(manifest_path: str, nav_id_order: list) -> bool:
    """Sibling ordering only — does not touch parent_id, so no hierarchy re-validation needed."""
    items = MFDBCore.mfdb_core_load_entity(manifest_path, "NavLink")
    order_index = {nid: i for i, nid in enumerate(nav_id_order)}
    changed = False
    for i, n in enumerate(items):
        if n.get("nav_id") in order_index:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "NavLink", i, "nav_position", order_index[n["nav_id"]])
            changed = True
    return changed


def management_nav_get_tree(manifest_path: str) -> List[Dict[str, Any]]:
    """Resolve the flat, validated nav_id/parent_id rows into a nested JSON tree, ordered by nav_position at each level."""
    items = management_nav_list(manifest_path)
    node_map = {i["nav_id"]: dict(i, children=[]) for i in items}
    roots = []
    for i in items:
        node = node_map[i["nav_id"]]
        pid = i.get("parent_id")
        if pid and pid in node_map:
            node_map[pid]["children"].append(node)
        else:
            roots.append(node)
    for node in node_map.values():
        # AUDIT FIX (2026-07-26): same `or 0` null-safety fix as
        # management_nav_list() above.
        node["children"].sort(key=lambda n: n.get("nav_position") or 0)
    roots.sort(key=lambda n: n.get("nav_position") or 0)
    return roots

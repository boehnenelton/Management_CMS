"""
Library:        lib_bejson_Management_components.py
Family:         Web_Framework
Description:    Component-level HTML/CSS skeleton system — merges Lineage B's
                 granular component_map + skeleton_store architecture
                 (components addressable and swappable independently) with
                 Lineage A's distribution mechanism (embedded directly in the
                 distributed root MFDB, not left behind in the library, and
                 resyncable after the fact). Replaces the earlier
                 single whole-page Template entity.

                 A component (e.g. "app_shell") owns one or more skeleton
                 rows (html/css/js) tagged with component_id_fk. Skeletons
                 use {{token}} placeholders resolved by the caller — same
                 convention as Lineage B, deliberately kept "dumb" (no
                 conditionals/loops) per the original design intent of never
                 needing much post-scaffold editing.

                 Seeded with ONE component ("app_shell") holding the real,
                 current HB_Framework design verbatim. The multi-component
                 API is fully functional for registering additional
                 components later; this library does not guess at how to
                 split the existing single-page design into further pieces.
Version:        1.1.0
Library_Version: 002
Date:           2026-07-21
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  6b2e9a4d-7c1f-4e8b-9a3d-5f2c8b1e4a97

CHANGELOG (1.1.0, 2026-07-21): Added user_customized field to
SKELETON_STORE_FIELDS and webframework_skeletons_set_customized(), part of
the audit item 4 fix (scaffold_resync_components silently overwriting local
edits). See lib_bejson_Management_scaffold.py changelog for the resync-side
half of this fix.
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

# The Components MFDB ships inside the library itself — canonical source,
# distributed into every app's root MFDB at deploy/resync time.
COMPONENTS_MFDB_ROOT = os.path.join(LIB_DIR, "ComponentsMFDB")
COMPONENTS_MANIFEST = os.path.join(COMPONENTS_MFDB_ROOT, "104a.mfdb.bejson")

COMPONENT_MAP_FIELDS = [
    {"name": "component_id",         "type": "string"},
    {"name": "component_label",      "type": "string"},
    {"name": "html_skeleton_id_fk",  "type": "string"},
    {"name": "css_skeleton_id_fk",   "type": "string"},
    {"name": "js_skeleton_id_fk",    "type": "string"},
    {"name": "component_version",    "type": "string"},
    {"name": "created_at",           "type": "string"},
]

SKELETON_STORE_FIELDS = [
    {"name": "skeleton_id",       "type": "string"},
    {"name": "skeleton_type",     "type": "string"},   # "html" | "css" | "js"
    {"name": "skeleton_content",  "type": "string"},
    {"name": "component_id_fk",   "type": "string"},
    {"name": "created_at",        "type": "string"},
    # Audit item 4 fix (2026-07-21): defaults False on every new row (both
    # canonical and per-app). When True, webframework_scaffold_resync_components()
    # skips overwriting that row's skeleton_content on the app's own copy,
    # so a locally-customized skeleton survives future canonical resyncs
    # instead of being silently clobbered on every app restart. Set via
    # webframework_skeletons_set_customized() — no dashboard toggle wired
    # to it yet; that UI is a separate follow-up (see CHECKLIST.md item 4b).
    {"name": "user_customized",   "type": "boolean"},
]


def webframework_components_init() -> str:
    """Creates the library's canonical Components MFDB if it doesn't already exist. Idempotent."""
    if os.path.exists(COMPONENTS_MANIFEST):
        return COMPONENTS_MANIFEST
    return MFDBCore.mfdb_core_create_database(
        root_dir=COMPONENTS_MFDB_ROOT,
        db_name="Web_Framework Components",
        entities=[
            {"name": "ComponentMap", "file_path": "data/component_map.bejson",
             "primary_key": "component_id", "fields": COMPONENT_MAP_FIELDS},
            {"name": "SkeletonStore", "file_path": "data/skeleton_store.bejson",
             "primary_key": "skeleton_id", "fields": SKELETON_STORE_FIELDS},
        ],
        db_description="Distributed global MFDB holding component-level HTML/CSS/JS skeletons for Web_Framework.",
    )


def webframework_components_register(
    component_id: str,
    label: str,
    html_content: Optional[str] = None,
    css_content: Optional[str] = None,
    js_content: Optional[str] = None,
    version: str = "1.0.0",
) -> str:
    """
    Registers (or re-registers) a component and its skeleton(s) in the
    library's canonical Components MFDB. Any of html/css/js not given is
    left unset for this component. Returns the component_id.
    """
    webframework_components_init()
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing = webframework_components_get_record(component_id)
    html_id = existing["html_skeleton_id_fk"] if existing else None
    css_id = existing["css_skeleton_id_fk"] if existing else None
    js_id = existing["js_skeleton_id_fk"] if existing else None

    if html_content is not None:
        html_id = _upsert_skeleton(html_id, "html", html_content, component_id, created_at)
    if css_content is not None:
        css_id = _upsert_skeleton(css_id, "css", css_content, component_id, created_at)
    if js_content is not None:
        js_id = _upsert_skeleton(js_id, "js", js_content, component_id, created_at)

    records = MFDBCore.mfdb_core_load_entity(COMPONENTS_MANIFEST, "ComponentMap")
    for i, r in enumerate(records):
        if r.get("component_id") == component_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(
                COMPONENTS_MANIFEST, "ComponentMap", i,
                {"component_label": label, "html_skeleton_id_fk": html_id,
                 "css_skeleton_id_fk": css_id, "js_skeleton_id_fk": js_id, "component_version": version},
            )
            return component_id

    MFDBCore.mfdb_core_add_entity_record(
        COMPONENTS_MANIFEST, "ComponentMap",
        [component_id, label, html_id, css_id, js_id, version, created_at],
    )
    return component_id


def _upsert_skeleton(existing_id: Optional[str], skeleton_type: str, content: str,
                      component_id: str, created_at: str) -> str:
    if existing_id:
        records = MFDBCore.mfdb_core_load_entity(COMPONENTS_MANIFEST, "SkeletonStore")
        for i, r in enumerate(records):
            if r.get("skeleton_id") == existing_id:
                MFDBCore.mfdb_core_update_entity_record(COMPONENTS_MANIFEST, "SkeletonStore", i, "skeleton_content", content)
                return existing_id
    skeleton_id = f"sk_{skeleton_type}_{component_id}_{str(uuid.uuid4())[:8]}"
    MFDBCore.mfdb_core_add_entity_record(
        COMPONENTS_MANIFEST, "SkeletonStore",
        [skeleton_id, skeleton_type, content, component_id, created_at, False],
    )
    return skeleton_id


def webframework_skeletons_set_customized(manifest_path: str, skeleton_id: str, customized: bool = True) -> bool:
    """
    Marks (or unmarks) a skeleton row as user-customized on a given app's own
    manifest (NOT the canonical COMPONENTS_MANIFEST — pass the deployed app's
    104a.mfdb.bejson path). While True, webframework_scaffold_resync_components()
    will not overwrite that row's skeleton_content. No dashboard UI calls this
    yet (audit item 4b) — available for direct/scripted use in the meantime.
    """
    records = MFDBCore.mfdb_core_load_entity(manifest_path, "SkeletonStore")
    for i, r in enumerate(records):
        if r.get("skeleton_id") == skeleton_id:
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "SkeletonStore", i, "user_customized", customized)
            return True
    return False


def webframework_components_list() -> List[Dict[str, Any]]:
    webframework_components_init()
    return MFDBCore.mfdb_core_load_entity(COMPONENTS_MANIFEST, "ComponentMap")


def webframework_components_get_record(component_id: str) -> Optional[Dict[str, Any]]:
    for c in webframework_components_list():
        if c.get("component_id") == component_id:
            return c
    return None


def webframework_skeletons_list() -> List[Dict[str, Any]]:
    webframework_components_init()
    return MFDBCore.mfdb_core_load_entity(COMPONENTS_MANIFEST, "SkeletonStore")


def webframework_components_get_html(component_id: str) -> Optional[str]:
    return _get_skeleton_content(COMPONENTS_MANIFEST, component_id, "html")


def webframework_components_get_css(component_id: str) -> Optional[str]:
    return _get_skeleton_content(COMPONENTS_MANIFEST, component_id, "css")


def webframework_components_render_html(component_id: str, token_map: Dict[str, Any]) -> Optional[str]:
    """Retrieves the component's HTML skeleton and resolves {{token}} placeholders. Unknown tokens left as-is."""
    raw = webframework_components_get_html(component_id)
    if raw is None:
        return None
    for k, v in token_map.items():
        raw = raw.replace("{{" + k + "}}", str(v or ""))
    return raw


def _get_skeleton_content(manifest_path: str, component_id: str, kind: str) -> Optional[str]:
    comp_records = MFDBCore.mfdb_core_load_entity(manifest_path, "ComponentMap")
    comp = next((c for c in comp_records if c.get("component_id") == component_id), None)
    if not comp:
        return None
    fk = comp.get(f"{kind}_skeleton_id_fk")
    if not fk:
        return None
    skeletons = MFDBCore.mfdb_core_load_entity(manifest_path, "SkeletonStore")
    row = next((s for s in skeletons if s.get("skeleton_id") == fk), None)
    return row.get("skeleton_content") if row else None


def webframework_components_get_from_manifest(manifest_path: str, component_id: str, kind: str) -> Optional[str]:
    """
    Generic getter: reads a component's html/css/js content from ANY manifest
    that has ComponentMap + SkeletonStore entities — used to pull content out
    of a root MFDB that was already distributed to a target app, as opposed
    to the library's own canonical ComponentsMFDB.
    """
    return _get_skeleton_content(manifest_path, component_id, kind)

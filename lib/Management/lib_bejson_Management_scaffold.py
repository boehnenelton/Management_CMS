"""
Library:        lib_bejson_Management_scaffold.py
Family:         Web_Framework
Description:    Deploys a bare-bones app scaffold: root MFDB (manifest +
                 TaxonomyType entity — the global registry of all
                 taxonomies — plus ComponentMap/SkeletonStore entities
                 carrying the pre-built HTML/CSS component skeletons,
                 embedded directly in this distributed root MFDB). No app
                 data, no HTML3 dependency. Also deploys per-taxonomy
                 templated MFDBs (own manifest/entity + own HTML/CSS,
                 pulled from the already-distributed root) under
                 /Content/<taxonomy>/<mfdb_subfolder>.

                 Merge note: this version replaces the single whole-page
                 Template entity with the granular component_map +
                 skeleton_store architecture (component-addressable HTML/
                 CSS/JS skeletons) — see lib_bejson_Management_components.py.
                 This is groundwork only — the Management library builds
                 actual app functionality on top of a deployed scaffold.
Version:        2.2.0
Library_Version: 003
Date:           2026-07-21
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  a7d4f1e8-3c6b-4a9d-8e5f-2b7c1a4d9e63

CHANGELOG (2.2.0, 2026-07-21): Audit item 4 fix. Both the first-deploy embed
path and webframework_scaffold_resync_components() now write the new
user_customized field (default False). resync_components() skips overwriting
a SkeletonStore row's skeleton_content when the app's own copy has
user_customized=True, so local edits survive future canonical resyncs
instead of being silently clobbered on every restart. The loose
scaffold_template.html/scaffold_style.css rewrite needed no separate fix —
it already reads back from this same (now-protected) entity, not from the
canonical library, so it stays consistent automatically.
"""

import os
import sys
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore
from lib_bejson_Management_scaffold_taxonomy import TAXONOMY_TYPE_SCHEMA
import lib_bejson_Management_scaffold_taxonomy as Taxonomy
import lib_bejson_Management_components as Components

# Default component every scaffold deploy embeds — the real, current
# design, kept as one component until a real decomposition into
# App Shell / Base Panel / Modal / Toolbar (etc.) is specified.
DEFAULT_COMPONENT_ID = "app_shell"

# Common baseline fields every taxonomy's records share, taken verbatim
# from the original spec note's "COMMON MFDB ENTITY TAXONOMY SCHEMA":
# TAXONOMY, TYPE, CATEGORY, ID, LABEL, IDX_POSITION, IDX_SORTING, Active,
# Hidden — placed first in every taxonomy's entity schema, entity-specific
# fields differ after. created_at appended at the end (not in the original
# list, but required by house style for every record).
COMMON_TAXONOMY_FIELDS = [
    {"name": "taxonomy",     "type": "string"},
    {"name": "type",         "type": "string"},
    {"name": "category",     "type": "string"},
    {"name": "id",           "type": "string"},
    {"name": "label",        "type": "string"},
    {"name": "idx_position", "type": "integer"},
    {"name": "idx_sorting",  "type": "string"},
    {"name": "active",       "type": "boolean"},
    {"name": "hidden",       "type": "boolean"},
    {"name": "created_at",   "type": "string"},
]

# Standard category lookup schema — every taxonomy gets one of these
# paired entities by default (e.g. NoteCategory, TaskCategory,
# LinkCategory): cat_id, cat_name, cat_created_at. Not itself a taxonomy —
# never gets COMMON_TAXONOMY_FIELDS.
CATEGORY_LOOKUP_FIELDS = [
    {"name": "cat_id",         "type": "string"},
    {"name": "cat_name",       "type": "string"},
    {"name": "cat_created_at", "type": "string"},
]


def webframework_scaffold_deploy(target_root: str, app_name: str) -> Dict[str, str]:
    """
    Deploys the bare-bones scaffold at target_root:
      - target_root/104a.mfdb.bejson              (manifest)
      - target_root/data/taxonomytype.bejson       (TaxonomyType entity)
      - target_root/data/component_map.bejson      (ComponentMap entity)
      - target_root/data/skeleton_store.bejson     (SkeletonStore entity)
      - target_root/scaffold_template.html         (loose copy of the
        default "app_shell" component's HTML, for convenience)
      - target_root/scaffold_style.css

    After this call, the root MFDB at target_root is self-contained: it
    carries its own copy of every embedded component. Downstream taxonomy
    deploys pull component content from THIS distributed root, not from
    the library again.
    """
    os.makedirs(target_root, exist_ok=True)

    manifest_path = MFDBCore.mfdb_core_create_database(
        root_dir=target_root,
        db_name=app_name,
        entities=[
            {"name": "TaxonomyType", "file_path": "data/taxonomytype.bejson",
             "primary_key": "taxonomy_id", "fields": TAXONOMY_TYPE_SCHEMA},
            {"name": "ComponentMap", "file_path": "data/component_map.bejson",
             "primary_key": "component_id", "fields": Components.COMPONENT_MAP_FIELDS},
            {"name": "SkeletonStore", "file_path": "data/skeleton_store.bejson",
             "primary_key": "skeleton_id", "fields": Components.SKELETON_STORE_FIELDS},
        ],
        db_description=f"Root MFDB for {app_name} — Web_Framework scaffold deployment. Carries its own embedded component skeletons.",
    )

    _embed_all_components(manifest_path)

    template_dest = os.path.join(target_root, "scaffold_template.html")
    style_dest = os.path.join(target_root, "scaffold_style.css")
    with open(template_dest, "w", encoding="utf-8") as f:
        f.write(Components.webframework_components_get_from_manifest(manifest_path, DEFAULT_COMPONENT_ID, "html") or "")
    with open(style_dest, "w", encoding="utf-8") as f:
        f.write(Components.webframework_components_get_from_manifest(manifest_path, DEFAULT_COMPONENT_ID, "css") or "")

    return {
        "manifest_path": manifest_path,
        "taxonomy_entity_path": os.path.join(target_root, "data", "taxonomytype.bejson"),
        "component_map_path": os.path.join(target_root, "data", "component_map.bejson"),
        "skeleton_store_path": os.path.join(target_root, "data", "skeleton_store.bejson"),
        "template_path": template_dest,
        "style_path": style_dest,
    }


def _embed_all_components(manifest_path: str) -> None:
    """Copies every canonical library component + its skeletons into the given root manifest."""
    for comp in Components.webframework_components_list():
        MFDBCore.mfdb_core_add_entity_record(
            manifest_path, "ComponentMap",
            [comp["component_id"], comp["component_label"], comp["html_skeleton_id_fk"],
             comp["css_skeleton_id_fk"], comp["js_skeleton_id_fk"], comp["component_version"], comp["created_at"]],
        )
    for skel in Components.webframework_skeletons_list():
        MFDBCore.mfdb_core_add_entity_record(
            manifest_path, "SkeletonStore",
            [skel["skeleton_id"], skel["skeleton_type"], skel["skeleton_content"],
             skel["component_id_fk"], skel["created_at"], False],
        )


def webframework_scaffold_deploy_taxonomy_mfdb(
    root_manifest_path: str,
    content_root: str,
    taxonomy_label: str,
    entity_name: str,
    entity_fields: list,
    mfdb_subfolder: str = "MFDB",
    prepend_common_fields: bool = True,
    component_id: str = DEFAULT_COMPONENT_ID,
    deploy_category_lookup: bool = True,
    category_entity_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Deploys a per-taxonomy templated MFDB, per the /Content/<taxonomy>/<mfdb_subfolder>
    layout (mfdb_subfolder is caller-supplied since the spec sketch itself is not
    consistent across taxonomies). Also deploys that taxonomy's own HTML/CSS,
    pulled OUT of root_manifest_path (the root MFDB already distributed to this
    app), for the given component_id (defaults to "app_shell").

    prepend_common_fields: defaults to True — every new taxonomy is compatible
    with the common schema by default.

    deploy_category_lookup: defaults to True — STANDARD going forward. Every
    new taxonomy gets its own paired Category lookup entity (cat_id, cat_name,
    cat_created_at — CATEGORY_LOOKUP_FIELDS) in the same MFDB, mirroring
    NoteCategory/TaskCategory/LinkCategory. Pass False to opt out for a
    taxonomy that genuinely doesn't need categories.

    category_entity_name: defaults to f"{entity_name}Category" (e.g. "Note"
    -> "NoteCategory", "Link" -> "LinkCategory"). Override when the entity
    name doesn't match the desired category name (e.g. entity_name="TodoItem"
    but you want "TaskCategory").
    """
    taxonomy_dir = os.path.join(content_root, taxonomy_label)
    mfdb_root = os.path.join(taxonomy_dir, mfdb_subfolder)
    os.makedirs(taxonomy_dir, exist_ok=True)

    if prepend_common_fields:
        existing_names = {f["name"] for f in entity_fields}
        fields = [f for f in COMMON_TAXONOMY_FIELDS if f["name"] not in existing_names] + entity_fields
    else:
        fields = entity_fields

    entities = [{"name": entity_name, "file_path": f"data/{entity_name.lower()}.bejson", "fields": fields}]

    resolved_category_name = category_entity_name or f"{entity_name}Category"
    if deploy_category_lookup:
        entities.append({
            "name": resolved_category_name,
            "file_path": f"data/{resolved_category_name.lower()}.bejson",
            "primary_key": "cat_id",
            "fields": CATEGORY_LOOKUP_FIELDS,
        })

    manifest_path = MFDBCore.mfdb_core_create_database(
        root_dir=mfdb_root,
        db_name=f"{taxonomy_label} MFDB",
        entities=entities,
        db_description=f"Templated MFDB for taxonomy: {taxonomy_label}",
    )

    label_lower = taxonomy_label.lower()
    template_dest = os.path.join(taxonomy_dir, f"{label_lower}_template.html")
    style_dest = os.path.join(taxonomy_dir, f"{label_lower}_style.css")
    template_html = Components.webframework_components_get_from_manifest(root_manifest_path, component_id, "html") or ""
    # AUDIT FIX (LOW #6/#7): the app_shell component's master HTML has
    # `<link href="hb_style.css">` hardcoded — correct for the HB_Framework/
    # copy that's literally named that, wrong for every taxonomy stamped
    # out here, since style_dest (right above) always uses the per-
    # taxonomy name f"{label_lower}_style.css", never "hb_style.css".
    # Traced this as the actual source of the exact same broken-link bug
    # already found (and fixed, file-by-file) across all 11 existing
    # Content/*_template.html copies — without this fix, every FUTURE
    # taxonomy scaffolded through this function reproduces it again.
    # Substituting to the real per-taxonomy filename before writing, so
    # the stamped-out template always points at the file that's actually
    # sitting next to it.
    template_html = template_html.replace('href="hb_style.css"', f'href="{label_lower}_style.css"')
    with open(template_dest, "w", encoding="utf-8") as f:
        f.write(template_html)
    with open(style_dest, "w", encoding="utf-8") as f:
        f.write(Components.webframework_components_get_from_manifest(root_manifest_path, component_id, "css") or "")

    result = {
        "manifest_path": manifest_path,
        "entity_path": os.path.join(mfdb_root, "data", f"{entity_name.lower()}.bejson"),
        "template_path": template_dest,
        "style_path": style_dest,
    }
    if deploy_category_lookup:
        result["category_entity_name"] = resolved_category_name
        result["category_entity_path"] = os.path.join(mfdb_root, "data", f"{resolved_category_name.lower()}.bejson")
    return result


def webframework_scaffold_resync_components(target_root: str) -> Dict[str, Any]:
    """
    Pushes the library's current canonical component/skeleton content out to
    an already-deployed app: updates the root MFDB's own ComponentMap/
    SkeletonStore entities, rewrites the root's loose HTML/CSS files (for the
    default component), then cascades to every taxonomy registered in the
    root's TaxonomyType entity.
    """
    manifest_path = os.path.join(target_root, "104a.mfdb.bejson")

    root_comps = MFDBCore.mfdb_core_load_entity(manifest_path, "ComponentMap")
    root_comp_by_id = {c["component_id"]: i for i, c in enumerate(root_comps)}
    root_skels = MFDBCore.mfdb_core_load_entity(manifest_path, "SkeletonStore")
    root_skel_by_id = {s["skeleton_id"]: i for i, s in enumerate(root_skels)}

    for comp in Components.webframework_components_list():
        cid = comp["component_id"]
        if cid in root_comp_by_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(
                manifest_path, "ComponentMap", root_comp_by_id[cid],
                {"component_label": comp["component_label"], "html_skeleton_id_fk": comp["html_skeleton_id_fk"],
                 "css_skeleton_id_fk": comp["css_skeleton_id_fk"], "js_skeleton_id_fk": comp["js_skeleton_id_fk"],
                 "component_version": comp["component_version"]},
            )
        else:
            MFDBCore.mfdb_core_add_entity_record(
                manifest_path, "ComponentMap",
                [comp["component_id"], comp["component_label"], comp["html_skeleton_id_fk"],
                 comp["css_skeleton_id_fk"], comp["js_skeleton_id_fk"], comp["component_version"], comp["created_at"]],
            )

    for skel in Components.webframework_skeletons_list():
        sid = skel["skeleton_id"]
        if sid in root_skel_by_id:
            existing_row = root_skels[root_skel_by_id[sid]]
            # Audit item 4 fix: previously this ran unconditionally on every
            # startup, silently clobbering any local edit to a deployed
            # app's own skeleton_content. Now skipped whenever the app's
            # own copy is flagged user_customized (see
            # webframework_skeletons_set_customized()).
            if existing_row.get("user_customized"):
                continue
            MFDBCore.mfdb_core_update_entity_record(manifest_path, "SkeletonStore", root_skel_by_id[sid], "skeleton_content", skel["skeleton_content"])
        else:
            MFDBCore.mfdb_core_add_entity_record(
                manifest_path, "SkeletonStore",
                [skel["skeleton_id"], skel["skeleton_type"], skel["skeleton_content"], skel["component_id_fk"], skel["created_at"], False],
            )

    root_template_path = os.path.join(target_root, "scaffold_template.html")
    root_style_path = os.path.join(target_root, "scaffold_style.css")
    # AUDIT FIX (LOW #6/#7): this is the actual write path that produces
    # (and re-produces, on every resync) scaffold_template.html /
    # assets/scaffold_template.html / every Content/*_template.html — the
    # same "href=hb_style.css" hardcoded-filename bug from
    # webframework_scaffold_deploy_taxonomy_mfdb() above lives here too,
    # twice (root, then again in the per-taxonomy loop below). Without
    # this fix, running a resync would silently UNDO the file-by-file
    # fixes already applied to the 11 existing template.html copies.
    root_template_html = (Components.webframework_components_get_from_manifest(manifest_path, DEFAULT_COMPONENT_ID, "html") or "") \
        .replace('href="hb_style.css"', 'href="scaffold_style.css"')
    with open(root_template_path, "w", encoding="utf-8") as f:
        f.write(root_template_html)
    with open(root_style_path, "w", encoding="utf-8") as f:
        f.write(Components.webframework_components_get_from_manifest(manifest_path, DEFAULT_COMPONENT_ID, "css") or "")

    resynced_taxonomies = []
    for t in Taxonomy.webframework_taxonomy_list_types(manifest_path):
        tax_mfdb_path = t.get("mfdb_path")
        if not tax_mfdb_path:
            continue
        # AUDIT FIX (H-4): mfdb_path is stored project-relative now (see
        # webframework_taxonomy_register_type()'s docstring for why), but
        # this function has to keep working against OLDER data that still
        # has the absolute Termux path baked in from before that fix —
        # os.path.isabs() tells us which we've got. target_root is this
        # function's own project-root parameter (already used two lines
        # up for scaffold_template_path/scaffold_style_path), so anchoring
        # a relative mfdb_path here needs no new dependency.
        if not os.path.isabs(tax_mfdb_path):
            tax_mfdb_path = os.path.join(target_root, tax_mfdb_path)
        taxonomy_dir = os.path.dirname(os.path.dirname(tax_mfdb_path))
        if not os.path.isdir(taxonomy_dir):
            continue
        label_lower = (t.get("label") or t.get("taxonomy") or "").lower()
        if not label_lower:
            continue
        # AUDIT FIX (LOW #6/#7): same substitution as the root copy above,
        # per-taxonomy filename this time.
        tax_template_html = (Components.webframework_components_get_from_manifest(manifest_path, DEFAULT_COMPONENT_ID, "html") or "") \
            .replace('href="hb_style.css"', f'href="{label_lower}_style.css"')
        with open(os.path.join(taxonomy_dir, f"{label_lower}_template.html"), "w", encoding="utf-8") as f:
            f.write(tax_template_html)
        with open(os.path.join(taxonomy_dir, f"{label_lower}_style.css"), "w", encoding="utf-8") as f:
            f.write(Components.webframework_components_get_from_manifest(manifest_path, DEFAULT_COMPONENT_ID, "css") or "")
        resynced_taxonomies.append(t.get("label") or t.get("taxonomy"))

    return {"root_template_path": root_template_path, "root_style_path": root_style_path, "resynced_taxonomies": resynced_taxonomies}

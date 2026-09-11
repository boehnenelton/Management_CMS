"""
Library:        lib_bejson_Management_bootstrap.py
Family:         Management
Description:    Deploys the three Management sections (Notes, Tasks, Links)
                 as atomically-separated MFDBs under <app_root>/Content/,
                 using Web_Framework's per-taxonomy scaffold deploy, and
                 registers each in the root TaxonomyType registry. This is
                 the wiring point between Web_Framework (groundwork) and
                 Management (this app's actual sections) — the two remain
                 independent libraries; this module is what connects them
                 for Management_CMS specifically (formerly "Homepage
                 Builder" — the app was renamed, this module's own logic
                 didn't need to change since app_name is just a parameter
                 it's passed).

                 Category lookup entities (NoteCategory/TaskCategory/
                 LinkCategory) are no longer created manually here — they
                 are now deployed automatically by Web_Framework's
                 webframework_scaffold_deploy_taxonomy_mfdb() itself
                 (deploy_category_lookup=True by default, the new
                 ecosystem-wide standard). Tasks needs an explicit
                 category_entity_name override since its entity_name
                 ("TodoItem") doesn't match the desired category name
                 ("TaskCategory").
Version:        5.0.0
Date:           2026-07-04
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  3d7a1e9c-5f2b-4c8d-a1e6-7b9c0d2f3a26
"""

import os
import sys
from typing import Any, Dict

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
WEBFRAMEWORK_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Web_Framework"))
for d in (CORE_DIR, WEBFRAMEWORK_DIR, LIB_DIR):
    if d not in sys.path:
        sys.path.append(d)

import lib_bejson_Management_scaffold as Scaffold
import lib_bejson_Management_scaffold_taxonomy as Taxonomy
from lib_bejson_Management_notes import NOTE_FIELDS
from lib_bejson_Management_tasks import TODO_ITEM_FIELDS
from lib_bejson_Management_links import LINK_FIELDS
from lib_bejson_Management_pages import PAGE_FIELDS, PAGE_SEO_FIELDS
from lib_bejson_Management_landing import LANDING_SECTION_FIELDS
from lib_bejson_Management_media import MEDIA_FIELDS
from lib_bejson_Management_nav import NAV_LINK_FIELDS


def management_bootstrap_deploy(app_root: str, app_name: str) -> Dict[str, Any]:
    """
    Deploys the root Web_Framework scaffold at app_root, then deploys Notes,
    Tasks, and Links each as their own atomically-separated MFDB under
    app_root/Content/, and registers all three in the root TaxonomyType
    registry. Returns manifest paths for each, keyed by section.

    Each taxonomy automatically gets its own Category lookup entity
    (NoteCategory/TaskCategory/LinkCategory) via Web_Framework's default
    deploy_category_lookup=True — that's the standard now, not something
    this module has to wire up by hand.

    Also deploys Pages — the CMS/publishing side of the app, kept
    deliberately separate from the personal-management taxonomies above.
    Built on the exact same MFDBCore/Web_Framework backbone, nothing
    different needed for it. LandingSection is a secondary entity in the
    same Pages MFDB (page_id_fk links back to a Page), not itself a
    taxonomy.
    """
    root = Scaffold.webframework_scaffold_deploy(app_root, app_name)
    content_root = os.path.join(app_root, "Content")

    notes = Scaffold.webframework_scaffold_deploy_taxonomy_mfdb(
        root["manifest_path"], content_root, "Notes", "Note", NOTE_FIELDS,
        mfdb_subfolder="MFDB", prepend_common_fields=True
        # category_entity_name defaults to "NoteCategory" — matches entity_name "Note".
    )

    tasks = Scaffold.webframework_scaffold_deploy_taxonomy_mfdb(
        root["manifest_path"], content_root, "Tasks", "TodoItem", TODO_ITEM_FIELDS,
        mfdb_subfolder="MFDB", prepend_common_fields=True,
        category_entity_name="TaskCategory",  # entity_name "TodoItem" wouldn't default to this
    )

    links = Scaffold.webframework_scaffold_deploy_taxonomy_mfdb(
        root["manifest_path"], content_root, "Links", "Link", LINK_FIELDS,
        mfdb_subfolder="MFDB", prepend_common_fields=True
        # category_entity_name defaults to "LinkCategory" — matches entity_name "Link".
    )

    pages = Scaffold.webframework_scaffold_deploy_taxonomy_mfdb(
        root["manifest_path"], content_root, "Pages", "Page", PAGE_FIELDS,
        mfdb_subfolder="MFDB", prepend_common_fields=True
        # category_entity_name defaults to "PageCategory" — matches entity_name "Page".
    )
    _add_secondary_entity(pages["manifest_path"], "LandingSection", LANDING_SECTION_FIELDS)
    _add_secondary_entity(pages["manifest_path"], "PageSeo", PAGE_SEO_FIELDS)
    _add_secondary_entity(pages["manifest_path"], "Media", MEDIA_FIELDS)
    _add_secondary_entity(pages["manifest_path"], "NavLink", NAV_LINK_FIELDS)

    # AUDIT FIX (H-4): same fix as lib_bejson_Management_init.py's
    # management_cms_init() — mfdb_path used to be stored as whatever
    # absolute path *["manifest_path"] already was, baking in the device
    # path it was created on. root["manifest_path"]'s own directory is
    # this project's root; store each taxonomy's mfdb_path relative to it.
    _root_dir = os.path.dirname(root["manifest_path"])
    def _rel_mfdb_path(p):
        try:
            return os.path.relpath(p, _root_dir)
        except ValueError:
            return p  # different drive on Windows, etc. — fall back to absolute

    Taxonomy.webframework_taxonomy_register_type(
        root["manifest_path"], taxonomy="note", mfdb_path=_rel_mfdb_path(notes["manifest_path"]), label="Notes"
    )
    Taxonomy.webframework_taxonomy_register_type(
        root["manifest_path"], taxonomy="task", mfdb_path=_rel_mfdb_path(tasks["manifest_path"]), label="Tasks"
    )
    Taxonomy.webframework_taxonomy_register_type(
        root["manifest_path"], taxonomy="link", mfdb_path=_rel_mfdb_path(links["manifest_path"]), label="Links"
    )
    Taxonomy.webframework_taxonomy_register_type(
        root["manifest_path"], taxonomy="page", mfdb_path=_rel_mfdb_path(pages["manifest_path"]), label="Pages"
    )

    return {"root": root, "notes": notes, "tasks": tasks, "links": links, "pages": pages}


def _add_secondary_entity(manifest_path: str, entity_name: str, fields: list) -> str:
    """Adds an additional entity file to an already-deployed MFDB manifest (e.g. LandingSection alongside Page)."""
    import lib_bejson_Core_mfdb_core as MFDBCore
    return MFDBCore.mfdb_core_create_entity_file(
        manifest_path=manifest_path,
        entity_name=entity_name,
        file_path_rel=f"data/{entity_name.lower()}.bejson",
        fields=fields,
    )

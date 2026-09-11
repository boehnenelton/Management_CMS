"""
Library:         lib_bejson_Management_init
Family:          management_cms
Description:     Centralized initialization for the management_cms family,
                  per OFFICIAL_PLAN.MD Job B. Scaffolds all five MFDB
                  manifests under Content/ (Section II) using the identical
                  MFDBCore manifest+entity split for Category, Nav, Page,
                  Post, and Media (per Directive 2 — the earlier standalone
                  flat-104a-document workaround for Category/Nav was
                  retired once validate_list() was decoupled from file I/O),
                  registers each into the root TaxonomyType registry via
                  webframework_taxonomy_register_type(), and wires the
                  Section V audit hooks (deep_verify / self_heal /
                  sync_all_counts).
Version:         2.0.0
Library_Version: 002
Date:            2026-07-09
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   8b2d5a9f-3c7e-4b1d-9a5f-2c8e6b3d1f74
"""

import os
import sys
from typing import Any, Dict

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
WEBFRAMEWORK_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Web_Framework"))
for _dir in (CORE_DIR, WEBFRAMEWORK_DIR):
    if _dir not in sys.path:
        sys.path.append(_dir)

import lib_bejson_Core_mfdb_core as MFDBCore
import lib_bejson_Management_scaffold_taxonomy as WebFrameworkTaxonomy

from lib_bejson_Management_taxonomy import CATEGORY_FIELDS, TAG_FIELDS
from lib_bejson_Management_content import PAGE_FIELDS, PAGE_SEO_FIELDS, POST_FIELDS
from lib_bejson_Management_media_cms import MEDIA_FIELDS

# Section II — the five Content/ roots. Per Directive 2, ALL FIVE follow the
# identical MFDBCore manifest+entity split — no special-casing for
# Category/Nav anymore.
_MFDB_LAYOUT = {
    "category": {"root": "Content/Category/MFDB", "db_name": "management_cms_category",
                 "entities": [{"name": "Category", "fields": CATEGORY_FIELDS, "primary_key": "id"}]},
    # Nav entity removed 2026-08-02 library consolidation — was deployed on
    # every new site but never actually used for real navigation (the real
    # Site Nav has always flowed through lib_bejson_Management_nav.py's
    # NavLink entity instead). lib_bejson_management_cms_nav.py deleted.
    "page":     {"root": "Content/Page/MFDB", "db_name": "management_cms_page",
                 "entities": [{"name": "Page", "fields": PAGE_FIELDS, "primary_key": "id"},
                              {"name": "PageSeo", "fields": PAGE_SEO_FIELDS, "primary_key": "seo_id"}]},
    "post":     {"root": "Content/Post/MFDB", "db_name": "management_cms_post",
                 "entities": [{"name": "Post", "fields": POST_FIELDS, "primary_key": "id"},
                              {"name": "Tag", "fields": TAG_FIELDS, "primary_key": "id"}]},
    "media":    {"root": "Content/media/MFDB", "db_name": "management_cms_media",
                 "entities": [{"name": "Media", "fields": MEDIA_FIELDS, "primary_key": "id"}]},
}


def management_cms_init(project_root: str, root_manifest_path: str,
                         taxonomy_prefix: str = "") -> Dict[str, str]:
    """
    Scaffold all five Section II MFDB manifests under project_root/, and
    register each into the app's root TaxonomyType registry
    (root_manifest_path). Idempotent — an entity whose 104a.mfdb.bejson
    already exists at its target path is left untouched, not recreated,
    AND is not re-registered into TaxonomyType a second time (fixed —
    webframework_taxonomy_register_type() always appends a new row with no
    dedup of its own, so calling this on every app startup without this
    guard would spam duplicate rows every single restart).

    taxonomy_prefix: prepended to each of "category"/"nav"/"page"/"post"/
    "media" before registering (e.g. "cms_" -> "cms_page"). Needed for apps
    (like Management_CMS) that already register a bare "page"/"nav"/
    "media" taxonomy for an unrelated, pre-existing manifest — registering
    this family's Page/Nav/Media under the same bare name would be two
    different manifests both claiming the same logical taxonomy name in
    the registry. Defaults to "" (preserves prior behavior for callers with
    no naming collision).

    Returns {taxonomy_name: manifest_path} for all five (keys include the
    prefix if one was given) — identical shape for Category/Nav/Page/Post/
    Media, per Target State Verification.
    """
    results: Dict[str, str] = {}
    existing_taxonomies = None  # lazily loaded, only if root_manifest_path already has entries

    for name, spec in _MFDB_LAYOUT.items():
        taxonomy_name = f"{taxonomy_prefix}{name}"
        entity_root = os.path.join(project_root, spec["root"])
        manifest_path = os.path.join(entity_root, "104a.mfdb.bejson")
        newly_created = not os.path.exists(manifest_path)

        if newly_created:
            manifest_path = MFDBCore.mfdb_core_create_database(
                root_dir=entity_root, db_name=spec["db_name"], entities=spec["entities"],
                db_description=f"management_cms {name} entity — public hosting layer",
            )

        already_registered = False
        if not newly_created:
            if existing_taxonomies is None:
                existing_taxonomies = WebFrameworkTaxonomy.webframework_taxonomy_list_types(root_manifest_path)
            already_registered = any(t.get("taxonomy") == taxonomy_name for t in existing_taxonomies)

        if not already_registered:
            # AUDIT FIX (H-4): mfdb_path used to be stored as whatever
            # absolute path manifest_path already was (SCRIPT_PATH is
            # always absolute per this project's self-locating-script
            # convention) — meaning every TaxonomyType row baked in the
            # exact device path it was created on, breaking on any other
            # machine/copy of the project (verified: scaffold.py's resync
            # step silently no-ops everywhere downstream of this once the
            # path doesn't exist locally). Storing it relative to the
            # project root (root_manifest_path's own directory) instead —
            # scaffold.py's consumer now re-anchors a relative mfdb_path
            # against its own target_root parameter at read time.
            root_dir = os.path.dirname(root_manifest_path)
            try:
                stored_mfdb_path = os.path.relpath(manifest_path, root_dir)
            except ValueError:
                stored_mfdb_path = manifest_path  # different drive on Windows, etc. — fall back to absolute
            WebFrameworkTaxonomy.webframework_taxonomy_register_type(
                root_manifest_path, taxonomy=taxonomy_name, type_="management_cms",
                category="public_hosting", label=name.capitalize(), mfdb_path=stored_mfdb_path,
            )

        results[taxonomy_name] = manifest_path

    return results


def management_cms_audit(manifest_path: str) -> Dict[str, Any]:
    """
    Section V audit hook: sync record counts, deep-verify, self-heal on any
    fixable finding. Run after any data-migration pass and before every
    static-site export. Works identically across all five taxonomies now
    that Category/Nav share the same manifest pattern as Page/Post/Media —
    the Target State Verification requirement.
    """
    sync_result = MFDBCore.mfdb_core_sync_all_counts(manifest_path)
    verify_result = MFDBCore.mfdb_core_deep_verify(manifest_path)
    heal_result = None
    if verify_result:
        # Any finding at all (COUNT_MISMATCH, POSITIONAL_VIOLATION, MISSING_FILE, ...)
        # is worth an mfdb_core_self_heal() pass — it no-ops safely on findings it
        # can't fix and reports "remaining_errors" for those, per its own docstring.
        heal_result = MFDBCore.mfdb_core_self_heal(manifest_path)
    return {"sync": sync_result, "verify": verify_result, "heal": heal_result}

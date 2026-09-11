"""
Library:        lib_bejson_Management_cli.py
Family:         Management
Description:    Terminal-native CLI core for this app — no web admin
                 needed. Wraps the existing stateless Management/
                 Web_Framework functions in a small stateful project
                 object so a CLI (or any script) doesn't have to
                 re-resolve manifest paths on every call.

                 Adapted from a third-party CLI tool evaluated for value
                 (it was independently built on top of an earlier
                 snapshot of these exact libraries). Renamed out of a
                 conflicting "CMS" family into Management, where it
                 belongs. Improvement carried over from that tool: manifest
                 paths are resolved dynamically through the TaxonomyType
                 registry (_get_taxonomy_manifest) rather than hardcoded
                 Content/<Section>/MFDB paths — this is a better pattern
                 than app.py's current hardcoded constants and should be
                 considered for app.py too.
Version:        1.0.1
Date:           2026-07-26
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  8b2e5c9f-3a7d-4c1e-9f6b-2d8a5c9e4f71

CHANGELOG (1.0.1, 2026-07-26): Dead-code sweep. Removed 3 unused imports —
management_tasks_toggle_done, management_landing_update_section,
management_landing_remove_section — each confirmed to appear nowhere else
in this file (imported but no CLI menu path ever calls them). The
underlying functions themselves are untouched in their source libraries;
only the redundant import names here were removed. No CLI behavior
changes — confirmed the module still imports cleanly.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
WEBFRAMEWORK_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Web_Framework"))
for d in (CORE_DIR, WEBFRAMEWORK_DIR, LIB_DIR):
    if d not in sys.path:
        sys.path.append(d)

import lib_bejson_Core_mfdb_core as MFDBCore
import lib_bejson_Management_scaffold_taxonomy as Taxonomy

from lib_bejson_Management_bootstrap import management_bootstrap_deploy
from lib_bejson_Management_config import management_config_load, management_config_save, management_config_get_settings_list
from lib_bejson_Management_notes import (management_notes_add, management_notes_list, management_notes_update,
                                          management_notes_delete, management_notes_category_add,
                                          management_notes_category_list, management_notes_category_delete)
from lib_bejson_Management_tasks import (management_tasks_add, management_tasks_list, management_tasks_update,
                                          management_tasks_delete,
                                          management_tasks_category_add, management_tasks_category_list,
                                          management_tasks_category_delete)
from lib_bejson_Management_links import (management_links_add, management_links_list, management_links_update,
                                          management_links_delete, management_links_category_add,
                                          management_links_category_list, management_links_category_delete)
from lib_bejson_Management_pages import (management_pages_add, management_pages_list, management_pages_get,
                                          management_pages_update, management_pages_delete,
                                          management_pages_publish, management_pages_archive,
                                          management_pages_seo_set, management_pages_seo_get,
                                          management_pages_category_add, management_pages_category_list,
                                          management_pages_category_delete)
from lib_bejson_Management_landing import (management_landing_add_section, management_landing_get_sections,
                                            management_landing_reorder_sections, management_landing_render_sections)
from lib_bejson_Management_media import (management_media_add, management_media_list, management_media_get,
                                          management_media_delete)
from lib_bejson_Management_nav import (management_nav_add, management_nav_list, management_nav_update,
                                        management_nav_delete, management_nav_reorder)
from lib_bejson_Management_build import management_build_render_homepage, management_build_write_export


class ManagementCLIProject:
    """
    Stateful project handle for CLI/script use — resolves manifest paths
    once via the TaxonomyType registry and exposes every Management
    function pre-bound to this project's root. The underlying library
    functions stay stateless; this is purely an ergonomic wrapper.
    """

    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.root_manifest = os.path.join(self.project_root, "104a.mfdb.bejson")

    def exists(self) -> bool:
        return os.path.isfile(self.root_manifest)

    def init_project(self, site_name: str) -> Dict[str, Any]:
        if self.exists():
            raise FileExistsError(f"Project already exists at {self.project_root}")
        return management_bootstrap_deploy(self.project_root, site_name)

    def _get_taxonomy_manifest(self, taxonomy: str) -> Optional[str]:
        """Resolves a section's MFDB manifest path via the TaxonomyType registry, not a hardcoded path."""
        if not self.exists():
            return None
        for t in Taxonomy.webframework_taxonomy_list_types(self.root_manifest):
            if t.get("taxonomy") == taxonomy:
                mfdb_path = t.get("mfdb_path")
                # AUDIT FIX (H-4): mfdb_path may be an older absolute
                # (device-specific) path or the current project-relative
                # form — self.project_root is always absolute
                # (os.path.abspath in __init__), so re-anchoring a
                # relative value here is safe and a no-op for absolute ones.
                if mfdb_path and not os.path.isabs(mfdb_path):
                    mfdb_path = os.path.join(self.project_root, mfdb_path)
                return mfdb_path
        return None

    # ---- Pages -----------------------------------------------------

    def page_create(self, title: str, **kwargs) -> str:
        manifest = self._require_manifest("page")
        return management_pages_add(manifest, title, **kwargs)

    def page_list(self, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        if not manifest:
            return []
        pages = management_pages_list(manifest)
        if status and status != "all":
            pages = [p for p in pages if p.get("status") == status]
        if category:
            pages = [p for p in pages if p.get("category") == category]
        return pages

    def page_get(self, page_id: str) -> Optional[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_pages_get(manifest, page_id=page_id) if manifest else None

    def page_update(self, page_id: str, **fields) -> bool:
        manifest = self._require_manifest("page")
        return management_pages_update(manifest, page_id, **fields)

    def page_delete(self, page_id: str) -> bool:
        manifest = self._require_manifest("page")
        return management_pages_delete(manifest, page_id)

    def page_publish(self, page_id: str) -> bool:
        manifest = self._require_manifest("page")
        return management_pages_publish(manifest, page_id)

    def page_archive(self, page_id: str) -> bool:
        manifest = self._require_manifest("page")
        return management_pages_archive(manifest, page_id)

    # ---- Page Category ----------------------------------------------

    def category_create(self, name: str) -> str:
        return management_pages_category_add(self._require_manifest("page"), name)

    def category_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_pages_category_list(manifest) if manifest else []

    def category_delete(self, cat_id: str) -> bool:
        return management_pages_category_delete(self._require_manifest("page"), cat_id)

    # ---- SEO ---------------------------------------------------------

    def seo_set(self, page_id: str, **seo_fields) -> str:
        return management_pages_seo_set(self._require_manifest("page"), page_id, **seo_fields)

    def seo_get(self, page_id: str) -> Optional[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_pages_seo_get(manifest, page_id) if manifest else None

    # ---- Landing sections ---------------------------------------------

    def landing_add_section(self, page_id: str, section_type: str, section_data: dict, idx_position: Optional[int] = None) -> str:
        return management_landing_add_section(self._require_manifest("page"), page_id, section_type, section_data, idx_position)

    def landing_get_sections(self, page_id: str) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_landing_get_sections(manifest, page_id) if manifest else []

    def landing_reorder(self, page_id: str, section_id_order: list) -> bool:
        return management_landing_reorder_sections(self._require_manifest("page"), page_id, section_id_order)

    def landing_render(self, page_id: str, primary_color: str = "#DE2626") -> str:
        manifest = self._get_taxonomy_manifest("page")
        return management_landing_render_sections(manifest, page_id, primary_color) if manifest else ""

    # ---- Media ---------------------------------------------------------

    def media_add(self, filename: str, original_path: str, file_type: str, **kwargs) -> str:
        return management_media_add(self._require_manifest("page"), filename, original_path, file_type, **kwargs)

    def media_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_media_list(manifest) if manifest else []

    def media_delete(self, media_id: str) -> bool:
        return management_media_delete(self._require_manifest("page"), media_id)

    # ---- Navigation -----------------------------------------------------

    def nav_add(self, label: str, url: str, target: str = "_self") -> str:
        return management_nav_add(self._require_manifest("page"), label, url, target)

    def nav_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_nav_list(manifest, active_only) if manifest else []

    def nav_delete(self, nav_id: str) -> bool:
        return management_nav_delete(self._require_manifest("page"), nav_id)

    def nav_reorder(self, nav_id_order: list) -> bool:
        return management_nav_reorder(self._require_manifest("page"), nav_id_order)

    # ---- Notes / Tasks / Links passthroughs (personal management side) --

    def note_add(self, title: str, content: str, **kwargs) -> str:
        return management_notes_add(self._require_manifest("note"), title, content, **kwargs)

    def note_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("note")
        return management_notes_list(manifest) if manifest else []

    def task_add(self, text: str, **kwargs) -> str:
        return management_tasks_add(self._require_manifest("task"), text, **kwargs)

    def task_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("task")
        return management_tasks_list(manifest) if manifest else []

    def link_add(self, title: str, url: str, **kwargs) -> str:
        return management_links_add(self._require_manifest("link"), title, url, **kwargs)

    def link_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("link")
        return management_links_list(manifest) if manifest else []

    # ---- Link health check (real HTTP, not stubbed) ---------------------

    def check_link_health(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        try:
            import requests
            resp = requests.head(url, timeout=timeout, allow_redirects=True,
                                  headers={"User-Agent": "BEJSON-Management-LinkChecker/1.0"})
            return {"url": url, "status_code": resp.status_code, "reachable": resp.status_code < 400}
        except Exception as e:
            return {"url": url, "status_code": 0, "reachable": False, "error": str(e)}

    def link_audit(self) -> List[Dict[str, Any]]:
        """Checks every personal Link's health. Real HTTP calls, not stubbed."""
        results = []
        for link in self.link_list():
            check = self.check_link_health(link.get("url", ""))
            results.append({**check, "link_id": link.get("id"), "title": link.get("label")})
        return results

    # ---- Config ------------------------------------------------------

    def config_get_all(self) -> Dict[str, Any]:
        return management_config_load(self.project_root)

    def config_update(self, updates: Dict[str, Any]) -> None:
        management_config_save(self.project_root, updates)

    def config_get_settings(self) -> List[Dict[str, str]]:
        return management_config_get_settings_list(self.project_root)

    # ---- Build ---------------------------------------------------------

    def build_site(self, export_dir: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.config_get_all()
        links = self.link_list()
        notes_manifest = self._get_taxonomy_manifest("note")
        tasks_manifest = self._get_taxonomy_manifest("task")
        notes = management_notes_list(notes_manifest) if notes_manifest else []
        tasks = management_tasks_list(tasks_manifest) if tasks_manifest else []
        cats_grouped: Dict[str, list] = {}
        for l in links:
            cats_grouped.setdefault(l.get("category") or "Uncategorized", []).append(
                {"url": l.get("url"), "label": l.get("label"), "icon": l.get("icon"), "description": l.get("description")}
            )
        html = management_build_render_homepage(cfg, cats_grouped, notes, tasks)
        return management_build_write_export(export_dir or os.path.join(self.project_root, "Export"), html)

    # ---- Internal --------------------------------------------------------

    def _require_manifest(self, taxonomy: str) -> str:
        manifest = self._get_taxonomy_manifest(taxonomy)
        if not manifest:
            raise RuntimeError(f'"{taxonomy}" taxonomy not found — is this project initialized?')
        return manifest

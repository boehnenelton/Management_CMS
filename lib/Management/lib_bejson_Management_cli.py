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
import re
import sys
import shutil
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
WEBFRAMEWORK_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Web_Framework"))
for d in (CORE_DIR, WEBFRAMEWORK_DIR, LIB_DIR):
    if d not in sys.path:
        sys.path.append(d)

import lib_bejson_Core_mfdb_core as MFDBCore
import lib_bejson_Management_scaffold_taxonomy as Taxonomy
import lib_bejson_Management_init as CmsInit

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
# AUDIT FIX (2026-09-24): Pages/Category/SEO used to come from
# lib_bejson_Management_pages.py, which wrote to the taxonomy-scaffold
# "Content/Pages" (plural) Page entity — a schema fork the real web app
# (app.py) never reads or writes; see that module's docstring for the full
# trace. Now sourced from the same lib_bejson_Management_content.py /
# lib_bejson_Management_taxonomy.py functions app.py itself calls, against
# the same cms_page/cms_category manifests, via self._cms_manifest() below
# — one Page/PageSeo/Category implementation, reachable identically from
# the CLI and the web admin.
from lib_bejson_Management_content import (management_cms_content_create_page, management_cms_content_list_pages,
                                            management_cms_content_get_page, management_cms_content_update_page,
                                            management_cms_content_delete_page,
                                            management_cms_content_seo_set, management_cms_content_seo_get,
                                            management_cms_content_create_post, management_cms_content_list_posts,
                                            management_cms_content_get_post, management_cms_content_update_post,
                                            management_cms_content_delete_post, management_cms_content_publish_post,
                                            management_cms_content_archive_post)
from lib_bejson_Management_taxonomy import (management_cms_taxonomy_add_category, management_cms_taxonomy_get_categories,
                                             management_cms_taxonomy_delete_category)
# AUDIT FIX (2026-09-26): app.py's /api/pages*//api/posts* create/update
# routes always run content through this exact lint -> sanitize (with
# markdown-render first when content_markdown was supplied without
# content_html) pipeline before storage — content_html is baked verbatim
# into the public static-site export, so skipping it is a real stored-XSS
# gap, not just a data-consistency one. page_create/page_update below now
# run through it too (they didn't before this fix), as does the new
# post_create/post_update. See lib_bejson_Management_content_safety.py's
# own docstring for why this lives in a shared module instead of being
# hand-copied here.
from lib_bejson_Management_content_safety import _lint_content_html, _sanitize_content_html, _render_markdown
from lib_bejson_Management_landing import (management_landing_add_section, management_landing_get_sections,
                                            management_landing_reorder_sections, management_landing_render_sections)
from lib_bejson_Management_media import (management_media_add, management_media_list, management_media_get,
                                          management_media_delete)
from lib_bejson_Management_media_cms import (management_cms_media_add, management_cms_media_list,
                                              management_cms_media_delete)
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

    def _cms_manifest(self, section: str) -> str:
        """
        Resolves a management_cms Content/ manifest ("page", "category",
        "post", "media") the same way app.py does: via
        management_cms_init(), which is idempotent and safe to call every
        time (no-ops on manifests that already exist, doesn't re-register
        an already-registered taxonomy — see that function's docstring).
        This makes Pages/Category/SEO CLI calls work whether the project
        was originally bootstrapped by app.py's first web request or by
        this CLI's init_project(), without needing a separate migration
        step for older CLI-only projects.
        """
        if not self.exists():
            raise RuntimeError(f'"{section}" not found — is this project initialized?')
        manifests = CmsInit.management_cms_init(self.project_root, self.root_manifest, taxonomy_prefix="cms_")
        return manifests[f"cms_{section}"]

    def _apply_content_safety(self, fields: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        """
        Mirrors app.py's create_page()/create_post() (force=True: always
        runs, content_html defaults to "") and update_page()/update_post()
        (force=False: only runs if "content_html" was actually supplied)
        inline content-safety block — markdown-render content_markdown
        into content_html first if content_html wasn't explicitly given,
        then lint (raises ValueError on malformed markup, mirroring
        app.py's 400 response) and sanitize whatever's left before it's
        ever persisted. Returns a new dict; never mutates the caller's.
        """
        fields = dict(fields)
        if fields.get("content_markdown") and not fields.get("content_html"):
            fields["content_html"] = _render_markdown(fields["content_markdown"])
        if force or "content_html" in fields:
            issues = _lint_content_html(fields.get("content_html", ""))
            if issues:
                raise ValueError("content_html has malformed markup: " + "; ".join(issues))
            fields["content_html"] = _sanitize_content_html(fields.get("content_html", ""))
        return fields

    # ---- Pages -----------------------------------------------------
    # Backed by lib_bejson_Management_content.py — the same implementation
    # app.py's /api/pages* routes use. See _cms_manifest() above and
    # lib_bejson_Management_pages.py's docstring for why this no longer
    # goes through that module.

    def page_create(self, title: str, **kwargs) -> str:
        kwargs = self._apply_content_safety(kwargs, force=True)
        return management_cms_content_create_page(self._cms_manifest("page"), title, **kwargs)

    def page_list(self, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        return management_cms_content_list_pages(
            self._cms_manifest("page"), status=status if status != "all" else None, category_id_fk=category)

    def page_get(self, page_id: str) -> Optional[Dict[str, Any]]:
        return management_cms_content_get_page(self._cms_manifest("page"), page_id=page_id)

    def page_update(self, page_id: str, **fields) -> bool:
        fields = self._apply_content_safety(fields, force=False)
        return management_cms_content_update_page(self._cms_manifest("page"), page_id, **fields)

    def page_delete(self, page_id: str) -> bool:
        return management_cms_content_delete_page(self._cms_manifest("page"), page_id)

    def page_publish(self, page_id: str) -> bool:
        return management_cms_content_update_page(self._cms_manifest("page"), page_id, status="published")

    def page_archive(self, page_id: str) -> bool:
        return management_cms_content_update_page(self._cms_manifest("page"), page_id, status="archived")

    # ---- Page Category ----------------------------------------------
    # Backed by lib_bejson_Management_taxonomy.py's shared Category entity
    # (category_type="page" discriminator) — the same one app.py's
    # /api/categories routes use, not a page-only lookup table.

    def category_create(self, name: str) -> str:
        return management_cms_taxonomy_add_category(self._cms_manifest("category"), name, category_type="page")

    def category_list(self) -> List[Dict[str, Any]]:
        return management_cms_taxonomy_get_categories(self._cms_manifest("category"), category_type="page")

    def category_delete(self, cat_id: str) -> bool:
        if not management_cms_taxonomy_delete_category(self._cms_manifest("category"), cat_id):
            return False
        # AUDIT FIX (2026-09-24): mirrors app.py's delete_category() route —
        # the taxonomy delete only re-parents child categories, it can't
        # reach Page/Post's manifests, so anything that referenced this
        # category would keep a category_id_fk pointing at nothing. Sweep
        # both and null the FK, logging (not silently swallowing) any
        # individual cleanup failure — same DAT-02 floor app.py applies.
        # The category is gone either way; this loop is best-effort cleanup.
        page_manifest = self._cms_manifest("page")
        for page in management_cms_content_list_pages(page_manifest):
            if page.get("category_id_fk") == cat_id:
                try:
                    management_cms_content_update_page(page_manifest, page["id"], category_id_fk=None)
                except Exception as e:
                    log.error("category_delete(%s): failed to clear page %s: %s", cat_id, page.get("id"), e)
        post_manifest = self._cms_manifest("post")
        for post in management_cms_content_list_posts(post_manifest, status=None):
            if post.get("category_id_fk") == cat_id:
                try:
                    management_cms_content_update_post(post_manifest, post["id"], category_id_fk=None)
                except Exception as e:
                    log.error("category_delete(%s): failed to clear post %s: %s", cat_id, post.get("id"), e)
        return True

    # ---- Posts ---------------------------------------------------------
    # Same implementation app.py's /api/posts* routes use, same pattern
    # as Pages above (added 2026-09-26 — previously the CLI had no post
    # management at all).

    def post_create(self, title: str, **kwargs) -> str:
        kwargs = self._apply_content_safety(kwargs, force=True)
        return management_cms_content_create_post(self._cms_manifest("post"), title, **kwargs)

    def post_list(self, status: Optional[str] = "published", category: Optional[str] = None) -> List[Dict[str, Any]]:
        return management_cms_content_list_posts(
            self._cms_manifest("post"), status=status if status != "all" else None, category_id_fk=category)

    def post_get(self, post_id: str) -> Optional[Dict[str, Any]]:
        return management_cms_content_get_post(self._cms_manifest("post"), post_id=post_id)

    def post_update(self, post_id: str, **fields) -> bool:
        fields = self._apply_content_safety(fields, force=False)
        return management_cms_content_update_post(self._cms_manifest("post"), post_id, **fields)

    def post_delete(self, post_id: str) -> bool:
        return management_cms_content_delete_post(self._cms_manifest("post"), post_id)

    def post_publish(self, post_id: str) -> bool:
        return management_cms_content_publish_post(self._cms_manifest("post"), post_id)

    def post_archive(self, post_id: str) -> bool:
        return management_cms_content_archive_post(self._cms_manifest("post"), post_id)

    # ---- Post Category ------------------------------------------------
    # Same shared Category entity as Page Category, category_type="post".
    # post_category_delete is just category_delete — the FK self-heal
    # sweep there already clears both Page and Post regardless of which
    # type the deleted category was.

    def post_category_create(self, name: str) -> str:
        return management_cms_taxonomy_add_category(self._cms_manifest("category"), name, category_type="post")

    def post_category_list(self) -> List[Dict[str, Any]]:
        return management_cms_taxonomy_get_categories(self._cms_manifest("category"), category_type="post")

    def post_category_delete(self, cat_id: str) -> bool:
        return self.category_delete(cat_id)

    # ---- SEO ---------------------------------------------------------

    def seo_set(self, page_id: str, **seo_fields) -> str:
        return management_cms_content_seo_set(self._cms_manifest("page"), page_id, **seo_fields)

    def seo_get(self, page_id: str) -> Optional[Dict[str, Any]]:
        return management_cms_content_seo_get(self._cms_manifest("page"), page_id)

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
    # AUDIT FIX (2026-09-24): app.py's upload_media()/delete_media() always
    # keep two records in sync per file — the admin Media row (this
    # Pages-manifest entity) and its CmsMedia sibling in cms_media (see
    # media_cms.py's DAT-03 fix), FK'd by admin_media_id. This CLI's
    # media_add/media_delete previously only ever touched the admin side,
    # so anything added here was invisible to the static-site build
    # (management_cms_static_build() reads cms_media, not the admin Media
    # entity) — a real, reachable gap of the same shape as the Page bug
    # above, not just a theoretical one. Now creates/removes both, exactly
    # matching app.py's own DAT-03 logic (delete matches by admin_media_id
    # first, falling back to original_path for pre-DAT-03 records).

    def _uploads_dir(self) -> str:
        return os.path.join(self.project_root, "Content", "media", "uploads")

    def _is_managed_path(self, path: str) -> bool:
        """
        True only if path resolves inside this project's own Content/ tree
        (symlinks resolved) — that covers both the uploads copy and the
        WebP sibling media.py writes under the manifest's own media/ dir.
        Anything outside (e.g. a record registered against an external
        path) is never treated as ours to delete.
        """
        real = os.path.realpath(path if os.path.isabs(path) else os.path.join(self.project_root, path))
        root = os.path.realpath(os.path.join(self.project_root, "Content"))
        return real == root or real.startswith(root + os.sep)

    def media_add(self, filename: str, original_path: str, file_type: str, **kwargs) -> str:
        # AUDIT FIX (2026-09-28): like app.py's upload_media(), copy the file
        # into the project-owned Content/media/uploads/ and register THAT
        # copy. Registering the caller's file in place meant the project
        # depended on an arbitrary external path (move/delete it and the
        # static build breaks) and left media_delete() nothing it could
        # safely clean up — deleting a file the project doesn't own would
        # destroy the user's data. Missing source files register as-is
        # (external/metadata-only), same as before.
        if os.path.isfile(original_path):
            os.makedirs(self._uploads_dir(), exist_ok=True)
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename or original_path)) or "file"
            dest = os.path.join(self._uploads_dir(), f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{safe}")
            shutil.copy2(original_path, dest)
            original_path = dest
        admin_media_id = management_media_add(self._require_manifest("page"), filename, original_path,
                                               file_type, **kwargs)
        management_cms_media_add(self._cms_manifest("media"), filename, original_path,
                                  mime_type=kwargs.get("mime_type"), alt_text=kwargs.get("alt_text", ""),
                                  admin_media_id=admin_media_id)
        return admin_media_id

    def media_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("page")
        return management_media_list(manifest) if manifest else []

    def media_delete(self, media_id: str) -> bool:
        record = management_media_get(self._require_manifest("page"), media_id)
        if not record:
            return False
        # AUDIT FIX (2026-09-28): mirrors app.py's delete_media() — remove the
        # physical file and its WebP sibling, not just the metadata row (the
        # storage leak). Only files inside this project's own uploads dir are
        # ever unlinked (realpath containment), so a record pointing at an
        # external path can never cause deletion of a file the project
        # doesn't own. Best-effort: a filesystem hiccup is logged, not fatal.
        for field in ("original_path", "webp_path"):
            p = record.get(field)
            if p and self._is_managed_path(p):
                fp = p if os.path.isabs(p) else os.path.join(self.project_root, p)
                try:
                    os.unlink(fp)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    log.error("media_delete(%s): could not remove %s: %s", media_id, fp, e)
        if not management_media_delete(self._require_manifest("page"), media_id):
            return False

        cms_manifest = self._cms_manifest("media")
        cms_records = management_cms_media_list(cms_manifest)
        matched = next((r for r in cms_records if r.get("admin_media_id") == media_id), None)
        if not matched:
            original_path = record.get("original_path")
            if original_path:
                matched = next((r for r in cms_records if r.get("original_path") == original_path), None)
        if matched:
            management_cms_media_delete(cms_manifest, matched.get("id"))
        return True

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
    # update/delete/category_* added 2026-09-26 — previously only add/list
    # existed here despite the underlying functions already being
    # imported. category_add replicates app.py's case-insensitive
    # duplicate-name guard (409 there; ValueError here) — that check
    # lives in the route, not the library function, so it would otherwise
    # be silently missing for CLI-created categories.
    #
    # AUDIT FIX (2026-09-26, found via smoke test): Note/TodoItem/Link
    # entities don't have a real "title"/"text" field — the display name
    # is the generic taxonomy "label" field. management_notes_add() (and
    # its Task/Link siblings) already translate their friendly title/text
    # param to label=... internally, but management_notes_update() (and
    # siblings) are raw **fields passthroughs with no such translation —
    # calling update(id, title="...") doesn't silently do the wrong
    # thing, it raises BEJSONCoreError("Failed to update field 'title'"),
    # since "title" isn't a real field name on these entities at all.
    # app.py's own /api/notes, /api/todos, /api/links PUT routes already
    # carry this exact translation at the route level (note_title/
    # todo_text/title -> label) — the CLI just never had it. Replicated
    # here, plus app.py's add_note/update_note color allow-list
    # (_NOTE_COLS/_clean_note_color), which had the same gap.

    _NOTE_COLORS = frozenset(("#f5f5f5", "#fef9c3", "#d1fae5", "#dbeafe", "#fce7f3", "#ede9fe"))

    def _clean_note_color(self, value: Optional[str]) -> str:
        return value if value in self._NOTE_COLORS else "#f5f5f5"

    def note_add(self, title: str, content: str, color: Optional[str] = None, **kwargs) -> str:
        return management_notes_add(self._require_manifest("note"), title, content,
                                     color=self._clean_note_color(color), **kwargs)

    def note_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("note")
        return management_notes_list(manifest) if manifest else []

    def note_update(self, note_id: str, **fields) -> bool:
        if "title" in fields:
            fields["label"] = fields.pop("title")
        if "color" in fields:
            fields["color"] = self._clean_note_color(fields["color"])
        return management_notes_update(self._require_manifest("note"), note_id, **fields)

    def note_delete(self, note_id: str) -> bool:
        return management_notes_delete(self._require_manifest("note"), note_id)

    def note_category_add(self, name: str) -> str:
        manifest = self._require_manifest("note")
        name = (name or "").strip()
        if not name:
            raise ValueError("cat_name required")
        existing = [c["cat_name"].lower() for c in management_notes_category_list(manifest)]
        if name.lower() in existing:
            raise ValueError("Category already exists")
        return management_notes_category_add(manifest, name)

    def note_category_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("note")
        return management_notes_category_list(manifest) if manifest else []

    def note_category_delete(self, cat_id: str) -> bool:
        return management_notes_category_delete(self._require_manifest("note"), cat_id)

    def task_add(self, text: str, **kwargs) -> str:
        return management_tasks_add(self._require_manifest("task"), text, **kwargs)

    def task_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("task")
        return management_tasks_list(manifest) if manifest else []

    def task_update(self, todo_id: str, **fields) -> bool:
        if "text" in fields:
            fields["label"] = fields.pop("text")
        return management_tasks_update(self._require_manifest("task"), todo_id, **fields)

    def task_delete(self, todo_id: str) -> bool:
        return management_tasks_delete(self._require_manifest("task"), todo_id)

    def task_category_add(self, name: str) -> str:
        manifest = self._require_manifest("task")
        name = (name or "").strip()
        if not name:
            raise ValueError("cat_name required")
        existing = [c["cat_name"].lower() for c in management_tasks_category_list(manifest)]
        if name.lower() in existing:
            raise ValueError("Category already exists")
        return management_tasks_category_add(manifest, name)

    def task_category_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("task")
        return management_tasks_category_list(manifest) if manifest else []

    def task_category_delete(self, cat_id: str) -> bool:
        return management_tasks_category_delete(self._require_manifest("task"), cat_id)

    def link_add(self, title: str, url: str, **kwargs) -> str:
        return management_links_add(self._require_manifest("link"), title, url, **kwargs)

    def link_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("link")
        return management_links_list(manifest) if manifest else []

    def link_update(self, link_id: str, **fields) -> bool:
        if "title" in fields:
            fields["label"] = fields.pop("title")
        return management_links_update(self._require_manifest("link"), link_id, **fields)

    def link_delete(self, link_id: str) -> bool:
        return management_links_delete(self._require_manifest("link"), link_id)

    def link_category_add(self, name: str) -> str:
        manifest = self._require_manifest("link")
        name = (name or "").strip()
        if not name:
            raise ValueError("cat_name required")
        existing = [c["cat_name"].lower() for c in management_links_category_list(manifest)]
        if name.lower() in existing:
            raise ValueError("Category already exists")
        return management_links_category_add(manifest, name)

    def link_category_list(self) -> List[Dict[str, Any]]:
        manifest = self._get_taxonomy_manifest("link")
        return management_links_category_list(manifest) if manifest else []

    def link_category_delete(self, cat_id: str) -> bool:
        return management_links_category_delete(self._require_manifest("link"), cat_id)

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

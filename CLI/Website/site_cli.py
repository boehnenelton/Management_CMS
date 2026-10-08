#!/usr/bin/env python3
"""
File Name & Relative Path: CLI/Website/site_cli.py
Description:    Website/CMS CLI entry point — Pages, Posts, Media,
                 Categories, Navigation, Landing sections, SEO, and the
                 static-site Build/Export. A terminal front-end over
                 lib_bejson_Management_cli.py's ManagementCLIProject
                 (page_*/post_*/media_*/category_*/nav_*/landing_*/
                 seo_*/build_site methods), kept fully separate from
                 CLI/Notes/notes_cli.py per project convention — that's
                 the Notes/Tasks/Links self-management front-end. Both
                 point at the same Management_CMS project root by default
                 (config/config.json's project_root_dir), the same way
                 app.py already serves both halves out of one shared
                 Content/ tree — this isn't two separate datasets, just
                 two separate, purpose-built front doors onto the one
                 project.
                 No hardcoded absolute paths anywhere in this file: every
                 directory it needs (lib/Management, lib/Core, the project
                 root, the default export dir) is resolved at runtime as
                 SCRIPT_PATH + a relative offset read out of config/
                 config.json (BEJSON 104a ScriptConfig, loaded via a Field
                 Map Cache — never a hardcoded positional index — per the
                 format spec).
VERSION:        1.0.0
Author Credit:  Elton Boehnen · eltonboehnen@gmail.com · boehnenelton2024.pages.dev · github.com/boehnenelton
RELATIONAL_ID:  60e36f68-afc8-4a5d-b18a-f2418b6b50df
"""

import os
import sys
import json
import logging
import shutil
from typing import Any, Dict, List, Optional

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_PATH, "config", "config.json")


def _load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads config/config.json (BEJSON 104a ScriptConfig) via a Field Map
    Cache — field name -> column index in each Values row — rather than
    a hardcoded positional index, per the format's own Field Map Cache
    mandate. Boundary-sanitizes (strips) every string key/value.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    field_map = {str(field["name"]).strip(): i for i, field in enumerate(doc.get("Fields", []))}
    settings: Dict[str, Any] = {}
    for row in doc.get("Values", []):
        name = str(row[field_map["setting_name"]]).strip()
        value = row[field_map["setting_value"]]
        if isinstance(value, str):
            value = value.strip()
        settings[name] = value
    return settings


_cfg = _load_config(CONFIG_PATH)

_LIB_MANAGEMENT_DIR = os.path.normpath(os.path.join(SCRIPT_PATH, _cfg["lib_management_dir"]))
_LIB_CORE_DIR = os.path.normpath(os.path.join(SCRIPT_PATH, _cfg["lib_core_dir"]))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_PATH, _cfg["project_root_dir"]))
DEFAULT_EXPORT_DIR = os.path.normpath(os.path.join(SCRIPT_PATH, _cfg.get("default_export_dir", "../../Export")))

for _d in (_LIB_CORE_DIR, _LIB_MANAGEMENT_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import lib_bejson_Management_cli as CLI  # noqa: E402  (path setup must run first)
# AUDIT FIX (2026-09-27, found while testing this new tool):
# ManagementCLIProject.build_site() (lib_bejson_Management_cli.py) calls
# lib_bejson_Management_build.py's Notes/Tasks/Links-driven personal-
# dashboard export — deliberately kept, per app.py's own 2026-07-21 audit
# comment, only because the CLI still used it. It does NOT build the CMS
# site (Pages/Posts/Media/Nav/SEO) this tool actually manages — that's
# lib_bejson_Management_static_builder.py's management_cms_static_build(),
# the one app.py's own /api/build route calls. Imported directly here so
# this tool's "Build / Export" menu publishes what it actually manages,
# with the same manifest wiring app.py uses (including the admin_nav_
# manifest_path fix documented in app.py — nav comes from the Pages
# manifest, not an unused cms_nav one).
import lib_bejson_Management_static_builder as StaticBuilder  # noqa: E402

logging.basicConfig(level=getattr(logging, str(_cfg.get("log_level", "WARNING")).upper(), logging.WARNING),
                     stream=sys.stderr, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---- small input helpers -------------------------------------------------

def _prompt(msg: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{msg}{suffix}: ").strip()
    return val if val else (default or "")


def _prompt_optional(msg: str) -> Optional[str]:
    val = input(f"{msg} (blank to skip): ").strip()
    return val if val else None


def _prompt_yn(msg: str, default_no: bool = True) -> bool:
    suffix = " [y/N]" if default_no else " [Y/n]"
    val = input(f"{msg}{suffix}: ").strip().lower()
    if not val:
        return not default_no
    return val.startswith("y")


def _print_rows(rows: List[Dict[str, Any]], columns: List[str]) -> None:
    if not rows:
        print("  (none)")
        return
    for r in rows:
        parts = [f"{c}={r.get(c)!r}" for c in columns]
        print("  - " + "  ".join(parts))


def _run(label: str, fn, *args, **kwargs):
    """Runs an action, prints a plain result or a one-line error — never a raw traceback."""
    try:
        result = fn(*args, **kwargs)
        print(f"{label}: OK" + (f" -> {result}" if result not in (None, True) else ""))
        return result
    except (ValueError, RuntimeError, FileExistsError) as e:
        print(f"{label}: FAILED — {e}")
        return None
    except Exception as e:
        log.exception("%s: unexpected error", label)
        print(f"{label}: FAILED (unexpected) — {e}")
        return None


# ---- menus -----------------------------------------------------------------

def pages_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Pages --")
        print(" 1) List pages")
        print(" 2) Add page")
        print(" 3) Update page")
        print(" 4) Delete page")
        print(" 5) Publish page")
        print(" 6) Archive page")
        print(" 7) View page SEO")
        print(" 8) Set page SEO")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            status = _prompt_optional("Filter by status (draft/published/archived, blank=all)")
            _print_rows(project.page_list(status=status or "all"), ["id", "title", "slug", "status"])
        elif choice == "2":
            title = _prompt("Title")
            if not title:
                print("Title required.")
                continue
            content_markdown = _prompt_optional("Content (Markdown — rendered, linted, sanitized automatically)")
            category_id_fk = _prompt_optional("Category id")
            status = _prompt("Status", default="draft")
            fields: Dict[str, Any] = {"status": status}
            if content_markdown is not None:
                fields["content_markdown"] = content_markdown
            if category_id_fk is not None:
                fields["category_id_fk"] = category_id_fk
            _run("page_create", project.page_create, title, **fields)
        elif choice == "3":
            page_id = _prompt("Page id")
            title = _prompt_optional("New title")
            content_markdown = _prompt_optional("New content (Markdown)")
            fields: Dict[str, Any] = {}
            if title is not None:
                fields["title"] = title
            if content_markdown is not None:
                fields["content_markdown"] = content_markdown
            _run("page_update", project.page_update, page_id, **fields)
        elif choice == "4":
            page_id = _prompt("Page id")
            if _prompt_yn(f"Delete page {page_id}?"):
                _run("page_delete", project.page_delete, page_id)
        elif choice == "5":
            page_id = _prompt("Page id")
            _run("page_publish", project.page_publish, page_id)
        elif choice == "6":
            page_id = _prompt("Page id")
            _run("page_archive", project.page_archive, page_id)
        elif choice == "7":
            page_id = _prompt("Page id")
            seo = _run("seo_get", project.seo_get, page_id)
            if seo:
                for k, v in seo.items():
                    print(f"    {k} = {v!r}")
        elif choice == "8":
            page_id = _prompt("Page id")
            meta_title = _prompt_optional("Meta title")
            meta_keywords = _prompt_optional("Meta keywords")
            fields = {k: v for k, v in {"meta_title": meta_title, "meta_keywords": meta_keywords}.items()
                      if v is not None}
            _run("seo_set", project.seo_set, page_id, **fields)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def posts_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Posts --")
        print(" 1) List posts")
        print(" 2) Add post")
        print(" 3) Update post")
        print(" 4) Delete post")
        print(" 5) Publish post")
        print(" 6) Archive post")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            status = _prompt_optional("Filter by status (draft/published/archived, blank=all)")
            _print_rows(project.post_list(status=status or "all"), ["id", "title", "slug", "status"])
        elif choice == "2":
            title = _prompt("Title")
            if not title:
                print("Title required.")
                continue
            content_markdown = _prompt_optional("Content (Markdown — rendered, linted, sanitized automatically)")
            category_id_fk = _prompt_optional("Category id")
            status = _prompt("Status", default="draft")
            fields: Dict[str, Any] = {"status": status}
            if content_markdown is not None:
                fields["content_markdown"] = content_markdown
            if category_id_fk is not None:
                fields["category_id_fk"] = category_id_fk
            _run("post_create", project.post_create, title, **fields)
        elif choice == "3":
            post_id = _prompt("Post id")
            title = _prompt_optional("New title")
            content_markdown = _prompt_optional("New content (Markdown)")
            fields: Dict[str, Any] = {}
            if title is not None:
                fields["title"] = title
            if content_markdown is not None:
                fields["content_markdown"] = content_markdown
            _run("post_update", project.post_update, post_id, **fields)
        elif choice == "4":
            post_id = _prompt("Post id")
            if _prompt_yn(f"Delete post {post_id}?"):
                _run("post_delete", project.post_delete, post_id)
        elif choice == "5":
            post_id = _prompt("Post id")
            _run("post_publish", project.post_publish, post_id)
        elif choice == "6":
            post_id = _prompt("Post id")
            _run("post_archive", project.post_archive, post_id)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def categories_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Categories (shared by Pages and Posts) --")
        print(" 1) List page categories")
        print(" 2) List post categories")
        print(" 3) Add page category")
        print(" 4) Add post category")
        print(" 5) Delete category (either type — also clears any Page/Post referencing it)")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            _print_rows(project.category_list(), ["id", "title", "slug"])
        elif choice == "2":
            _print_rows(project.post_category_list(), ["id", "title", "slug"])
        elif choice == "3":
            name = _prompt("Category name")
            _run("category_create", project.category_create, name)
        elif choice == "4":
            name = _prompt("Category name")
            _run("post_category_create", project.post_category_create, name)
        elif choice == "5":
            cat_id = _prompt("Category id")
            if _prompt_yn(f"Delete category {cat_id}?"):
                _run("category_delete", project.category_delete, cat_id)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def media_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Media --")
        print(" 1) List media")
        print(" 2) Add media (from a local file path)")
        print(" 3) Delete media")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            _print_rows(project.media_list(), ["media_id", "filename", "file_type", "original_path"])
        elif choice == "2":
            original_path = _prompt("Local file path")
            if not os.path.isfile(original_path):
                print(f"File not found: {original_path}")
                continue
            filename = _prompt("Filename to store as", default=os.path.basename(original_path))
            file_type = _prompt("File type (image/document/etc.)", default="image")
            alt_text = _prompt_optional("Alt text")
            fields = {"alt_text": alt_text} if alt_text is not None else {}
            _run("media_add", project.media_add, filename, original_path, file_type, **fields)
        elif choice == "3":
            media_id = _prompt("Media id")
            if _prompt_yn(f"Delete media {media_id}?"):
                _run("media_delete", project.media_delete, media_id)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def nav_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Navigation --")
        print(" 1) List nav links")
        print(" 2) Add nav link")
        print(" 3) Delete nav link")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            _print_rows(project.nav_list(), ["nav_id", "nav_label", "nav_url", "nav_target"])
        elif choice == "2":
            label = _prompt("Label")
            url = _prompt("URL")
            if not label or not url:
                print("Label and URL required.")
                continue
            target = _prompt("Target", default="_self")
            _run("nav_add", project.nav_add, label, url, target)
        elif choice == "3":
            nav_id = _prompt("Nav link id")
            if _prompt_yn(f"Delete nav link {nav_id}?"):
                _run("nav_delete", project.nav_delete, nav_id)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def landing_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Landing Page Sections --")
        print(" 1) List sections for a page")
        print(" 2) Add section to a page")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            page_id = _prompt("Page id")
            _print_rows(project.landing_get_sections(page_id), ["section_id", "section_type", "idx_position"])
        elif choice == "2":
            page_id = _prompt("Page id")
            section_type = _prompt("Section type (e.g. hero, cta, gallery)")
            heading = _prompt_optional("Heading (goes into section_data)")
            section_data = {"heading": heading} if heading else {}
            _run("landing_add_section", project.landing_add_section, page_id, section_type, section_data)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def _build_cms_static_site(project: "CLI.ManagementCLIProject", export_dir: str, site_url: str = "") -> Dict[str, Any]:
    """
    Builds the real CMS site (Pages/Posts/Categories/Media/Nav/SEO) via
    the same lib_bejson_Management_static_builder.py function app.py's own
    build route calls — see the AUDIT FIX comment near this file's
    StaticBuilder import for why that's not project.build_site().

    AUDIT FIX (2026-09-28): site_url was previously pulled from
    project.config_get_all(), but "site_url has no dedicated Settings
    field today" (app.py's own comment on this) — app.py instead captures
    it live from request.host_url when a build is triggered through the
    running app, which this offline CLI has no equivalent of.
    config_update({"site_url": ...}) was a silent no-op (management_
    config_save only persists the app's known settings schema), so every
    build here was silently using "" regardless of what was "set" —
    correct by accident (empty already degrades to root-relative output),
    not by design. Takes site_url as an explicit parameter now — the
    build menu prompts for it — same as the effect of the M-6/BLD-01
    empty/loopback-degrades-to-relative behavior in
    management_cms_shared_export_site_url(), now actually exercised
    instead of only ever hitting the empty-string path.
    """
    cfg = project.config_get_all()
    site_config = {
        "site_title": cfg.get("site_title", "My Site"),
        "site_tagline": cfg.get("site_subtitle", ""),
        "footer_text": cfg.get("footer_text", ""),
        "site_url": site_url,
        "feed_posts_limit": 20,
    }
    return StaticBuilder.management_cms_static_build(
        project._cms_manifest("page"), project._cms_manifest("post"),
        project._cms_manifest("category"), project._cms_manifest("media"),
        site_config, export_dir,
        root_manifest_path=project.root_manifest,
        admin_nav_manifest_path=project._get_taxonomy_manifest("page"),
    )


def build_menu(project: "CLI.ManagementCLIProject") -> None:
    print("\n-- Build / Export --")
    print(" 1) Build the CMS site (Pages/Posts/Categories/Media/Nav/SEO)")
    print(" 2) Build the legacy personal-dashboard export (Notes/Tasks/Links homepage)")
    print(" 0) Back")
    choice = input("> ").strip()
    if choice == "1":
        export_dir = _prompt("Export directory", default=DEFAULT_EXPORT_DIR)
        site_url = _prompt_optional("Site URL for canonical/OG tags (blank = relative paths only)") or ""
        result = _run("build_cms_static_site", _build_cms_static_site, project, export_dir, site_url)
        if result:
            for w in result.get("warnings", []):
                print(f"  warning: {w}")
            print(f"  Export written to: {export_dir}")
    elif choice == "2":
        export_dir = _prompt("Export directory", default=DEFAULT_EXPORT_DIR)
        result = _run("build_site (legacy)", project.build_site, export_dir)
        if result:
            print(f"  Export written to: {export_dir}")
    elif choice == "0":
        return
    else:
        print("Unrecognized option.")


def config_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Project Config --")
        print(" 1) Show all settings")
        print(" 2) Update a setting")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            for k, v in project.config_get_all().items():
                print(f"  {k} = {v!r}")
        elif choice == "2":
            key = _prompt("Setting name")
            value = _prompt("New value")
            _run("config_update", project.config_update, {key: value})
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def factory_reset() -> None:
    print("\n!! FACTORY RESET !!")
    print(f"This deletes the ENTIRE shared project at:\n  {PROJECT_ROOT}")
    print("That includes Pages, Posts, Media, Categories, Nav AND Notes, Tasks, Links —")
    print("everything notes_cli.py manages too, not just the website side.")
    confirm = input("Type RESET to confirm, anything else to cancel: ").strip()
    if confirm != "RESET":
        print("Cancelled.")
        return
    if os.path.isdir(PROJECT_ROOT):
        shutil.rmtree(PROJECT_ROOT)
        print("Project directory removed. Run this tool again to re-initialize.")
    else:
        print("Nothing to remove — project directory doesn't exist.")


def main() -> None:
    print("=" * 60)
    print(" Website CLI — CMS (Pages / Posts / Media / Nav / SEO / Build)")
    print(f" Project root: {PROJECT_ROOT}")
    print("=" * 60)

    project = CLI.ManagementCLIProject(PROJECT_ROOT)

    if not project.exists():
        print("\nNo project found at that path.")
        if _prompt_yn("Initialize a new one here?", default_no=False):
            site_name = _prompt("Site name", default="My Site")
            _run("init_project", project.init_project, site_name)
        else:
            print("Nothing to do without a project. Exiting.")
            return

    while True:
        print("\n== Main Menu ==")
        print(" 1) Pages")
        print(" 2) Posts")
        print(" 3) Categories")
        print(" 4) Media")
        print(" 5) Navigation")
        print(" 6) Landing page sections")
        print(" 7) Build / Export static site")
        print(" 8) Project config")
        print(" 9) Factory reset (delete everything, start over)")
        print(" 0) Exit")
        choice = input("> ").strip()
        if choice == "1":
            pages_menu(project)
        elif choice == "2":
            posts_menu(project)
        elif choice == "3":
            categories_menu(project)
        elif choice == "4":
            media_menu(project)
        elif choice == "5":
            nav_menu(project)
        elif choice == "6":
            landing_menu(project)
        elif choice == "7":
            build_menu(project)
        elif choice == "8":
            config_menu(project)
        elif choice == "9":
            factory_reset()
            if not project.exists():
                if _prompt_yn("Re-initialize now?", default_no=False):
                    site_name = _prompt("Site name", default="My Site")
                    _run("init_project", project.init_project, site_name)
                else:
                    print("Exiting.")
                    return
        elif choice == "0":
            print("Bye.")
            return
        else:
            print("Unrecognized option.")


if __name__ == "__main__":
    main()

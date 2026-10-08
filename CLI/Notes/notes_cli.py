#!/usr/bin/env python3
"""
File Name & Relative Path: CLI/Notes/notes_cli.py
Description:    Self-management CLI entry point — Notes, Tasks, and Links
                 only. A terminal front-end over lib_bejson_Management_cli.
                 py's ManagementCLIProject (note_*/task_*/link_* methods),
                 kept fully separate from CLI/Website/site_cli.py per
                 project convention — that's the Pages/Posts/Media/Nav/
                 Category/SEO/Build front-end. Both point at the same
                 Management_CMS project root by default (config/
                 config.json's project_root_dir), the same way app.py
                 already serves Notes/Tasks/Links and Pages/Posts/Media
                 out of one shared Content/ tree — this isn't two separate
                 datasets, just two separate, purpose-built front doors
                 onto the one project.
                 No hardcoded absolute paths anywhere in this file: every
                 directory it needs (lib/Management, lib/Core, the project
                 root) is resolved at runtime as SCRIPT_PATH + a relative
                 offset read out of config/config.json (BEJSON 104a
                 ScriptConfig, loaded via a Field Map Cache — never a
                 hardcoded positional index — per the format spec).
VERSION:        1.0.0
Author Credit:  Elton Boehnen · eltonboehnen@gmail.com · boehnenelton2024.pages.dev · github.com/boehnenelton
RELATIONAL_ID:  319569af-42d3-4016-b467-a23aa4e78a91
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

for _d in (_LIB_CORE_DIR, _LIB_MANAGEMENT_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import lib_bejson_Management_cli as CLI  # noqa: E402  (path setup must run first)

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

def notes_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Notes --")
        print(" 1) List notes")
        print(" 2) Add note")
        print(" 3) Update note")
        print(" 4) Delete note")
        print(" 5) List categories")
        print(" 6) Add category")
        print(" 7) Delete category")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            _print_rows(project.note_list(), ["id", "label", "category", "color"])
        elif choice == "2":
            title = _prompt("Title")
            if not title:
                print("Title required.")
                continue
            content = _prompt("Content")
            color = _prompt_optional("Color (hex, e.g. #fef9c3)")
            category = _prompt_optional("Category id")
            _run("note_add", project.note_add, title, content, color=color, category=category)
        elif choice == "3":
            note_id = _prompt("Note id")
            title = _prompt_optional("New title")
            content = _prompt_optional("New content")
            fields = {k: v for k, v in {"title": title, "content": content}.items() if v is not None}
            _run("note_update", project.note_update, note_id, **fields)
        elif choice == "4":
            note_id = _prompt("Note id")
            if _prompt_yn(f"Delete note {note_id}?"):
                _run("note_delete", project.note_delete, note_id)
        elif choice == "5":
            _print_rows(project.note_category_list(), ["cat_id", "cat_name"])
        elif choice == "6":
            name = _prompt("Category name")
            _run("note_category_add", project.note_category_add, name)
        elif choice == "7":
            cat_id = _prompt("Category id")
            if _prompt_yn(f"Delete category {cat_id}?"):
                _run("note_category_delete", project.note_category_delete, cat_id)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def tasks_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Tasks --")
        print(" 1) List tasks")
        print(" 2) Add task")
        print(" 3) Update task")
        print(" 4) Delete task")
        print(" 5) List categories")
        print(" 6) Add category")
        print(" 7) Delete category")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            _print_rows(project.task_list(), ["id", "label", "done", "priority", "category"])
        elif choice == "2":
            text = _prompt("Task text")
            if not text:
                print("Task text required.")
                continue
            priority = _prompt_optional("Priority")
            detail = _prompt_optional("Detail")
            category = _prompt_optional("Category id")
            _run("task_add", project.task_add, text, priority=priority, detail=detail, category=category)
        elif choice == "3":
            todo_id = _prompt("Task id")
            text = _prompt_optional("New text")
            done = _prompt_optional("Done (true/false)")
            fields: Dict[str, Any] = {}
            if text is not None:
                fields["text"] = text
            if done is not None:
                fields["done"] = done.strip().lower() in ("true", "1", "yes", "y")
            _run("task_update", project.task_update, todo_id, **fields)
        elif choice == "4":
            todo_id = _prompt("Task id")
            if _prompt_yn(f"Delete task {todo_id}?"):
                _run("task_delete", project.task_delete, todo_id)
        elif choice == "5":
            _print_rows(project.task_category_list(), ["cat_id", "cat_name"])
        elif choice == "6":
            name = _prompt("Category name")
            _run("task_category_add", project.task_category_add, name)
        elif choice == "7":
            cat_id = _prompt("Category id")
            if _prompt_yn(f"Delete category {cat_id}?"):
                _run("task_category_delete", project.task_category_delete, cat_id)
        elif choice == "0":
            return
        else:
            print("Unrecognized option.")


def links_menu(project: "CLI.ManagementCLIProject") -> None:
    while True:
        print("\n-- Links --")
        print(" 1) List links")
        print(" 2) Add link")
        print(" 3) Update link")
        print(" 4) Delete link")
        print(" 5) List categories")
        print(" 6) Add category")
        print(" 7) Delete category")
        print(" 8) Check health of one link (real HTTP)")
        print(" 9) Audit all links (real HTTP)")
        print(" 0) Back")
        choice = input("> ").strip()
        if choice == "1":
            _print_rows(project.link_list(), ["id", "label", "url", "category"])
        elif choice == "2":
            title = _prompt("Title")
            url = _prompt("URL")
            if not title or not url:
                print("Title and URL required.")
                continue
            category = _prompt_optional("Category id")
            icon = _prompt_optional("Icon")
            description = _prompt_optional("Description")
            _run("link_add", project.link_add, title, url, category=category, icon=icon, description=description)
        elif choice == "3":
            link_id = _prompt("Link id")
            title = _prompt_optional("New title")
            url = _prompt_optional("New URL")
            fields = {k: v for k, v in {"title": title, "url": url}.items() if v is not None}
            _run("link_update", project.link_update, link_id, **fields)
        elif choice == "4":
            link_id = _prompt("Link id")
            if _prompt_yn(f"Delete link {link_id}?"):
                _run("link_delete", project.link_delete, link_id)
        elif choice == "5":
            _print_rows(project.link_category_list(), ["cat_id", "cat_name"])
        elif choice == "6":
            name = _prompt("Category name")
            _run("link_category_add", project.link_category_add, name)
        elif choice == "7":
            cat_id = _prompt("Category id")
            if _prompt_yn(f"Delete category {cat_id}?"):
                _run("link_category_delete", project.link_category_delete, cat_id)
        elif choice == "8":
            url = _prompt("URL to check")
            print(" ", _run("check_link_health", project.check_link_health, url))
        elif choice == "9":
            print("Checking all links (this makes real HTTP requests)...")
            for r in project.link_audit():
                print(f"  - {r.get('title')}: {r.get('url')} -> "
                      f"{'OK' if r.get('reachable') else 'UNREACHABLE'} ({r.get('status_code')})")
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
    print("That includes Notes, Tasks, Links, AND Pages, Posts, Media, Categories —")
    print("everything site_cli.py manages too, not just Notes/Tasks/Links.")
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
    print(" Notes CLI — self-management (Notes / Tasks / Links)")
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
        print(" 1) Notes")
        print(" 2) Tasks")
        print(" 3) Links")
        print(" 4) Project config")
        print(" 9) Factory reset (delete everything, start over)")
        print(" 0) Exit")
        choice = input("> ").strip()
        if choice == "1":
            notes_menu(project)
        elif choice == "2":
            tasks_menu(project)
        elif choice == "3":
            links_menu(project)
        elif choice == "4":
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

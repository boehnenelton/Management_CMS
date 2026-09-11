"""
Library:        lib_bejson_Management_config.py
Family:         Management
Description:    Config load/save for Management_CMS (formerly "Homepage
                 Builder") — factored out
                 into its own file (adopted from Lineage B's separation of
                 concerns) but backed by the real Core MFDB write path
                 rather than a bare open()/json.dump, and with a
                 create-if-missing default so a fresh app can cold-start
                 without hand-seeded data.
Version:        1.0.0
Date:           2026-07-03
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  5b8d2f7a-3e6c-4a1b-9d4f-7c2a5e8b1d30
"""

import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_bejson_core as BejsonCore

MANAGEMENT_CONFIG_DEFAULT_VALUES = {
    "Format": "BEJSON",
    "Format_Version": "104a",
    "Format_Creator": "Elton Boehnen",
    "Records_Type": ["ScriptConfig"],
    "Fields": [
        {"name": "setting_name",  "type": "string"},
        {"name": "setting_value", "type": "string"},
        {"name": "description",   "type": "string"},
    ],
    "Values": [
        ["site_title",    "My Homepage", "Title on exported homepage"],
        ["site_subtitle", "Start Page",  "Subtitle / tagline"],
        # Feature request (Elton): global footer. Freeform — a copyright
        # notice, a company name, "All rights reserved", whatever;
        # combined with an auto-computed "© <year> <site_title>" in
        # management_cms_shared_build_footer_html(). Empty by default so
        # a fresh site's footer stays to just the copyright line, not an
        # unwanted placeholder sentence.
        ["footer_text",   "",            "Extra footer text (e.g. \"All rights reserved.\") — appears after the auto copyright line"],
        ["show_clock",    "true",        "Show live clock on exported page"],
        ["show_greeting", "true",        "Show time-based greeting"],
        ["accent_color",  "#DE2626",     "Accent colour"],
        ["bg_color",      "#0a0a0a",     "Background colour"],
        ["port",          "5030",        "Flask server port"],
        # AUDIT FIX (M-5): "debug" removed here, 2026-08-14 — verified
        # zero consumers anywhere in app.py, lib/Management/*.py, or
        # templates/index.html (grepped, not assumed) before removing.
        # See docs/dead_code.md.
    ]
}


def _resolve_config_path(config_data_root) -> Path:
    return Path(config_data_root) / "config" / "config.bejson"


def management_config_load_raw(config_data_root) -> Dict[str, Any]:
    """Returns the raw BEJSON 104a dict. Creates the default file if missing."""
    config_path = _resolve_config_path(config_data_root)
    if not config_path.exists():
        BejsonCore.bejson_core_atomic_write(str(config_path), MANAGEMENT_CONFIG_DEFAULT_VALUES)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def management_config_load(config_data_root) -> Dict[str, Any]:
    """Returns config as a plain dict with Python-typed values (bools/int coerced)."""
    raw = management_config_load_raw(config_data_root)
    out = {}
    for key, value, _desc in raw["Values"]:
        if key in ("show_clock", "show_greeting", "debug"):
            out[key] = str(value).lower() == "true"
        elif key == "port":
            out[key] = int(value)
        else:
            out[key] = value
    return out


def management_config_save(config_data_root, payload: Dict[str, Any]) -> None:
    """Updates config values from payload. Unknown keys ignored. Booleans/ints serialised as strings."""
    raw = management_config_load_raw(config_data_root)
    for row in raw["Values"]:
        key = row[0]
        if key in payload:
            value = payload[key]
            row[1] = ("true" if value else "false") if isinstance(value, bool) else str(value)
    BejsonCore.bejson_core_atomic_write(str(_resolve_config_path(config_data_root)), raw)


def management_config_get_settings_list(config_data_root) -> List[Dict[str, str]]:
    """Returns settings as a list of dicts for a settings UI."""
    raw = management_config_load_raw(config_data_root)
    return [{"setting_name": r[0], "setting_value": r[1], "description": r[2]} for r in raw["Values"]]

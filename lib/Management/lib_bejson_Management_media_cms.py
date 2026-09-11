"""
Library:         lib_bejson_Management_media_cms
Family:          management_cms
Description:     Media registry for the public-hosting layer. There is no
                  standalone KIMI "Assets" module to port from — see the
                  merge report Sec. I: KIMI's only trace of assets is an
                  unused schema stub in Core.py's init_site(), never read
                  or written by any function. This module instead extends
                  lib_bejson_Management_media.py's real, working CRUD
                  (management_media_add/list/get/update/delete) with the
                  file-hash validation and WebP optimization OFFICIAL_PLAN.MD
                  Sec. IV calls for — net-new logic, not a port, since
                  nothing in the provided source implements it today.

                  Requires Pillow for WebP conversion. If Pillow is not
                  installed, management_cms_media_add() still records the
                  file (with file_hash populated) but leaves webp_path
                  empty rather than failing the whole call — the bootstrap
                  fail-loudly rule applies to missing *required* structure,
                  not to an optional image-optimization dependency.
Version:         1.2.0
Library_Version: 003
Date:            2026-07-25
Author:          Elton Boehnen
Contact:         eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator:  Elton Boehnen
RELATIONAL_ID:   4d9a2c7f-8b3e-4a1d-9c6f-2e8b5a4d9c73

CHANGELOG (1.2.0, 2026-07-25): Checklist item 2b:
management_cms_media_add() migrated from a raw positional list to
mfdb_core_add_entity_record_by_name(). Retested functionally after
migration.
"""

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore
from lib_bejson_Management_shared import (
    management_cms_shared_gen_id,
    management_cms_shared_now_iso,
)

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Schema — Media (Content/media/MFDB/104a.mfdb.bejson)
# ---------------------------------------------------------------------------

MEDIA_FIELDS = [
    {"name": "id",            "type": "string"},
    {"name": "filename",      "type": "string"},
    {"name": "original_path", "type": "string"},
    {"name": "mime_type",     "type": "string"},
    {"name": "file_hash",     "type": "string"},   # SHA-256 hex digest
    {"name": "webp_path",     "type": "string"},   # empty if not an image or Pillow unavailable
    {"name": "alt_text",      "type": "string"},
    {"name": "created_at",    "type": "string"},
    # AUDIT FIX (DAT-03): the CmsMedia record and its sibling admin Media
    # record (a separate entity, PAGES_MANIFEST's own "Media" — see
    # app.py's upload_media(), which creates one of each per upload) had
    # no foreign key between them at all — only the coincidence that both
    # were created from the same original_path in the same request.
    # delete_media() matched them back up by comparing that path string,
    # which breaks the moment either side's path is normalized/rewritten
    # differently (exactly the H-4 portability fix's absolute-vs-relative
    # split already did once) — a real, recurring pattern, not
    # hypothetical. Appended at the end, per this project's schema-change
    # convention (new fields are appended, never inserted mid-array) —
    # existing rows get "" via the fallback in management_cms_media_add()
    # below, and every read site treats "" the same as "no admin_media_id
    # recorded", falling back to the old path-match behavior for records
    # created before this field existed.
    {"name": "admin_media_id", "type": "string"},
]

_IMAGE_MIME_PREFIXES = ("image/",)


def _file_hash(original_path: str) -> str:
    """SHA-256 of the file contents, per Section IV's file-hash validation requirement."""
    digest = hashlib.sha256()
    with open(original_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generate_webp(original_path: str, manifest_path: str) -> str:
    """
    Generate a WebP copy alongside the original, stored under the Media
    manifest's own media/ subfolder. Returns the ABSOLUTE webp_path (see
    BUG FIX note below), or "" if the source isn't an image or Pillow isn't
    installed.

    BUG FIX: this used to return a path relative to the manifest's own
    directory (out_path.relative_to(out_dir.parent)) rather than an
    absolute one. original_path is stored absolute; webp_path was not —
    two path fields on the same entity with different resolution
    semantics. The real-world effect: management_cms_static_build()'s
    _management_cms_copy_media() step checks os.path.exists(webp_path)
    before copying, but a manifest-relative string resolves against the
    *process's current working directory*, not the manifest's directory —
    so that check silently failed every time, and WebP variants never
    actually made it into Export/media/ despite generating correctly on
    disk. Fixed by returning an absolute path like original_path already
    does, removing the ambiguity entirely.
    """
    if not _PIL_AVAILABLE:
        return ""
    try:
        with Image.open(original_path) as img:
            out_dir = Path(os.path.dirname(os.path.abspath(manifest_path))) / "media"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(original_path).stem
            out_path = out_dir / f"{stem}.webp"
            img.save(out_path, "WEBP", quality=85)
            return str(out_path.resolve())
    except Exception:
        return ""


def management_cms_media_add(manifest_path: str, filename: str, original_path: str,
                              mime_type: Optional[str] = None, alt_text: str = "",
                              admin_media_id: str = "") -> str:
    media_id = management_cms_shared_gen_id()
    created_at = management_cms_shared_now_iso()
    file_hash = _file_hash(original_path) if os.path.exists(original_path) else ""
    webp_path = ""
    if mime_type and mime_type.startswith(_IMAGE_MIME_PREFIXES) and os.path.exists(original_path):
        webp_path = _generate_webp(original_path, manifest_path)
    row_map = {
        "id": media_id, "filename": filename, "original_path": original_path,
        "mime_type": mime_type, "file_hash": file_hash, "webp_path": webp_path,
        "alt_text": alt_text, "created_at": created_at,
        # AUDIT FIX (DAT-03): real FK to the sibling admin Media record,
        # in addition to (not replacing) original_path — see MEDIA_FIELDS'
        # own comment above for why. Defaults to "" for any caller that
        # doesn't pass one, matching the fallback every read site expects.
        "admin_media_id": admin_media_id,
    }
    # CHECKLIST ITEM 2b FIX (2026-07-25): migrated to
    # mfdb_core_add_entity_record_by_name().
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Media", row_map)
    return media_id


def management_cms_media_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "Media")


def management_cms_media_get(manifest_path: str, media_id: str) -> Optional[Dict[str, Any]]:
    for m in management_cms_media_list(manifest_path):
        if m.get("id") == media_id:
            return m
    return None


def management_cms_media_update(manifest_path: str, media_id: str, **fields) -> bool:
    items = management_cms_media_list(manifest_path)
    for i, m in enumerate(items):
        if m.get("id") == media_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Media", i, fields)
            return True
    return False


def management_cms_media_delete(manifest_path: str, media_id: str) -> bool:
    items = management_cms_media_list(manifest_path)
    for i, m in enumerate(items):
        if m.get("id") == media_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Media", i)
            return True
    return False

"""
Library:        lib_bejson_Management_media
Family:         Management
Description:    Media registry — tracks imported files (images/video/docs/
                 audio) with type, mime, dimensions, and alt text. Not a
                 taxonomy itself; deployed as a secondary entity in the
                 Pages MFDB. Adapted from an evaluated third-party CLI
                 tool that used these libraries as its own foundation —
                 rebuilt here with full UUIDs and standard MFDBCore access.

                 Media Performance Pass: SHA-256 file_hash and WebP
                 optimization (webp_path) added, matching the logic already
                 built for the public-hosting layer's
                 lib_bejson_Management_media_cms.py, so admin-side media
                 gets the same integrity tracking and lightweight image
                 variants regardless of which layer touches a file first.
                 Requires Pillow for WebP conversion; if unavailable,
                 file_hash is still populated and webp_path is left empty
                 rather than failing the add — an optional dependency
                 missing isn't the kind of structural failure the
                 fail-loudly bootstrap rule is about.
Version:        2.3.0
Date:            2026-07-09
Author:          Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  6c1ae086-bba7-49c2-a68b-58113aa21b75

CHANGELOG (2.3.0, 2026-07-25): New file — a live-app-only copy of the
original lib_bejson_Management_media.py, created because Elton asked to fix
the positional-add-call fragility without risking the original (still used
by lib_bejson_Management_cli.py). All mfdb_core_add_entity_record() calls
migrated to mfdb_core_add_entity_record_by_name(). Functionally retested
through the real app.py import path, not just in isolation. The original
file is untouched.
"""

import hashlib
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.normpath(os.path.join(LIB_DIR, "..", "Core"))
if CORE_DIR not in sys.path:
    sys.path.append(CORE_DIR)

import lib_bejson_Core_mfdb_core as MFDBCore

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

MEDIA_FIELDS = [
    {"name": "media_id",         "type": "string"},
    {"name": "filename",         "type": "string"},
    {"name": "original_path",    "type": "string"},
    {"name": "file_type",        "type": "string"},   # image | video | document | audio | youtube | external_image
    {"name": "mime_type",        "type": "string"},
    {"name": "file_size_bytes",  "type": "integer"},
    {"name": "width",            "type": "integer"},
    {"name": "height",           "type": "integer"},
    {"name": "file_hash",        "type": "string"},   # SHA-256 hex digest
    {"name": "webp_path",        "type": "string"},   # empty if not an image or Pillow unavailable
    {"name": "alt_text",         "type": "string"},
    {"name": "created_at",       "type": "string"},
    # External links (YouTube embeds, hotlinked images) — no local file at
    # all, so original_path/file_hash/webp_path/width/height stay empty for
    # these rows. Appended at the end (not inserted earlier) for the same
    # backward-compatibility reason as the Page "title" field fix: BEJSON
    # rows are positional, and adding a field to the middle of an existing
    # schema would misalign every value after it for rows already on disk.
    {"name": "external_url",     "type": "string"},
]

_IMAGE_MIME_PREFIXES = ("image/",)


def _file_hash(original_path: str) -> str:
    digest = hashlib.sha256()
    with open(original_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generate_webp(original_path: str, manifest_path: str) -> str:
    """
    Generate a WebP copy alongside the manifest, in a media/ subfolder.
    Returns "" on failure or if Pillow is unavailable.

    BUG FIX: previously returned a path relative to the manifest's own
    directory instead of absolute (matching original_path's own
    convention) — see the identical fix and full explanation in
    lib_bejson_Management_media_cms.py's _generate_webp(). Same root
    cause, same fix, kept consistent between the two media modules.
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


def management_media_add(manifest_path: str, filename: str, original_path: str,
                          file_type: str, mime_type: Optional[str] = None,
                          file_size_bytes: Optional[int] = None, width: Optional[int] = None,
                          height: Optional[int] = None, alt_text: Optional[str] = None) -> str:
    media_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    file_hash = _file_hash(original_path) if os.path.exists(original_path) else ""
    webp_path = ""
    if mime_type and mime_type.startswith(_IMAGE_MIME_PREFIXES) and os.path.exists(original_path):
        webp_path = _generate_webp(original_path, manifest_path)

    # LIVE-COPY FIX (2026-07-25): migrated from a raw positional list to
    # mfdb_core_add_entity_record_by_name() — MEDIA_FIELDS maps 1:1.
    # Original lib_bejson_Management_media.py untouched.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Media", {
        "media_id": media_id, "filename": filename, "original_path": original_path,
        "file_type": file_type, "mime_type": mime_type, "file_size_bytes": file_size_bytes,
        "width": width, "height": height, "file_hash": file_hash, "webp_path": webp_path,
        "alt_text": alt_text, "created_at": created_at, "external_url": "",
    })
    return media_id


_YOUTUBE_ID_PATTERNS = (
    r"(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
)

def _extract_youtube_id(url: str) -> Optional[str]:
    for pattern in _YOUTUBE_ID_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def management_media_add_external(manifest_path: str, media_type: str, url: str,
                                   title: str = "", alt_text: str = "") -> str:
    """
    Registers an external link (no local file) into the same Media
    registry uploads use — media_type: "youtube" | "external_image".
    For YouTube, the raw URL is normalized to a canonical watch URL and
    external_url stores that; filename holds a human label (falls back to
    the video ID) for display in the picker. Raises ValueError for an
    unrecognized YouTube URL or an unsupported media_type, since silently
    registering a broken link isn't useful to anyone.
    """
    media_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if media_type == "youtube":
        video_id = _extract_youtube_id(url)
        if not video_id:
            raise ValueError(f"Could not extract a YouTube video ID from: {url}")
        normalized_url = f"https://www.youtube.com/watch?v={video_id}"
        display_name = title or video_id
        row_map = {
            "media_id": media_id, "filename": display_name, "original_path": "",
            "file_type": "youtube", "mime_type": "video/youtube",
            "file_size_bytes": None, "width": None, "height": None,
            "file_hash": "", "webp_path": "", "alt_text": alt_text,
            "created_at": created_at, "external_url": normalized_url,
        }
    elif media_type == "external_image":
        display_name = title or url.rsplit("/", 1)[-1] or "external image"
        row_map = {
            "media_id": media_id, "filename": display_name, "original_path": "",
            "file_type": "external_image", "mime_type": "image/external",
            "file_size_bytes": None, "width": None, "height": None,
            "file_hash": "", "webp_path": "", "alt_text": alt_text,
            "created_at": created_at, "external_url": url,
        }
    else:
        raise ValueError(f"Unsupported external media_type: {media_type!r}")

    # LIVE-COPY FIX (2026-07-25): migrated from a raw positional list to
    # mfdb_core_add_entity_record_by_name(), same as the upload path above.
    MFDBCore.mfdb_core_add_entity_record_by_name(manifest_path, "Media", row_map)
    return media_id


def management_media_list(manifest_path: str) -> List[Dict[str, Any]]:
    return MFDBCore.mfdb_core_load_entity(manifest_path, "Media")


def management_media_get(manifest_path: str, media_id: str) -> Optional[Dict[str, Any]]:
    for m in management_media_list(manifest_path):
        if m.get("media_id") == media_id:
            return m
    return None


def management_media_update(manifest_path: str, media_id: str, **fields) -> bool:
    items = management_media_list(manifest_path)
    for i, m in enumerate(items):
        if m.get("media_id") == media_id:
            MFDBCore.mfdb_core_update_entity_record_bulk(manifest_path, "Media", i, fields)
            return True
    return False


def management_media_delete(manifest_path: str, media_id: str) -> bool:
    items = management_media_list(manifest_path)
    for i, m in enumerate(items):
        if m.get("media_id") == media_id:
            MFDBCore.mfdb_core_remove_entity_record(manifest_path, "Media", i)
            return True
    return False

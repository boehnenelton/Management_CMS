"""
Library:        lib_bejson_Core_bejson_path_guard.py
Family:         Core
Description:    Secure path resolver and boundary protection logic.
Version:        1.0.0
Date:           2026-06-02
Author:         Elton Boehnen
Contact:        eltonboehnen@gmail.com | boehnenelton2024.pages.dev | github.com/boehnenelton
Format_Creator: Elton Boehnen
RELATIONAL_ID:  8d1b4d5d-97bf-4b8f-aa48-0af3386b503f
"""

import os
from pathlib import Path

def bejson_safe_join(base_dir: str, *paths: str) -> str:
    """
    Safely join paths and ensure the result is within the base_dir.
    Mitigates path traversal attacks (Phase 2).
    """
    base_path = Path(base_dir).resolve()
    # Handle environment variables in paths if any
    resolved_paths = [os.path.expandvars(p) for p in paths]
    target_path = base_path.joinpath(*resolved_paths).resolve()

    # BUG FIX: the previous check was `str(target_path).startswith(str(base_path))`,
    # a bare string-prefix comparison with no path-separator boundary. That
    # allows a sibling directory that merely SHARES base_path's string prefix
    # to pass as "inside" it — e.g. base_dir="/srv/app", and a zip member
    # resolving to "/srv/app_evil/payload" would incorrectly be accepted,
    # since "/srv/app_evil" starts with "/srv/app" as raw text. This is the
    # exact class of bug Zip Slip mitigations exist to prevent, and this
    # function is the one call site (lib_bejson_Core_mfdb_core.py's archive
    # extraction loop) that relies on it for that purpose. Fixed by requiring
    # target_path to equal base_path or start with base_path + a path
    # separator, so a sibling directory can never satisfy the check.
    if target_path != base_path and not str(target_path).startswith(str(base_path) + os.sep):
        raise ValueError(f"Path traversal detected: {target_path} is outside of {base_path}")

    return str(target_path)

def resolve_storage_path(path: str) -> str:
    """
    Standardized resolve_path utility for environment abstraction (Phase 1).
    Prioritizes $BEJSON_STORAGE_ROOT.
    """
    storage_root = os.environ.get("BEJSON_STORAGE_ROOT")
    if not storage_root:
        # Fallback to local home if storage root is unknown
        storage_root = os.path.expanduser("~")
        
    if not path:
        return storage_root

    # Standardize absolute paths from legacy hardcoding (if encountered)
    if path.startswith("/storage/emulated/0"):
        return path.replace("/storage/emulated/0", storage_root)
        
    return path

def _bejson_mfdb_escapes_root(relative_path: str) -> bool:
    """
    Relative-depth path traversal check.  Normalizes separators then counts
    directory depth segment by segment.  Returns True (path is unsafe) if any
    '..' segment attempts to drop the depth below 0, indicating an escape
    above the MFDB root.

    Mirrors _escapesRoot in lib_bejson_Core_mfdb_validators.ts exactly
    (Remediation NEW-08).

    Args:
        relative_path: A relative path string, e.g. '../104a.mfdb.bejson'.

    Returns:
        True  — path escapes root (unsafe, reject).
        False — path stays within root (safe).
    """
    normalized = relative_path.replace("\\", "/")
    parts = normalized.split("/")
    depth = 0
    for part in parts:
        if part == "..":
            depth -= 1
            if depth < 0:
                return True
        elif part != "." and part != "":
            depth += 1
    return False


VERSION = "1.2.1"

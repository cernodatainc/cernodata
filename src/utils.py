"""
src/utils.py

Shared utility functions for file system operations.
"""

import hashlib
import json
import os
import socket
from typing import Any, Optional, Union

__all__ = [
    "mkdirs",
    "find_available_port",
    "resolve_pdf_path",
    "resolve_and_validate_pdf_path",
    "generate_document_id",
    "safe_load_json",
]


def safe_load_json(file_path: Union[str, os.PathLike[str]], default: Any = None) -> Any:
    """Safely reads and deserializes a UTF-8 JSON file if it exists, returning default on failure."""
    fpath = os.fspath(file_path)
    if not os.path.exists(fpath):
        return default
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return default


_DOC_ID_MODULUS = 1_000_000


def generate_document_id(source_filename: str) -> str:
    """Generates a stable pseudo-unique document ID from a source filename."""
    base_name = os.path.basename(source_filename)
    digest = hashlib.sha1(base_name.encode("utf-8")).hexdigest()
    return f"doc_{int(digest, 16) % _DOC_ID_MODULUS:06d}"


def resolve_pdf_path(path: str) -> str:
    """
    Resolves relative or bare PDF filenames to actual filesystem paths,
    checking repository root, src/e2e/, and output/ directories.
    """
    if not path:
        return path
    if os.path.exists(path):
        return path

    norm = path.replace("\\", "/")
    basename = os.path.basename(norm)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    candidates = [
        os.path.join(repo_root, norm),
        os.path.join(repo_root, "src", "e2e", basename),
        os.path.join(repo_root, "src", "e2e", norm),
        os.path.join(repo_root, "output", basename),
        os.path.join(repo_root, basename),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return os.path.abspath(cand)

    return path


def resolve_and_validate_pdf_path(path: str) -> str:
    """
    Resolves relative or bare PDF filenames to actual filesystem paths
    and verifies the file exists on disk, raising FileNotFoundError otherwise.
    """
    resolved = resolve_pdf_path(path)
    if not os.path.exists(resolved):
        raise FileNotFoundError(f"PDF document not found: '{path}'")
    return resolved


def find_available_port(start_port: int = 8000, max_attempts: int = 50) -> int:
    """
    Finds an available TCP port starting from start_port by testing bind availability.
    Falls back to an OS-assigned ephemeral port if the scanned range is exhausted.
    """
    attempts = max(0, max_attempts)
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def mkdirs(
    path: Optional[Union[str, os.PathLike[str]]] = None,
    mode: int = 0o777,
    exist_ok: bool = True,
) -> None:
    """
    Recursively creates directories like os.makedirs, safely ignoring
    empty strings and None paths.
    """
    path_str = os.fspath(path) if path is not None else ""
    if not path_str:
        return
    os.makedirs(path_str, mode=mode, exist_ok=exist_ok)

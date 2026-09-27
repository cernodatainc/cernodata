"""
src/utils.py

Shared utility functions for file system operations.
"""

import os
import socket
from typing import Optional, Union

__all__ = ["mkdirs", "find_available_port", "resolve_pdf_path"]


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


def find_available_port(start_port: int = 8000, max_attempts: int = 50) -> int:
    """Finds an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def mkdirs(
    path: Optional[Union[str, os.PathLike]] = None,
    mode: int = 0o777,
    exist_ok: bool = True,
) -> None:
    """
    Recursively creates directories like os.makedirs, safely ignoring
    empty strings and None paths.
    """
    if not path:
        return
    path_str = os.fspath(path)
    if not path_str:
        return
    os.makedirs(path_str, mode=mode, exist_ok=exist_ok)

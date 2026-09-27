"""
src/utils.py

Shared utility functions for file system operations.
"""

import os
from typing import Optional, Union

__all__ = ["mkdirs"]


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

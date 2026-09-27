"""
src/parsers/pdf_utils.py

Shared pypdfium2 context manager utilities for safe PDF lifecycle management.
"""

import os
from contextlib import contextmanager
from typing import Iterator, Optional, Any

HAS_PYPDFIUM = False
try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


@contextmanager
def open_pdf(pdf_path: str) -> Iterator[Optional[Any]]:
    """
    Context manager that safely opens a PDF document with pypdfium2,
    yielding the PdfDocument or None on failure, and ensuring closure on exit.
    """
    if not HAS_PYPDFIUM or not os.path.exists(pdf_path):
        yield None
        return

    try:
        pdf = pypdfium2.PdfDocument(pdf_path)
    except Exception:
        yield None
        return

    try:
        yield pdf
    finally:
        pdf.close()

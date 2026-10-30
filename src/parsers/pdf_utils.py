"""
src/parsers/pdf_utils.py

Shared pypdfium2 context manager utilities for safe PDF lifecycle management.
"""

import os
import logging
from contextlib import contextmanager
from typing import Iterator, Optional, Any, List, Dict

logger = logging.getLogger("cernodata.pdf_utils")

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
    if not HAS_PYPDFIUM:
        logger.warning("pypdfium2 is not available to open %s", pdf_path)
        yield None
        return
    if not os.path.exists(pdf_path):
        logger.warning("PDF path does not exist: %s", pdf_path)
        yield None
        return

    try:
        pdf = pypdfium2.PdfDocument(pdf_path)
    except Exception as ex:
        logger.error("Failed opening PDF document '%s': %s", pdf_path, ex)
        yield None
        return

    try:
        yield pdf
    finally:
        pdf.close()


def slice_pdf_pages(pdf_path: str, page_indices: List[int], output_dir: str) -> str:
    """No-op hook returning original PDF path until single-page slicing is implemented."""
    # TODO(TASK-801): Implement `slice_pdf_pages(pdf_path, page_indices, output_dir)` using `pypdfium2` (`import_pages`)
    # so `FallbackLoopHandler` can extract and re-parse only failing pages instead of the entire PDF.
    _ = (page_indices, output_dir)
    return pdf_path


def extract_layout_only_boxes(pdf_path: str) -> List[Dict[str, Any]]:
    """No-op hook returning an empty box list until structure-only debug pass is implemented."""
    # TODO(TASK-1002): Implement a fast structure-only page bounding-box extractor here for the
    # Web Hub and Viewer 'Instant Layout Preview (Skip OCR)' button.
    _ = pdf_path
    return []

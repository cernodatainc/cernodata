"""
src/visualization/viewer/pdf_renderer.py

Helper functions for rendering PDF pages to base64 data URIs.
"""

import os
import base64
import io

from typing import List, Dict, Any, Optional

HAS_PYPDFIUM = False
try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


def page_to_base64(pdf_path: str, page_index: int = 0, scale: float = 150 / 72.0) -> str:
    """Renders PDF page to PNG and converts to base64 data URI."""
    if HAS_PYPDFIUM and os.path.exists(pdf_path):
        try:
            pdf = pypdfium2.PdfDocument(pdf_path)
            if 0 <= page_index < len(pdf):
                pil_img = pdf[page_index].render(scale=scale).to_pil().convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
        except Exception as e:
            print(f"[WARN] Base64 page render error: {e}")

    svg_canvas = '<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792" style="background:#111827;"></svg>'
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_canvas.encode('utf-8')).decode('utf-8')}"


def get_pdf_page_dimensions(pdf_path: str) -> List[Dict[str, float]]:
    """Returns the width and height of each page in points."""
    dimensions: List[Dict[str, float]] = []
    if HAS_PYPDFIUM and os.path.exists(pdf_path):
        try:
            pdf = pypdfium2.PdfDocument(pdf_path)
            for page in pdf:
                w, h = page.get_size()
                dimensions.append({"width": round(float(w), 2), "height": round(float(h), 2)})
            return dimensions
        except Exception as e:
            print(f"[WARN] Could not retrieve PDF page dimensions: {e}")
    return dimensions


def render_all_pages_to_base64(pdf_path: str, total_pages: Optional[int] = None, scale: float = 150 / 72.0) -> List[str]:
    """Renders all PDF pages to PNG and converts them to base64 data URIs."""
    if HAS_PYPDFIUM and os.path.exists(pdf_path):
        try:
            pdf = pypdfium2.PdfDocument(pdf_path)
            count = len(pdf)
            if total_pages is not None:
                count = min(count, total_pages)
            images: List[str] = []
            for i in range(count):
                pil_img = pdf[i].render(scale=scale).to_pil().convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                images.append(f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}")
            if images:
                return images
        except Exception as e:
            print(f"[WARN] Base64 all pages render error: {e}")

    return [page_to_base64(pdf_path, page_index=0, scale=scale)]

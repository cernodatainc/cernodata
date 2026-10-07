"""
src/pipeline/server/routes/ocr.py

Interactive section OCR parsing API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

from typing import Any, Dict

from src.parsers.section_ocr import parse_image_ocr, parse_section_from_pdf
from src.pipeline.server.http_utils import send_json_response
from src.pipeline.server.routes.base import BaseApiRoutesMixin


class OcrRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling on-demand sub-section OCR execution endpoints."""

    def _handle_post_parse_ocr(self, payload: Dict[str, Any]) -> None:
        """
        Parses selected DOM section or image via OCR.

        Args:
            payload: Dictionary with image_base64 or (pdf_path and bbox), node_id, page, language.
        """
        node_id = payload.get("node_id", "")
        image_base64 = payload.get("image_base64")
        bbox = payload.get("bbox")
        try:
            page = int(payload.get("page") or 1)
        except (ValueError, TypeError):
            page = 1
        pdf_path = payload.get("pdf_path") or self.session.pdf_path
        language = payload.get("language") or self.session.language or "en"

        print(f"\n[SERVER API] Parsing selected section '{node_id}' using OCR (Lang: {language})...")

        ocr_result: Any
        if image_base64:
            ocr_result = parse_image_ocr(image_base64, language=language)
        elif pdf_path and bbox:
            ocr_result = parse_section_from_pdf(pdf_path, page, bbox, language=language)
        else:
            send_json_response(self, 400, {  # type: ignore[arg-type]
                "success": False,
                "error": "Either image_base64 or (pdf_path and bbox) must be provided.",
            })
            return

        if not isinstance(ocr_result, dict):
            ocr_result = {"success": False, "error": "Invalid OCR result structure"}

        response_data = {
            "success": ocr_result.get("success", False),
            "node_id": node_id,
            "text": ocr_result.get("text", ""),
            "confidence": ocr_result.get("confidence", 0.0),
            "lines": ocr_result.get("lines", []),
            "error": ocr_result.get("error"),
        }
        send_json_response(self, 200 if response_data["success"] else 422, response_data)  # type: ignore[arg-type]

"""
src/pipeline/server/routes/ocr.py

Interactive section OCR parsing API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.parsers.section_ocr import (
    get_available_ocr_engines,
    parse_image_ocr_multi,
    parse_section_from_pdf_multi,
)
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger


class OcrRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling on-demand sub-section OCR execution endpoints."""

    def _handle_get_ocr_engines(self) -> None:
        """Returns list of available and registered OCR engines."""
        engines = get_available_ocr_engines()
        self.send_json(200, {"engines": engines, "default": "rapidocr"})

    def _handle_post_parse_ocr(self, payload: Dict[str, Any]) -> None:
        """
        Parses selected DOM section or image via one or more OCR engines.

        Args:
            payload: Dictionary with image_base64 or (pdf_path and bbox), node_id, page, language, engine/engines.
        """
        node_id = str(payload.get("node_id") or "")
        image_base64 = payload.get("image_base64")
        bbox = payload.get("bbox")
        try:
            page = int(payload.get("page") or 1)
        except (ValueError, TypeError):
            page = 1
        pdf_path = payload.get("pdf_path") or self.session.pdf_path
        language = payload.get("language") or self.session.language or "en"

        raw_engines = payload.get("engines")
        raw_engine = payload.get("engine")
        selected_engines: List[str] = []
        if isinstance(raw_engines, (list, tuple)) and raw_engines:
            selected_engines = [str(e).strip().lower() for e in raw_engines if str(e).strip()]
        elif raw_engine and isinstance(raw_engine, str) and raw_engine.strip():
            selected_engines = [raw_engine.strip().lower()]

        if not selected_engines:
            selected_engines = ["rapidocr"]

        logger.info(
            "Parsing section '%s' using OCR engines: %s (Lang: %s)",
            node_id,
            ", ".join(selected_engines),
            language,
        )

        multi_results: Dict[str, Any]
        if image_base64:
            multi_results = parse_image_ocr_multi(image_base64, engines=selected_engines, language=language)
        elif pdf_path and bbox:
            multi_results = parse_section_from_pdf_multi(
                pdf_path, page, bbox, engines=selected_engines, language=language
            )
        else:
            self.send_bad_request("Either image_base64 or (pdf_path and bbox) must be provided.")
            return

        # Determine primary/best result (highest confidence among successful runs)
        best_engine: Optional[str] = None
        best_result: Dict[str, Any] = {}
        for eng in selected_engines:
            r = multi_results.get(eng)
            if isinstance(r, dict) and r.get("success"):
                if not best_result or float(r.get("confidence", 0.0)) > float(best_result.get("confidence", 0.0)):
                    best_engine = eng
                    best_result = dict(r)

        if not best_result:
            first_eng = selected_engines[0] if selected_engines else "rapidocr"
            best_engine = first_eng
            first_raw = multi_results.get(first_eng)
            best_result = dict(first_raw) if isinstance(first_raw, dict) else {"success": False, "error": "No OCR result"}

        has_any_success = any(
            isinstance(r, dict) and r.get("success", False) for r in multi_results.values()
        )

        response_data: Dict[str, Any] = {
            "success": has_any_success,
            "node_id": node_id,
            "text": best_result.get("text", ""),
            "confidence": best_result.get("confidence", 0.0),
            "lines": best_result.get("lines", []),
            "engine": best_engine,
            "engines": selected_engines,
            "results": multi_results,
            "error": best_result.get("error"),
        }
        self.send_json(200 if has_any_success else 422, response_data)

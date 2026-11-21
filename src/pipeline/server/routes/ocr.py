"""
src/pipeline/server/routes/ocr.py

Interactive section OCR parsing API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.parsers.ocr_flags import parse_ocr_custom_flags, summarize_applied_flags
from src.parsers.section_ocr import (
    get_available_ocr_engines,
    parse_image_ocr_multi,
    parse_section_from_pdf_multi,
)
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger
from src.utils import resolve_pdf_path


class SectionOcrRequest(BaseModel):
    """Validated and normalized request payload for section OCR parsing."""

    model_config = ConfigDict(extra="ignore")

    node_id: str = ""
    image_base64: Optional[str] = None
    bbox: Optional[Any] = None
    page: int = 1
    pdf_path: str = ""
    language: str = ""
    engines: List[str] = Field(default_factory=list)
    custom_flags: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return {}
        norm = dict(data)
        raw_engines = norm.get("engines")
        raw_engine = norm.get("engine")
        if isinstance(raw_engines, (list, tuple)) and raw_engines:
            norm["engines"] = [str(e).strip().lower() for e in raw_engines if str(e).strip()]
        elif raw_engine and isinstance(raw_engine, str) and raw_engine.strip():
            norm["engines"] = [raw_engine.strip().lower()]
        else:
            norm["engines"] = []
        try:
            norm["page"] = max(1, int(norm.get("page") or 1))
        except (ValueError, TypeError):
            norm["page"] = 1
        norm["node_id"] = str(norm.get("node_id") or "")
        norm["pdf_path"] = str(norm.get("pdf_path") or "")
        norm["language"] = str(norm.get("language") or "")
        norm["custom_flags"] = str(norm.get("custom_flags") or "").strip()
        return norm


class OcrRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling on-demand sub-section OCR execution endpoints."""

    def _handle_get_ocr_engines(self) -> None:
        """Returns list of available and registered OCR engines."""
        engines = get_available_ocr_engines()
        self.send_json(200, {"engines": engines})

    def _handle_post_parse_ocr(self, payload: Dict[str, Any]) -> None:
        """
        Parses selected DOM section or image via one or more OCR engines.

        Args:
            payload: Dictionary with image_base64 or (pdf_path and bbox), node_id, page, language, engine/engines.
        """
        req = SectionOcrRequest.model_validate(payload)
        raw_pdf = req.pdf_path or self.session.pdf_path
        pdf_path = resolve_pdf_path(raw_pdf) if raw_pdf else ""
        language = req.language or self.session.language or "en"
        selected_engines = req.engines

        if not selected_engines:
            self.send_bad_request(
                "Missing or empty 'engines' / 'engine' parameter. An OCR engine must be explicitly specified."
            )
            return

        available = get_available_ocr_engines()
        invalid = [e for e in selected_engines if e not in available]
        if invalid:
            self.send_bad_request(
                f"Unknown OCR engine(s): {', '.join(invalid)}. Available engines: {', '.join(available)}"
            )
            return

        parsed_flags = parse_ocr_custom_flags(req.custom_flags)
        logger.info(
            "Parsing section '%s' using OCR engines: %s (Lang: %s%s)",
            req.node_id,
            ", ".join(selected_engines),
            language,
            f", Flags: {req.custom_flags}" if req.custom_flags else "",
        )

        multi_results: Dict[str, Any]
        if req.image_base64:
            multi_results = parse_image_ocr_multi(
                req.image_base64, engines=selected_engines, language=language, custom_flags=req.custom_flags
            )
        elif pdf_path and req.bbox:
            multi_results = parse_section_from_pdf_multi(
                pdf_path, req.page, req.bbox, engines=selected_engines, language=language, custom_flags=req.custom_flags
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
                if not best_result or float(r.get("confidence") or 0.0) > float(best_result.get("confidence") or 0.0):
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
            "node_id": req.node_id,
            "text": best_result.get("text", ""),
            "confidence": best_result.get("confidence", 0.0),
            "lines": best_result.get("lines", []),
            "engine": best_engine,
            "engines": selected_engines,
            "custom_flags": req.custom_flags,
            "applied_flags": summarize_applied_flags(parsed_flags),
            "results": multi_results,
            "error": best_result.get("error"),
        }
        self.send_json(200 if has_any_success else 422, response_data)

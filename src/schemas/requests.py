"""
src/schemas/requests.py

Pydantic boundary request schemas for cernodata HTTP server API endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _coerce_optional_str_list(raw: Any) -> Optional[List[str]]:
    """Coerces list/tuple sequences into a list of stripped non-empty strings, or None."""
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    return None


def _normalize_mapping(data: Any) -> Dict[str, Any]:
    """Ensures raw JSON payload is a mutable dictionary."""
    return dict(data) if isinstance(data, dict) else {}


class SaveDomRequest(BaseModel):
    """Validated boundary payload for /api/save_dom."""

    model_config = ConfigDict(extra="ignore")

    dom: Dict[str, Any]
    output_dir: str = ""
    raw_dom: Optional[Dict[str, Any]] = None
    diff: Optional[Dict[str, Any]] = None
    violations: Optional[List[Dict[str, Any]]] = None
    decision: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        if norm.get("output_dir") is None:
            norm["output_dir"] = ""
        else:
            norm["output_dir"] = str(norm["output_dir"])
        return norm

    @field_validator("dom")
    @classmethod
    def _require_non_empty_dom(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if not value:
            raise ValueError("Missing dom payload")
        return value


class VerifyLayersRequest(BaseModel):
    """Validated boundary payload for /api/verify_layers."""

    model_config = ConfigDict(extra="ignore")

    output_dir: str = ""
    verification_layers: Optional[List[str]] = None
    language: str = ""
    target_threshold: float = 0.82

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        norm["output_dir"] = str(norm.get("output_dir") or "")
        norm["language"] = str(norm.get("language") or "")
        norm["verification_layers"] = _coerce_optional_str_list(norm.get("verification_layers"))
        if norm.get("target_threshold") is None:
            norm["target_threshold"] = 0.82
        return norm


class RunPipelineRequest(BaseModel):
    """Validated boundary payload for /api/run."""

    model_config = ConfigDict(extra="ignore")

    pdf_path: str = ""
    language: str = ""
    target_threshold: float = 0.85
    preset: Optional[str] = None
    align_skew: bool = True
    visualize: bool = True
    with_plan: bool = False
    plan_config: Optional[Dict[str, Any]] = None
    force: bool = False
    verification_layers: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        norm["pdf_path"] = str(norm.get("pdf_path") or "")
        norm["language"] = str(norm.get("language") or "")
        raw_preset = norm.get("preset")
        norm["preset"] = str(raw_preset).strip() if raw_preset else None
        if norm.get("target_threshold") is None:
            norm["target_threshold"] = 0.85
        if norm.get("align_skew") is None:
            norm["align_skew"] = True
        if norm.get("visualize") is None:
            norm["visualize"] = True
        norm["with_plan"] = bool(norm.get("with_plan", False))
        norm["force"] = bool(norm.get("force", norm.get("force_rerun", False)))
        norm["verification_layers"] = _coerce_optional_str_list(norm.get("verification_layers"))
        return norm


class RerunPipelineRequest(BaseModel):
    """Validated boundary payload for /api/rerun."""

    model_config = ConfigDict(extra="ignore")

    preset: str = ""
    pdf_path: str = ""
    language: str = ""
    force: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        raw_preset = norm.get("preset")
        norm["preset"] = str(raw_preset).strip() if raw_preset else ""
        norm["pdf_path"] = str(norm.get("pdf_path") or "")
        norm["language"] = str(norm.get("language") or "")
        norm["force"] = bool(norm.get("force", norm.get("force_rerun", False)))
        return norm


class RemoveRunRequest(BaseModel):
    """Validated boundary payload for /api/remove_run."""

    model_config = ConfigDict(extra="ignore")

    run_id: str = ""
    output_dir: Optional[str] = None
    document_path: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        norm["run_id"] = str(norm.get("run_id") or "").strip()
        raw_doc = norm.get("document_path")
        norm["document_path"] = str(raw_doc).strip() if raw_doc else None
        return norm


class AddDocumentsRequest(BaseModel):
    """Validated boundary payload for /api/documents and /api/add_file."""

    model_config = ConfigDict(extra="ignore")

    paths: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        collected: List[str] = []
        raw_paths = norm.get("paths")
        if isinstance(raw_paths, list):
            collected.extend(str(p) for p in raw_paths if p)
        for key in ("file_path", "path", "filename", "document_path"):
            val = norm.get(key)
            if val and str(val) not in collected:
                collected.append(str(val))
        return {"paths": collected}


class DocumentTargetRequest(BaseModel):
    """Validated boundary payload for /api/forget_file and /api/unforget_file."""

    model_config = ConfigDict(extra="ignore")

    target_path: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        raw = norm.get("file_path") or norm.get("document_path") or norm.get("path") or norm.get("target_path") or ""
        return {"target_path": str(raw).strip()}


class SubmitPlanRequest(BaseModel):
    """Validated boundary payload for /api/submit_plan parameter extraction."""

    model_config = ConfigDict(extra="ignore")

    document_path: str = ""
    language: Optional[str] = None
    target_threshold: Optional[float] = None
    override_primary: Optional[str] = None
    override_order: Optional[List[str]] = None
    verification_layers: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_inputs(cls, data: Any) -> Dict[str, Any]:
        norm = _normalize_mapping(data)
        raw_doc = norm.get("document_path")
        norm["document_path"] = raw_doc.strip() if isinstance(raw_doc, str) else ""
        raw_lang = norm.get("language")
        if isinstance(raw_lang, str) and raw_lang.strip() and raw_lang.strip().lower() != "none":
            norm["language"] = raw_lang.strip()
        else:
            norm["language"] = None
        raw_order = norm.get("override_order")
        if isinstance(raw_order, (list, tuple)) and raw_order:
            cleaned_order = [str(p) for p in raw_order if p]
            norm["override_order"] = cleaned_order or None
        else:
            norm["override_order"] = None
        norm["verification_layers"] = _coerce_optional_str_list(norm.get("verification_layers"))
        raw_thresh = norm.get("target_threshold")
        if raw_thresh is not None:
            try:
                norm["target_threshold"] = float(raw_thresh)
            except (ValueError, TypeError):
                norm["target_threshold"] = None
        return norm

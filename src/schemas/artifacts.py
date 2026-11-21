"""
src/schemas/artifacts.py

Validated artifact container and filesystem loader for pipeline execution runs.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.dom.enums import DecisionStatus
from src.parsers.pdf_utils import get_pdf_page_count
from src.schemas.decision import DecisionTreeSchema
from src.schemas.dom import DocumentDOMSchema
from src.schemas.execution import PipelineExecutionResultSchema
from src.schemas.plan import DocumentPlanSchema
from src.schemas.violations import QualityViolationSchema, parse_violations_payload
from src.utils import resolve_pdf_path, safe_load_json as _read_json_file

logger = logging.getLogger("cernodata.schemas.artifacts")

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _validate_optional_dict(schema_cls: Type[_ModelT], raw: Any, label: str, run_dir: str) -> Optional[_ModelT]:
    """Validates a dictionary against schema_cls, logging and returning None on failure."""
    if not isinstance(raw, dict):
        return None
    try:
        return schema_cls.model_validate(raw)
    except ValidationError as e:
        logger.debug("Ignoring invalid %s in %s: %s", label, run_dir, e)
        return None


class ValidatedRunArtifacts(BaseModel):
    """Strongly-typed and validated container holding cohesive pipeline run artifacts."""

    model_config = ConfigDict(extra="ignore")

    dom: DocumentDOMSchema
    decision: DecisionTreeSchema
    plan: Optional[DocumentPlanSchema] = None
    execution_result: Optional[PipelineExecutionResultSchema] = None
    violations: List[QualityViolationSchema] = Field(default_factory=list)
    raw_dom: Optional[DocumentDOMSchema] = None
    diff: Dict[str, Any] = Field(default_factory=dict)
    chosen_preset: str = ""
    status: DecisionStatus = DecisionStatus.ACCEPT
    overall_confidence: float = 1.0
    document_path: str = ""
    document_name: str = "Unknown"

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: Any) -> DecisionStatus:
        return DecisionStatus.coerce(v)

    @property
    def active_violations(self) -> List[QualityViolationSchema]:
        """Returns list of violations that are not suppressed, accepted, or fixed."""
        return [v for v in self.violations if v.is_active()]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes validated artifacts to dictionary for backwards-compatible consumers."""
        return self.model_dump()


def _resolve_doc_pdf_path(doc_path: str, repo_root: Optional[str] = None) -> Optional[str]:
    """Resolves a document path to an existing PDF file, scoped to repo_root when provided."""
    if not doc_path:
        return None
    norm = doc_path.replace("\\", "/")
    if repo_root:
        base = os.path.basename(norm)
        for cand in (
            norm if os.path.isabs(norm) else os.path.join(repo_root, norm),
            os.path.join(repo_root, "src", "e2e", base),
            os.path.join(repo_root, "output", base),
            os.path.join(repo_root, base),
        ):
            if os.path.isfile(cand):
                return cand
        return None
    resolved = resolve_pdf_path(doc_path)
    return resolved if os.path.isfile(resolved) else None


def _validate_run_pages(
    dom: DocumentDOMSchema,
    dec_schema: DecisionTreeSchema,
    doc_path: str,
    run_dir: str,
    repo_root: Optional[str] = None,
) -> bool:
    """
    Validates that run page counts and page indices are consistent with the DOM
    and the source PDF document (when available on disk).
    """
    if dom.total_pages < 1:
        logger.debug("Dropping run %s: non-positive total_pages (%d)", run_dir, dom.total_pages)
        return False

    for node in dom.nodes:
        if node.global_page_index < 1 or node.global_page_index > dom.total_pages:
            logger.debug(
                "Dropping run %s: node %s has out-of-bounds global_page_index=%d (total_pages=%d)",
                run_dir,
                node.node_id,
                node.global_page_index,
                dom.total_pages,
            )
            return False

    for page_key in dec_schema.per_page_confidence:
        try:
            page_num = int(page_key)
        except (ValueError, TypeError):
            continue
        if page_num < 1 or page_num > dom.total_pages:
            logger.debug(
                "Dropping run %s: per_page_confidence has out-of-bounds page %d (total_pages=%d)",
                run_dir,
                page_num,
                dom.total_pages,
            )
            return False

    pdf_file = _resolve_doc_pdf_path(doc_path, repo_root=repo_root)
    if pdf_file:
        actual_pages = get_pdf_page_count(pdf_file)
        if actual_pages is not None and actual_pages >= 1 and dom.total_pages != actual_pages:
            logger.debug(
                "Dropping run %s: run total_pages (%d) does not match document '%s' page count (%d)",
                run_dir,
                dom.total_pages,
                pdf_file,
                actual_pages,
            )
            return False

    return True


def load_validated_run_artifacts(
    run_dir: str,
    repo_root: Optional[str] = None,
) -> Optional[ValidatedRunArtifacts]:
    """
    Loads and validates run artifacts strictly from an output directory.
    If required artifacts are missing or fail contract validation, drops the run by returning None.

    Args:
        run_dir: Path to output directory containing pipeline run artifacts.

    Returns:
        ValidatedRunArtifacts instance if all contract schemas pass, otherwise None.
    """
    dom_path = os.path.join(run_dir, "document_dom.json")
    dom_raw = _read_json_file(dom_path)
    if dom_raw is None or not isinstance(dom_raw, dict):
        logger.debug("Dropping run %s: missing or invalid document_dom.json", run_dir)
        return None

    try:
        dom = DocumentDOMSchema.model_validate(dom_raw)
    except ValidationError as e:
        logger.debug("Dropping run %s: DocumentDOM validation failed: %s", run_dir, e)
        return None

    # Load decision tree or execution result
    dec_raw = _read_json_file(os.path.join(run_dir, "decision_tree.json"))
    exec_result = _validate_optional_dict(
        PipelineExecutionResultSchema,
        _read_json_file(os.path.join(run_dir, "plan_execution_result.json")),
        "plan_execution_result.json",
        run_dir,
    )

    if dec_raw is None and exec_result and exec_result.decision:
        dec_schema = exec_result.decision
    else:
        dec_opt = _validate_optional_dict(DecisionTreeSchema, dec_raw, "decision_tree.json", run_dir)
        if dec_opt is None:
            logger.debug("Dropping run %s: missing or invalid decision_tree.json and plan_execution_result.json", run_dir)
            return None
        dec_schema = dec_opt

    # Load plan if present
    plan_schema = (
        exec_result.plan
        if exec_result and exec_result.plan
        else _validate_optional_dict(DocumentPlanSchema, _read_json_file(os.path.join(run_dir, "plan.json")), "plan.json", run_dir)
    )

    # Load violations
    viols_raw = _read_json_file(os.path.join(run_dir, "quality_violations.json"))
    if viols_raw is None and exec_result and exec_result.violations:
        violations = exec_result.violations
    else:
        try:
            violations = parse_violations_payload(viols_raw if viols_raw is not None else [])
        except ValidationError:
            violations = []

    # Optional raw DOM and diff
    raw_dom_schema = _validate_optional_dict(
        DocumentDOMSchema,
        _read_json_file(os.path.join(run_dir, "raw_document_dom.json")),
        "raw_document_dom.json",
        run_dir,
    )
    diff_data = _read_json_file(os.path.join(run_dir, "run_diff.json")) or {}

    chosen_preset = (
        dec_schema.chosen_preset
        or dec_schema.preset_id
        or (exec_result.chosen_preset if exec_result else None)
        or (plan_schema.primary_preset if plan_schema else "")
        or ""
    )
    status = (
        dec_schema.status
        or (exec_result.status if exec_result else DecisionStatus.ACCEPT)
    )
    exec_conf = (
        exec_result.overall_confidence
        if exec_result and "overall_confidence" in exec_result.model_fields_set
        else (
            exec_result.decision.overall_confidence
            if exec_result and exec_result.decision and "overall_confidence" in exec_result.decision.model_fields_set
            else None
        )
    )
    overall_conf = (
        dec_schema.overall_confidence
        if "overall_confidence" in dec_schema.model_fields_set
        else (exec_conf if exec_conf is not None else dec_schema.overall_confidence)
    )

    doc_path = ""
    if plan_schema and plan_schema.document_path:
        doc_path = plan_schema.document_path
    elif dom.source_filename:
        doc_path = dom.source_filename

    if not _validate_run_pages(dom, dec_schema, doc_path, run_dir, repo_root=repo_root):
        return None

    doc_name = os.path.basename(doc_path) if doc_path else "Unknown"

    return ValidatedRunArtifacts(
        dom=dom,
        decision=dec_schema,
        plan=plan_schema,
        execution_result=exec_result,
        violations=violations,
        raw_dom=raw_dom_schema or dom,
        diff=diff_data if isinstance(diff_data, dict) else {},
        chosen_preset=chosen_preset,
        status=status,
        overall_confidence=float(overall_conf),
        document_path=doc_path,
        document_name=doc_name,
    )

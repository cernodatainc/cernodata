"""
src/schemas/artifacts.py

Validated artifact container and filesystem loader for pipeline execution runs.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.schemas.decision import DecisionTreeSchema
from src.schemas.dom import DocumentDOMSchema
from src.schemas.execution import PipelineExecutionResultSchema
from src.schemas.plan import DocumentPlanSchema
from src.schemas.violations import QualityViolationSchema, parse_violations_payload

logger = logging.getLogger("cernodata.schemas.artifacts")


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
    chosen_preset: str = "docling_fast"
    status: str = "ACCEPT"
    overall_confidence: float = 1.0
    document_path: str = ""
    document_name: str = "Unknown"

    @property
    def active_violations(self) -> List[QualityViolationSchema]:
        """Returns list of violations that are not suppressed, accepted, or fixed."""
        return [v for v in self.violations if v.is_active()]

    def to_dict(self) -> Dict[str, Any]:
        """Serializes validated artifacts to dictionary for backwards-compatible consumers."""
        return self.model_dump()


def _read_json_file(file_path: str) -> Optional[Any]:
    """Reads and deserializes a JSON file if it exists, returning None on missing or corrupt files."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.debug("Failed reading JSON file %s: %s", file_path, e)
        return None


def load_validated_run_artifacts(run_dir: str) -> Optional[ValidatedRunArtifacts]:
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
    dec_path = os.path.join(run_dir, "decision_tree.json")
    dec_raw = _read_json_file(dec_path)

    plan_res_path = os.path.join(run_dir, "plan_execution_result.json")
    plan_res_raw = _read_json_file(plan_res_path)
    exec_result: Optional[PipelineExecutionResultSchema] = None
    if isinstance(plan_res_raw, dict):
        try:
            exec_result = PipelineExecutionResultSchema.model_validate(plan_res_raw)
        except ValidationError:
            pass

    if dec_raw is None and exec_result and exec_result.decision:
        dec_schema = exec_result.decision
    elif isinstance(dec_raw, dict):
        try:
            dec_schema = DecisionTreeSchema.model_validate(dec_raw)
        except ValidationError as e:
            logger.debug("Dropping run %s: DecisionTree validation failed: %s", run_dir, e)
            return None
    else:
        logger.debug("Dropping run %s: missing decision_tree.json and valid plan_execution_result.json", run_dir)
        return None

    # Load plan if present
    plan_schema: Optional[DocumentPlanSchema] = None
    if exec_result and exec_result.plan:
        plan_schema = exec_result.plan
    else:
        plan_path = os.path.join(run_dir, "plan.json")
        plan_raw = _read_json_file(plan_path)
        if isinstance(plan_raw, dict):
            try:
                plan_schema = DocumentPlanSchema.model_validate(plan_raw)
            except ValidationError:
                pass

    # Load violations
    q_viols_path = os.path.join(run_dir, "quality_violations.json")
    viols_raw = _read_json_file(q_viols_path)
    if viols_raw is None and exec_result and exec_result.violations:
        violations = exec_result.violations
    else:
        try:
            violations = parse_violations_payload(viols_raw if viols_raw is not None else [])
        except ValidationError:
            violations = []

    # Optional raw DOM and diff
    raw_dom_path = os.path.join(run_dir, "raw_document_dom.json")
    raw_dom_data = _read_json_file(raw_dom_path)
    raw_dom_schema: Optional[DocumentDOMSchema] = None
    if isinstance(raw_dom_data, dict):
        try:
            raw_dom_schema = DocumentDOMSchema.model_validate(raw_dom_data)
        except ValidationError:
            pass

    diff_path = os.path.join(run_dir, "run_diff.json")
    diff_data = _read_json_file(diff_path) or {}

    chosen_preset = (
        dec_schema.chosen_preset
        or (exec_result.chosen_preset if exec_result else None)
        or (plan_schema.primary_preset if plan_schema else "docling_fast")
    )
    status = (
        dec_schema.status
        or (exec_result.status if exec_result else "ACCEPT")
    )
    exec_conf = (
        exec_result.overall_confidence
        if exec_result and exec_result.overall_confidence is not None
        else (exec_result.decision.overall_confidence if exec_result and exec_result.decision else None)
    )
    overall_conf = (
        dec_schema.overall_confidence
        if dec_schema.overall_confidence is not None
        else (exec_conf if exec_conf is not None else 1.0)
    )

    doc_path = ""
    if plan_schema and plan_schema.document_path:
        doc_path = plan_schema.document_path
    elif dom.source_filename:
        doc_path = dom.source_filename

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

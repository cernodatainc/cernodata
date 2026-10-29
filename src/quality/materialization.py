"""
src/quality/materialization.py

Materialized document verification and scoring engine.
Evaluates document confidence and quality violations across chosen verification layers,
materializes the results onto DOM nodes, and persists updated artifacts to disk.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from src.dom import DocumentDOM
from src.quality.evaluator import evaluate_document_confidence
from src.quality.layers import normalize_layer_name, normalize_layers
from src.quality.violations import detect_quality_violations
from src.utils import mkdirs

logger = logging.getLogger("cernodata.quality.materialization")


def group_violations_by_layer(
    violations: List[Dict[str, Any]], active_layers: Sequence[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Groups violation dictionaries into buckets keyed by normalized verification layer."""
    by_layer: Dict[str, List[Dict[str, Any]]] = {lyr: [] for lyr in active_layers}
    for v in violations:
        raw_type = v.get("type", "")
        norm_type = normalize_layer_name(raw_type) or raw_type or "other"
        by_layer.setdefault(norm_type, []).append(v)
    return by_layer


@dataclass
class MaterializedVerificationResult:
    """Strongly-typed materialized verification record containing criteria scores and violations."""
    document_id: str
    source_filename: str
    selected_layers: List[str]
    overall_confidence: float
    per_page_confidence: Dict[int, float]
    layer_scores: Dict[str, float]
    per_page_layer_scores: Dict[int, Dict[str, float]]
    total_violations: int
    violations: List[Dict[str, Any]]
    violations_by_layer: Dict[str, List[Dict[str, Any]]]
    is_accepted: bool
    target_threshold: float
    status: str
    materialized_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output_dir: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts result object to standard dictionary representation."""
        return asdict(self)

    @staticmethod
    def _parse_page_scores(raw_per_page: Dict[Any, Any]) -> Dict[int, float]:
        per_page: Dict[int, float] = {}
        for p_k, p_v in raw_per_page.items():
            try:
                per_page[int(p_k)] = float(p_v)
            except (ValueError, TypeError) as ex:
                logger.debug("Skipping invalid page score %r=%r: %s", p_k, p_v, ex)
        return per_page

    @staticmethod
    def _parse_page_layer_scores(raw_per_page_layers: Dict[Any, Any]) -> Dict[int, Dict[str, float]]:
        per_page_layers: Dict[int, Dict[str, float]] = {}
        for p_k, p_v in raw_per_page_layers.items():
            if isinstance(p_v, dict):
                try:
                    per_page_layers[int(p_k)] = {str(k): float(v) for k, v in p_v.items()}
                except (ValueError, TypeError) as ex:
                    logger.debug("Skipping invalid page layer scores for page %r: %s", p_k, ex)
        return per_page_layers

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MaterializedVerificationResult:
        """Hydrates a MaterializedVerificationResult instance from dictionary payload."""
        return cls(
            document_id=str(data.get("document_id", "")),
            source_filename=str(data.get("source_filename", "")),
            selected_layers=list(data.get("selected_layers", [])),
            overall_confidence=float(data.get("overall_confidence", 0.0)),
            per_page_confidence=cls._parse_page_scores(data.get("per_page_confidence", {})),
            layer_scores={str(k): float(v) for k, v in data.get("layer_scores", {}).items()},
            per_page_layer_scores=cls._parse_page_layer_scores(data.get("per_page_layer_scores", {})),
            total_violations=int(data.get("total_violations", 0)),
            violations=list(data.get("violations", [])),
            violations_by_layer={
                str(k): list(v) for k, v in data.get("violations_by_layer", {}).items()
            },
            is_accepted=bool(data.get("is_accepted", False)),
            target_threshold=float(data.get("target_threshold", 0.82)),
            status=str(data.get("status", "ACCEPT")),
            materialized_at=str(data.get("materialized_at", datetime.now(timezone.utc).isoformat())),
            output_dir=data.get("output_dir"),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_decision(
        cls,
        dom: DocumentDOM,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        active_layers: List[str],
        output_dir: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        materialized_at: Optional[str] = None,
    ) -> MaterializedVerificationResult:
        """Constructs a MaterializedVerificationResult from evaluated DOM, decision payload, and violations."""
        raw_overall = decision.get("overall_confidence", 1.0)
        conf_val = float(raw_overall) if raw_overall is not None else 1.0
        raw_thresh = decision.get("target_confidence_threshold", 0.82)
        thresh_val = float(raw_thresh) if raw_thresh is not None else 0.82
        return cls(
            document_id=dom.document_id,
            source_filename=dom.source_filename,
            selected_layers=active_layers,
            overall_confidence=conf_val,
            per_page_confidence=cls._parse_page_scores(decision.get("per_page_confidence", {})),
            layer_scores={str(k): float(v) for k, v in decision.get("layer_scores", {}).items()},
            per_page_layer_scores=cls._parse_page_layer_scores(decision.get("per_page_layer_scores", {})),
            total_violations=len(violations),
            violations=violations,
            violations_by_layer=group_violations_by_layer(violations, active_layers),
            is_accepted=bool(decision.get("is_accepted", conf_val >= thresh_val)),
            target_threshold=thresh_val,
            status=str(decision.get("status", "ACCEPT")),
            materialized_at=materialized_at or datetime.now(timezone.utc).isoformat(),
            output_dir=output_dir,
            metadata=metadata or {},
        )

    def save(self, target_dir: Optional[str] = None) -> str:
        """Saves materialized verification report to disk and returns file path."""
        out_dir = target_dir or self.output_dir or "output"
        mkdirs(out_dir)
        report_path = os.path.join(out_dir, "verification_result.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        return report_path


def materialize_document_verification(
    dom: DocumentDOM,
    selected_layers: Optional[Sequence[str]] = None,
    language: Optional[str] = "en",
    target_threshold: float = 0.82,
    output_dir: Optional[str] = None,
    persist: bool = True,
) -> MaterializedVerificationResult:
    """
    Evaluates violations and confidence scores based on selected verification layers in a materialized manner.
    Mutates node.violations in-place on DOM and persists artifacts when output_dir is provided.
    """
    active_layers = normalize_layers(selected_layers)
    violations = detect_quality_violations(dom, language=language, layers=active_layers)
    metrics = evaluate_document_confidence(dom, language=language, layers=active_layers)
    overall_conf = metrics["overall_confidence"]
    per_page_conf = metrics["per_page_confidence"]
    layer_scores = metrics.get("layer_scores", {})

    is_accepted = overall_conf >= target_threshold
    status = "ACCEPT" if is_accepted else "TRIGGER_FALLBACK"
    materialized_time = datetime.now(timezone.utc).isoformat()
    slice_pages = [page for page, sc in per_page_conf.items() if sc < target_threshold]

    decision_record: Dict[str, Any] = {
        "language": language,
        "target_confidence_threshold": target_threshold,
        "overall_confidence": overall_conf,
        "per_page_confidence": per_page_conf,
        "per_page_layer_scores": metrics.get("per_page_layer_scores", {}),
        "is_accepted": is_accepted,
        "status": status,
        "selected_layers": active_layers,
        "layer_scores": layer_scores,
        "pages_requiring_slicing": slice_pages,
        "materialized_at": materialized_time,
        "decision_tree": {
            "action": "ACCEPT_OUTPUT" if is_accepted else "PATH_B_WIGGLE_PARAMETERS",
            "reason": (
                f"Overall confidence ({overall_conf}) {'meets' if is_accepted else 'below'} "
                f"target threshold ({target_threshold}) across layers: {', '.join(active_layers)}."
            ),
        },
    }

    result = MaterializedVerificationResult.from_decision(
        dom=dom,
        decision=decision_record,
        violations=violations,
        active_layers=active_layers,
        output_dir=output_dir,
        materialized_at=materialized_time,
        metadata={
            "detected_languages": metrics.get("detected_languages", {}),
            "primary_detected_language": metrics.get("primary_detected_language", "en"),
            "language": language,
        },
    )

    if output_dir and persist:
        mkdirs(output_dir)
        result.save(output_dir)

        viol_data = {
            "document_id": dom.document_id,
            "source_filename": dom.source_filename,
            "language": language or "en",
            "detected_languages": metrics.get("detected_languages", {}),
            "primary_detected_language": metrics.get("primary_detected_language", "en"),
            "selected_layers": active_layers,
            "layer_scores": layer_scores,
            "total_violations": len(violations),
            "violations": violations,
            "materialized_at": materialized_time,
        }
        with open(os.path.join(output_dir, "quality_violations.json"), "w", encoding="utf-8") as f:
            json.dump(viol_data, f, indent=2)

        decision_record.pop("per_page_layer_scores", None)
        with open(os.path.join(output_dir, "decision_tree.json"), "w", encoding="utf-8") as f:
            json.dump(decision_record, f, indent=2)

        with open(os.path.join(output_dir, "document_dom.json"), "w", encoding="utf-8") as f:
            json.dump(dom.to_dict(), f, indent=2)

        plan_res_file = os.path.join(output_dir, "plan_execution_result.json")
        if os.path.exists(plan_res_file):
            try:
                with open(plan_res_file, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                plan_data.update({
                    "decision": decision_record,
                    "total_violations": len(violations),
                    "status": status,
                    "selected_layers": active_layers,
                    "materialized_at": materialized_time,
                })
                with open(plan_res_file, "w", encoding="utf-8") as f:
                    json.dump(plan_data, f, indent=2)
            except Exception as ex:
                logger.debug("Could not update plan_execution_result.json: %s", ex)

    return result

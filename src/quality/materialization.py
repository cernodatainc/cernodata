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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MaterializedVerificationResult:
        """Hydrates a MaterializedVerificationResult instance from dictionary payload."""
        per_page = {
            int(k): float(v)
            for k, v in data.get("per_page_confidence", {}).items()
        }
        per_page_layers: Dict[int, Dict[str, float]] = {}
        for p_k, p_v in data.get("per_page_layer_scores", {}).items():
            if isinstance(p_v, dict):
                per_page_layers[int(p_k)] = {str(k): float(v) for k, v in p_v.items()}

        return cls(
            document_id=str(data.get("document_id", "")),
            source_filename=str(data.get("source_filename", "")),
            selected_layers=list(data.get("selected_layers", [])),
            overall_confidence=float(data.get("overall_confidence", 0.0)),
            per_page_confidence=per_page,
            layer_scores={str(k): float(v) for k, v in data.get("layer_scores", {}).items()},
            per_page_layer_scores=per_page_layers,
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

    # Step 1: Detect violations for active layers and materialize onto DOM nodes
    violations = detect_quality_violations(dom, language=language, layers=active_layers)

    # Step 2: Evaluate confidence scores and layer breakdowns
    metrics = evaluate_document_confidence(dom, language=language, layers=active_layers)
    overall_conf = metrics["overall_confidence"]
    per_page_conf = metrics["per_page_confidence"]
    layer_scores = metrics.get("layer_scores", {})
    per_page_layer_scores = metrics.get("per_page_layer_scores", {})

    # Step 3: Group violations by layer
    violations_by_layer: Dict[str, List[Dict[str, Any]]] = {lyr: [] for lyr in active_layers}
    for v in violations:
        raw_type = v.get("type", "")
        norm_type = normalize_layer_name(raw_type) or raw_type
        violations_by_layer.setdefault(norm_type, []).append(v)

    is_accepted = overall_conf >= target_threshold
    status = "ACCEPT" if is_accepted else "TRIGGER_FALLBACK"
    materialized_time = datetime.now(timezone.utc).isoformat()

    result = MaterializedVerificationResult(
        document_id=dom.document_id,
        source_filename=dom.source_filename,
        selected_layers=active_layers,
        overall_confidence=overall_conf,
        per_page_confidence=per_page_conf,
        layer_scores=layer_scores,
        per_page_layer_scores=per_page_layer_scores,
        total_violations=len(violations),
        violations=violations,
        violations_by_layer=violations_by_layer,
        is_accepted=is_accepted,
        target_threshold=target_threshold,
        status=status,
        materialized_at=materialized_time,
        output_dir=output_dir,
        metadata={
            "detected_languages": metrics.get("detected_languages", {}),
            "primary_detected_language": metrics.get("primary_detected_language", "en"),
            "language": language,
        },
    )

    # Step 4: Persist materialized view to disk if output_dir is supplied and persist is True
    if output_dir and persist:
        mkdirs(output_dir)
        result.save(output_dir)

        # 1. Update quality_violations.json
        viol_file = os.path.join(output_dir, "quality_violations.json")
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
        with open(viol_file, "w", encoding="utf-8") as f:
            json.dump(viol_data, f, indent=2)

        # 2. Update decision_tree.json
        dec_file = os.path.join(output_dir, "decision_tree.json")
        slice_pages = [page for page, sc in per_page_conf.items() if sc < target_threshold]
        decision_record: Dict[str, Any] = {
            "language": language,
            "target_confidence_threshold": target_threshold,
            "overall_confidence": overall_conf,
            "per_page_confidence": per_page_conf,
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
        with open(dec_file, "w", encoding="utf-8") as f:
            json.dump(decision_record, f, indent=2)

        # 3. Update document_dom.json with newly materialized node.violations
        dom_file = os.path.join(output_dir, "document_dom.json")
        with open(dom_file, "w", encoding="utf-8") as f:
            json.dump(dom.to_dict(), f, indent=2)

        # 4. Update plan_execution_result.json if present
        plan_res_file = os.path.join(output_dir, "plan_execution_result.json")
        if os.path.exists(plan_res_file):
            try:
                with open(plan_res_file, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)
                plan_data["decision"] = decision_record
                plan_data["total_violations"] = len(violations)
                plan_data["status"] = status
                plan_data["selected_layers"] = active_layers
                plan_data["materialized_at"] = materialized_time
                with open(plan_res_file, "w", encoding="utf-8") as f:
                    json.dump(plan_data, f, indent=2)
            except Exception as ex:
                logger.debug("Could not update plan_execution_result.json: %s", ex)

    return result

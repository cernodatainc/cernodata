"""
src/pipeline/pipeline_steps.py

Discrete execution steps for skew alignment, quality inspection, and decision evaluation.
"""

from typing import Dict, Any, List, Tuple, Optional

from src.dom import DocumentDOM
from src.quality import detect_quality_violations, apply_text_skew_alignment
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.planner.models import IngestionConfig


def align_document_skew(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
    """Auto-detects and applies local text line skew orientation angles per node."""
    if align_skew:
        return apply_text_skew_alignment(dom, pdf_path)
    return dom


def evaluate_quality_and_decision_tree(
    dom: DocumentDOM,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: Optional[str] = "en",
    preset: str = "docling_fast",
    current_preset_score: float = 0.90,
    next_preset_score: float = 0.72,
    config: Optional[IngestionConfig] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Extracts quality violation records and evaluates confidence scores against target threshold."""
    if config is not None:
        target_threshold = config.target_threshold
        language = config.language
        preset = config.preset

    violations = detect_quality_violations(dom, language=language)
    engine = DecisionTreeEngine(
        target_threshold=target_threshold,
        current_preset_score=current_preset_score,
        next_preset_score=next_preset_score,
        language=language,
    )
    decision = engine.evaluate(dom)
    decision["chosen_preset"] = preset
    return decision, violations

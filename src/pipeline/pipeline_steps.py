"""
src/pipeline/pipeline_steps.py

Discrete execution steps for skew alignment, quality inspection, and decision evaluation.
"""

from typing import Dict, Any, List, Tuple, Optional, Sequence

from src.dom import DocumentDOM
from src.quality import detect_quality_violations, apply_text_skew_alignment
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.planner.models import IngestionConfig


def align_document_skew(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
    """Auto-detects and applies local text line skew orientation angles per node."""
    if align_skew:
        return apply_text_skew_alignment(dom, pdf_path)
    return dom


def run_postprocessing_steps(
    dom: DocumentDOM, config: Optional[IngestionConfig] = None
) -> DocumentDOM:
    """No-op hook for running declarative DOM postprocessing steps."""
    # TODO(TASK-501): Execute `PostprocessorChain` (letterhead stripping TASK-502, hyphenation defragmentation
    # TASK-503, watermark filter TASK-504, and regex/PII scrubbing TASK-505) and record audit trail on `dom`.
    _ = config
    return dom


def run_ollama_ocr_repair_step(
    dom: DocumentDOM, violations: List[Dict[str, Any]]
) -> DocumentDOM:
    """No-op hook for repairing OCR-corrupted nodes with a local Ollama SLM."""
    # TODO(TASK-403): Selectively repair nodes flagged with OCR quality violations using `OllamaClient`
    # while enforcing the <=25% length-drift anti-hallucination check.
    _ = violations
    return dom


def evaluate_quality_and_decision_tree(
    dom: DocumentDOM,
    target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
    language: Optional[str] = "en",
    preset: str = "docling_fast",
    current_preset_score: float = 0.90,
    next_preset_score: float = 0.72,
    config: Optional[IngestionConfig] = None,
    verification_layers: Optional[Sequence[str]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Extracts quality violation records and evaluates confidence scores against target threshold across verification layers."""
    layers = verification_layers
    if config is not None:
        target_threshold = config.target_threshold
        language = config.language
        preset = config.preset
        if config.verification_layers is not None:
            layers = config.verification_layers

    engine = DecisionTreeEngine(
        target_threshold=target_threshold,
        current_preset_score=current_preset_score,
        next_preset_score=next_preset_score,
        language=language,
        verification_layers=layers,
    )
    decision = engine.evaluate(dom)
    decision["chosen_preset"] = preset
    detected_langs = decision.get("detected_languages")
    violations = detect_quality_violations(
        dom, language=language, page_languages=detected_langs, layers=layers
    )
    return decision, violations

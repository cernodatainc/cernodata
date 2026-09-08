"""
src/quality package re-exports
"""
from src.quality.garbage import compute_garbage_ratio, compute_garbage_details
from src.quality.language_config import (
    LanguageConfig,
    get_language_config,
    register_language_config
)
from src.quality.language import compute_language_score
from src.quality.evaluator import (
    evaluate_page_confidence,
    evaluate_document_confidence,
    load_quality_config
)
from src.quality.violations import detect_quality_violations
from src.quality.skew import detect_node_text_skew, apply_text_skew_alignment

__all__ = [
    "LanguageConfig",
    "get_language_config",
    "register_language_config",
    "compute_garbage_ratio",
    "compute_garbage_details",
    "compute_language_score",
    "evaluate_page_confidence",
    "evaluate_document_confidence",
    "load_quality_config",
    "detect_quality_violations",
    "detect_node_text_skew",
    "apply_text_skew_alignment"
]

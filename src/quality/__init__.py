"""
src/quality package re-exports
"""
from src.quality.garbage import compute_garbage_ratio, compute_garbage_details
from src.quality.language_config import (
    LanguageConfig,
    get_language_config,
    register_language_config
)
from src.quality.language import (
    compute_language_score,
    detect_text_language,
    detect_page_language,
    detect_document_languages
)
from src.quality.evaluator import (
    DocumentConfidenceMetrics,
    evaluate_page_confidence,
    evaluate_document_confidence,
    load_quality_config
)
from src.quality.layers import (
    ALL_VERIFICATION_LAYERS,
    DEFAULT_VERIFICATION_LAYERS,
    LAYER_METADATA,
    VerificationLayer,
    normalize_layer_name,
    normalize_layers,
)
from src.quality.materialization import (
    MaterializedVerificationResult,
    materialize_document_verification,
)
from src.quality.violations import detect_quality_violations
from src.quality.skew import detect_node_text_skew, apply_text_skew_alignment

__all__ = [
    "ALL_VERIFICATION_LAYERS",
    "DEFAULT_VERIFICATION_LAYERS",
    "DocumentConfidenceMetrics",
    "LAYER_METADATA",
    "LanguageConfig",
    "MaterializedVerificationResult",
    "VerificationLayer",
    "apply_text_skew_alignment",
    "compute_garbage_details",
    "compute_garbage_ratio",
    "compute_language_score",
    "detect_document_languages",
    "detect_node_text_skew",
    "detect_page_language",
    "detect_quality_violations",
    "detect_text_language",
    "evaluate_document_confidence",
    "evaluate_page_confidence",
    "get_language_config",
    "load_quality_config",
    "materialize_document_verification",
    "normalize_layer_name",
    "normalize_layers",
    "register_language_config",
]

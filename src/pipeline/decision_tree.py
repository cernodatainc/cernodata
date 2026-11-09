"""
src/pipeline/decision_tree.py

cernodata Decision Tree Iteration Engine.
Evaluates parsing confidence scores against target threshold and routes dual-path fallback loops.
"""
from typing import Dict, Any, Optional, Sequence
from src.dom import DocumentDOM
from src.dom.enums import PresetKind, PipelineAction
from src.quality import evaluate_document_confidence

DEFAULT_TARGET_CONFIDENCE_THRESHOLD = 0.82
DEFAULT_CURRENT_PRESET_SCORE = 0.90
DEFAULT_NEXT_PRESET_SCORE = 0.72
DEFAULT_WIGGLE_DELTA_THRESHOLD = 0.20
DEFAULT_WIGGLE_RENDERING_DPI = 200
DEFAULT_WIGGLE_CONTRAST_ENHANCEMENT = 1.2
DEFAULT_WIGGLE_TABLE_DETECTION_MODE = "strict_grid"

PRESET_ID = PresetKind.DOCLING_FAST.value
NEXT_PRESET_ID = PresetKind.DOCLING_DEEP.value
NEXT_PRESET_SCORE = DEFAULT_NEXT_PRESET_SCORE


class DecisionTreeEngine:
    """
    Evaluates parsing confidence against target threshold and drives dual-path fallback loops.
    """

    def __init__(
        self,
        target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
        current_preset_score: Optional[float] = None,
        next_preset_score: Optional[float] = None,
        language: Optional[str] = "en",
        verification_layers: Optional[Sequence[str]] = None,
        preset_id: str = PRESET_ID,
        next_preset_id: Optional[str] = None,
        wiggle_delta_threshold: float = DEFAULT_WIGGLE_DELTA_THRESHOLD,
        wiggle_parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.target_threshold = target_threshold
        self.language = language
        self.verification_layers = list(verification_layers) if verification_layers is not None else None
        self.preset_id = preset_id

        from src.pipeline.planner import PresetPlanner
        scores = PresetPlanner().calculate_scores()
        order = PresetPlanner().suggest_preset_order(scores)
        resolved_next = next_preset_id or next((p for p in order if p != preset_id), NEXT_PRESET_ID)
        self.next_preset_id = resolved_next

        self.current_preset_score = (
            current_preset_score
            if current_preset_score is not None
            else scores.get(self.preset_id, DEFAULT_CURRENT_PRESET_SCORE)
        )
        self.next_preset_score = (
            next_preset_score
            if next_preset_score is not None
            else scores.get(self.next_preset_id, DEFAULT_NEXT_PRESET_SCORE)
        )
        self.wiggle_delta_threshold = wiggle_delta_threshold
        self.wiggle_parameters = dict(wiggle_parameters) if wiggle_parameters is not None else None

    def evaluate(self, dom: DocumentDOM) -> Dict[str, Any]:
        metrics = evaluate_document_confidence(
            dom, language=self.language, layers=self.verification_layers
        )
        overall_conf = metrics["overall_confidence"]
        per_page_conf = metrics["per_page_confidence"]

        slice_pages = [page for page, score in per_page_conf.items() if score < self.target_threshold]
        is_accepted = overall_conf >= self.target_threshold
        delta = round(self.current_preset_score - self.next_preset_score, 4)

        result: Dict[str, Any] = {
            "preset_id": self.preset_id,
            "language": self.language,
            "detected_languages": metrics.get("detected_languages", {}),
            "detected_language_confidences": metrics.get("detected_language_confidences", {}),
            "primary_detected_language": metrics.get("primary_detected_language", "en"),
            "target_confidence_threshold": self.target_threshold,
            "overall_confidence": overall_conf,
            "per_page_confidence": per_page_conf,
            "selected_layers": metrics.get("selected_layers", []),
            "layer_scores": metrics.get("layer_scores", {}),
            "per_page_layer_scores": metrics.get("per_page_layer_scores", {}),
            "is_accepted": is_accepted,
            "pages_requiring_slicing": slice_pages,
            "decision_tree": {}
        }

        lang_label = f" [Language: {self.language}]" if self.language else " [Language: auto-detected]"
        if is_accepted:
            result["status"] = "ACCEPT"
            result["decision_tree"] = {
                "action": PipelineAction.ACCEPT_OUTPUT.value,
                "reason": f"Overall confidence ({overall_conf}) >= target threshold ({self.target_threshold}){lang_label}"
            }
        else:
            result["status"] = "TRIGGER_FALLBACK"
            recommended_wiggles: Dict[str, Any] = {
                "rendering_dpi": DEFAULT_WIGGLE_RENDERING_DPI,
                "ocr_language_hint": [self.language] if self.language else [],
                "table_detection_mode": DEFAULT_WIGGLE_TABLE_DETECTION_MODE,
                "contrast_enhancement": DEFAULT_WIGGLE_CONTRAST_ENHANCEMENT,
            }
            if self.wiggle_parameters:
                recommended_wiggles.update(self.wiggle_parameters)

            thresh = self.wiggle_delta_threshold
            target_next = self.next_preset_id
            if delta >= thresh:
                action = PipelineAction.PATH_B_WIGGLE_PARAMETERS.value
                reason = (
                    f"Delta ({delta}) >= {thresh:.2f}. Language/quality heuristics below threshold "
                    f"({overall_conf} < {self.target_threshold}). Wiggling OCR language hint and DPI."
                )
            else:
                action = PipelineAction.PATH_A_SWITCH_PRESET.value
                hint_str = f" with explicit '{self.language}' language hint." if self.language else "."
                reason = f"Delta ({delta}) < {thresh:.2f}. Switching to next preset candidate ('{target_next}'){hint_str}"

            result["decision_tree"] = {
                "action": action,
                "score_delta": delta,
                "reason": reason,
                "next_preset_candidate": target_next,
                "recommended_parameter_adjustments": recommended_wiggles,
                "page_slice_queue": slice_pages
            }

        return result

"""
src/decision_tree.py

cernodata Decision Tree Iteration Engine.
Evaluates parsing output against target confidence thresholds and determines fallback actions:
- ACCEPT output
- Path B: Parameter Wiggling (Delta Δ >= 0.20)
- Path A: Preset Switching (Delta Δ < 0.20)
"""

from typing import Dict, Any, List
try:
    from src.dom import DocumentDOM
    from src.heuristics import evaluate_document_confidence
except ImportError:
    from dom import DocumentDOM
    from heuristics import evaluate_document_confidence

DEFAULT_TARGET_CONFIDENCE_THRESHOLD = 0.82
PRESET_ID = "docling_fast"
NEXT_PRESET_ID = "docling_deep"
NEXT_PRESET_SCORE = 0.72


class DecisionTreeEngine:
    """
    Evaluates parsing confidence against target threshold and drives dual-path fallback loops,
    incorporating language hints and diacritic verification.
    """

    def __init__(
        self,
        target_threshold: float = DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
        current_preset_score: float = 0.90,
        next_preset_score: float = NEXT_PRESET_SCORE,
        language: str = "en"
    ):
        self.target_threshold = target_threshold
        self.current_preset_score = current_preset_score
        self.next_preset_score = next_preset_score
        self.language = language

    def evaluate(self, dom: DocumentDOM) -> Dict[str, Any]:
        metrics = evaluate_document_confidence(dom, language=self.language)
        overall_conf = metrics["overall_confidence"]
        per_page_conf = metrics["per_page_confidence"]

        slice_pages = [page for page, score in per_page_conf.items() if score < self.target_threshold]
        is_accepted = overall_conf >= self.target_threshold
        delta = round(self.current_preset_score - self.next_preset_score, 4)

        result: Dict[str, Any] = {
            "preset_id": PRESET_ID,
            "language": self.language,
            "target_confidence_threshold": self.target_threshold,
            "overall_confidence": overall_conf,
            "per_page_confidence": per_page_conf,
            "is_accepted": is_accepted,
            "pages_requiring_slicing": slice_pages,
            "decision_tree": {}
        }

        if is_accepted:
            result["status"] = "ACCEPT"
            result["decision_tree"] = {
                "action": "ACCEPT_OUTPUT",
                "reason": f"Overall confidence ({overall_conf}) >= target threshold ({self.target_threshold}) [Language: {self.language}]"
            }
        else:
            result["status"] = "TRIGGER_FALLBACK"
            recommended_wiggles = {
                "rendering_dpi": 200,
                "ocr_language_hint": [self.language],
                "table_detection_mode": "strict_grid",
                "contrast_enhancement": 1.2
            }
            if delta >= 0.20:
                action = "PATH_B_WIGGLE_PARAMETERS"
                reason = f"Delta Δ ({delta}) >= 0.20. Language/quality heuristics below threshold ({overall_conf} < {self.target_threshold}). Wiggling OCR language hint and DPI."
            else:
                action = "PATH_A_SWITCH_PRESET"
                reason = f"Delta Δ ({delta}) < 0.20. Switching to next preset candidate ('{NEXT_PRESET_ID}') with explicit '{self.language}' language hint."

            result["decision_tree"] = {
                "action": action,
                "score_delta": delta,
                "reason": reason,
                "next_preset_candidate": NEXT_PRESET_ID,
                "recommended_parameter_adjustments": recommended_wiggles,
                "page_slice_queue": slice_pages
            }

        return result

"""
src/quality/evaluator.py

Page-level (S_i) and document-level (S) confidence score evaluators.
"""

from typing import List, Dict, Any, Optional
from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_ratio
from src.quality.language import compute_language_score
from src.quality.language_config import get_language_config


def evaluate_page_confidence(
    nodes: List[DOMNode], language: str = "en", diacritic_hit: Optional[float] = None
) -> float:
    """
    Computes quality confidence score S_i for a set of DOMNodes on a single page.
    Applies configurable diacritic anomaly hits at node and page levels.
    """
    if not nodes:
        return 0.0

    config = get_language_config(language)
    hit = diacritic_hit if diacritic_hit is not None else (config.diacritic_hit if config else 0.0)

    node_scores = []
    diacritic_anomalies_count = 0
    for node in nodes:
        raw_text = node.content.get("raw_text", "")

        char_score = max(0.0, 1.0 - (compute_garbage_ratio(raw_text) * 3.0))
        lang_score = compute_language_score(raw_text, language=language, diacritic_hit=hit)

        combined_text_score = char_score * lang_score

        if node.type == "table_grid":
            cell_alignment = node.content.get("cell_alignment_score", 0.95)
            score = 0.5 * combined_text_score + 0.5 * cell_alignment
        else:
            score = combined_text_score

        node_scores.append(score)

        if config:
            diacritic_anomalies_count += len(config.find_anomalous_substitutions(raw_text))
            diacritic_anomalies_count += len(config.find_diacritic_conflicts(raw_text))

    base_score = float(sum(node_scores) / len(node_scores))

    if hit > 0 and diacritic_anomalies_count > 0:
        page_penalty = min(0.60, diacritic_anomalies_count * hit)
        return max(0.0, float(base_score - page_penalty))

    return base_score


def evaluate_document_confidence(
    dom: DocumentDOM, language: str = "en", diacritic_hit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Evaluates confidence score across all pages in a DocumentDOM.
    """
    pages_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    page_scores: Dict[int, float] = {}
    for page_no, p_nodes in pages_nodes.items():
        score_i = evaluate_page_confidence(p_nodes, language=language, diacritic_hit=diacritic_hit)
        page_scores[page_no] = round(score_i, 4)

    overall_confidence = round(
        sum(page_scores.values()) / max(1, len(page_scores)), 4
    )

    return {
        "overall_confidence": overall_confidence,
        "per_page_confidence": page_scores
    }

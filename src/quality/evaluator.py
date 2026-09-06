"""
src/quality/evaluator.py

Page-level (S_i) and document-level (S) confidence score evaluators.
"""

from typing import List, Dict, Any
from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_ratio
from src.quality.language import compute_language_score


def evaluate_page_confidence(nodes: List[DOMNode], language: str = "en") -> float:
    """
    Computes quality confidence score S_i for a set of DOMNodes on a single page.
    """
    if not nodes:
        return 0.0

    node_scores = []
    for node in nodes:
        raw_text = node.content.get("raw_text", "")
        
        char_score = max(0.0, 1.0 - (compute_garbage_ratio(raw_text) * 3.0))
        lang_score = compute_language_score(raw_text, language=language)

        combined_text_score = char_score * lang_score

        if node.type == "table_grid":
            cell_alignment = node.content.get("cell_alignment_score", 0.95)
            score = 0.5 * combined_text_score + 0.5 * cell_alignment
        else:
            score = combined_text_score

        node_scores.append(score)

    return float(sum(node_scores) / len(node_scores))


def evaluate_document_confidence(dom: DocumentDOM, language: str = "en") -> Dict[str, Any]:
    """
    Evaluates confidence score across all pages in a DocumentDOM.
    """
    pages_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    page_scores: Dict[int, float] = {}
    for page_no, p_nodes in pages_nodes.items():
        score_i = evaluate_page_confidence(p_nodes, language=language)
        page_scores[page_no] = round(score_i, 4)

    overall_confidence = round(
        sum(page_scores.values()) / max(1, len(page_scores)), 4
    )

    return {
        "overall_confidence": overall_confidence,
        "per_page_confidence": page_scores
    }

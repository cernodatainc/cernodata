"""
src/quality/evaluator.py

Page-level (S_i) and document-level (S) confidence score evaluators.
"""

import functools
import json
import logging
import os
from typing import List, Dict, Any, Optional, Sequence, Tuple, TypedDict
from collections import Counter
from src.dom import DOMNode, DocumentDOM
from src.quality.handlers import (
    DiacriticsLayerHandler,
    GeometryLayerHandler,
    StructureLayerHandler,
    SymbolsLayerHandler,
    TablesLayerHandler,
    get_suppressed_violation_types,
)
from src.quality.language import detect_page_language
from src.quality.language_config import get_language_config
from src.quality.layers import ActiveVerificationLayers, VerificationLayer, normalize_layers

logger = logging.getLogger("cernodata.quality.evaluator")

_SYMBOLS_HANDLER = SymbolsLayerHandler()
_DIACRITICS_HANDLER = DiacriticsLayerHandler()
_STRUCTURE_HANDLER = StructureLayerHandler()
_TABLES_HANDLER = TablesLayerHandler()
_GEOMETRY_HANDLER = GeometryLayerHandler()


class DocumentConfidenceMetrics(TypedDict, total=False):
    """Strongly-typed metrics dictionary evaluating confidence and detected languages across pages."""
    overall_confidence: float
    per_page_confidence: Dict[int, float]
    detected_languages: Dict[int, str]
    detected_language_confidences: Dict[int, float]
    primary_detected_language: str
    selected_layers: List[str]
    layer_scores: Dict[str, float]
    per_page_layer_scores: Dict[int, Dict[str, float]]


@functools.lru_cache(maxsize=1)
def load_quality_config() -> Dict[str, Any]:
    """Loads quality configuration from config.json located in the quality module directory."""
    config_dir = os.path.dirname(os.path.abspath(__file__))
    for fname in ("config.json", "quality_config.json", "diacritic_config.json"):
        fpath = os.path.join(config_dir, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as jde:
                logger.warning("Corrupt JSON in quality config file %s: %s", fpath, jde)
            except Exception as ex:
                logger.warning("Failed loading quality config from %s: %s", fpath, ex)
    return {
        "diacritic_hit": 0.20,
        "max_diacritic_penalty": 0.60,
        "garbage_multiplier": 3.0,
        "garbage_threshold": 0.05
    }


def evaluate_page_confidence_details(
    nodes: List[DOMNode],
    language: str = "en",
    diacritic_hit: Optional[float] = None,
    layers: Optional[Sequence[str]] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Computes quality confidence score S_i and per-layer score breakdown for nodes on a single page.
    Applies configurable anomaly hits strictly to selected verification layers.
    """
    if not nodes:
        return 0.0, {}

    active_layers = ActiveVerificationLayers.from_layers(layers)

    q_cfg = load_quality_config()
    config = get_language_config(language)
    hit = diacritic_hit if diacritic_hit is not None else q_cfg.get(
        "diacritic_hit", config.diacritic_hit if config else 0.20
    )
    max_diacritic_penalty = q_cfg.get("max_diacritic_penalty", 0.60)
    garbage_multiplier = q_cfg.get("garbage_multiplier", 3.0)

    node_scores = []
    char_scores = []
    lang_scores = []
    struct_scores = []
    table_scores = []
    geom_scores = []

    for node in nodes:
        suppressed_types = get_suppressed_violation_types(node)

        c_score = 1.0
        if active_layers.symbols:
            c_score = _SYMBOLS_HANDLER.evaluate_node(
                node, suppressed_types=suppressed_types, garbage_multiplier=garbage_multiplier
            )
            char_scores.append(c_score)

        l_score = 1.0
        if active_layers.diacritics:
            l_score = _DIACRITICS_HANDLER.evaluate_node(
                node, language=language, diacritic_hit=hit, config=config, suppressed_types=suppressed_types
            )
            lang_scores.append(l_score)

        s_score = 1.0
        if active_layers.structure:
            s_score = _STRUCTURE_HANDLER.evaluate_node(node)
            struct_scores.append(s_score)

        g_score = 1.0
        if active_layers.geometry:
            g_score = _GEOMETRY_HANDLER.evaluate_node(node)
            geom_scores.append(g_score)

        combined_text_score = c_score * l_score * s_score * g_score

        if node.type == "table_grid" and active_layers.tables:
            # TODO(TASK-103): Replace static `cell_alignment_score` fallback with real Level 4 Markdown table
            # grid validation (column count consistency across rows, numeric alignment, and empty header checks).
            t_score = _TABLES_HANDLER.evaluate_node(node)
            table_scores.append(t_score)
            score = 0.5 * combined_text_score + 0.5 * t_score
        else:
            score = combined_text_score

        node_scores.append(score)

    base_score = float(sum(node_scores) / len(node_scores))
    page_penalty = (
        _DIACRITICS_HANDLER.compute_page_penalty(
            nodes, language=language, diacritic_hit=hit, config=config, max_penalty=max_diacritic_penalty
        )
        if active_layers.diacritics
        else 0.0
    )

    final_score = max(0.0, float(base_score - page_penalty))

    layer_breakdown: Dict[str, float] = {}
    if active_layers.symbols and char_scores:
        layer_breakdown[VerificationLayer.SYMBOLS.value] = round(float(sum(char_scores) / len(char_scores)), 4)
    if active_layers.diacritics and lang_scores:
        d_avg = float(sum(lang_scores) / len(lang_scores))
        layer_breakdown[VerificationLayer.DIACRITICS.value] = round(max(0.0, float(d_avg - page_penalty)), 4)
    if active_layers.structure and struct_scores:
        layer_breakdown[VerificationLayer.STRUCTURE.value] = round(float(sum(struct_scores) / len(struct_scores)), 4)
    if active_layers.tables and table_scores:
        layer_breakdown[VerificationLayer.TABLES.value] = round(float(sum(table_scores) / len(table_scores)), 4)
    if active_layers.geometry and geom_scores:
        layer_breakdown[VerificationLayer.GEOMETRY.value] = round(float(sum(geom_scores) / len(geom_scores)), 4)

    return final_score, layer_breakdown


def evaluate_page_confidence(
    nodes: List[DOMNode],
    language: str = "en",
    diacritic_hit: Optional[float] = None,
    layers: Optional[Sequence[str]] = None,
) -> float:
    """
    Computes quality confidence score S_i for a set of DOMNodes on a single page.
    Applies configurable diacritic anomaly hits at node and page levels across selected criteria.
    """
    score, _ = evaluate_page_confidence_details(
        nodes=nodes,
        language=language,
        diacritic_hit=diacritic_hit,
        layers=layers,
    )
    return score


def evaluate_document_confidence(
    dom: DocumentDOM,
    language: Optional[str] = "en",
    diacritic_hit: Optional[float] = None,
    layers: Optional[Sequence[str]] = None,
) -> DocumentConfidenceMetrics:
    """
    Evaluates confidence score across all pages in a DocumentDOM based on selected criteria.
    """
    pages_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    normalized_active = normalize_layers(layers)
    page_scores: Dict[int, float] = {}
    page_languages: Dict[int, str] = {}
    page_confidences: Dict[int, float] = {}
    per_page_layer_scores: Dict[int, Dict[str, float]] = {}

    layer_accumulators: Dict[str, List[float]] = {k: [] for k in normalized_active}

    for page_no, p_nodes in pages_nodes.items():
        det_lang, det_conf, _ = detect_page_language(p_nodes)
        page_languages[page_no] = det_lang
        page_confidences[page_no] = det_conf

        effective_lang = det_lang if (not language or language.lower() in ("auto", "none")) else language
        score_i, layer_details = evaluate_page_confidence_details(
            p_nodes,
            language=effective_lang,
            diacritic_hit=diacritic_hit,
            layers=normalized_active,
        )
        page_scores[page_no] = round(score_i, 4)
        per_page_layer_scores[page_no] = layer_details
        for lyr, l_val in layer_details.items():
            if lyr in layer_accumulators:
                layer_accumulators[lyr].append(l_val)

    overall_confidence = round(
        sum(page_scores.values()) / max(1, len(page_scores)), 4
    )

    layer_overall: Dict[str, float] = {}
    for lyr, vals in layer_accumulators.items():
        if vals:
            layer_overall[lyr] = round(sum(vals) / len(vals), 4)

    primary_detected = "en"
    if page_languages:
        primary_detected = Counter(page_languages.values()).most_common(1)[0][0]

    metrics: DocumentConfidenceMetrics = {
        "overall_confidence": overall_confidence,
        "per_page_confidence": page_scores,
        "detected_languages": page_languages,
        "detected_language_confidences": page_confidences,
        "primary_detected_language": primary_detected,
        "selected_layers": normalized_active,
        "layer_scores": layer_overall,
        "per_page_layer_scores": per_page_layer_scores,
    }
    return metrics

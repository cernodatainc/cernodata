"""
src/quality/handlers.py

Modular verification layer handlers for document quality continuum.
Provides base handler interface and text-level verification implementations (Symbols, Diacritics).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_details, compute_garbage_ratio
from src.quality.language import compute_language_score
from src.quality.language_config import LanguageConfig
from src.quality.layers import LAYER_METADATA, VerificationLayer


def make_node_violation(
    node: DOMNode,
    counter: int,
    v_type: str,
    rule_type: str,
    description: str,
    severity: str = "WARNING",
    detected_snippet: str = "",
    suggestion: Optional[str] = None,
    suggested_correction: Optional[str] = None,
) -> Dict[str, Any]:
    """Constructs a standardized quality violation record dictionary for a DOMNode."""
    record: Dict[str, Any] = {
        "violation_id": f"viol_p{node.global_page_index}_v{counter}",
        "global_page_index": node.global_page_index,
        "node_id": node.node_id,
        "type": v_type,
        "rule_type": rule_type,
        "severity": severity,
        "detected_snippet": detected_snippet,
        "suggestion": suggestion,
        "suppressed": False,
        "description": description,
        "bounding_box": node.bounding_box.to_dict(),
    }
    if suggested_correction is not None:
        record["suggested_correction"] = suggested_correction
    return record


def is_violation_suppressed(violation: Any) -> bool:
    """Evaluates whether a violation record dictionary has been flagged as suppressed."""
    if not isinstance(violation, dict):
        return False
    supp_val = violation.get("suppressed", False)
    return (supp_val is True) or (str(supp_val).lower() in ("true", "1"))


def get_suppressed_violation_lookup(node: DOMNode) -> Dict[str, bool]:
    """Extracts a lookup mapping keyed by violation_id, rule_type, and type to suppression status."""
    lookup: Dict[str, bool] = {}
    for ev in getattr(node, "violations", []):
        if isinstance(ev, dict):
            is_supp = is_violation_suppressed(ev)
            if ev.get("violation_id"):
                lookup[str(ev["violation_id"])] = is_supp
            if ev.get("rule_type"):
                lookup[str(ev["rule_type"])] = is_supp
            if ev.get("type"):
                lookup[str(ev["type"])] = is_supp
    return lookup


def get_suppressed_violation_types(node: DOMNode) -> Dict[str, bool]:
    """Extracts a mapping of violation types that have been marked as suppressed on a DOMNode."""
    return {
        str(v.get("type", "")): True
        for v in getattr(node, "violations", [])
        if isinstance(v, dict) and is_violation_suppressed(v)
    }


class VerificationLayerHandler(ABC):
    """Abstract base handler implementing violation detection and confidence scoring for a quality layer."""

    @property
    @abstractmethod
    def layer_id(self) -> str:
        """Canonical layer identifier string."""

    @property
    def level(self) -> int:
        """Continuum verification tier level (1-5)."""
        return int(LAYER_METADATA.get(self.layer_id, {}).get("level", 1))

    @property
    def name(self) -> str:
        """Human-readable display name for the verification layer."""
        return str(LAYER_METADATA.get(self.layer_id, {}).get("name", self.layer_id))

    @property
    def description(self) -> str:
        """Brief narrative description of quality criteria verified."""
        return str(LAYER_METADATA.get(self.layer_id, {}).get("description", ""))

    @abstractmethod
    def detect_violations(
        self,
        dom: DocumentDOM,
        counter: int = 1,
        language: Optional[str] = "en",
        page_configs: Optional[Dict[int, Optional[LanguageConfig]]] = None,
        fixed_config: Optional[LanguageConfig] = None,
    ) -> List[Dict[str, Any]]:
        """Scans DOM nodes and produces structured violation records for this verification layer."""

    @abstractmethod
    def evaluate_node(
        self,
        node: DOMNode,
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        suppressed_types: Optional[Dict[str, bool]] = None,
        garbage_multiplier: float = 3.0,
    ) -> float:
        """Computes localized confidence score contribution in range [0.0, 1.0] for a single node."""

    def compute_page_penalty(
        self,
        nodes: List[DOMNode],
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        max_penalty: float = 0.60,
    ) -> float:
        """Computes aggregate page-level penalty deduction. Defaults to 0.0."""
        return 0.0


class SymbolsLayerHandler(VerificationLayerHandler):
    """Level 1 verification: OCR noise, character corruption, punctuation soup, and alphanumeric ratio."""

    @property
    def layer_id(self) -> str:
        return VerificationLayer.SYMBOLS.value

    @staticmethod
    def check_node_violations(
        node: DOMNode, raw_text: str, counter: int, threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """Checks node raw text for OCR damage, punctuation soup, or corrupt characters."""
        details = compute_garbage_details(raw_text)
        gb_ratio = details["ratio"]
        if gb_ratio <= threshold:
            return []

        reasons = []
        if details.get("unicode_ratio", 0) > 0:
            reasons.append("unicode corruption")
        if details.get("rep_ratio", 0) > 0:
            reasons.append("character repetition")
        if details.get("soup_ratio", 0) > 0:
            reasons.append("punctuation soup / fragmented OCR tokens")
        if details.get("low_alnum_penalty", 0) > 0:
            reasons.append("low alphanumeric ratio")

        desc_detail = f" ({', '.join(reasons)})" if reasons else ""
        return [
            make_node_violation(
                node=node,
                counter=counter,
                v_type="symbols",
                rule_type="garbage_character_ratio",
                severity="HIGH",
                detected_snippet=raw_text[:60],
                description=f"High ratio of OCR noise or corrupt characters ({round(gb_ratio, 3)}){desc_detail}",
            )
        ]

    def detect_violations(
        self,
        dom: DocumentDOM,
        counter: int = 1,
        language: Optional[str] = "en",
        page_configs: Optional[Dict[int, Optional[LanguageConfig]]] = None,
        fixed_config: Optional[LanguageConfig] = None,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        for node in dom.nodes:
            raw_text = node.content.get("raw_text", "")
            violations.extend(self.check_node_violations(node, raw_text, counter + len(violations)))
        return violations

    def evaluate_node(
        self,
        node: DOMNode,
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        suppressed_types: Optional[Dict[str, bool]] = None,
        garbage_multiplier: float = 3.0,
    ) -> float:
        supp = suppressed_types or {}
        if supp.get("symbols"):
            return 1.0
        raw_text = node.content.get("raw_text", "")
        return max(0.0, 1.0 - (compute_garbage_ratio(raw_text) * garbage_multiplier))


class DiacriticsLayerHandler(VerificationLayerHandler):
    """Level 2 verification: Language-specific diacritic anomalies, foreign conflicts, and OCR substitution."""

    @property
    def layer_id(self) -> str:
        return VerificationLayer.DIACRITICS.value

    @staticmethod
    def check_node_violations(
        node: DOMNode, raw_text: str, config: Optional[LanguageConfig], counter: int
    ) -> List[Dict[str, Any]]:
        """Checks text nodes for OCR substitution anomalies and conflicting diacritics."""
        if not config or not raw_text or config.code == "en":
            return []

        violations: List[Dict[str, Any]] = []
        for anom_char, match_snippet, suggested in config.find_anomalous_substitutions(raw_text):
            rewrite = raw_text.replace(match_snippet, suggested, 1) if match_snippet else raw_text
            violations.append(
                make_node_violation(
                    node=node,
                    counter=counter + len(violations),
                    v_type="diacritic",
                    rule_type="ocr_character_substitution",
                    severity="WARNING",
                    detected_snippet=match_snippet,
                    suggestion=rewrite,
                    suggested_correction=suggested,
                    description=f"OCR '{anom_char}' character substitution anomaly detected ('{match_snippet}' -> '{suggested}')",
                )
            )

        for conf_char, match_snippet, suggested in config.find_diacritic_conflicts(raw_text):
            rewrite = raw_text.replace(match_snippet, suggested, 1) if match_snippet else raw_text
            violations.append(
                make_node_violation(
                    node=node,
                    counter=counter + len(violations),
                    v_type="diacritic",
                    rule_type="diacritic_conflict",
                    severity="WARNING",
                    detected_snippet=match_snippet,
                    suggestion=rewrite,
                    suggested_correction=suggested,
                    description=f"Diacritic conflict detected: '{conf_char}' is not valid in {config.name} ('{match_snippet}' -> '{suggested}')",
                )
            )
        return violations

    def detect_violations(
        self,
        dom: DocumentDOM,
        counter: int = 1,
        language: Optional[str] = "en",
        page_configs: Optional[Dict[int, Optional[LanguageConfig]]] = None,
        fixed_config: Optional[LanguageConfig] = None,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        for node in dom.nodes:
            raw_text = node.content.get("raw_text", "")
            cfg = page_configs.get(node.global_page_index) if page_configs else fixed_config
            violations.extend(self.check_node_violations(node, raw_text, cfg, counter + len(violations)))
        return violations

    def evaluate_node(
        self,
        node: DOMNode,
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        suppressed_types: Optional[Dict[str, bool]] = None,
        garbage_multiplier: float = 3.0,
    ) -> float:
        supp = suppressed_types or {}
        effective_hit = 0.0 if supp.get("diacritic") else diacritic_hit
        raw_text = node.content.get("raw_text", "")
        return compute_language_score(raw_text, language=language, diacritic_hit=effective_hit)

    def compute_page_penalty(
        self,
        nodes: List[DOMNode],
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        max_penalty: float = 0.60,
    ) -> float:
        if not config or diacritic_hit <= 0:
            return 0.0
        anomalies_count = 0
        for node in nodes:
            if not get_suppressed_violation_types(node).get("diacritic"):
                raw_text = node.content.get("raw_text", "")
                anomalies_count += len(config.find_anomalous_substitutions(raw_text))
                anomalies_count += len(config.find_diacritic_conflicts(raw_text))
        return min(max_penalty, anomalies_count * diacritic_hit) if anomalies_count > 0 else 0.0


from src.quality.handlers_structural import (  # noqa: E402
    GeometryLayerHandler,
    StructureLayerHandler,
    TablesLayerHandler,
)

__all__ = [
    "DiacriticsLayerHandler",
    "GeometryLayerHandler",
    "StructureLayerHandler",
    "SymbolsLayerHandler",
    "TablesLayerHandler",
    "VerificationLayerHandler",
    "get_suppressed_violation_lookup",
    "get_suppressed_violation_types",
    "is_violation_suppressed",
    "make_node_violation",
]

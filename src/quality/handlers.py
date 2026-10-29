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
from src.quality.layers import VerificationLayer


class VerificationLayerHandler(ABC):
    """Abstract base handler implementing violation detection and confidence scoring for a quality layer."""

    @property
    @abstractmethod
    def layer_id(self) -> str:
        """Canonical layer identifier string."""

    @property
    @abstractmethod
    def level(self) -> int:
        """Continuum verification tier level (1-5)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name for the verification layer."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief narrative description of quality criteria verified."""

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

    @property
    def level(self) -> int:
        return 1

    @property
    def name(self) -> str:
        return "Symbols & Character Integrity"

    @property
    def description(self) -> str:
        return "OCR noise, character corruption, punctuation soup, and alphanumeric density."

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
            details = compute_garbage_details(raw_text)
            gb_ratio = details["ratio"]
            if gb_ratio > 0.05:
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
                violations.append({
                    "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                    "global_page_index": node.global_page_index,
                    "node_id": node.node_id,
                    "type": "symbols",
                    "rule_type": "garbage_character_ratio",
                    "severity": "HIGH",
                    "detected_snippet": raw_text[:60],
                    "suggestion": None,
                    "suppressed": False,
                    "description": f"High ratio of OCR noise or corrupt characters ({round(gb_ratio, 3)}){desc_detail}",
                    "bounding_box": node.bounding_box.to_dict(),
                })
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

    @property
    def level(self) -> int:
        return 2

    @property
    def name(self) -> str:
        return "Language & Diacritic Accuracy"

    @property
    def description(self) -> str:
        return "Language-specific diacritic anomalies, foreign diacritic conflicts, and OCR substitution."

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
            if not cfg or not raw_text or cfg.code == "en":
                continue

            for anom_char, match_snippet, suggested in cfg.find_anomalous_substitutions(raw_text):
                rewrite = raw_text.replace(match_snippet, suggested, 1) if match_snippet else raw_text
                violations.append({
                    "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                    "global_page_index": node.global_page_index,
                    "node_id": node.node_id,
                    "type": "diacritic",
                    "rule_type": "ocr_character_substitution",
                    "severity": "WARNING",
                    "detected_snippet": match_snippet,
                    "suggested_correction": suggested,
                    "suggestion": rewrite,
                    "suppressed": False,
                    "description": f"OCR '{anom_char}' character substitution anomaly detected ('{match_snippet}' -> '{suggested}')",
                    "bounding_box": node.bounding_box.to_dict(),
                })

            for conf_char, match_snippet, suggested in cfg.find_diacritic_conflicts(raw_text):
                rewrite = raw_text.replace(match_snippet, suggested, 1) if match_snippet else raw_text
                violations.append({
                    "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                    "global_page_index": node.global_page_index,
                    "node_id": node.node_id,
                    "type": "diacritic",
                    "rule_type": "diacritic_conflict",
                    "severity": "WARNING",
                    "detected_snippet": match_snippet,
                    "suggested_correction": suggested,
                    "suggestion": rewrite,
                    "suppressed": False,
                    "description": f"Diacritic conflict detected: '{conf_char}' is not valid in {cfg.name} ('{match_snippet}' -> '{suggested}')",
                    "bounding_box": node.bounding_box.to_dict(),
                })
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
            supp = {
                str(v.get("type", "")): True
                for v in getattr(node, "violations", [])
                if (v.get("suppressed") is True) or (str(v.get("suppressed", "false")).lower() in ("true", "1"))
            }
            if not supp.get("diacritic"):
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
]

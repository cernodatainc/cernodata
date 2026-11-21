"""
src/quality/handlers.py

Modular verification layer handlers for document quality continuum.
Provides base handler interface and text-level verification implementations (Symbols, Diacritics).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_details, compute_garbage_ratio
from src.quality.language import compute_language_score
from src.quality.language_config import LanguageConfig, get_language_config
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
                k_id = str(ev["violation_id"])
                lookup[k_id] = lookup.get(k_id, False) or is_supp
            if ev.get("rule_type"):
                k_rule = str(ev["rule_type"])
                lookup[k_rule] = lookup.get(k_rule, False) or is_supp
            if ev.get("type"):
                k_type = str(ev["type"])
                lookup[k_type] = lookup.get(k_type, False) or is_supp
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
    def _extract_verifiable_text(node: DOMNode, raw_text: str) -> str:
        """Extracts cell text for table_grid nodes so markdown borders do not trigger noise checks."""
        if node.type != "table_grid":
            return raw_text
        rows = node.content.get("rows")
        if isinstance(rows, list) and rows:
            cells = [str(c).strip() for r in rows if isinstance(r, list) for c in r if str(c).strip()]
            if cells:
                return " ".join(cells)
        if "|" in raw_text:
            stripped = re.sub(r"^\s*\|[\s:\-\|]+\|\s*$", " ", raw_text, flags=re.MULTILINE)
            return re.sub(r"\s*\|\s*", " ", stripped).strip()
        return raw_text

    @staticmethod
    def check_node_violations(
        node: DOMNode,
        raw_text: str,
        counter: int,
        threshold: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """Checks node raw text for OCR damage, punctuation soup, or corrupt characters."""
        verif_text = SymbolsLayerHandler._extract_verifiable_text(node, raw_text)
        details = compute_garbage_details(verif_text)
        gb_ratio = details["ratio"]
        if gb_ratio <= threshold:
            return []

        reasons = [
            label
            for key, label in (
                ("unicode_ratio", "unicode corruption"),
                ("rep_ratio", "character repetition"),
                ("soup_ratio", "punctuation soup / fragmented OCR tokens"),
                ("low_alnum_penalty", "low alphanumeric ratio"),
            )
            if details.get(key, 0) > 0
        ]

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
        verif_text = self._extract_verifiable_text(node, raw_text)
        base_confidence = float(node.content.get("confidence", 1.0))
        return max(0.0, base_confidence - (compute_garbage_ratio(verif_text) * garbage_multiplier))


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
        checks = (
            (
                "ocr_character_substitution",
                config.find_anomalous_substitutions(raw_text),
                lambda c, m, s: f"OCR '{c}' character substitution anomaly detected ('{m}' -> '{s}')",
            ),
            (
                "diacritic_conflict",
                config.find_diacritic_conflicts(raw_text),
                lambda c, m, s: (
                    f"Diacritic conflict detected: '{c}' is not valid in {config.name} ('{m}' -> '{s}')"
                    if s and s != m
                    else f"Diacritic conflict detected: '{c}' is not valid in {config.name} in '{m}'"
                ),
            ),
        )
        for rule_type, items, fmt_desc in checks:
            for char_val, match_snippet, suggested in items:
                has_replacement = bool(suggested and suggested != match_snippet)
                rewrite = (
                    re.sub(rf"\b{re.escape(match_snippet)}\b", suggested, raw_text, count=1)
                    if (match_snippet and has_replacement)
                    else None
                )
                violations.append(
                    make_node_violation(
                        node=node,
                        counter=counter + len(violations),
                        v_type="diacritic",
                        rule_type=rule_type,
                        severity="WARNING",
                        detected_snippet=match_snippet,
                        suggestion=rewrite,
                        suggested_correction=suggested if has_replacement else "",
                        description=fmt_desc(char_val, match_snippet, suggested),
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
        if page_configs is None and fixed_config is None:
            lang = (language or "en").lower().strip()
            if lang == "auto":
                from src.quality.language import detect_document_languages
                page_langs = detect_document_languages(dom)
                page_configs = {p: get_language_config(code) for p, code in page_langs.items()}
            else:
                fixed_config = get_language_config(lang)
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
        if supp.get("diacritic") or supp.get("diacritics"):
            return 1.0
        raw_text = node.content.get("raw_text", "")
        if config is not None:
            return config.compute_score(raw_text, diacritic_hit=diacritic_hit)
        return compute_language_score(raw_text, language=language, diacritic_hit=diacritic_hit)

    def compute_page_penalty(
        self,
        nodes: List[DOMNode],
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        max_penalty: float = 0.60,
    ) -> float:
        cfg = config or get_language_config((language or "en").lower().strip())
        if not cfg or diacritic_hit <= 0:
            return 0.0
        anomalies_count = 0
        for node in nodes:
            supp = get_suppressed_violation_types(node)
            if not (supp.get("diacritic") or supp.get("diacritics")):
                raw_text = node.content.get("raw_text", "")
                anomalies_count += len(cfg.find_anomalous_substitutions(raw_text))
                anomalies_count += len(cfg.find_diacritic_conflicts(raw_text))
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

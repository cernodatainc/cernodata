"""
src/quality/language_config.py

Language configuration definitions, OCR diacritic substitution mappings,
and diacritic conflict resolution rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
import re

ALL_KNOWN_DIACRITICS: Set[str] = set(
    "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"          # Polish
    "äöüßÄÖÜ"                     # German
    "éèêëàâçîïôûùÉÈÊËÀÂÇÎÏÔÛÙ"    # French
    "ñáéíóúü¿¡ÑÁÉÍÓÚÜ"            # Spanish
    "čďěňřšťůžČĎĚŇŘŠŤŮŽ"          # Czech / Slovak
    "åæøÅÆØ"                      # Scandinavian
    "őűŐŰ"                        # Hungarian
    "ãõÃÕ"                        # Portuguese
)


@dataclass
class LanguageConfig:
    """
    Configuration model specifying language-specific character validity,
    expected diacritics, OCR substitution anomalies, and diacritic conflict resolution.
    """
    code: str
    name: str
    valid_diacritics: Set[str]
    conflicting_diacritics: Set[str] = field(default_factory=set)
    common_substitutions: Dict[str, List[str]] = field(default_factory=dict)
    anomalous_chars: Dict[str, str] = field(default_factory=dict)
    allowed_anomalous_tokens: Set[str] = field(default_factory=set)
    conflicting_diacritic_replacements: Dict[str, str] = field(default_factory=dict)
    common_word_corrections: Dict[str, str] = field(default_factory=dict)
    min_words_for_diacritic_check: int = 12
    no_diacritics_penalty: float = 0.15
    conflict_penalty_per_occurrence: float = 0.20
    max_conflict_penalty: float = 0.60
    anomalous_char_penalty_per_occurrence: float = 0.15
    max_anomalous_char_penalty: float = 0.50

    def __post_init__(self) -> None:
        if not self.conflicting_diacritics and self.code != "en":
            self.conflicting_diacritics = set(ALL_KNOWN_DIACRITICS - self.valid_diacritics)

    def find_diacritic_conflicts(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Finds diacritics in text that do not exist in this language.
        Returns a list of tuples: (conflicting_char, word_snippet, suggested_replacement).
        """
        if not self.conflicting_diacritics or not text:
            return []

        conflicts: List[Tuple[str, str, str]] = []
        tokens = re.findall(r"\b\w+\b", text)
        for token in tokens:
            for char in token:
                if char in self.conflicting_diacritics:
                    replacement_char = self.conflicting_diacritic_replacements.get(char, "")
                    suggested = token.replace(char, replacement_char) if replacement_char else token
                    conflicts.append((char, token, suggested))
        return conflicts

    def find_anomalous_substitutions(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Finds anomalous characters that indicate OCR character substitution errors.
        Returns a list of tuples: (anomalous_char, word_snippet, suggested_replacement).
        """
        if not self.anomalous_chars or not text:
            return []

        results: List[Tuple[str, str, str]] = []
        handled_chars: Set[str] = set()
        for anom_char, repl_char in self.anomalous_chars.items():
            base_char = anom_char.lower()
            if base_char in handled_chars:
                continue
            handled_chars.add(base_char)

            matches = re.findall(rf"\b\w*{re.escape(base_char)}\w*\b", text, re.IGNORECASE)
            for match in matches:
                clean_match = match.strip(".,;:!?()[]\"'*")
                if clean_match.lower() not in self.allowed_anomalous_tokens:
                    lower_repl = repl_char.lower()
                    upper_repl = repl_char.upper()
                    suggested = clean_match.replace(base_char, lower_repl).replace(base_char.upper(), upper_repl)
                    results.append((base_char, clean_match, suggested))
        return results

    def compute_score(self, text: str) -> float:
        """
        Computes language fidelity score between 0.0 and 1.0.
        Penalizes anomalous character substitutions, foreign diacritic conflicts,
        and lack of diacritics in longer passages.
        """
        if not text or self.code == "en":
            return 1.0

        score = 1.0

        anom_matches = self.find_anomalous_substitutions(text)
        if anom_matches:
            penalty = min(
                self.max_anomalous_char_penalty,
                len(anom_matches) * self.anomalous_char_penalty_per_occurrence
            )
            score -= penalty

        conflicts = self.find_diacritic_conflicts(text)
        if conflicts:
            penalty = min(
                self.max_conflict_penalty,
                len(conflicts) * self.conflict_penalty_per_occurrence
            )
            score -= penalty

        if self.valid_diacritics:
            has_diacritics = any(c in self.valid_diacritics for c in text)
            words = text.split()
            if len(words) > self.min_words_for_diacritic_check and not has_diacritics:
                score -= self.no_diacritics_penalty

        return max(0.0, score)


POLISH_CONFIG = LanguageConfig(
    code="pl",
    name="Polish",
    valid_diacritics=set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"),
    common_substitutions={
        "ą": ["q", "a"],
        "ę": ["e"],
        "ń": ["n"],
        "ć": ["c"],
        "ł": ["l", "1", "t"],
        "ó": ["o", "ö"],
        "ś": ["s"],
        "ź": ["z"],
        "ż": ["z"],
        "Ą": ["Q", "A"],
        "Ę": ["E"],
        "Ń": ["N"],
        "Ć": ["C"],
        "Ł": ["L", "T"],
        "Ó": ["O", "Ö"],
        "Ś": ["S"],
        "Ź": ["Z"],
        "Ż": ["Z"]
    },
    anomalous_chars={"q": "ą", "Q": "Ą"},
    allowed_anomalous_tokens={
        "sql", "query", "q1", "q2", "q3", "q4", "quality", "qr", "quick", "status", "faq"
    },
    conflicting_diacritic_replacements={
        "ö": "ó", "Ö": "Ó",
        "ä": "ą", "Ä": "Ą",
        "ü": "u", "Ü": "U",
        "ë": "ę", "Ë": "Ę"
    },
    common_word_corrections={
        "piqtku": "piątku",
        "granicq": "granicą"
    },
    min_words_for_diacritic_check=12
)

GERMAN_CONFIG = LanguageConfig(
    code="de",
    name="German",
    valid_diacritics=set("äöüßÄÖÜ"),
    common_substitutions={
        "ä": ["a", "ae"],
        "ö": ["o", "oe"],
        "ü": ["u", "ue"],
        "ß": ["ss", "B"]
    },
    conflicting_diacritic_replacements={
        "ą": "a", "ę": "e", "ł": "l", "ń": "n", "ś": "s", "ź": "z", "ż": "z", "ć": "c",
        "é": "e", "è": "e", "à": "a", "ç": "c", "ñ": "n"
    },
    min_words_for_diacritic_check=15
)

FRENCH_CONFIG = LanguageConfig(
    code="fr",
    name="French",
    valid_diacritics=set("éèêëàâçîïôûùÉÈÊËÀÂÇÎÏÔÛÙ"),
    common_substitutions={
        "é": ["e"], "è": ["e"], "ê": ["e"], "ë": ["e"],
        "à": ["a"], "â": ["a"], "ç": ["c"],
        "î": ["i"], "ï": ["i"], "ô": ["o"], "û": ["u"], "ù": ["u"]
    },
    min_words_for_diacritic_check=15
)

SPANISH_CONFIG = LanguageConfig(
    code="es",
    name="Spanish",
    valid_diacritics=set("ñáéíóúü¿¡ÑÁÉÍÓÚÜ"),
    common_substitutions={
        "ñ": ["n"], "á": ["a"], "é": ["e"], "í": ["i"], "ó": ["o"], "ú": ["u"], "ü": ["u"]
    },
    min_words_for_diacritic_check=15
)

ENGLISH_CONFIG = LanguageConfig(
    code="en",
    name="English",
    valid_diacritics=set(),
    conflicting_diacritics=set(),
    common_substitutions={},
    min_words_for_diacritic_check=999999
)

LANGUAGE_CONFIGS: Dict[str, LanguageConfig] = {
    "pl": POLISH_CONFIG,
    "de": GERMAN_CONFIG,
    "fr": FRENCH_CONFIG,
    "es": SPANISH_CONFIG,
    "en": ENGLISH_CONFIG
}


def get_language_config(language: str) -> Optional[LanguageConfig]:
    """Retrieves language configuration for the given language code."""
    if not language:
        return None
    return LANGUAGE_CONFIGS.get(language.lower().strip())


def register_language_config(config: LanguageConfig) -> None:
    """Registers or overrides a language configuration."""
    LANGUAGE_CONFIGS[config.code.lower().strip()] = config

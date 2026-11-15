"""Regression tests: diacritic conflict suggestions must never equal the original text."""

from __future__ import annotations

import unittest

from src.quality.languages.models import LanguageConfig


class TestDiacriticSuggestions(unittest.TestCase):
    def test_unmapped_conflict_has_no_noop_suggestion(self) -> None:
        cfg = LanguageConfig(
            code="pl",
            name="Polish",
            valid_diacritics=set("ąćęłńóśźż"),
            conflicting_diacritics={"š"},
        )
        conflicts = cfg.find_diacritic_conflicts("šwięto")
        self.assertEqual(len(conflicts), 1)
        char, token, suggested = conflicts[0]
        self.assertEqual(char, "š")
        self.assertEqual(suggested, "")
        self.assertEqual(token, "šwięto")

    def test_mapped_conflict_suggests_changed_text(self) -> None:
        cfg = LanguageConfig(
            code="pl",
            name="Polish",
            valid_diacritics=set("ąćęłńóśźż"),
            conflicting_diacritics={"š"},
            conflicting_diacritic_replacements={"š": "ś"},
        )
        _, token, suggested = cfg.find_diacritic_conflicts("šwięto")[0]
        self.assertEqual(suggested, "święto")
        self.assertNotEqual(suggested, token)

    def test_capitalized_words_skipped(self) -> None:
        cfg = LanguageConfig(
            code="pl",
            name="Polish",
            valid_diacritics=set("ąćęłńóśźż"),
            conflicting_diacritics={"Š", "é", "ü"},
            anomalous_chars={"q": "ą"},
        )
        self.assertEqual(cfg.find_diacritic_conflicts("Šwięto Légera Düsseldorf"), [])
        self.assertEqual(cfg.find_anomalous_substitutions("Quebec Quentin"), [])


if __name__ == "__main__":
    unittest.main()

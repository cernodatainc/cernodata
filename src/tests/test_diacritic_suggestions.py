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
            conflicting_diacritics={"Š"},
        )
        conflicts = cfg.find_diacritic_conflicts("Šwięto")
        self.assertEqual(len(conflicts), 1)
        char, token, suggested = conflicts[0]
        self.assertEqual(char, "Š")
        self.assertEqual(suggested, "")
        self.assertEqual(token, "Šwięto")

    def test_mapped_conflict_suggests_changed_text(self) -> None:
        cfg = LanguageConfig(
            code="pl",
            name="Polish",
            valid_diacritics=set("ąćęłńóśźż"),
            conflicting_diacritics={"Š"},
            conflicting_diacritic_replacements={"Š": "Ś"},
        )
        _, token, suggested = cfg.find_diacritic_conflicts("Šwięto")[0]
        self.assertEqual(suggested, "Święto")
        self.assertNotEqual(suggested, token)


if __name__ == "__main__":
    unittest.main()

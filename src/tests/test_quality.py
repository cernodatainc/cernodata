"""
src/tests/test_quality.py

Unit tests for quality continuum, garbage metrics, language checks, diacritic anomalies, and text skew detection.
"""

import unittest
import numpy as np
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.quality import (
    compute_garbage_ratio,
    compute_language_score,
    evaluate_page_confidence,
    detect_quality_violations,
    detect_node_text_skew,
    LanguageConfig,
    get_language_config,
    register_language_config
)


class TestQualityMetrics(unittest.TestCase):

    def test_garbage_ratio(self):
        self.assertEqual(compute_garbage_ratio("Clean Text"), 0.0)
        dirty_text = "Clean\x00\x01\x02Text"
        self.assertGreater(compute_garbage_ratio(dirty_text), 0.0)

    def test_polish_language_diacritic_anomaly_detection(self):
        clean_pl_text = "Sprawdź termin wykupu swoich obligacji i zamień je na nowe w piątku."
        pl_score_clean = compute_language_score(clean_pl_text, language="pl")
        self.assertEqual(pl_score_clean, 1.0)

        corrupted_pl_text = "Sprawdź termin wykupu swoich obligacji i zamień je na nowe w piqtku."
        pl_score_corrupted = compute_language_score(corrupted_pl_text, language="pl")
        self.assertLess(pl_score_corrupted, 1.0)

    def test_detect_quality_violations(self):
        node = DOMNode(
            node_id="n_viol", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Infolinia czynna w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_viol", source_filename="sample.pdf", total_pages=1, nodes=[node])

        violations = detect_quality_violations(dom, language="pl")
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v["detected_snippet"], "piqtku")
        self.assertEqual(v["suggested_correction"], "piątku")
        self.assertEqual(v["rule_type"], "ocr_character_substitution")

    def test_detect_node_text_skew(self):
        # Test on blank/empty array returns 0.0
        blank_crop = np.ones((50, 200, 3), dtype=np.uint8) * 255
        angle = detect_node_text_skew(blank_crop)
        self.assertEqual(angle, 0.0)

    def test_language_config_registry_and_substitutions(self):
        config = get_language_config("pl")
        self.assertIsNotNone(config)
        self.assertIn("ą", config.valid_diacritics)
        self.assertIn("q", config.common_substitutions.get("ą", []))
        self.assertIn("a", config.common_substitutions.get("ą", []))
        self.assertIn("e", config.common_substitutions.get("ę", []))
        self.assertIn("n", config.common_substitutions.get("ń", []))
        self.assertIn("ö", config.conflicting_diacritics)

    def test_diacritic_conflict_reduces_page_confidence(self):
        clean_node = DOMNode(
            node_id="n_clean", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Sprawdź termin wykupu obligacji w piątku."}
        )
        conflicted_node = DOMNode(
            node_id="n_conflict", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Sprawdź termin wykupu Möbel w piątku."}
        )
        clean_confidence = evaluate_page_confidence([clean_node], language="pl")
        conflicted_confidence = evaluate_page_confidence([conflicted_node], language="pl")

        self.assertEqual(clean_confidence, 1.0)
        self.assertLess(conflicted_confidence, clean_confidence)

    def test_detect_diacritic_conflict_violation(self):
        node = DOMNode(
            node_id="n_umlaut", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Firma dostarczy nowe Möbel do biura."}
        )
        dom = DocumentDOM(document_id="doc_umlaut", source_filename="sample.pdf", total_pages=1, nodes=[node])
        violations = detect_quality_violations(dom, language="pl")

        conflict_viols = [v for v in violations if v["rule_type"] == "diacritic_conflict"]
        self.assertEqual(len(conflict_viols), 1)
        v = conflict_viols[0]
        self.assertEqual(v["detected_snippet"], "Möbel")
        self.assertEqual(v["suggested_correction"], "Móbel")
        self.assertIn("not valid in Polish", v["description"])

    def test_custom_language_config_registration(self):
        custom_config = LanguageConfig(
            code="custom_lang",
            name="Custom Language",
            valid_diacritics=set("čšž"),
            conflicting_diacritics=set("öäü"),
            common_substitutions={"č": ["c"], "š": ["s"], "ž": ["z"]}
        )
        register_language_config(custom_config)
        retrieved = get_language_config("custom_lang")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Custom Language")

        clean_score = compute_language_score("Poročilo o delu in stroških", language="custom_lang")
        conflicted_score = compute_language_score("Poročilo o delu Möbel", language="custom_lang")
        self.assertEqual(clean_score, 1.0)
        self.assertLess(conflicted_score, 1.0)


if __name__ == "__main__":
    unittest.main()

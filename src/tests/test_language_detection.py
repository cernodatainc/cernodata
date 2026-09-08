"""
src/tests/test_language_detection.py

Unit tests for language autodetection heuristics, page-level and document-level language identification,
and automated language handling in quality evaluation and decision trees.
"""

import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.quality import (
    detect_text_language,
    detect_page_language,
    detect_document_languages,
    evaluate_document_confidence,
    detect_quality_violations
)
from src.pipeline import DecisionTreeEngine


class TestLanguageDetection(unittest.TestCase):

    def test_detect_text_language_polish(self):
        pl_text = "Sprawdź termin wykupu swoich obligacji i zamień je na nowe w piątku."
        lang, conf, scores = detect_text_language(pl_text)
        self.assertEqual(lang, "pl")
        self.assertGreater(conf, 0.3)

    def test_detect_text_language_english(self):
        en_text = "Automated PDF extraction pipeline with confidence-guided decision tree."
        lang, conf, scores = detect_text_language(en_text)
        self.assertEqual(lang, "en")
        self.assertGreater(conf, 0.4)

    def test_detect_text_language_french(self):
        fr_text = "Le présent document atteste de la conformité aux normes françaises."
        lang, conf, scores = detect_text_language(fr_text)
        self.assertEqual(lang, "fr")
        self.assertGreater(conf, 0.3)

    def test_detect_text_language_german(self):
        de_text = "Die Bestätigung der Angaben erfolgt durch die zuständige Behörde."
        lang, conf, scores = detect_text_language(de_text)
        self.assertEqual(lang, "de")
        self.assertGreater(conf, 0.3)

    def test_detect_text_language_spanish(self):
        es_text = "El presente documento certifica la recepción de los fondos en la cuenta."
        lang, conf, scores = detect_text_language(es_text)
        self.assertEqual(lang, "es")
        self.assertGreater(conf, 0.3)

    def test_detect_page_language(self):
        nodes = [
            DOMNode(
                node_id="n1", type="heading", global_page_index=1, temp_slice_index=1,
                bounding_box=BoundingBox(10, 10, 100, 50),
                content={"raw_text": "Zamień obligacje skarbowe"}
            ),
            DOMNode(
                node_id="n2", type="paragraph", global_page_index=1, temp_slice_index=1,
                bounding_box=BoundingBox(10, 60, 100, 100),
                content={"raw_text": "Sprawdź termin wykupu swoich obligacji"}
            )
        ]
        lang, conf, _ = detect_page_language(nodes)
        self.assertEqual(lang, "pl")

    def test_detect_document_languages_multilingual(self):
        nodes = [
            DOMNode(
                node_id="p1_n1", type="paragraph", global_page_index=1, temp_slice_index=1,
                bounding_box=BoundingBox(10, 10, 100, 50),
                content={"raw_text": "Sprawdź termin wykupu swoich obligacji w piątku."}
            ),
            DOMNode(
                node_id="p2_n1", type="paragraph", global_page_index=2, temp_slice_index=2,
                bounding_box=BoundingBox(10, 10, 100, 50),
                content={"raw_text": "This document contains English text for automated evaluation."}
            )
        ]
        dom = DocumentDOM(document_id="doc_multi", source_filename="multi.pdf", total_pages=2, nodes=nodes)
        page_langs = detect_document_languages(dom)
        self.assertEqual(page_langs[1], "pl")
        self.assertEqual(page_langs[2], "en")

    def test_evaluate_document_confidence_with_auto_language(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Sprawdź termin wykupu w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_auto", source_filename="auto.pdf", total_pages=1, nodes=[node])
        metrics = evaluate_document_confidence(dom, language="auto")
        self.assertIn("detected_languages", metrics)
        self.assertEqual(metrics["detected_languages"][1], "pl")
        self.assertEqual(metrics["primary_detected_language"], "pl")
        # With auto-detected pl, 'piqtku' triggers diacritic substitution hit
        self.assertLess(metrics["overall_confidence"], 1.0)

    def test_decision_tree_engine_includes_detected_languages(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Clean English text for testing decision tree."}
        )
        dom = DocumentDOM(document_id="doc_dt", source_filename="dt.pdf", total_pages=1, nodes=[node])
        engine = DecisionTreeEngine(language="en")
        res = engine.evaluate(dom)
        self.assertIn("detected_languages", res)
        self.assertIn("primary_detected_language", res)
        self.assertEqual(res["primary_detected_language"], "en")

    def test_detect_quality_violations_auto_language(self):
        node = DOMNode(
            node_id="n1", type="paragraph", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 100, 50),
            content={"raw_text": "Sprawdź termin wykupu w piqtku."}
        )
        dom = DocumentDOM(document_id="doc_viol_auto", source_filename="viol.pdf", total_pages=1, nodes=[node])
        violations = detect_quality_violations(dom, language="auto")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["rule_type"], "ocr_character_substitution")


if __name__ == "__main__":
    unittest.main()

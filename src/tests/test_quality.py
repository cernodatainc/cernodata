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
    detect_node_text_skew
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


if __name__ == "__main__":
    unittest.main()

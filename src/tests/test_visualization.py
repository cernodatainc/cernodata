"""
src/tests/test_visualization.py

Unit tests for PageVisualizer overlay rendering.
"""

import os
import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.quality import detect_quality_violations
from src.visualization import PageVisualizer


class TestVisualization(unittest.TestCase):

    def test_visualizer_rendering(self):
        node = DOMNode(
            node_id="n1", type="heading", global_page_index=1, temp_slice_index=1,
            bounding_box=BoundingBox(50, 50, 400, 100), content={"raw_text": "Infolinia czynna w piqtku"}
        )
        dom = DocumentDOM(document_id="doc_vis", source_filename="sample.pdf", total_pages=1, nodes=[node])
        violations = detect_quality_violations(dom, language="pl")

        visualizer = PageVisualizer(dpi=72)
        out_paths = visualizer.render_overlay("non_existent.pdf", dom, violations=violations, output_dir="test_output")
        self.assertGreater(len(out_paths), 0)
        self.assertTrue(os.path.exists(out_paths[0]))

        if os.path.exists(out_paths[0]):
            os.remove(out_paths[0])

    def test_visualizer_streaming_backgrounds_nonexistent(self):
        visualizer = PageVisualizer(dpi=72)
        backgrounds = list(visualizer._iter_pdf_page_backgrounds("non_existent.pdf"))
        self.assertEqual(len(backgrounds), 0)
        self.assertIsNone(visualizer._render_pdf_page_backgrounds("non_existent.pdf"))


if __name__ == "__main__":
    unittest.main()

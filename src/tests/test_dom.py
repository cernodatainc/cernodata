"""
src/tests/test_dom.py

Unit tests for DOM data models and primitives.
"""

import unittest
from src.dom import BoundingBox, DOMNode, DocumentDOM


class TestDOMPrimitives(unittest.TestCase):

    def test_bounding_box_dict(self):
        bbox = BoundingBox(10.123, 20.456, 100.789, 200.012, angle=45.0)
        b_dict = bbox.to_dict()
        self.assertEqual(b_dict["x0"], 10.12)
        self.assertEqual(b_dict["y0"], 20.46)
        self.assertEqual(b_dict["x1"], 100.79)
        self.assertEqual(b_dict["y1"], 200.01)
        self.assertEqual(b_dict["angle"], 45.0)

    def test_bounding_box_rotation_polygon(self):
        # 0 degree rotation unrotated corners
        bbox0 = BoundingBox(0.0, 0.0, 10.0, 20.0, angle=0.0)
        poly0 = bbox0.to_polygon()
        self.assertEqual(poly0, [(0.0, 0.0), (10.0, 0.0), (10.0, 20.0), (0.0, 20.0)])

        # 90 degree rotation
        bbox90 = BoundingBox(0.0, 0.0, 10.0, 20.0, angle=90.0)
        poly90 = bbox90.to_polygon()
        self.assertEqual(len(poly90), 4)

    def test_document_dom_serialization(self):
        bbox = BoundingBox(10.0, 20.0, 100.0, 200.0)
        node = DOMNode(
            node_id="node_1",
            type="heading",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=bbox,
            content={"raw_text": "Sample Title"}
        )
        dom = DocumentDOM(document_id="doc_1", source_filename="test.pdf", total_pages=1, nodes=[node])
        dom_dict = dom.to_dict()

        self.assertEqual(dom_dict["document_id"], "doc_1")
        self.assertEqual(len(dom_dict["nodes"]), 1)
        self.assertEqual(dom_dict["nodes"][0]["bounding_box"]["x0"], 10.0)


if __name__ == "__main__":
    unittest.main()

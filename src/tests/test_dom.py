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

    def test_merge_nodes_textual_same_type(self):
        n1 = DOMNode(
            node_id="p1",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 100.0, 50.0),
            content={"raw_text": "First line."}
        )
        n2 = DOMNode(
            node_id="p2",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 55.0, 100.0, 90.0),
            content={"raw_text": "Second line."}
        )
        dom = DocumentDOM(document_id="doc_merge", source_filename="test.pdf", total_pages=1, nodes=[n1, n2])
        merged = dom.merge_nodes("p1", "p2")

        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(merged.node_id, "p1")
        self.assertEqual(merged.type, "paragraph")
        self.assertEqual(merged.content["raw_text"], "First line.\nSecond line.")
        self.assertEqual(merged.bounding_box.x0, 10.0)
        self.assertEqual(merged.bounding_box.y0, 10.0)
        self.assertEqual(merged.bounding_box.y1, 90.0)

    def test_merge_nodes_different_types_with_user_selection(self):
        n1 = DOMNode(
            node_id="h1",
            type="heading",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(20.0, 15.0, 150.0, 40.0),
            content={"raw_text": "Chapter 1"}
        )
        n2 = DOMNode(
            node_id="p1",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(20.0, 45.0, 200.0, 80.0),
            content={"raw_text": "Beginning of the chapter."}
        )
        dom = DocumentDOM(document_id="doc_diff", source_filename="test.pdf", total_pages=1, nodes=[n1, n2])
        # User selects target_type="heading" and custom merged_text
        merged = dom.merge_nodes("h1", "p1", target_type="heading", merged_text="Chapter 1: Beginning of the chapter.")

        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(merged.type, "heading")
        self.assertEqual(merged.content["raw_text"], "Chapter 1: Beginning of the chapter.")
        self.assertEqual(merged.bounding_box.x1, 200.0)

    def test_merge_nodes_not_found(self):
        dom = DocumentDOM(document_id="doc_err", source_filename="test.pdf", total_pages=1, nodes=[])
        with self.assertRaises(ValueError):
            dom.merge_nodes("missing_1", "missing_2")


if __name__ == "__main__":
    unittest.main()

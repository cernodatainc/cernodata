"""
src/tests/test_dom.py

Unit tests for DOM data models and primitives.
"""

import os
import unittest
from src.dom import (
    BoundingBox,
    DOMNode,
    DocumentDOM,
    DOMNodeType,
    PresetKind,
    PipelineAction,
)


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

    def test_bounding_box_from_dict(self):
        raw = {"x0": 15.5, "y0": 25.5, "x1": 150.0, "y1": 250.0, "angle": 12.5, "quad": [[10, 20], [100, 20], [100, 50], [10, 50]]}
        bbox = BoundingBox.from_dict(raw)
        self.assertEqual(bbox.x0, 15.5)
        self.assertEqual(bbox.y0, 25.5)
        self.assertEqual(bbox.angle, 12.5)
        self.assertIsNotNone(bbox.quad)
        self.assertEqual(len(bbox.quad), 4)

    def test_dom_node_from_dict(self):
        raw_node = {
            "node_id": "node_test_1",
            "type": DOMNodeType.HEADING,
            "global_page_index": 2,
            "temp_slice_index": 2,
            "bounding_box": {"x0": 10.0, "y0": 10.0, "x1": 100.0, "y1": 30.0},
            "content": {"raw_text": "Section Header"},
            "template_hint_applied": "standard_title",
        }
        node = DOMNode.from_dict(raw_node)
        self.assertEqual(node.node_id, "node_test_1")
        self.assertEqual(node.type, "heading")
        self.assertEqual(node.global_page_index, 2)
        self.assertEqual(node.bounding_box.x1, 100.0)
        self.assertEqual(node.content["raw_text"], "Section Header")
        self.assertEqual(node.template_hint_applied, "standard_title")

    def test_document_dom_from_dict_and_json(self):
        raw_doc = {
            "document_id": "doc_roundtrip",
            "source_filename": "roundtrip.pdf",
            "total_pages": 3,
            "nodes": [
                {
                    "node_id": "n1",
                    "type": "paragraph",
                    "global_page_index": 1,
                    "temp_slice_index": 1,
                    "bounding_box": {"x0": 5.0, "y0": 5.0, "x1": 50.0, "y1": 20.0},
                    "content": {"raw_text": "First page text."},
                }
            ],
        }
        dom = DocumentDOM.from_dict(raw_doc)
        self.assertEqual(dom.document_id, "doc_roundtrip")
        self.assertEqual(dom.total_pages, 3)
        self.assertEqual(len(dom.nodes), 1)
        self.assertEqual(dom.nodes[0].content["raw_text"], "First page text.")

        # JSON roundtrip
        json_str = dom.to_json()
        reconstructed = DocumentDOM.from_json(json_str)
        self.assertEqual(reconstructed.document_id, dom.document_id)
        self.assertEqual(len(reconstructed.nodes), 1)
        self.assertEqual(reconstructed.nodes[0].node_id, "n1")

    def test_document_dom_save_and_load(self):
        import tempfile
        node = DOMNode(
            node_id="n_save",
            type="paragraph",
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(0, 0, 10, 10),
            content={"raw_text": "Persisted line."}
        )
        dom = DocumentDOM(document_id="doc_save", source_filename="save_test.pdf", total_pages=1, nodes=[node])

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "dom_test.json")
            dom.save(file_path)
            self.assertTrue(os.path.exists(file_path))

            loaded = DocumentDOM.load(file_path)
            self.assertEqual(loaded.document_id, "doc_save")
            self.assertEqual(len(loaded.nodes), 1)
            self.assertEqual(loaded.nodes[0].content["raw_text"], "Persisted line.")

    def test_dom_enums(self):
        self.assertEqual(DOMNodeType.PARAGRAPH, "paragraph")
        self.assertEqual(DOMNodeType.HEADING, "heading")
        self.assertEqual(PresetKind.DOCLING_FAST, "docling_fast")
        self.assertEqual(PresetKind.DOCLING_DEEP, "docling_deep")
        self.assertEqual(PresetKind.PYPDFIUM_RAPIDOCR, "pypdfium_rapidocr")
        self.assertEqual(PipelineAction.ACCEPT_OUTPUT, "ACCEPT_OUTPUT")
        self.assertEqual(PipelineAction.PATH_A_SWITCH_PRESET, "PATH_A_SWITCH_PRESET")
        self.assertEqual(PipelineAction.PATH_B_WIGGLE_PARAMETERS, "PATH_B_WIGGLE_PARAMETERS")


if __name__ == "__main__":
    unittest.main()

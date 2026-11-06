"""
src/tests/test_dom_manipulation.py

Unit tests verifying comprehensive DOM manipulation features:
- Querying by id, page, type, bounding box, and points
- Node insertion, replacement, removal, and property updating
- In-place node splitting and bounding box decollision
- Page slicing extraction and re-parsed sliced DOM merging
- Document metadata round-trip serialization and reading order sorting
"""

from __future__ import annotations

import unittest
from src.dom import (
    BoundingBox,
    DOMNode,
    DOMNodeType,
    DocumentDOM,
)


class TestDOMManipulation(unittest.TestCase):

    def _create_sample_dom(self) -> DocumentDOM:
        n1 = DOMNode(
            node_id="p1_title",
            type=DOMNodeType.HEADING,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(50.0, 50.0, 500.0, 90.0),
            content={"raw_text": "Sample Title Heading"},
        )
        n2 = DOMNode(
            node_id="p1_para1",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(50.0, 100.0, 500.0, 200.0),
            content={"raw_text": "First body paragraph line."},
        )
        n3 = DOMNode(
            node_id="p1_footer",
            type=DOMNodeType.FOOTER,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(50.0, 750.0, 500.0, 780.0),
            content={"raw_text": "Page 1 Footer"},
        )
        n4 = DOMNode(
            node_id="p2_para1",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=2,
            temp_slice_index=2,
            bounding_box=BoundingBox(50.0, 100.0, 500.0, 220.0),
            content={"raw_text": "Second page paragraph."},
        )
        return DocumentDOM(
            document_id="doc_manip_test",
            source_filename="test.pdf",
            total_pages=2,
            nodes=[n1, n2, n3, n4],
            metadata={"source_engine": "test_suite", "version": 1},
        )

    # -------------------------------------------------------------------------
    # Enums & BoundingBox Extensions
    # -------------------------------------------------------------------------

    def test_dom_node_type_extensions(self) -> None:
        self.assertEqual(DOMNodeType.PAGE_HEADER, "page_header")
        self.assertEqual(DOMNodeType.FOOTER, "footer")
        self.assertEqual(DOMNodeType.LIST_ITEM, "list_item")
        self.assertEqual(DOMNodeType.CAPTION, "caption")
        self.assertEqual(DOMNodeType.CODE_BLOCK, "code_block")

    def test_bounding_box_contains_and_transformations(self) -> None:
        box = BoundingBox(10.0, 20.0, 100.0, 200.0)
        self.assertTrue(box.contains_point(50.0, 100.0))
        self.assertTrue(box.contains_point(10.0, 20.0))
        self.assertFalse(box.contains_point(5.0, 100.0))
        self.assertFalse(box.contains_point(50.0, 250.0))

        inner_box = BoundingBox(20.0, 30.0, 90.0, 150.0)
        outer_box = BoundingBox(0.0, 0.0, 150.0, 250.0)
        self.assertTrue(box.contains_box(inner_box))
        self.assertFalse(box.contains_box(outer_box))

        translated = box.translate(10.0, -5.0)
        self.assertEqual((translated.x0, translated.y0, translated.x1, translated.y1), (20.0, 15.0, 110.0, 195.0))

        scaled = box.scale(2.0, 0.5)
        self.assertEqual((scaled.x0, scaled.y0, scaled.x1, scaled.y1), (20.0, 10.0, 200.0, 100.0))

        cloned = box.clone()
        self.assertEqual(cloned.to_dict(), box.to_dict())
        self.assertIsNot(cloned, box)

    # -------------------------------------------------------------------------
    # DOMNode Property and Mutation Tests
    # -------------------------------------------------------------------------

    def test_dom_node_text_property_and_mutations(self) -> None:
        node = DOMNode(
            node_id="n_text_test",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 100.0, 50.0),
            content={"raw_text": "Initial Text"},
        )
        self.assertEqual(node.text, "Initial Text")

        node.text = "Updated via property"
        self.assertEqual(node.text, "Updated via property")
        self.assertEqual(node.content["raw_text"], "Updated via property")
        self.assertEqual(node.user_correction_note, "Updated via property")

        node.update_text("New Text Value", user_note="Correction audit")
        self.assertEqual(node.text, "New Text Value")
        self.assertEqual(node.user_correction_note, "Correction audit")
        self.assertTrue(node.is_custom)

        new_box = BoundingBox(20.0, 20.0, 150.0, 80.0)
        node.update_bbox(new_box)
        self.assertEqual(node.bounding_box, new_box)

    def test_dom_node_spatial_queries_and_violations(self) -> None:
        n1 = DOMNode(
            node_id="n1",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 100.0, 100.0),
        )
        n2 = DOMNode(
            node_id="n2",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(50.0, 50.0, 150.0, 150.0),
        )
        n3 = DOMNode(
            node_id="n3",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=2,
            temp_slice_index=2,
            bounding_box=BoundingBox(10.0, 10.0, 100.0, 100.0),
        )

        self.assertTrue(n1.contains_point(50.0, 50.0))
        self.assertTrue(n1.intersects(n2))
        self.assertFalse(n1.intersects(n3))  # Different page
        self.assertGreater(n1.iou(n2), 0.0)
        self.assertEqual(n1.iou(n3), 0.0)

        self.assertFalse(n1.has_violations())
        viol = {"type": "diacritic", "rule": "polish_diacritic"}
        n1.add_violation(viol)
        self.assertTrue(n1.has_violations())
        self.assertEqual(len(n1.violations), 1)
        # Adding duplicate does not duplicate entry
        n1.add_violation(viol)
        self.assertEqual(len(n1.violations), 1)

        n1.clear_violations()
        self.assertFalse(n1.has_violations())

    def test_dom_node_clone(self) -> None:
        node = DOMNode(
            node_id="orig",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 50, 50),
            content={"raw_text": "Original"},
            violations=[{"type": "warn"}],
        )
        cloned = node.clone()
        self.assertEqual(cloned.node_id, node.node_id)
        self.assertEqual(cloned.content["raw_text"], "Original")
        self.assertIsNot(cloned, node)
        self.assertIsNot(cloned.content, node.content)
        self.assertIsNot(cloned.bounding_box, node.bounding_box)

    # -------------------------------------------------------------------------
    # DocumentDOM Retrieval & Query Tests
    # -------------------------------------------------------------------------

    def test_document_dom_queries(self) -> None:
        dom = self._create_sample_dom()

        # Query by ID
        found = dom.get_node_by_id("p1_title")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.type, DOMNodeType.HEADING)
        self.assertIsNone(dom.get_node_by_id("missing_id"))

        # Query by page
        p1_nodes = dom.get_nodes_by_page(1)
        self.assertEqual(len(p1_nodes), 3)
        p2_nodes = dom.get_nodes_by_page(2)
        self.assertEqual(len(p2_nodes), 1)
        self.assertEqual(dom.get_nodes_by_page(99), [])

        # Query by type
        headings = dom.get_nodes_by_type(DOMNodeType.HEADING)
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0].node_id, "p1_title")
        paras = dom.get_nodes_by_type("paragraph")
        self.assertEqual(len(paras), 2)

        # Spatial intersecting queries
        intersecting = dom.find_nodes_intersecting(BoundingBox(40.0, 40.0, 100.0, 80.0), page_index=1)
        self.assertEqual(len(intersecting), 1)
        self.assertEqual(intersecting[0].node_id, "p1_title")

        # Point queries
        point_nodes = dom.find_nodes_containing_point(100.0, 150.0, page_index=1)
        self.assertEqual(len(point_nodes), 1)
        self.assertEqual(point_nodes[0].node_id, "p1_para1")

        # Custom predicate filter
        filtered = dom.filter_nodes(lambda n: "Footer" in n.text)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].node_id, "p1_footer")

    # -------------------------------------------------------------------------
    # DocumentDOM Mutation & Modification Tests
    # -------------------------------------------------------------------------

    def test_document_dom_mutations(self) -> None:
        dom = self._create_sample_dom()

        # Add node updating total_pages
        new_node = DOMNode(
            node_id="p3_new",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=3,
            temp_slice_index=3,
            bounding_box=BoundingBox(10, 10, 100, 100),
            content={"raw_text": "Page three"},
        )
        dom.add_node(new_node)
        self.assertEqual(dom.total_pages, 3)
        self.assertEqual(len(dom.nodes), 5)

        # Update node text
        updated = dom.update_node_text("p1_para1", "Replaced paragraph content")
        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertEqual(updated.text, "Replaced paragraph content")

        # Update node type
        dom.update_node_type("p1_title", DOMNodeType.PARAGRAPH)
        self.assertEqual(dom.get_node_by_id("p1_title").type, DOMNodeType.PARAGRAPH)

        # Update node bbox
        new_bbox = BoundingBox(0, 0, 300, 300)
        dom.update_node_bbox("p1_title", new_bbox)
        self.assertEqual(dom.get_node_by_id("p1_title").bounding_box, new_bbox)

        # Replace node
        replacement = DOMNode(
            node_id="p1_title",
            type=DOMNodeType.HEADING,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10, 10, 200, 50),
            content={"raw_text": "Brand New Title"},
        )
        self.assertTrue(dom.replace_node("p1_title", replacement))
        self.assertEqual(dom.get_node_by_id("p1_title").text, "Brand New Title")

        # Remove node
        removed = dom.remove_node("p1_footer")
        self.assertIsNotNone(removed)
        assert removed is not None
        self.assertEqual(removed.node_id, "p1_footer")
        self.assertIsNone(dom.get_node_by_id("p1_footer"))

    def test_document_dom_in_place_split_node(self) -> None:
        dom = self._create_sample_dom()
        split_parts = dom.split_node("p1_para1", char_offset=10)
        self.assertEqual(len(split_parts), 2)
        self.assertIsNone(dom.get_node_by_id("p1_para1"))
        self.assertIsNotNone(dom.get_node_by_id("p1_para1_s1"))
        self.assertIsNotNone(dom.get_node_by_id("p1_para1_s2"))

    # -------------------------------------------------------------------------
    # Slicing and Splicing Tests
    # -------------------------------------------------------------------------

    def test_extract_page_slice_and_merge_sliced_dom(self) -> None:
        dom = self._create_sample_dom()

        # Extract page 2 slice
        slice_doc = dom.extract_page_slice([2])
        self.assertEqual(slice_doc.total_pages, 1)
        self.assertEqual(len(slice_doc.nodes), 1)
        self.assertEqual(slice_doc.nodes[0].temp_slice_index, 1)
        self.assertEqual(slice_doc.nodes[0].global_page_index, 2)

        # Simulate re-parsing page 2 with new text
        slice_doc.nodes[0].text = "Re-parsed high-accuracy page 2 content"

        # Splice back into primary DOM
        dom.merge_sliced_dom(slice_doc, slice_to_global_map={1: 2})
        p2_node = dom.get_node_by_id("p2_para1")
        self.assertIsNotNone(p2_node)
        assert p2_node is not None
        self.assertEqual(p2_node.text, "Re-parsed high-accuracy page 2 content")

    # -------------------------------------------------------------------------
    # Inspection, Utilities, and Decollision Tests
    # -------------------------------------------------------------------------

    def test_document_dom_text_and_reading_order(self) -> None:
        dom = self._create_sample_dom()
        p1_text = dom.get_text(page_index=1, separator=" | ")
        self.assertIn("Sample Title Heading", p1_text)
        self.assertIn("First body paragraph line.", p1_text)
        self.assertIn("Page 1 Footer", p1_text)

        all_text = dom.get_text()
        self.assertIn("Second page paragraph.", all_text)

        dom.sort_nodes(by_reading_order=True)
        self.assertEqual(dom.nodes[0].node_id, "p1_title")

    def test_overlapping_pairs_and_vertical_decollide(self) -> None:
        n1 = DOMNode(
            node_id="top_box",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 10.0, 100.0, 60.0),
        )
        n2 = DOMNode(
            node_id="bot_box",
            type=DOMNodeType.PARAGRAPH,
            global_page_index=1,
            temp_slice_index=1,
            bounding_box=BoundingBox(10.0, 50.0, 100.0, 110.0),  # 10px overlap [50, 60]
        )
        dom = DocumentDOM(document_id="doc_decol", source_filename="test.pdf", total_pages=1, nodes=[n1, n2])

        overlaps = dom.find_overlapping_pairs(page_index=1)
        self.assertEqual(len(overlaps), 1)

        decollided = dom.decollide_vertical("top_box", "bot_box", padding=2.0)
        self.assertTrue(decollided)

        top_updated = dom.get_node_by_id("top_box")
        bot_updated = dom.get_node_by_id("bot_box")
        assert top_updated is not None and bot_updated is not None
        self.assertLessEqual(top_updated.bounding_box.y1, bot_updated.bounding_box.y0)

    def test_metadata_round_trip(self) -> None:
        dom = self._create_sample_dom()
        dom.metadata["audit_trail"] = ["parsed_docling_fast", "verified"]
        d = dom.to_dict()
        self.assertIn("metadata", d)
        self.assertEqual(d["metadata"]["audit_trail"], ["parsed_docling_fast", "verified"])

        restored = DocumentDOM.from_dict(d)
        self.assertEqual(restored.metadata["audit_trail"], ["parsed_docling_fast", "verified"])

        cloned = dom.clone()
        self.assertEqual(cloned.metadata, dom.metadata)
        self.assertIsNot(cloned.metadata, dom.metadata)


if __name__ == "__main__":
    unittest.main()

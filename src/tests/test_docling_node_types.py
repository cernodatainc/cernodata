"""
src/tests/test_docling_node_types.py

Unit tests for mapping Docling item labels to DocumentDOM node types.
These run without Docling installed: they exercise the resolver with stub items.
"""

import unittest
from enum import Enum
from src.parsers.docling_parser import _resolve_node_type


class _StubItem:
    def __init__(self, label):
        self.label = label


class _StubLabel(str, Enum):
    """Mimics docling_core DocItemLabel, a str-backed Enum."""
    SECTION_HEADER = "section_header"
    PAGE_HEADER = "page_header"


class TestResolveNodeType(unittest.TestCase):

    def test_section_header_is_heading(self):
        self.assertEqual(_resolve_node_type(_StubItem("section_header")), "heading")

    def test_title_is_heading(self):
        self.assertEqual(_resolve_node_type(_StubItem("title")), "heading")

    def test_page_header_and_footer_are_header_footer(self):
        self.assertEqual(_resolve_node_type(_StubItem("page_header")), "header_footer")
        self.assertEqual(_resolve_node_type(_StubItem("page_footer")), "header_footer")

    def test_table_is_table_grid(self):
        self.assertEqual(_resolve_node_type(_StubItem("table")), "table_grid")

    def test_picture_is_figure(self):
        self.assertEqual(_resolve_node_type(_StubItem("picture")), "figure")

    def test_body_text_labels_are_paragraph(self):
        for label in ("text", "paragraph", "list_item", "caption", "footnote"):
            self.assertEqual(_resolve_node_type(_StubItem(label)), "paragraph", label)

    def test_enum_labels_resolve_by_value(self):
        self.assertEqual(_resolve_node_type(_StubItem(_StubLabel.SECTION_HEADER)), "heading")
        self.assertEqual(_resolve_node_type(_StubItem(_StubLabel.PAGE_HEADER)), "header_footer")

    def test_label_case_is_ignored(self):
        self.assertEqual(_resolve_node_type(_StubItem("Section_Header")), "heading")

    def test_unknown_heading_like_label_falls_back_to_heading(self):
        self.assertEqual(_resolve_node_type(_StubItem("field_heading")), "heading")

    def test_missing_label_is_paragraph(self):
        self.assertEqual(_resolve_node_type(object()), "paragraph")
        self.assertEqual(_resolve_node_type(_StubItem(None)), "paragraph")


if __name__ == "__main__":
    unittest.main()

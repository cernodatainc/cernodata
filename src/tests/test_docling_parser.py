"""
src/tests/test_docling_parser.py

Unit tests for DoclingParser item-to-node content mapping.
These run without Docling installed: they exercise the mapping helpers with stub items.
"""

import unittest
from src.parsers.docling_parser import _build_node_content, _resolve_node_type, _resolve_raw_text


class _StubTextItem:
    label = "text"

    def __init__(self, text):
        self.text = text


class _StubPictureItem:
    """Mimics docling PictureItem: it has a label and provenance but no text attribute."""
    label = "picture"

    def __init__(self, caption=None, raise_on_caption=False):
        self._caption = caption
        self._raise = raise_on_caption

    def caption_text(self, doc):
        if self._raise:
            raise RuntimeError("caption lookup failed")
        return self._caption

    def __str__(self):
        return "self_ref='#/pictures/0' parent=RefItem(cref='#/body') label=<DocItemLabel.PICTURE: 'picture'>"

    __repr__ = __str__


class _StubItemWithoutCaptionApi:
    label = "picture"

    def __str__(self):
        return "self_ref='#/pictures/1' parent=RefItem(cref='#/body')"


class TestDoclingParserContent(unittest.TestCase):

    def test_text_item_keeps_stripped_text(self):
        content = _build_node_content(_StubTextItem("  Hello world  "), "paragraph")
        self.assertEqual(content["raw_text"], "Hello world")

    def test_item_without_text_attribute_does_not_leak_repr(self):
        item = _StubPictureItem()
        content = _build_node_content(item, _resolve_node_type(item))
        self.assertEqual(content["raw_text"], "")
        self.assertNotIn("self_ref", content["raw_text"])

    def test_item_without_text_or_caption_api_yields_empty_string(self):
        item = _StubItemWithoutCaptionApi()
        self.assertEqual(_resolve_raw_text(item, "figure", doc=object()), "")

    def test_figure_uses_caption_when_available(self):
        item = _StubPictureItem(caption="  Figure 1. Bond yield curve  ")
        content = _build_node_content(item, "figure", doc=object())
        self.assertEqual(content["raw_text"], "Figure 1. Bond yield curve")

    def test_figure_caption_requires_doc(self):
        item = _StubPictureItem(caption="Figure 1. Bond yield curve")
        self.assertEqual(_resolve_raw_text(item, "figure", doc=None), "")

    def test_figure_caption_lookup_error_is_swallowed(self):
        item = _StubPictureItem(raise_on_caption=True)
        self.assertEqual(_resolve_raw_text(item, "figure", doc=object()), "")

    def test_non_string_text_attribute_is_ignored(self):
        item = _StubTextItem(None)
        self.assertEqual(_resolve_raw_text(item, "paragraph"), "")

    def test_picture_label_resolves_to_figure(self):
        self.assertEqual(_resolve_node_type(_StubPictureItem()), "figure")


if __name__ == "__main__":
    unittest.main()

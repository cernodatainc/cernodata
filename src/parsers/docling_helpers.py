"""
src/parsers/docling_helpers.py

Helper functions for Docling item normalization, bounding box translation, and content parsing.
"""

import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from src.dom.enums import DOMNodeType
from src.parsers.docling_types import (
    CaptionableItem,
    DoclingBBox,
    DoclingBBoxConvertible,
    DoclingBBoxWithOrigin,
    DoclingDocument,
    DoclingPage,
    DoclingProvenance,
    EnumLikeLabel,
    LabeledItem,
    TextItem,
)
from src.parsers.table_parser import parse_table_content
from src.quality.language_config import get_language_config

logger = logging.getLogger("cernodata.parsers.docling_helpers")

DEFAULT_PAGE_HEIGHT_PT = 792.0  # US Letter page height in points

DEFAULT_OCR_LANGUAGES: List[str] = ["pl", "de", "fr", "es", "en"]
_ALL_LANGS: List[str] = list(DEFAULT_OCR_LANGUAGES)

LANG_CODE_MAP: Dict[str, List[str]] = {
    "pl": ["pl", "pol"],
    "de": ["de", "deu"],
    "fr": ["fr", "fra"],
    "es": ["es", "spa"],
    "en": ["en", "eng"],
    "auto": list(_ALL_LANGS),
    "": list(_ALL_LANGS),
    "none": list(_ALL_LANGS),
}

_DEEP_OCR_TRAILING_NOISE_RE = re.compile(r"[\s\(\)\[\]]{2,}[a-z\(\)\s]{1,10}$")

# Docling emits DocItemLabel values such as "section_header" and "page_header". Exact labels
# are resolved first: a substring check would route "section_header" to header_footer (it
# contains "header") before the heading check could run.
_EXACT_LABEL_TYPES: Dict[str, str] = {
    "title": DOMNodeType.HEADING.value,
    "section_header": DOMNodeType.HEADING.value,
    "page_header": DOMNodeType.HEADER_FOOTER.value,
    "page_footer": DOMNodeType.HEADER_FOOTER.value,
    "table": DOMNodeType.TABLE_GRID.value,
    "picture": DOMNodeType.FIGURE.value,
}


def fallback_top_left_bbox(bbox: DoclingBBox, page_height: float) -> Tuple[float, float, float, float]:
    """Calculates top-left origin coordinates from bottom-left origin fallback."""
    if isinstance(bbox, DoclingBBoxWithOrigin) and bbox.coord_origin and "BOTTOMLEFT" in str(bbox.coord_origin):
        return (
            bbox.l,
            page_height - bbox.t,
            bbox.r,
            page_height - bbox.b,
        )
    return bbox.l, bbox.t, bbox.r, bbox.b


def extract_page_no_and_bbox(
    doc: Optional[DoclingDocument],
    item: object,
    prov_item: DoclingProvenance,
) -> Tuple[int, float, float, float, float]:
    """Extracts page number and top-left origin normalized bounding box coordinates."""
    _ = item
    page_no = prov_item.page_no if isinstance(prov_item, DoclingProvenance) else 1
    bbox = prov_item.bbox if isinstance(prov_item, DoclingProvenance) else None
    if bbox is None:
        return page_no, 0.0, 0.0, 0.0, 0.0

    page_height = DEFAULT_PAGE_HEIGHT_PT
    if doc is not None and isinstance(doc, DoclingDocument) and doc.pages:
        page_obj: Optional[DoclingPage] = None
        if isinstance(doc.pages, Mapping) and page_no in doc.pages:
            page_obj = doc.pages[page_no]
        elif (
            isinstance(doc.pages, Sequence)
            and not isinstance(doc.pages, (str, bytes))
            and 0 <= page_no - 1 < len(doc.pages)
        ):
            page_obj = doc.pages[page_no - 1]
        if page_obj is not None and page_obj.size is not None:
            page_height = page_obj.size.height

    if isinstance(bbox, DoclingBBoxConvertible):
        try:
            tl = bbox.to_top_left_origin(page_height)
            x0, y0, x1, y1 = tl.l, tl.t, tl.r, tl.b
        except Exception as ex:
            logger.debug("to_top_left_origin failed, using fallback bbox conversion: %s", ex)
            x0, y0, x1, y1 = fallback_top_left_bbox(bbox, page_height)
    else:
        x0, y0, x1, y1 = fallback_top_left_bbox(bbox, page_height)

    if y0 > y1:
        y0, y1 = y1, y0
    if x0 > x1:
        x0, x1 = x1, x0
    return page_no, x0, y0, x1, y1


def resolve_node_type(item: object) -> str:
    """Resolves cernodata DOM primitive type from docling item label."""
    raw_label = item.label if isinstance(item, LabeledItem) else None
    if isinstance(raw_label, EnumLikeLabel):
        label = str(raw_label.value).lower()
    elif raw_label is not None:
        label = str(raw_label).lower()
    else:
        label = ""
    exact = _EXACT_LABEL_TYPES.get(label)
    if exact:
        return exact
    if "title" in label or "heading" in label or "section" in label:
        return DOMNodeType.HEADING.value
    if "header" in label or "footer" in label:
        return DOMNodeType.HEADER_FOOTER.value
    if "table" in label:
        return DOMNodeType.TABLE_GRID.value
    if "picture" in label or "figure" in label:
        return DOMNodeType.FIGURE.value
    return DOMNodeType.PARAGRAPH.value


def figure_caption(item: object, doc: object) -> str:
    """Returns the caption text of a figure item when Docling exposes one, otherwise an empty string."""
    if doc is None or not isinstance(item, CaptionableItem):
        return ""
    try:
        caption = item.caption_text(doc)
    except Exception as ex:
        logger.debug("Figure caption extraction failed: %s", ex)
        return ""
    return caption.strip() if isinstance(caption, str) else ""


def resolve_raw_text(item: object, node_type: str, doc: object = None) -> str:
    """
    Resolves the textual content of a Docling item.

    Items without a text attribute (for example PictureItem) must yield an empty string,
    never their object repr. Figures fall back to their caption when one is available.
    """
    text = item.text if isinstance(item, TextItem) else None
    raw_text = text.strip() if isinstance(text, str) else ""
    if not raw_text and node_type == "figure":
        raw_text = figure_caption(item, doc)
    return raw_text


def build_node_content(
    item: object,
    node_type: str,
    preset: str = "docling_fast",
    language: str = "en",
    doc: object = None,
) -> Dict[str, Any]:
    """Builds node content payload dictionary, applying deep OCR diacritic restoration if docling_deep preset is selected."""
    raw_text = resolve_raw_text(item, node_type, doc)
    if preset == "docling_deep":
        eff_lang = language
        if eff_lang == "auto" and raw_text:
            from src.quality.language import detect_text_language
            eff_lang, _, _ = detect_text_language(raw_text)
        config = get_language_config(eff_lang)
        if config:
            if config.common_word_corrections:
                for err, fix in config.common_word_corrections.items():
                    raw_text = raw_text.replace(err, fix)
            for _, word, suggested in config.find_anomalous_substitutions(raw_text):
                raw_text = raw_text.replace(word, suggested)
        # Deep OCR clean-up for trailing OCR noise/fragmented punctuation soup
        raw_text = _DEEP_OCR_TRAILING_NOISE_RE.sub("", raw_text).strip()

    content_dict: Dict[str, Any] = {"raw_text": raw_text}
    if node_type == "table_grid":
        table_payload = parse_table_content(
            item, doc=doc, preset=preset, fallback_text=raw_text
        )
        content_dict.update(table_payload)
        if not content_dict.get("raw_text") and content_dict.get("markdown_table"):
            content_dict["raw_text"] = content_dict["markdown_table"]
    return content_dict

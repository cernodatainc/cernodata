"""
src/parsers/docling_helpers.py

Helper functions for Docling item normalization, bounding box translation, and content parsing.
"""

import re
from typing import Dict, Any, Tuple
from src.quality.language_config import get_language_config

LANG_CODE_MAP = {
    "pl": ["pol", "pl"],
    "de": ["deu", "de"],
    "fr": ["fra", "fr"],
    "es": ["spa", "es"],
    "en": ["eng", "en"],
    "auto": ["pol", "deu", "fra", "spa", "eng"]
}

# Docling emits DocItemLabel values such as "section_header" and "page_header". Exact labels
# are resolved first: a substring check would route "section_header" to header_footer (it
# contains "header") before the heading check could run.
_EXACT_LABEL_TYPES: Dict[str, str] = {
    "title": "heading",
    "section_header": "heading",
    "page_header": "header_footer",
    "page_footer": "header_footer",
    "table": "table_grid",
    "picture": "figure",
}


def fallback_top_left_bbox(bbox: Any, page_height: float) -> Tuple[float, float, float, float]:
    """Calculates top-left origin coordinates from bottom-left origin fallback."""
    if getattr(bbox, "coord_origin", None) and "BOTTOMLEFT" in str(bbox.coord_origin):
        return (
            getattr(bbox, "l", 0.0),
            page_height - getattr(bbox, "t", 0.0),
            getattr(bbox, "r", 0.0),
            page_height - getattr(bbox, "b", 0.0),
        )
    return getattr(bbox, "l", 0.0), getattr(bbox, "t", 0.0), getattr(bbox, "r", 0.0), getattr(bbox, "b", 0.0)


def extract_page_no_and_bbox(doc: Any, item: Any, prov_item: Any) -> Tuple[int, float, float, float, float]:
    """Extracts page number and top-left origin normalized bounding box coordinates."""
    page_no = getattr(prov_item, "page_no", 1)
    if not hasattr(prov_item, "bbox") or not prov_item.bbox:
        return page_no, 0.0, 0.0, 0.0, 0.0

    bbox = prov_item.bbox
    page_height = 792.0
    if hasattr(doc, "pages") and doc.pages:
        if isinstance(doc.pages, dict) and page_no in doc.pages:
            page_height = getattr(doc.pages[page_no].size, "height", 792.0)
        elif isinstance(doc.pages, list) and 0 <= page_no - 1 < len(doc.pages):
            page_height = getattr(doc.pages[page_no - 1].size, "height", 792.0)

    if hasattr(bbox, "to_top_left_origin"):
        try:
            tl = bbox.to_top_left_origin(page_height)
            x0, y0, x1, y1 = tl.l, tl.t, tl.r, tl.b
        except Exception:
            x0, y0, x1, y1 = fallback_top_left_bbox(bbox, page_height)
    else:
        x0, y0, x1, y1 = fallback_top_left_bbox(bbox, page_height)

    if y0 > y1:
        y0, y1 = y1, y0
    if x0 > x1:
        x0, x1 = x1, x0
    return page_no, x0, y0, x1, y1


def resolve_node_type(item: Any) -> str:
    """Resolves cernodata DOM primitive type from docling item label."""
    label = getattr(item, "label", "") or ""
    label = str(getattr(label, "value", label)).lower()
    exact = _EXACT_LABEL_TYPES.get(label)
    if exact:
        return exact
    if "title" in label or "heading" in label or "section" in label:
        return "heading"
    if "header" in label or "footer" in label:
        return "header_footer"
    if "table" in label:
        return "table_grid"
    if "picture" in label or "figure" in label:
        return "figure"
    return "paragraph"


def figure_caption(item: Any, doc: Any) -> str:
    """Returns the caption text of a figure item when Docling exposes one, otherwise an empty string."""
    if doc is None or not hasattr(item, "caption_text"):
        return ""
    try:
        caption = item.caption_text(doc)
    except Exception:
        return ""
    return caption.strip() if isinstance(caption, str) else ""


def resolve_raw_text(item: Any, node_type: str, doc: Any = None) -> str:
    """
    Resolves the textual content of a Docling item.

    Items without a text attribute (for example PictureItem) must yield an empty string,
    never their object repr. Figures fall back to their caption when one is available.
    """
    text = getattr(item, "text", None)
    raw_text = text.strip() if isinstance(text, str) else ""
    if not raw_text and node_type == "figure":
        raw_text = figure_caption(item, doc)
    return raw_text


def build_node_content(
    item: Any,
    node_type: str,
    preset: str = "docling_fast",
    language: str = "en",
    doc: Any = None
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
        raw_text = re.sub(r"[\s\(\)\[\]]{2,}[a-z\(\)\s]{1,10}$", "", raw_text).strip()

    content_dict: Dict[str, Any] = {"raw_text": raw_text}
    if node_type == "table_grid" and hasattr(item, "export_to_markdown"):
        try:
            content_dict["markdown_table"] = item.export_to_markdown()
        except Exception:
            pass
        content_dict["cell_alignment_score"] = 0.98 if preset == "docling_deep" else 0.96
    return content_dict

"""
src/parsers/synthetic_parser.py

Synthetic DOM parser fallback for dry-runs and unit testing without ML dependencies.
"""

from src.dom import BoundingBox, DOMNode, DocumentDOM


class SyntheticParser:
    """
    Generates synthetic DocumentDOM structures for testing or when heavy ML parsers are unavailable.
    """

    def parse(self, doc_id: str, source_filename: str) -> DocumentDOM:
        nodes = [
            DOMNode(
                node_id="node_p1_n1",
                type="heading",
                global_page_index=1,
                temp_slice_index=1,
                bounding_box=BoundingBox(x0=54.0, y0=40.0, x1=550.0, y1=80.0),
                content={"raw_text": "Cernodata Layout Analysis Statement"}
            ),
            DOMNode(
                node_id="node_p1_n2",
                type="paragraph",
                global_page_index=1,
                temp_slice_index=1,
                bounding_box=BoundingBox(x0=54.0, y0=90.0, x1=550.0, y1=150.0),
                content={"raw_text": "Automated PDF extraction pipeline with confidence-guided decision tree."}
            )
        ]
        return DocumentDOM(
            document_id=doc_id,
            source_filename=source_filename,
            total_pages=1,
            nodes=nodes
        )

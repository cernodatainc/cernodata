"""
src/dom.py

Data structures and primitives for cernodata's standardized DocumentDOM schema.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional


@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "x0": round(self.x0, 2),
            "y0": round(self.y0, 2),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2)
        }


@dataclass
class DOMNode:
    node_id: str
    type: str  # heading, paragraph, table_grid, figure, header_footer, multi_column_group
    global_page_index: int
    temp_slice_index: int
    bounding_box: BoundingBox
    content: Dict[str, Any] = field(default_factory=dict)
    template_hint_applied: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "node_id": self.node_id,
            "type": self.type,
            "global_page_index": self.global_page_index,
            "temp_slice_index": self.temp_slice_index,
            "bounding_box": self.bounding_box.to_dict(),
            "content": self.content
        }
        if self.template_hint_applied:
            res["template_hint_applied"] = self.template_hint_applied
        return res


@dataclass
class DocumentDOM:
    document_id: str
    source_filename: str
    total_pages: int
    nodes: List[DOMNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source_filename": self.source_filename,
            "total_pages": self.total_pages,
            "nodes": [node.to_dict() for node in self.nodes]
        }

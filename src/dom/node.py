"""
src/dom/node.py

DOMNode element primitive for cernodata IR.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from src.dom.bounding_box import BoundingBox


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

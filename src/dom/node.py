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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DOMNode":
        """Reconstructs DOMNode from serialized dictionary representation."""
        raw_box = data.get("bounding_box", {})
        if isinstance(raw_box, dict):
            bbox = BoundingBox.from_dict(raw_box)
        elif isinstance(raw_box, BoundingBox):
            bbox = raw_box
        else:
            bbox = BoundingBox(0.0, 0.0, 0.0, 0.0)

        raw_type = data.get("type", "paragraph")
        node_type = raw_type.value if hasattr(raw_type, "value") else str(raw_type)

        return cls(
            node_id=str(data.get("node_id", "")),
            type=node_type,
            global_page_index=int(data.get("global_page_index", 1)),
            temp_slice_index=int(data.get("temp_slice_index", 1)),
            bounding_box=bbox,
            content=dict(data.get("content", {})),
            template_hint_applied=data.get("template_hint_applied"),
        )

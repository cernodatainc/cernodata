"""
src/dom/node.py

DOMNode element primitive for cernodata IR.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from src.dom.bounding_box import BoundingBox
from src.dom.enums import DOMNodeType


@dataclass
class DOMNode:
    node_id: str
    type: Union[DOMNodeType, str]  # heading, paragraph, table_grid, figure, header_footer, multi_column_group
    global_page_index: int
    temp_slice_index: int
    bounding_box: BoundingBox
    content: Dict[str, Any] = field(default_factory=dict)
    template_hint_applied: Optional[str] = None
    # TODO(TASK-903): Populate `template_hint_applied` and `content["template_zone_id"]` when spatial
    # zones from a DocumentTemplateHint match this node's bounding box.
    violations: List[Dict[str, Any]] = field(default_factory=list)
    is_merged: bool = False
    merged_from: Optional[List[Dict[str, Any]]] = None
    merged_at: Optional[str] = None
    user_correction_note: Optional[str] = None
    is_incorrect_text: Optional[bool] = None
    ocr_confidence: Optional[float] = None
    is_custom: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        node_type = self.type.value if isinstance(self.type, DOMNodeType) else str(self.type)
        res: Dict[str, Any] = {
            "node_id": self.node_id,
            "type": node_type,
            "global_page_index": self.global_page_index,
            "temp_slice_index": self.temp_slice_index,
            "bounding_box": self.bounding_box.to_dict(),
            "content": self.content,
            "violations": self.violations,
        }
        if self.template_hint_applied:
            res["template_hint_applied"] = self.template_hint_applied
        if self.is_merged:
            res["is_merged"] = self.is_merged
        if self.merged_from:
            res["merged_from"] = self.merged_from
        if self.merged_at:
            res["merged_at"] = self.merged_at
        if self.user_correction_note:
            res["user_correction_note"] = self.user_correction_note
        if self.is_incorrect_text is not None:
            res["is_incorrect_text"] = self.is_incorrect_text
        if self.ocr_confidence is not None:
            res["ocr_confidence"] = self.ocr_confidence
        if self.is_custom:
            res["is_custom"] = self.is_custom
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
            violations=list(data.get("violations", [])),
            is_merged=bool(data.get("is_merged", False)),
            merged_from=data.get("merged_from"),
            merged_at=data.get("merged_at"),
            user_correction_note=data.get("user_correction_note"),
            is_incorrect_text=data.get("is_incorrect_text"),
            ocr_confidence=data.get("ocr_confidence"),
            is_custom=data.get("is_custom"),
        )

    def split_at_offset(
        self, char_offset: int, vertical_ratio: Optional[float] = None
    ) -> List["DOMNode"]:
        """
        Splits this node's text and vertical bounding box into two separate nodes.

        Args:
            char_offset: Character index in raw text where the split occurs.
            vertical_ratio: Fraction [0.05, 0.95] for vertical bounding box split.
                           If None, defaults to proportional text length ratio.

        Returns:
            List of two new DOMNode instances, or [self] if offset is out of bounds.
        """
        raw_text = str(self.content.get("raw_text") or self.user_correction_note or "")
        if char_offset <= 0 or char_offset >= len(raw_text):
            return [self]

        text1 = raw_text[:char_offset].rstrip("\r\n")
        text2 = raw_text[char_offset:].lstrip("\r\n")

        if vertical_ratio is not None:
            ratio = max(0.05, min(0.95, float(vertical_ratio)))
        else:
            total_len = len(text1) + len(text2)
            ratio = max(0.05, min(0.95, len(text1) / total_len)) if total_len > 0 else 0.5

        y_mid = round(self.bounding_box.y0 + (self.bounding_box.y1 - self.bounding_box.y0) * ratio, 2)

        bbox1 = BoundingBox(
            x0=self.bounding_box.x0,
            y0=self.bounding_box.y0,
            x1=self.bounding_box.x1,
            y1=y_mid,
            angle=self.bounding_box.angle,
        )
        bbox2 = BoundingBox(
            x0=self.bounding_box.x0,
            y0=y_mid,
            x1=self.bounding_box.x1,
            y1=self.bounding_box.y1,
            angle=self.bounding_box.angle,
        )

        content1 = dict(self.content)
        content1["raw_text"] = text1
        content2 = dict(self.content)
        content2["raw_text"] = text2

        node1 = DOMNode(
            node_id=f"{self.node_id}_s1",
            type=self.type,
            global_page_index=self.global_page_index,
            temp_slice_index=self.temp_slice_index,
            bounding_box=bbox1,
            content=content1,
            violations=[],
            user_correction_note=text1,
            is_custom=True,
        )
        node2 = DOMNode(
            node_id=f"{self.node_id}_s2",
            type=self.type,
            global_page_index=self.global_page_index,
            temp_slice_index=self.temp_slice_index,
            bounding_box=bbox2,
            content=content2,
            violations=[],
            user_correction_note=text2,
            is_custom=True,
        )
        return [node1, node2]


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
        for key in (
            "template_hint_applied",
            "is_merged",
            "merged_from",
            "merged_at",
            "user_correction_note",
            "is_custom",
            "is_incorrect_text",
            "ocr_confidence",
        ):
            val = getattr(self, key)
            if key in ("is_incorrect_text", "ocr_confidence"):
                if val is not None:
                    res[key] = val
            elif val:
                res[key] = val
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

        optional_fields = {
            k: data[k]
            for k in (
                "template_hint_applied",
                "merged_from",
                "merged_at",
                "user_correction_note",
                "is_incorrect_text",
                "ocr_confidence",
                "is_custom",
            )
            if k in data
        }

        return cls(
            node_id=str(data.get("node_id", "")),
            type=node_type,
            global_page_index=int(data.get("global_page_index", 1)),
            temp_slice_index=int(data.get("temp_slice_index", 1)),
            bounding_box=bbox,
            content=dict(data.get("content", {})),
            violations=list(data.get("violations", [])),
            is_merged=bool(data.get("is_merged", False)),
            **optional_fields,
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
        parts = ((1, self.bounding_box.y0, y_mid, text1), (2, y_mid, self.bounding_box.y1, text2))
        return [
            DOMNode(
                node_id=f"{self.node_id}_s{idx}",
                type=self.type,
                global_page_index=self.global_page_index,
                temp_slice_index=self.temp_slice_index,
                bounding_box=BoundingBox(
                    x0=self.bounding_box.x0, y0=y0, x1=self.bounding_box.x1, y1=y1, angle=self.bounding_box.angle
                ),
                content={**self.content, "raw_text": txt},
                violations=[],
                user_correction_note=txt,
                is_custom=True,
            )
            for idx, y0, y1, txt in parts
        ]


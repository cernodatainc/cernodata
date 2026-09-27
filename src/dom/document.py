"""
src/dom/document.py

DocumentDOM tree container primitive.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from src.dom.bounding_box import BoundingBox
from src.dom.node import DOMNode


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

    def merge_nodes(
        self,
        node_id_1: str,
        node_id_2: str,
        target_type: Optional[str] = None,
        merged_text: Optional[str] = None,
        text_separator: str = "\n"
    ) -> DOMNode:
        """
        Merges two DOM nodes within this document.
        Combines bounding boxes, unifies content/text, and replaces both nodes with a single merged node.
        """
        idx1 = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id_1), -1)
        idx2 = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id_2), -1)
        if idx1 == -1 or idx2 == -1:
            raise ValueError(f"Nodes not found: {node_id_1}, {node_id_2}")

        n1 = self.nodes[idx1]
        n2 = self.nodes[idx2]

        upper, lower = (n1, n2) if (n1.bounding_box.y0 <= n2.bounding_box.y0) else (n2, n1)
        res_type = target_type if target_type is not None else upper.type

        merged_bbox = BoundingBox(
            x0=min(n1.bounding_box.x0, n2.bounding_box.x0),
            y0=min(n1.bounding_box.y0, n2.bounding_box.y0),
            x1=max(n1.bounding_box.x1, n2.bounding_box.x1),
            y1=max(n1.bounding_box.y1, n2.bounding_box.y1)
        )

        merged_content = dict(upper.content)
        merged_content.update(lower.content)

        if merged_text is not None:
            merged_content["raw_text"] = merged_text
        else:
            t1 = str(upper.content.get("raw_text", "")).strip()
            t2 = str(lower.content.get("raw_text", "")).strip()
            if t1 and t2:
                merged_content["raw_text"] = f"{t1}{text_separator}{t2}"
            elif t1 or t2:
                merged_content["raw_text"] = t1 or t2

        merged_node = DOMNode(
            node_id=upper.node_id,
            type=res_type,
            global_page_index=upper.global_page_index,
            temp_slice_index=upper.temp_slice_index,
            bounding_box=merged_bbox,
            content=merged_content
        )

        new_nodes: List[DOMNode] = []
        for n in self.nodes:
            if n.node_id == upper.node_id:
                new_nodes.append(merged_node)
            elif n.node_id == lower.node_id:
                continue
            else:
                new_nodes.append(n)
        self.nodes = new_nodes
        return merged_node

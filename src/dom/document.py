"""
src/dom/document.py

DocumentDOM tree container primitive and DOM manipulation operations.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from src.dom.bounding_box import BoundingBox
from src.dom.enums import DOMNodeType
from src.dom.node import DOMNode
from src.utils import save_json


@dataclass
class DocumentDOM:
    document_id: str
    source_filename: str
    total_pages: int
    nodes: List[DOMNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "document_id": self.document_id,
            "source_filename": self.source_filename,
            "total_pages": self.total_pages,
            "nodes": [node.to_dict() for node in self.nodes],
        }
        if self.metadata:
            res["metadata"] = self.metadata
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentDOM":
        """Reconstructs DocumentDOM from serialized dictionary representation."""
        nodes = [
            DOMNode.from_dict(n) if isinstance(n, dict) else n
            for n in data.get("nodes", [])
            if isinstance(n, (dict, DOMNode))
        ]
        total_pages = data.get("total_pages")
        if total_pages is None:
            total_pages = max((n.global_page_index for n in nodes), default=1)

        metadata = dict(data.get("metadata", {}))

        return cls(
            document_id=str(data.get("document_id", "")),
            source_filename=str(data.get("source_filename", "")),
            total_pages=int(total_pages),
            nodes=nodes,
            metadata=metadata,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "DocumentDOM":
        """Parses a JSON string directly into a DocumentDOM instance."""
        return cls.from_dict(json.loads(json_str))

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serializes DocumentDOM to a JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def load(cls, filepath: str) -> "DocumentDOM":
        """Loads and parses a DocumentDOM instance from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def save(self, filepath: str, indent: int = 2) -> None:
        """Serializes and saves DocumentDOM to a target JSON file path."""
        save_json(filepath, self.to_dict(), indent=indent)

    # -------------------------------------------------------------------------
    # Node Querying and Retrieval
    # -------------------------------------------------------------------------

    def get_node_by_id(self, node_id: str) -> Optional[DOMNode]:
        """Finds and returns a DOMNode by its unique node_id, or None if not found."""
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def get_nodes_by_page(self, page_index: int) -> List[DOMNode]:
        """Returns all DOM nodes located on the specified 1-based page index."""
        return [n for n in self.nodes if n.global_page_index == page_index]

    def get_nodes_by_type(self, node_type: Union[DOMNodeType, str]) -> List[DOMNode]:
        """Returns all DOM nodes matching the specified structural node type."""
        target_val = node_type.value if hasattr(node_type, "value") else str(node_type)
        return [
            n for n in self.nodes
            if (n.type.value if hasattr(n.type, "value") else str(n.type)) == target_val
        ]

    def find_nodes_intersecting(
        self, bbox: BoundingBox, page_index: Optional[int] = None
    ) -> List[DOMNode]:
        """Finds all DOM nodes whose bounding boxes intersect the target bbox."""
        return [
            n for n in self.nodes
            if (page_index is None or n.global_page_index == page_index)
            and n.bounding_box.intersects(bbox)
        ]

    def find_nodes_containing_point(
        self, x: float, y: float, page_index: Optional[int] = None
    ) -> List[DOMNode]:
        """Finds all DOM nodes whose bounding boxes contain the coordinates (x, y)."""
        return [
            n for n in self.nodes
            if (page_index is None or n.global_page_index == page_index)
            and n.bounding_box.contains_point(x, y)
        ]

    def filter_nodes(self, predicate: Callable[[DOMNode], bool]) -> List[DOMNode]:
        """Returns all DOM nodes matching a custom predicate callable."""
        return [n for n in self.nodes if predicate(n)]

    # -------------------------------------------------------------------------
    # Node Manipulation (Insertion, Deletion, Updating)
    # -------------------------------------------------------------------------

    def add_node(self, node: DOMNode) -> None:
        """Appends a new DOMNode to this document and adjusts total_pages if necessary."""
        self.nodes.append(node)
        if node.global_page_index > self.total_pages:
            self.total_pages = node.global_page_index

    def insert_node(self, index: int, node: DOMNode) -> None:
        """Inserts a DOMNode at a specific index within nodes list."""
        self.nodes.insert(index, node)
        if node.global_page_index > self.total_pages:
            self.total_pages = node.global_page_index

    def remove_node(self, node_id: str) -> Optional[DOMNode]:
        """Removes a DOMNode by its unique node_id and returns the removed node, or None."""
        for idx, n in enumerate(self.nodes):
            if n.node_id == node_id:
                return self.nodes.pop(idx)
        return None

    def replace_node(self, node_id: str, new_node: DOMNode) -> bool:
        """Replaces an existing node matching node_id with new_node."""
        for idx, n in enumerate(self.nodes):
            if n.node_id == node_id:
                self.nodes[idx] = new_node
                if new_node.global_page_index > self.total_pages:
                    self.total_pages = new_node.global_page_index
                return True
        return False

    def update_node_text(self, node_id: str, new_text: str) -> Optional[DOMNode]:
        """Updates the text content and correction note of a target node."""
        node = self.get_node_by_id(node_id)
        if node is not None:
            node.update_text(new_text)
        return node

    def update_node_type(
        self, node_id: str, new_type: Union[DOMNodeType, str]
    ) -> Optional[DOMNode]:
        """Updates the structural type of a target node."""
        node = self.get_node_by_id(node_id)
        if node is not None:
            node.type = new_type
            node.is_custom = True
        return node

    def update_node_bbox(self, node_id: str, new_bbox: BoundingBox) -> Optional[DOMNode]:
        """Updates the bounding box of a target node."""
        node = self.get_node_by_id(node_id)
        if node is not None:
            node.update_bbox(new_bbox)
        return node

    # -------------------------------------------------------------------------
    # Node Splitting and Merging
    # -------------------------------------------------------------------------

    def split_node(
        self, node_id: str, char_offset: int, vertical_ratio: Optional[float] = None
    ) -> List[DOMNode]:
        """
        Splits a target node in place into two nodes at character offset and vertical ratio.
        Replaces the original node in `self.nodes` with the resulting split segments.
        """
        for idx, n in enumerate(self.nodes):
            if n.node_id == node_id:
                parts = n.split_at_offset(char_offset, vertical_ratio)
                if len(parts) > 1:
                    self.nodes[idx : idx + 1] = parts
                return parts
        raise ValueError(f"Node '{node_id}' not found in document.")

    def merge_nodes(
        self,
        node_id_1: str,
        node_id_2: str,
        target_type: Optional[str] = None,
        merged_text: Optional[str] = None,
        text_separator: str = "\n",
    ) -> DOMNode:
        """
        Merges two DOM nodes within this document.
        Combines bounding boxes, unifies content/text, and replaces both nodes with a single merged node.
        """
        if node_id_1 == node_id_2:
            raise ValueError(f"Cannot merge node '{node_id_1}' with itself.")

        idx1 = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id_1), -1)
        idx2 = next((i for i, n in enumerate(self.nodes) if n.node_id == node_id_2), -1)
        if idx1 == -1 or idx2 == -1:
            raise ValueError(f"Nodes not found: {node_id_1}, {node_id_2}")

        n1 = self.nodes[idx1]
        n2 = self.nodes[idx2]

        if n1.global_page_index != n2.global_page_index:
            raise ValueError(
                f"Cannot merge nodes across different pages: "
                f"page {n1.global_page_index} vs page {n2.global_page_index}."
            )

        upper, lower = (n1, n2) if (n1.bounding_box.y0 <= n2.bounding_box.y0) else (n2, n1)
        res_type = target_type if target_type is not None else upper.type
        merged_bbox = n1.bounding_box.union(n2.bounding_box)

        merged_content = dict(upper.content)
        for k, v in lower.content.items():
            if k not in merged_content:
                merged_content[k] = v

        if merged_text is not None:
            merged_content["raw_text"] = merged_text
        else:
            t1 = str(upper.content.get("raw_text", "")).strip()
            t2 = str(lower.content.get("raw_text", "")).strip()
            if t1 and t2:
                merged_content["raw_text"] = f"{t1}{text_separator}{t2}"
            elif t1 or t2:
                merged_content["raw_text"] = t1 or t2

        merged_violations = list(upper.violations) + [
            v for v in lower.violations if v not in upper.violations
        ]

        merged_node = DOMNode(
            node_id=upper.node_id,
            type=res_type,
            global_page_index=upper.global_page_index,
            temp_slice_index=upper.temp_slice_index,
            bounding_box=merged_bbox,
            content=merged_content,
            violations=merged_violations,
            is_merged=True,
            merged_from=[upper.to_dict(), lower.to_dict()],
            merged_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        self.nodes = [
            merged_node if n.node_id == upper.node_id else n
            for n in self.nodes
            if n.node_id != lower.node_id
        ]
        return merged_node

    # -------------------------------------------------------------------------
    # Page Slicing and Splicing Operations
    # -------------------------------------------------------------------------

    def extract_page_slice(self, page_indices: Sequence[int]) -> "DocumentDOM":
        """
        Extracts a sub-document slice containing only nodes from the given pages.
        Maps each page to consecutive 1-based temp_slice_index coordinates.
        """
        page_set = set(page_indices)
        slice_map = {orig: idx for idx, orig in enumerate(sorted(page_set), start=1)}
        sliced_nodes = []
        for n in self.nodes:
            if n.global_page_index in page_set:
                cloned = n.clone()
                cloned.temp_slice_index = slice_map[n.global_page_index]
                sliced_nodes.append(cloned)

        return DocumentDOM(
            document_id=f"{self.document_id}_slice",
            source_filename=self.source_filename,
            total_pages=len(page_set),
            nodes=sliced_nodes,
            metadata={"parent_document_id": self.document_id, "sliced_pages": list(page_indices)},
        )

    def merge_sliced_dom(
        self,
        sliced_dom: "DocumentDOM",
        slice_to_global_map: Optional[Dict[int, int]] = None,
    ) -> "DocumentDOM":
        """
        Splices re-parsed page slices from `sliced_dom` back into this DocumentDOM.
        Remaps temp_slice_index -> global_page_index via `slice_to_global_map` when provided,
        replaces existing nodes on affected pages, and restores canonical reading order.
        """
        if not sliced_dom.nodes:
            return self

        page_map = dict(slice_to_global_map) if slice_to_global_map is not None else {}
        affected_pages: Set[int] = set()
        spliced_nodes: List[DOMNode] = []

        for node in sliced_dom.nodes:
            cloned = node.clone()
            target_page = page_map.get(
                cloned.temp_slice_index,
                page_map.get(cloned.global_page_index, cloned.global_page_index),
            )
            cloned.global_page_index = target_page
            cloned.temp_slice_index = target_page
            affected_pages.add(target_page)
            spliced_nodes.append(cloned)

        # Remove existing nodes on affected pages and splice in new nodes
        self.nodes = [n for n in self.nodes if n.global_page_index not in affected_pages]
        self.nodes.extend(spliced_nodes)
        self.sort_nodes(by_reading_order=True)
        self.recompute_total_pages()
        return self

    # -------------------------------------------------------------------------
    # Reorganization and Inspection Utilities
    # -------------------------------------------------------------------------

    def sort_nodes(self, by_reading_order: bool = True) -> None:
        """Sorts nodes by page index, and optionally top-to-bottom, left-to-right reading order."""
        if by_reading_order:
            self.nodes.sort(
                key=lambda n: (n.global_page_index, n.bounding_box.y0, n.bounding_box.x0)
            )
        else:
            self.nodes.sort(key=lambda n: n.global_page_index)

    def get_text(self, page_index: Optional[int] = None, separator: str = "\n") -> str:
        """Returns the concatenated textual content of the document or a single page."""
        target_nodes = (
            self.get_nodes_by_page(page_index) if page_index is not None else self.nodes
        )
        ordered = sorted(
            target_nodes,
            key=lambda n: (n.global_page_index, n.bounding_box.y0, n.bounding_box.x0),
        )
        texts = [n.text.strip() for n in ordered if n.text.strip()]
        return separator.join(texts)

    def recompute_total_pages(self) -> int:
        """Recomputes and sets total_pages based on maximum global_page_index across all nodes."""
        self.total_pages = max((n.global_page_index for n in self.nodes), default=1)
        return self.total_pages

    def find_overlapping_pairs(
        self, page_index: Optional[int] = None, iou_threshold: float = 0.05
    ) -> List[Tuple[DOMNode, DOMNode, float]]:
        """Finds pairs of overlapping or colliding DOM nodes on the same page."""
        overlaps: List[Tuple[DOMNode, DOMNode, float]] = []
        target_nodes = (
            self.get_nodes_by_page(page_index) if page_index is not None else self.nodes
        )
        for i in range(len(target_nodes)):
            for j in range(i + 1, len(target_nodes)):
                n1, n2 = target_nodes[i], target_nodes[j]
                if n1.global_page_index == n2.global_page_index:
                    score = n1.iou(n2)
                    if score >= iou_threshold or n1.intersects(n2):
                        overlaps.append((n1, n2, score))
        return overlaps

    def decollide_vertical(
        self, node_id_1: str, node_id_2: str, padding: float = 2.0
    ) -> bool:
        """
        Adjusts vertical boundary coordinates of two vertically overlapping nodes on the same page.
        Returns True if decollision was performed, False otherwise.
        """
        n1 = self.get_node_by_id(node_id_1)
        n2 = self.get_node_by_id(node_id_2)
        if not n1 or not n2 or n1.global_page_index != n2.global_page_index:
            return False

        upper, lower = (
            (n1, n2) if n1.bounding_box.y0 <= n2.bounding_box.y0 else (n2, n1)
        )
        if upper.bounding_box.y1 > lower.bounding_box.y0:
            mid = (upper.bounding_box.y1 + lower.bounding_box.y0) / 2.0
            upper.bounding_box = BoundingBox(
                x0=upper.bounding_box.x0,
                y0=upper.bounding_box.y0,
                x1=upper.bounding_box.x1,
                y1=max(upper.bounding_box.y0, round(mid - padding / 2.0, 2)),
                angle=upper.bounding_box.angle,
            )
            lower.bounding_box = BoundingBox(
                x0=lower.bounding_box.x0,
                y0=min(lower.bounding_box.y1, round(mid + padding / 2.0, 2)),
                x1=lower.bounding_box.x1,
                y1=lower.bounding_box.y1,
                angle=lower.bounding_box.angle,
            )
            upper.is_custom = True
            lower.is_custom = True
            return True
        return False

    def clone(self) -> "DocumentDOM":
        """Creates a deep copy of this DocumentDOM."""
        return DocumentDOM(
            document_id=self.document_id,
            source_filename=self.source_filename,
            total_pages=self.total_pages,
            nodes=[n.clone() for n in self.nodes],
            metadata=dict(self.metadata),
        )

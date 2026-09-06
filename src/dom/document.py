"""
src/dom/document.py

DocumentDOM tree container primitive.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List
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

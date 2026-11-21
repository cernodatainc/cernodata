"""
src/pipeline/postprocessors/base.py

DOM postprocessor protocol, audit action record, and sequential chain runner (TASK-501).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable

from src.dom import DOMNodeOrigin, DocumentDOM


@dataclass
class PostprocessActionRecord:
    """Audit record capturing an individual DOM mutation performed by a postprocessor."""

    step_name: str
    action: str
    node_id: str
    page_index: int
    reason: str
    original_node_dict: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes this action record to a dictionary representation."""
        result: Dict[str, Any] = {
            "step_name": self.step_name,
            "action": self.action,
            "node_id": self.node_id,
            "page_index": self.page_index,
            "reason": self.reason,
        }
        if self.original_node_dict is not None:
            result["original_node_dict"] = self.original_node_dict
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PostprocessActionRecord":
        """Reconstructs a PostprocessActionRecord from a serialized dictionary."""
        raw_orig = data.get("original_node_dict")
        return cls(
            step_name=str(data.get("step_name", "")),
            action=str(data.get("action", "")),
            node_id=str(data.get("node_id", "")),
            page_index=int(data.get("page_index", 1)),
            reason=str(data.get("reason", "")),
            original_node_dict=dict(raw_orig) if isinstance(raw_orig, dict) else None,
        )


@runtime_checkable
class DOMPostprocessor(Protocol):
    """Protocol implemented by modular DocumentDOM postprocessing steps."""

    name: str

    def process(self, dom: DocumentDOM) -> Tuple[DocumentDOM, List[PostprocessActionRecord]]:
        """Transforms the supplied DocumentDOM and returns updated DOM with action records."""
        ...


class PostprocessorChain:
    """Runs an ordered sequence of DOMPostprocessor steps and logs their action records."""

    def __init__(self, steps: Optional[Sequence[DOMPostprocessor]] = None) -> None:
        self.steps: List[DOMPostprocessor] = list(steps) if steps else []
        self.history: List[PostprocessActionRecord] = []

    def add_step(self, step: DOMPostprocessor) -> None:
        """Appends a postprocessor step to the end of the execution chain."""
        self.steps.append(step)

    def run(self, dom: DocumentDOM) -> Tuple[DocumentDOM, List[PostprocessActionRecord]]:
        """Executes all registered postprocessors sequentially and persists action history on dom.metadata."""
        chain_records: List[PostprocessActionRecord] = []
        current_dom = dom

        for step in self.steps:
            current_dom, step_records = step.process(current_dom)
            for rec in step_records:
                if rec.action == "added_node":
                    added_node = current_dom.get_node_by_id(rec.node_id)
                    if added_node is not None:
                        added_node.origin = DOMNodeOrigin.POSTPROCESSED
                        if isinstance(added_node.content, dict):
                            added_node.content.setdefault("origin", DOMNodeOrigin.POSTPROCESSED.value)
                chain_records.append(rec)

        if chain_records:
            self.history.extend(chain_records)
            existing_actions = current_dom.metadata.get("postprocess_actions")
            action_dicts = list(existing_actions) if isinstance(existing_actions, list) else []
            action_dicts.extend(rec.to_dict() for rec in chain_records)
            current_dom.metadata["postprocess_actions"] = action_dicts

        return current_dom, chain_records

    def process(self, dom: DocumentDOM) -> Tuple[DocumentDOM, List[PostprocessActionRecord]]:
        """Protocol-compatible entry point delegating to run(dom)."""
        return self.run(dom)

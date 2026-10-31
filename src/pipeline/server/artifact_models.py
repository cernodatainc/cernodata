"""
src/pipeline/server/artifact_models.py

Typed data containers shared by server artifact loading and viewer hydration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypedDict


@dataclass
class RunArtifacts:
    """Strongly-typed container for loaded pipeline execution artifacts."""
    plan_execution_result: Dict[str, Any] = field(default_factory=dict)
    plan: Optional[Dict[str, Any]] = None
    decision: Dict[str, Any] = field(default_factory=dict)
    dom: Dict[str, Any] = field(default_factory=dict)
    raw_dom: Dict[str, Any] = field(default_factory=dict)
    diff: Dict[str, Any] = field(default_factory=dict)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    verification_result: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    chosen_preset: str = "N/A"
    status: str = "ACCEPT"
    overall_confidence: Optional[float] = None
    document_path: str = ""
    document_name: str = "Unknown"

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            if key in self.artifacts:
                return self.artifacts[key]
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.artifacts.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes artifacts to dictionary mapping."""
        res = {
            "plan_execution_result": self.plan_execution_result,
            "plan": self.plan,
            "decision": self.decision,
            "dom": self.dom,
            "raw_dom": self.raw_dom,
            "diff": self.diff,
            "violations": self.violations,
            "verification_result": self.verification_result,
            "chosen_preset": self.chosen_preset,
            "status": self.status,
            "overall_confidence": self.overall_confidence,
            "document_path": self.document_path,
            "document_name": self.document_name,
        }
        if self.artifacts:
            res["artifacts"] = self.artifacts
            for k, v in self.artifacts.items():
                res.setdefault(k, v)
        return res


class ViewerDataset(TypedDict, total=False):
    """Strongly-typed dataset schema required to hydrate interactive visual viewer."""
    dom: Dict[str, Any]
    raw_dom: Dict[str, Any]
    diff: Dict[str, Any]
    violations: List[Dict[str, Any]]
    decision: Dict[str, Any]
    detectedLanguages: Dict[str, Any]
    plan: Optional[Dict[str, Any]]
    pdfSourceFile: str
    activeLanguage: str
    pageImages: List[str]
    pageDimensions: List[Dict[str, float]]
    totalPages: int
    outputDir: str
    verificationResult: Dict[str, Any]
    verificationLayers: List[str]
    layerScores: Dict[str, float]
    activeStep: Optional[int]

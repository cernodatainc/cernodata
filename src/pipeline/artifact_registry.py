"""
src/pipeline/artifact_registry.py

Extensible artifact export and loading registry.
Decouples document post-processing artifact generators and loaders from monolithic
orchestrator and server artifact functions.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.dom import DocumentDOM
from src.utils import mkdirs

logger = logging.getLogger("cernodata.pipeline.artifact_registry")


@dataclass
class ArtifactDescriptor:
    """Specification describing a pipeline output artifact and its lifecycle hooks."""
    key: str
    filename: str
    export_hook: Optional[Callable[[DocumentDOM, Dict[str, Any], List[Dict[str, Any]], str, Optional[Dict[str, Any]]], Optional[str]]] = None
    load_hook: Optional[Callable[[str], Any]] = None
    description: str = ""


class ArtifactRegistry:
    """Registry coordinating pipeline artifact export and ingestion hooks."""

    def __init__(self) -> None:
        self._descriptors: Dict[str, ArtifactDescriptor] = {}

    def register(self, descriptor: ArtifactDescriptor) -> None:
        """Registers a pipeline artifact descriptor."""
        self._descriptors[descriptor.key] = descriptor

    def get(self, key: str) -> Optional[ArtifactDescriptor]:
        """Looks up an artifact descriptor by key."""
        return self._descriptors.get(key)

    def list_all(self) -> List[ArtifactDescriptor]:
        """Returns all registered artifact descriptors."""
        return list(self._descriptors.values())

    def export_artifacts(
        self,
        dom: DocumentDOM,
        decision: Dict[str, Any],
        violations: List[Dict[str, Any]],
        output_dir: str,
        plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Executes all registered export hooks, saving artifacts to output_dir."""
        mkdirs(output_dir)
        paths: Dict[str, str] = {}
        for desc in self._descriptors.values():
            if desc.export_hook is not None:
                try:
                    out_path = desc.export_hook(dom, decision, violations, output_dir, plan)
                    if out_path:
                        paths[desc.key] = out_path
                except Exception as ex:
                    logger.warning("Artifact export hook failed for '%s': %s", desc.key, ex)
        return paths

    def load_artifacts(self, run_dir: str) -> Dict[str, Any]:
        """Executes registered loading hooks for artifacts present in run_dir."""
        loaded: Dict[str, Any] = {}
        for desc in self._descriptors.values():
            if desc.load_hook is not None:
                file_path = os.path.join(run_dir, desc.filename)
                if os.path.exists(file_path):
                    try:
                        loaded[desc.key] = desc.load_hook(file_path)
                    except Exception as ex:
                        logger.debug("Failed loading artifact '%s' from %s: %s", desc.key, file_path, ex)
        return loaded


default_artifact_registry = ArtifactRegistry()

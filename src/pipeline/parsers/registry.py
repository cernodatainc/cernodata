"""
src/pipeline/parsers/registry.py

Registry and lookup mechanism for extensible parser preset adapters.
"""

from __future__ import annotations

from typing import List, Optional

from src.dom import DocumentDOM
from src.pipeline.parsers.adapters import (
    DoclingPresetAdapter,
    ParserExecutionOptions,
    ParserPresetAdapter,
    PyPdfiumPresetAdapter,
)


class ParserPresetRegistry:
    """Maintains an ordered collection of preset adapters and resolves them by preset name."""

    def __init__(self, adapters: Optional[List[ParserPresetAdapter]] = None) -> None:
        self._adapters: List[ParserPresetAdapter] = list(adapters) if adapters is not None else []

    def register(self, adapter: ParserPresetAdapter, prepend: bool = False) -> None:
        """Registers a new preset adapter."""
        if prepend:
            self._adapters.insert(0, adapter)
        else:
            self._adapters.append(adapter)

    def load_custom_presets(self, config_path: Optional[str] = None) -> None:
        """No-op hook for loading user-defined custom preset manifests into this registry."""
        # TODO(TASK-204): Load `CustomPresetConfig` entries from JSON and register CLI (`TASK-202`)
        # and HTTP (`TASK-203`) OCR adapters ahead of `DoclingPresetAdapter`.
        _ = config_path

    def resolve(self, preset: str) -> Optional[ParserPresetAdapter]:
        """Finds the first registered adapter that can handle the given preset."""
        for adapter in self._adapters:
            if adapter.can_handle(preset):
                return adapter
        return None

    def execute(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        """Resolves adapter and executes parsing."""
        adapter = self.resolve(options.preset)
        if adapter is None:
            raise ValueError(f"No parser preset adapter registered for preset '{options.preset}'")
        return adapter.parse(resolved_path, options)

    @classmethod
    def create_default(cls) -> ParserPresetRegistry:
        """Creates a registry pre-configured with default standard adapters."""
        # TODO(TASK-402): Register `VisionLlmPresetAdapter` for `vision_llm_direct` via local Ollama VLM.
        return cls([
            PyPdfiumPresetAdapter(),
            DoclingPresetAdapter(),
        ])


_default_registry = ParserPresetRegistry.create_default()


def get_default_parser_registry() -> ParserPresetRegistry:
    """Returns the shared default parser registry instance."""
    return _default_registry

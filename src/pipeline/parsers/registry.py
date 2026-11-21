"""
src/pipeline/parsers/registry.py

Registry and lookup mechanism for extensible parser preset adapters.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from src.dom import DocumentDOM
from src.parsers.section_ocr import get_default_section_parser
from src.pipeline.parsers.adapters import (
    DoclingPresetAdapter,
    ParserExecutionOptions,
    ParserPresetAdapter,
    PyPdfiumPresetAdapter,
)
from src.pipeline.parsers.cli_adapter import SubprocessCliPresetAdapter
from src.pipeline.parsers.http_adapter import HttpPresetAdapter
from src.schemas.custom_preset import (
    CustomPresetConfig,
    PresetBackendType,
    get_community_preset_recipes,
    load_custom_presets_file,
)

logger = logging.getLogger("cernodata.pipeline.parsers.registry")
DEFAULT_CUSTOM_PRESETS_PATH = os.path.join("output", "custom_presets.json")


class ParserPresetRegistry:
    """Maintains an ordered collection of preset adapters and resolves them by preset name."""

    def __init__(self, adapters: Optional[List[ParserPresetAdapter]] = None) -> None:
        self._adapters: List[ParserPresetAdapter] = list(adapters) if adapters is not None else []
        self._custom_presets: Dict[str, CustomPresetConfig] = {}

    def register(self, adapter: ParserPresetAdapter, prepend: bool = False) -> None:
        """Registers a new preset adapter."""
        if prepend:
            self._adapters.insert(0, adapter)
        else:
            self._adapters.append(adapter)

    def get_custom_preset(self, preset_id: str) -> Optional[CustomPresetConfig]:
        """Returns the CustomPresetConfig registered for preset_id, if any."""
        return self._custom_presets.get(preset_id)

    def register_custom_preset(
        self,
        config: CustomPresetConfig,
        prepend: bool = True,
    ) -> Optional[ParserPresetAdapter]:
        """Registers a CustomPresetConfig as a parser adapter and SectionOCRParser engine."""
        adapter: Optional[ParserPresetAdapter] = None
        section_parser = get_default_section_parser()

        if config.backend_type == PresetBackendType.CLI_SUBPROCESS:
            adapter = SubprocessCliPresetAdapter(config)
            if config.command_template:
                cli_engine = section_parser._create_cli_subprocess_engine(
                    config.command_template,
                    timeout_sec=config.timeout_sec,
                    output_format=config.output_format,
                    wiggle_parameters=config.wiggle_parameters,
                )
                section_parser.register_engine(config.preset_id, cli_engine)
        elif config.backend_type == PresetBackendType.HTTP_ENDPOINT:
            adapter = HttpPresetAdapter(config)
            if config.endpoint_url:
                http_engine = section_parser._create_http_endpoint_engine(
                    config.endpoint_url,
                    timeout_sec=config.timeout_sec,
                    preset_id=config.preset_id,
                )
                section_parser.register_engine(config.preset_id, http_engine)
        else:
            logger.warning(
                "Custom preset '%s' uses unsupported backend_type '%s'; skipping registration.",
                config.preset_id,
                config.backend_type.value,
            )
            return None

        self._custom_presets[config.preset_id] = config
        self._adapters = [
            existing
            for existing in self._adapters
            if existing.preset_id != config.preset_id
        ]
        if prepend:
            self._adapters.insert(0, adapter)
        else:
            docling_idx = next(
                (i for i, existing in enumerate(self._adapters) if isinstance(existing, DoclingPresetAdapter)),
                len(self._adapters),
            )
            self._adapters.insert(docling_idx, adapter)
        return adapter

    def load_custom_presets(
        self,
        config_path: Optional[str] = None,
        include_community_recipes: bool = True,
    ) -> List[CustomPresetConfig]:
        """Loads community recipes and user-defined custom presets into this registry."""
        loaded_by_id: Dict[str, CustomPresetConfig] = {}
        if include_community_recipes:
            for recipe in get_community_preset_recipes():
                loaded_by_id[recipe.preset_id] = recipe

        target_path = config_path if config_path is not None else DEFAULT_CUSTOM_PRESETS_PATH
        for user_cfg in load_custom_presets_file(target_path):
            loaded_by_id[user_cfg.preset_id] = user_cfg

        registered: List[CustomPresetConfig] = []
        for cfg in loaded_by_id.values():
            if self.register_custom_preset(cfg, prepend=True) is not None:
                registered.append(cfg)
        return registered

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

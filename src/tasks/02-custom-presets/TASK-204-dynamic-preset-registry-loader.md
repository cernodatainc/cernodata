# TASK-204: Fix catch-all Docling adapter and load custom presets into registry

Depends on: TASK-201, TASK-202, TASK-203

In `src/pipeline/parsers/adapters.py:93`, `DoclingPresetAdapter.can_handle` returns `True` for every string. Because it sits in `ParserPresetRegistry.create_default()`, it swallows `vision_llm_direct` and any custom preset registered after it.

- Change `DoclingPresetAdapter.can_handle` in `src/pipeline/parsers/adapters.py` so it only matches Docling presets (`preset in {"docling_fast", "docling_deep"}` or `preset.startswith("docling_")`).
- Implement `ParserPresetRegistry.load_custom_presets` in `src/pipeline/parsers/registry.py` to read `CustomPresetConfig` definitions (`TASK-201`) from `output/custom_presets.json` (and community recipes from `TASK-208`) and register `SubprocessCliPresetAdapter` (`TASK-202`) or `HttpPresetAdapter` (`TASK-203`) instances.
- Add unit tests in `src/tests/test_custom_preset_registry.py`.

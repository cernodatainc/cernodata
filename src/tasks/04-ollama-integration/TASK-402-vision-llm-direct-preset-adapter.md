# TASK-402: `vision_llm_direct` preset adapter via Ollama VLM

Depends on: TASK-401

`PresetKind.VISION_LLM_DIRECT` (`src/dom/enums.py:29`) appears in the planner and UI dropdowns (`src/visualization/data_shape_config.html:151`), but there is no adapter for it in `src/pipeline/parsers/adapters.py`.

Create `src/pipeline/parsers/vision_llm_adapter.py` and register it in `ParserPresetRegistry.create_default()` (`src/pipeline/parsers/registry.py`):

- `can_handle(self, preset: str) -> bool` returns `preset == "vision_llm_direct"`.
- `parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM`:
  - Renders each page of `resolved_path` to a base64 PNG via `pypdfium2` (`src/parsers/pdf_utils.py`).
  - Sends the image to `OllamaClient.generate` using a vision model (e.g. `llava` or `minicpm-v`, configurable via `CERNODATA_VLM_MODEL`).
  - Converts the extracted blocks into `DOMNode` instances (`heading`, `paragraph`, `table_grid`).

Add unit tests in `src/tests/test_vision_llm_adapter.py`.

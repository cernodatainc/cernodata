# TASK-201: Custom preset manifest schema

Preset names are currently limited to `docling_fast`, `docling_deep`, `pypdfium_rapidocr`, and `vision_llm_direct` (`src/dom/enums.py`). Users with domain-specific documents often need to plug in their own OCR or layout tool (such as Tesseract with custom language packs, PaddleOCR for CJK tables, Kraken for historical handwriting, or an internal HTTP OCR service).

Create `src/schemas/custom_preset.py` with dataclasses for defining a custom preset:

- `PresetBackendType` (`Enum`): `"cli_subprocess"`, `"http_endpoint"`, `"python_callable"`.
- `ParameterWiggleSpec`: parameter name, default value, and fallback values to try during Path B parameter wiggling (`parsing_decision_tree.md` Section 5.1).
- `CustomPresetConfig`:
  - `preset_id: str`
  - `display_name: str`
  - `backend_type: PresetBackendType`
  - `command_template: Optional[list[str]]` (supports `{input_path}`, `{output_path}`, `{page_index}`)
  - `endpoint_url: Optional[str]`
  - `output_format: str` (`"text"`, `"markdown"`, `"hocr"`, `"cernodata_dom_json"`)
  - `hardware_weight: str` (`"light_cpu"`, `"heavy_cpu"`, `"gpu_vram"`)
  - `timeout_sec: int = 120`
  - `wiggle_parameters: list[ParameterWiggleSpec]`

Include `to_dict()` / `from_dict()` validation and unit tests in `src/tests/test_custom_preset_schema.py`.

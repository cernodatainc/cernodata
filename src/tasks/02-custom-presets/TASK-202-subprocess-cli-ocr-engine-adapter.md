# TASK-202: Subprocess OCR engine adapter

Many OCR tools are standalone binaries or scripts (`tesseract`, `ocrmypdf`, `marker_single`, `nougat`). We need a `ParserPresetAdapter` (`src/pipeline/parsers/adapters.py`) that runs an external command and turns its output into a `DocumentDOM`.

Create `src/pipeline/parsers/cli_adapter.py` with `SubprocessCliPresetAdapter`:

- `can_handle(self, preset: str) -> bool` returns `preset == self.preset_id`.
- `parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM`:
  - Substitutes `{input_path}` and `{output_path}` (in a temp directory) into `command_template`.
  - Runs `subprocess.run(..., shell=False, capture_output=True, text=True, timeout=self.timeout_sec)`.
  - Converts `"cernodata_dom_json"` output via `DocumentDOM.from_dict()`, `"markdown"` output by splitting headings (`#`) and tables (`|`) into `DOMNode` items, and `"text"` output by splitting double newlines into `paragraph` nodes.
- Also wire `_create_cli_subprocess_engine` in `src/parsers/section_ocr.py` so section cutouts in the viewer can use a configured CLI OCR tool.

Add unit tests in `src/tests/test_cli_preset_adapter.py` using `sys.executable -c` as a cross-platform mock binary.

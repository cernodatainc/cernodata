# TASK-206: Custom preset parameter wiggling in `FallbackLoopHandler`

Depends on: TASK-204, TASK-205

In `src/pipeline/fallback_handler.py:43`, `_resolve_wiggle_parameters` currently only changes `ocr_scale` (`3.5` or `4.0`) and `force_full_page_ocr = True`. Custom OCR engines have their own tunable parameters (for example, Tesseract `--psm` page segmentation modes `3`, `6`, `11`, or contrast/deskew flags) defined in `CustomPresetConfig.wiggle_parameters` (`TASK-201`).

- Update `_resolve_wiggle_parameters` and `handle_fallback` in `src/pipeline/fallback_handler.py` so that if the active preset defines `wiggle_parameters`, Path B (`PATH_B_WIGGLE_PARAMETERS`) retries with those fallback parameter values and records them in the attempt log.
- Pass wiggled parameter values through `ParserExecutionOptions` (`src/pipeline/parsers/adapters.py`) to `SubprocessCliPresetAdapter` and `HttpPresetAdapter`.
- Add unit tests in `src/tests/test_parameter_wiggling.py`.

# TASK-1002: Instant layout preview (boxes only, skip OCR) in Web Hub and Viewer

When inspecting a new PDF or setting up a layout template (`Goal 09`), waiting minutes for full text OCR just to see where the bounding boxes land is slow (`Architecture_Specification.md` Section 3.1). A structure-only pass can extract page bounding boxes in under a second.

- Implement `extract_layout_only_boxes` in `src/parsers/pdf_utils.py` (or `src/parsers/layout_only.py`) using `pypdfium2` to extract text/object bounding rectangles into a `DocumentDOM` without running OCR.
- Wire `_run_fast_layout_preview` in `src/pipeline/server/routes/execution.py` and expose `POST /api/layout_preview` in `src/pipeline/server/handler.py`.
- Add an `"Instant Layout Preview (Skip OCR)"` button in `src/visualization/landing.html` (next to `[RUN] Run Pipeline Directly`) and in `src/visualization/viewer/html/toolbar.html`.

Add unit tests in `src/tests/test_layout_only_pass.py`.

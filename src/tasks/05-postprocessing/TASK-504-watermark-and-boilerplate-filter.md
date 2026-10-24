# TASK-504: Watermark and boilerplate stamp filter

Depends on: TASK-501

Scanned and enterprise PDFs often have diagonal watermarks (`"DRAFT"`, `"CONFIDENTIAL"`, `"COPY"`, `"DO NOT DISTRIBUTE"`) or Bates numbering stamps injected on every page.

Create `src/pipeline/postprocessors/watermark_filter.py` implementing `WatermarkAndBoilerplateFilter`:

- Strip standalone short nodes that match known watermark/stamp tokens (`TASK-507`) or user-provided boilerplate strings.
- Detect short uppercase overlay boxes ($\le 5$ words) whose bounding boxes collide with body paragraphs.
- Log stripped nodes in `PostprocessActionRecord` without removing normal body sentences that happen to contain the word "confidential" or "draft".

Add unit tests in `src/tests/test_watermark_filter.py`.

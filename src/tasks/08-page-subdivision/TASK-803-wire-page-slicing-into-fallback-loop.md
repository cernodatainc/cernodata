# TASK-803: Wire page slicing into `FallbackLoopHandler`

Depends on: TASK-801, TASK-802

Connect `slice_pdf_pages` (`TASK-801`) and `DocumentDOM.merge_sliced_dom` (`TASK-802`) inside `FallbackLoopHandler` (`src/pipeline/fallback_handler.py`).

- Implement `_slice_failing_pages_if_needed` in `src/pipeline/fallback_handler.py`:
  - Identify which pages fell below `config.target_threshold` in `decision["per_page_confidence"]` or have active violations.
  - When only a subset of pages in a multi-page document failed, slice those pages into a temporary PDF (`slice_pdf_pages`), run the fallback preset on the slice, and merge the resulting nodes back into the master `DocumentDOM` (`merge_sliced_dom`) before re-evaluating document confidence.
- Record the list of sliced pages in the `attempts` log entry.

Add unit tests in `src/tests/test_fallback_page_slicing.py`.

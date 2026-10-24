# TASK-804: Re-parse single page with chosen preset in the viewer

Depends on: TASK-803

When reviewing a multi-page PDF in `/viewer`, a user might find that page 12 has a complex table or faint scan that `docling_fast` missed, while the other 49 pages look fine. Using the page slicer (`TASK-801`, `TASK-802`), they should be able to re-run just page 12 with `docling_deep` or `vision_llm_direct` from the viewer.

- Add `POST /api/reparse_page` in `src/pipeline/server/routes/execution.py` and `src/pipeline/server/handler.py` accepting `{"page_index": int, "preset": str}`:
  - Slices `page_index` from the active PDF, runs `preset`, merges the new nodes into the session's `DocumentDOM` (`merge_sliced_dom`), re-runs quality evaluation, and saves the updated artifacts.
- Add a `"Re-parse Page with..."` preset dropdown and button to `src/visualization/viewer/html/inspector.html` (`#pageActionTitle` bar).

Add route tests in `src/tests/test_reparse_page_route.py`.

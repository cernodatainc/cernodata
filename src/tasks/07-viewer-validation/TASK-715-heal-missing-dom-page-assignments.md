# TASK-715: Heal missing or defaulted page assignments in DOM nodes

When validating or loading a run, `dom.nodes` may sometimes lack explicit `global_page_index` values or have all nodes defaulted to page `1` (especially in legacy or partially exported runs for multi-page documents).

While a run with a mismatched `total_pages` (e.g. a 6-page document with a 2-page run) is strictly invalid and dropped, the case where `global_page_index` is `1` or missing across DOM nodes is a special case that could potentially be healed rather than discarded.

- Design a non-intrusive UX for surfacing and confirming healed page assignments so the user is not interrupted or annoyed by repetitive prompts during normal browsing.
- Investigate heuristic or layout-based recovery (e.g. matching node text/bounding boxes against rendered PDF pages or re-running lightweight page-index attribution) when `global_page_index` is missing or collapsed to `1` on a multi-page document.
- Integrate optional healing into `load_validated_run_artifacts` (`src/schemas/artifacts.py`) or a dedicated repair pass in `src/pipeline/server/` once a clean UX is established.

Add unit tests in `src/tests/test_dom_page_healing.py` covering multi-page DOMs with missing or collapsed page assignments.

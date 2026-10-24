# TASK-107: Web UI output test builder and Q&A sandbox

Depends on: TASK-102, TASK-103, TASK-106

Expose the structural assertions (`TASK-102`), table checks (`TASK-103`), and retrieval Q&A checks (`TASK-106`) in the Web Hub (`src/visualization/landing.html`) so users can define output tests visually without editing JSON files.

- In `src/visualization/landing.html` (and `src/visualization/landing/execution.js`), add an "Output Expectations & Test Questions" card with:
  - A dropdown to load a starter domain template (`TASK-108`).
  - Inputs for required section headers and minimum table column counts.
  - A simple list where the user can add test questions (e.g. `"What is the total invoice amount?"`) and expected answer text (`"$1,450.00"`).
- Wire `_run_visual_test_suite_check` in `src/pipeline/server/routes/execution.py` so these checks run during pipeline execution.
- Implement `renderOutputTestSuiteResultsCard` in `src/visualization/landing/results.js` to show pass/fail badges for each rule and question in the results tab.

Add route tests in `src/tests/test_ui_test_suite_routes.py`.

# TASK-606: Web UI topic distribution chart and balance controls

Depends on: TASK-602, TASK-603, TASK-604

Show the detected topic distribution and balance choices in the Data Shape & Pipeline Planner (`src/visualization/data_shape_config.html`) and Web Hub (`src/visualization/landing.html`).

- Implement `renderCorpusBalanceQuestionnaireCard` in `src/visualization/data_shape/ui.js` (and `src/visualization/data_shape_config.html`):
  - Display horizontal proportion bars for each detected topic (`doc_count` and character share) along with any near-duplicate count warnings (`TASK-605`).
  - When `is_heavily_skewed` is true, highlight the question asking whether the skew is intentional and let the user click one of the three `CorpusBalanceIntent` cards (`Keep as-is`, `Balance topics equally`, or `Deduplicate and cap dominant topics`).
- Add `GET /api/corpus/balance` and `POST /api/corpus/balance` in `src/pipeline/server/routes/planning.py`.

Add route tests in `src/tests/test_corpus_routes.py`.

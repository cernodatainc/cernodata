# TASK-306: Web Hub downstream recommendation and export card

Depends on: TASK-304, TASK-305

Display the recommendation from `DownstreamAdvisor` (`TASK-305`) in the Web Hub's results view (`src/visualization/landing.html` under `#secResults`) and connect it to one-click downloads and watched-folder forwarding (`TASK-304`).

- Implement `renderDownstreamRecommendationAndConnectorCard` in `src/visualization/landing/results.js`:
  - Show the recommended export format, chunk size, and external tool suggestions based on the parsed document's structure.
  - Show any hygiene warnings with a link to inspect flagged pages in `/viewer`.
  - Provide buttons to download or forward `Clean Markdown`, `RAG Chunks (.jsonl)`, or `Fine-Tuning Dataset (.jsonl)`.
- Add `GET /api/export` in `src/pipeline/server/routes/persistence.py` and `src/pipeline/server/handler.py` to serve the requested export format.

Add unit tests in `src/tests/test_export_routes.py`.

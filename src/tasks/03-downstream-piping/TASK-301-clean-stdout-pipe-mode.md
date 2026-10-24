# TASK-301: Visual downstream connection wizard in the Web Hub

Users who already have a knowledge base or AI workspace set up (such as an Obsidian vault folder, an AnythingLLM watched folder, or a local web service) need a panel in the Web Hub (`src/visualization/landing.html`) to send CernoData's parsed outputs directly to that destination without using terminal commands.

- Add a "Connect Output to Pre-Existing Setup" section in `src/visualization/landing.html` (and `src/visualization/landing/results.js`) with:
  - A selector for destination type: Watched Local Folder, Local App Webhook URL, or Browser Download.
  - A selector for output format: Clean Markdown, RAG Chunks (`.jsonl`), Fine-Tuning Dataset (`.jsonl`), or Full DOM (`.json`).
  - A "Test Connection" button and an "Auto-forward when parsing finishes" checkbox.
- Implement `_handle_visual_downstream_connector` in `src/pipeline/server/routes/persistence.py` and expose `POST /api/connect_output` in `src/pipeline/server/handler.py`.

Add unit tests in `src/tests/test_visual_downstream_connector.py`.

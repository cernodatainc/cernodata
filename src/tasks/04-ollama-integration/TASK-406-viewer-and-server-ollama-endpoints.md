# TASK-406: Viewer and Hub Ollama UI controls and endpoints

Depends on: TASK-402, TASK-403, TASK-404, TASK-405

Connect the Ollama backend modules (`TASK-402` through `TASK-405`) to the Web Hub (`src/visualization/landing.html`) and Interactive Viewer (`src/visualization/viewer/`).

- Implement `_get_ollama_models_status` in `src/pipeline/server/routes/config.py` using `OllamaClient` (`TASK-401`).
- Add `POST /api/ollama/repair_node`, `POST /api/ollama/enrich`, and `POST /api/ollama/suggest_tests` in `src/pipeline/server/routes/ocr.py` (or a dedicated `ollama.py` route mixin) and register them in `src/pipeline/server/handler.py`.
- In `src/visualization/viewer/js/inspector_components.js` (`renderCutoutPreviewCardComponent`), add a "Repair Text with Local AI" button next to `[OCR] Parse Section with OCR`.
- In `src/visualization/landing.html`, show a status badge indicating whether local Ollama is online and a dropdown to pick an installed model for enrichment or test generation.

Add route tests in `src/tests/test_ollama_routes.py`.

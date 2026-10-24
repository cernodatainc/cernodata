# TASK-401: Standard-library Ollama HTTP client

Several parts of the pipeline need to talk to a local Ollama server (`vision_llm_direct` fallback parsing, post-OCR text repair, test question generation, and document summary enrichment).

Create `src/pipeline/ollama_client.py` using only Python's standard library (`urllib.request`, `urllib.error`, `json`):

- `OllamaClient(base_url: str = "http://localhost:11434", timeout_sec: int = 60)` (checking `CERNODATA_OLLAMA_URL` first).
- `is_available() -> bool`: fast GET to `/api/tags` (2s timeout) returning `False` on connection failure without raising.
- `list_models() -> list[str]`: returns installed model names from `/api/tags`.
- `generate(model: str, prompt: str, system: Optional[str] = None, images_base64: Optional[list[str]] = None, format_json: bool = False) -> str`: calls `POST /api/generate` with `stream=False`.

Add unit tests in `src/tests/test_ollama_client.py` with mocked `urllib.request.urlopen` calls.

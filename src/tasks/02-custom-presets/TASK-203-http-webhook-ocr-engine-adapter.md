# TASK-203: HTTP OCR engine adapter

Users frequently run OCR or layout models inside Docker containers or on another machine over HTTP (for example, a PaddleOCR server, Stirling-PDF, or Apache Tika).

Create `src/pipeline/parsers/http_adapter.py` implementing `HttpPresetAdapter`:

- Uses `urllib.request` from the standard library (no extra dependencies) to POST `{"filename": ..., "pdf_base64": ..., "preset": ...}` to `endpoint_url` with `timeout_sec`.
- Accepts either a full `DocumentDOM` JSON response (`"nodes"` list) or a simpler `{"pages": [{"page_index": 1, "text": "..."}]}` / `{"text": "..."}` response and builds `DOMNode` instances.
- Wire `_create_http_endpoint_engine` in `src/parsers/section_ocr.py` so single-box cutouts in the viewer can also call an HTTP OCR endpoint.

Add unit tests in `src/tests/test_http_preset_adapter.py`.

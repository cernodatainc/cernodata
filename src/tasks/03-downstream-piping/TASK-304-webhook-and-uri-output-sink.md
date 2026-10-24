# TASK-304: Watched folder and webhook output delivery

Depends on: TASK-301, TASK-302, TASK-303

When a user configures a watched folder or webhook URL in the Web Hub (`TASK-301`), the backend needs to format the `DocumentDOM` (`TASK-302`, `TASK-303`) and write or POST it to that destination.

Create `src/pipeline/exporters/output_sink.py` and hook it into `deliver_artifacts_to_sink` in `src/pipeline/artifact_exporter.py`:

- `deliver_to_sink(payload: str, content_type: str, target_uri: str, filename_stem: str = "document", timeout_sec: int = 30) -> dict[str, Any]`:
  - For `http://` or `https://` URLs, POST `payload.encode("utf-8")` with `urllib.request.urlopen` and return the HTTP status.
  - For local folder paths or `file://` URIs, write the formatted file (`<filename_stem>.md` or `<filename_stem>.jsonl`) into the destination directory.
- Return status details so the Web Hub UI can show a confirmation banner when the file is delivered.

Add unit tests in `src/tests/test_output_sink.py`.

# TASK-714: Single served application viewer and removal of per-run viewer.html generation

Depends on: TASK-712

Every pipeline execution currently calls `export_interactive_html_viewer` in `src/pipeline/artifact_exporter.py`, writing a monolithic `interactive_viewer.html` into each output directory (`output_dir/interactive_viewer.html`). This file inlines base64-encoded page images, full CSS stylesheets, and bundled JavaScript runtimes alongside raw JSON payloads.

Embedding the entire viewer runtime into every parsed output directory wastes disk space (often 5MB to 20MB per document), degrades batch processing throughput, pollutes git and artifact storage, and freezes obsolete viewer code into past runs. Since `cernodata` already includes an interactive server hub (`src/pipeline/server/`), the single served viewer application should dynamically inspect any run output on demand.

- Remove automatic generation of `interactive_viewer.html` from `export_and_package` in `src/pipeline/artifact_pipeline.py` and deprecate `export_interactive_html_viewer` in `src/pipeline/artifact_exporter.py`.
- Ensure output directories store only clean structured data: `dom.json`, `quality_violations.json`, `plan_execution_result.json`, and rendered overlay image files (`page_*.png`).
- Provide an optional CLI flag `--standalone-html` only for explicit single-file air-gapped export when requested by the user.
- Enhance server endpoints in `src/pipeline/server/routes.py`:
  - Route `/viewer?run=<run_id_or_path>` serves the unified Vite/Preact viewer app.
  - Endpoint `/api/viewer-dataset` accepts an optional `run_dir` parameter and returns the corresponding parsed DOM, quality violations, and page metadata as JSON.
  - Serve page raster images directly via `/api/runs/<run_id>/pages/<page_num>.png` instead of base64 inlining in HTML.
- Update the CLI `--view` (`-v`) flag in `src/main.py` to open `http://127.0.0.1:<port>/viewer?run=<output_dir>` in the default browser rather than opening a local `file://` HTML path.

Update unit tests in `src/tests/test_artifact_pipeline.py` and `src/tests/test_server_routes.py`.

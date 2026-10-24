# TASK-1001: Export reproducible pipeline script from the Web UI

Once a user tunes presets, thresholds, and cleanup steps in the Web Hub (`src/visualization/landing.html`) or Planner (`src/visualization/data_shape_config.html`), `Architecture_Specification.md` Section 8 and `data_storage_decision_tree.md` Section 4 specify a way to export a self-contained, human-readable Python script (`run_custom_pipeline.py`) that reproduces that exact setup for sharing or security auditing.

- Create `src/pipeline/script_exporter.py` with `generate_standalone_script(config: IngestionConfig, decision: Optional[dict[str, Any]] = None) -> str` and wire it into `export_standalone_runner_script` (`src/pipeline/artifact_exporter.py`) and `_handle_export_reproducible_package` (`src/pipeline/server/routes/persistence.py`).
- Embed the active preset, threshold, language, and any winning per-page fallback preset overrides into a standalone, type-annotated Python script.
- Add a `"Download Reproducible Pipeline"` button in `src/visualization/landing.html` (`#secResults`) and `src/visualization/data_shape_config.html`.

Add unit tests in `src/tests/test_script_exporter.py` verifying that the generated script parses cleanly via `ast.parse()`.

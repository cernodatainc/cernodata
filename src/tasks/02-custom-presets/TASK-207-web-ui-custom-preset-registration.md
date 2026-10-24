# TASK-207: Web UI custom OCR preset builder and recipe loader

Depends on: TASK-204, TASK-205

Users should be able to connect a custom OCR tool or load a community recipe directly from the browser in `src/visualization/landing.html` and `src/visualization/data_shape_config.html`.

- Implement `_get_custom_presets_catalog` in `src/pipeline/server/routes/config.py`, plus `POST /api/presets` (to save a `CustomPresetConfig` to `output/custom_presets.json` and register it) and `POST /api/presets/test` (to verify that the command or URL is reachable).
- Implement `initCustomPresetBuilderModal` in `src/visualization/landing/navigation.js` and add an "Add / Connect Custom OCR Preset" modal to `src/visualization/landing.html`:
  - Dropdown to pre-fill settings from the community recipes in `TASK-208`.
  - Inputs for preset name, local command or service URL, hardware type, and a "Test Connection" button.
  - Dynamically append saved custom presets to `#inpPreset` (`landing.html`) and `#overrideSelect` (`data_shape_config.html`).

Add route tests in `src/tests/test_preset_routes.py`.

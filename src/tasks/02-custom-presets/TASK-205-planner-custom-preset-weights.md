# TASK-205: Include custom presets in `PresetPlanner` scoring

Depends on: TASK-201

`PresetPlanner` (`src/pipeline/planner/planner.py`) currently scores only the hardcoded dictionary in `DEFAULT_PRESET_WEIGHTS` (`src/pipeline/planner/options.py`). When a user adds a custom preset, it needs to participate in planner scoring and appear in the suggested preset hierarchy.

- Update `PresetPlanner.__init__` in `src/pipeline/planner/planner.py` (at the `TODO(TASK-205)` comment) to accept or merge suitability weights from `CustomPresetConfig` entries.
- Map `CustomPresetConfig.hardware_weight` (`"light_cpu"`, `"heavy_cpu"`, `"gpu_vram"`) and target taxonomy hints into default weight values when explicit per-dimension weights are not provided.
- Add unit tests in `src/tests/test_planner_custom_presets.py`.

# TASK-1004: Calibrate `PresetPlanner` using observed run timings

Depends on: TASK-1003

`PresetPlanner` (`src/pipeline/planner/planner.py`) currently uses static weights from `DEFAULT_PRESET_WEIGHTS` regardless of how fast or slow each preset actually runs on the user's machine. Recording observed seconds-per-page from completed runs lets the planner adjust its speed/latency scoring to match the actual hardware.

- Create `src/pipeline/planner/calibration.py` to record and load an exponential moving average of `sec_per_page` per preset in `output/hardware_calibration.json`.
- Wire `_apply_hardware_calibration` in `src/pipeline/planner/planner.py` (`TODO(TASK-1004)`) to adjust speed/latency suitability scores when calibration data exists.

Add unit tests in `src/tests/test_planner_calibration.py`.

# TASK-710: In-viewer violation sensitivity and acceptance threshold tuner

Quality violations and page confidence scores are evaluated using static thresholds set at pipeline launch. In documents with tight typographic layouts, dense multi-column tables, or specialized terminology, default rules often raise false-positive violations (such as high box overlap or dictionary spellcheck flags). Today users must manually suppress violations one-by-one or modify source code.

- Add a "Rule Tolerances" button and sliding configuration drawer to `src/visualization/viewer/html/toolbar.html`.
- Add interactive controls for runtime sensitivity tuning:
  - Bounding box intersection-over-union (IoU) overlap tolerance slider (default 0.05).
  - OCR confidence and dictionary spellcheck threshold sliders.
  - Table grid minimum cell count and row alignment tolerance.
- In `src/visualization/viewer/js/state.js`, extend `recalculateScoring()` to accept dynamic tolerance weights, re-evaluate active violations in `violationsData`, and update page and overall confidence scores without re-running the extraction preset.
- Add an endpoint `POST /api/save_tolerances` to persist tuned document tolerance profiles to `output_dir/rule_tolerances.json`.

# TASK-902: Template misapplication detector

Depends on: TASK-901

If a user accidentally picks an "Invoice" template for a narrative contract, forcing invoice zones onto the page will ruin the parse (`data_storage_decision_tree.md` Section 3.2). We need a check that detects when a template doesn't fit the document so the pipeline can detach it and fall back to normal layout detection.

Create `src/quality/template_validator.py` and wire it into `_check_template_misapplication_violations` in `src/quality/violations.py`:

- Map each `TemplateZoneSpec.normalized_bbox` onto page coordinates (`612 x 792` default or page bounds).
- Check whether required zones contain at least one non-empty `DOMNode` matching `expected_node_type` and `expected_regex` (if set).
- If the fraction of failed required zones exceeds `template.max_empty_zone_failure_rate`, emit a violation (`rule_type="template_misapplication"`, `severity="HIGH"`) so the pipeline detaches the template.

Add unit tests in `src/tests/test_template_validator.py`.

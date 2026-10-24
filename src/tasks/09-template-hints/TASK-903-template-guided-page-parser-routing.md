# TASK-903: Apply template zones and add Web Hub template selector

Depends on: TASK-901, TASK-902

Connect `DocumentTemplateHint` (`TASK-901`) and `validate_template_application` (`TASK-902`) to the pipeline and Web Hub (`src/visualization/landing.html`).

- Create `src/pipeline/template_applier.py` with `apply_template_hint(dom: DocumentDOM, template: DocumentTemplateHint) -> DocumentDOM`:
  - Matches `DOMNode` bounding boxes against `template.zones`.
  - Sets `node.type = zone.expected_node_type`, `node.template_hint_applied = template.template_id`, and `node.content["template_zone_id"] = zone.zone_id`.
  - Drops nodes that fall inside `"ignore"` zones.
  - If `validate_template_application` (`TASK-902`) reports `template_misapplication`, revert the template changes and return the original `DocumentDOM` with a notice in the decision log.
- Implement `_get_template_hints_catalog` in `src/pipeline/server/routes/config.py` and add a "Document Layout Template (Optional)" dropdown in `src/visualization/landing.html`.

Add unit tests in `src/tests/test_template_applier.py`.

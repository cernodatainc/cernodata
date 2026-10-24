# TASK-901: Document template hint schema

`DOMNode` (`src/dom/node.py:20`) already has `template_hint_applied: Optional[str] = None` for standardized document layouts (`Architecture_Specification.md` Section 5.3, `data_storage_decision_tree.md` Section 3), such as invoices, tax forms, or patent front pages where specific page regions always hold the same type of content.

Create `src/schemas/template_hint.py`:

- `TemplateZoneSpec`:
  - `zone_id: str`
  - `normalized_bbox: tuple[float, float, float, float]` (`x0, y0, x1, y1` in `[0.0, 1.0]` relative to page width and height)
  - `expected_node_type: str` (`"heading"`, `"paragraph"`, `"table_grid"`, `"figure"`, `"header_footer"`, or `"ignore"`)
  - `preferred_preset: Optional[str] = None`
  - `required: bool = True`
  - `expected_regex: Optional[str] = None`
- `DocumentTemplateHint`:
  - `template_id: str`
  - `description: str`
  - `applies_to_pages: str` (`"first"`, `"all"`, `"last"`)
  - `zones: list[TemplateZoneSpec]`
  - `max_empty_zone_failure_rate: float = 0.25`

Include `to_dict()` / `from_dict()` serialization, coordinate bounds checking (`0.0 <= x0 < x1 <= 1.0`), and unit tests in `src/tests/test_template_hint_schema.py`.

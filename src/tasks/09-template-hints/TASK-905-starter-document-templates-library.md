# TASK-905: Starter document layout templates

Many recurring documents share standard spatial layouts: invoices (vendor top-left, invoice metadata top-right, line-item table in the middle, totals bottom-right), two-column academic title pages, patent front pages, and engineering drawing title blocks.

Create `src/schemas/examples/template_hints/` with 4 JSON files using normalized `[0.0, 1.0]` page coordinates (`x0, y0, x1, y1`) and a short `README.md`:

1. `standard_commercial_invoice.json`: vendor header zone, invoice metadata zone, line-item `table_grid` zone, totals `table_grid` zone, and remittance stub `ignore` zone.
2. `academic_two_column_first_page.json`: full-width title/author `heading` zone, `Abstract` zone, left/right column body zones, and bottom footnote zone.
3. `patent_front_page.json`: bibliographic code header zones, abstract zone, and representative drawing `figure` zone.
4. `engineering_blueprint_title_block.json`: main drawing `figure` zone and bottom-right title/revision `table_grid` zone.

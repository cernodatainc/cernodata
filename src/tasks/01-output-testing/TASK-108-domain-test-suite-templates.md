# TASK-108: Domain test suite templates

People working with legal contracts, invoices, academic papers, or medical/lab reports know what sections and tables a valid document in their field must have. Having starter templates lets users pick a document type in the UI instead of writing rules from scratch.

Create `src/schemas/examples/assertion_templates/` with 5 JSON templates and a short `README.md`:

1. `academic_paper.json`: expects headings like `Abstract`, `Introduction`, `Methods`/`Methodology`, and `References`, plus caption checks.
2. `financial_report_or_invoice.json`: expects invoice/balance sheet headers, currency patterns, and a table with at least 2 columns and a numeric amount column.
3. `legal_contract.json`: expects `Definitions`, `Governing Law`, and signature blocks, plus numbered clause patterns.
4. `technical_datasheet.json`: expects parameter/specification tables and unit patterns.
5. `government_or_regulatory_filing.json`: expects form identifiers, statutory references, and disclosure headers.

Each JSON file should include `"description"` notes explaining what each rule checks and stay under 180 lines.

# Assertion templates (TASK-108)

Starter `DocumentAssertionSuite` files (see `src/schemas/test_suite.py`) for common document types.
Pick the closest template, copy it, and adjust the rules to your documents.

| File | Document type |
| --- | --- |
| `academic_paper.json` | Research papers: IMRaD sections, captions, citations |
| `financial_report_or_invoice.json` | Invoices and financial statements: currency amounts, totals, amounts table |
| `legal_contract.json` | Contracts: definitions, governing law, numbered clauses, signatures |
| `technical_datasheet.json` | Datasheets: specification tables with units |
| `government_or_regulatory_filing.json` | Filings and forms: form IDs, statutory references, disclosures |

## Notes

- `description` keys document each rule for readers; the loader ignores them.
- Header rules match by substring search, case-insensitive by default. Regex rules are case-sensitive
  unless the pattern starts with `(?i)`.
- Table rules apply to every table in the document, so templates keep them to shape checks
  (`min_columns`, `min_rows`). Add `expected_column_headers` or `numeric_column_indices` only when all
  tables in your documents share that layout.
- `src/tests/test_assertion_templates.py` loads every template, so a broken regex or unknown node type fails the test suite.

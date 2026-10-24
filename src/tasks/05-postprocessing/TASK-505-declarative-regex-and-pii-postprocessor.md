# TASK-505: Regex replacement and PII redaction postprocessor

Depends on: TASK-501

Before exporting documents to shared knowledge bases or cloud tools, users often want to redact personal contact details (emails, phone numbers, national ID / IBAN numbers) or strip recurring internal document codes.

Create `src/pipeline/postprocessors/regex_scrubber.py` implementing `DeclarativeRegexPostprocessor`:

- Accept a list of rules: `{"name": str, "pattern": str, "action": "replace" | "drop_node", "replacement": str, "target_node_types": Optional[list[str]]}`.
- Provide built-in toggles for `redact_emails`, `redact_phones`, and `redact_iban_ssn`.
- Validate regex patterns on initialization and record all replacements/drops in `PostprocessActionRecord`.

Add unit tests in `src/tests/test_regex_scrubber.py`.

# TASK-507: Corporate letterhead, watermark, and boilerplate pattern catalog

Documents from different fields (legal, finance, healthcare, manufacturing, government) use recurring layouts and phrases for letterheads, page footers, Bates stamps, and ISO document control blocks. Having a well-tested pattern catalog makes the letterhead and watermark strippers (`TASK-502`, `TASK-504`) work out of the box.

Create `src/schemas/examples/postprocessing_rules/` with:

1. `default_strip_patterns.json` grouped into:
   - `page_numbering_patterns`: `"Page X of Y"`, `"Strona X z Y"`, `"Seite X von Y"`, `"- 12 -"`, Bates numbers.
   - `company_letterhead_indicators`: registration/tax IDs (`VAT`, `NIP`, `KRS`, `HRB`, `EIN`), street/postal footer lines, and ISO document control header markers (`Doc ID:`, `Rev:`, `Effective Date:`).
   - `watermark_stamps`: `"CONFIDENTIAL"`, `"DRAFT"`, `"INTERNAL USE ONLY"`, `"UNCONTROLLED COPY"`.
   - `disclaimer_footers`: standard email/document confidentiality footers.
   Include both `should_match` and `should_not_match` test strings for every pattern so we don't accidentally strip real body paragraphs.
2. `README.md` explaining how to add and test new patterns.

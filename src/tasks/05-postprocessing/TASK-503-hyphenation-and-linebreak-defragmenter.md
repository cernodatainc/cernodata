# TASK-503: Hyphenation and line-break defragmenter

Depends on: TASK-501

PDF extraction often leaves words split by end-of-line hyphens (`"docu-\nment"` or soft hyphens `\u00ad`), leaves Unicode ligatures (`\ufb01` for `"fi"`), or splits a sentence across two consecutive `paragraph` nodes at a column or page boundary.

Create `src/pipeline/postprocessors/text_defragmenter.py` implementing `TextDefragmenterPostprocessor`:

- Replace Unicode ligatures (`\ufb00`-`\ufb04`) and strip soft hyphens (`\u00ad`).
- Rejoin end-of-line hyphenated words (`r"([a-z])-\s*\n\s*([a-z])"` -> `r"\1\2"`) in `paragraph` nodes without altering `table_grid` Markdown syntax or intentional compound words.
- Optionally merge two consecutive `paragraph` nodes when the first ends mid-sentence (no terminal punctuation `.?!:;`) and the next starts with a lowercase letter.

Add unit tests in `src/tests/test_text_defragmenter.py`.

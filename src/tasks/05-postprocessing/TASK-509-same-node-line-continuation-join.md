# TASK-509: Join line continuations inside a single DOM node

Depends on: TASK-503

When a line continuation falls inside one DOM node, the extracted text keeps the break markers and the word comes out fragmented. For example `"sth st- -h sth"` or `"sth st-\nh sth"` must become `"sth sth sth"`, not `"sth st-h sth"` or `"sth st- h sth"`.

- In `src/pipeline/postprocessors/text_defragmenter.py` (TASK-503), add a rule that finds a trailing head (`word-`, `word...`) followed by whitespace or a newline and a tail (`-tail`, `...tail`, or a lowercase fragment) in the middle of a node's text, and joins them into a single word with the markers removed.
- Do not touch intentional compounds and ranges (`"well-known"`, `"2019-2020"`, `"A - B"`), standalone dashes, or `table_grid` Markdown syntax. Only join when the head ends a line or is followed by a tail that starts with the same marker.
- Record each join in the node `content` (for example `joined_continuations`) so the viewer can show and undo it, and write the corrected text to `raw_text` so quality checks no longer see the fragments.
- Apply the same rule to text the viewer produces after OCR re-parse of a section.

Add unit tests in `src/tests/test_text_defragmenter.py` for: hyphen join, ellipsis join, newline-separated join, preserved compounds and ranges, and unchanged tables.

# TASK-508: Detect line continuations across DOM nodes and merge them

Depends on: TASK-503

The symbols quality layer treats a line continuation fragment as valid text: a leading tail (`-th`, `-h`, `...sth`) at the start of a node, or a trailing head (`st-`, `sth...`) at the end of a node. When the head and tail fall on different DOM nodes (column break, page break, or an OCR line split into two boxes), they remain two separate nodes and downstream output keeps the dangling fragments.

- Extend `src/pipeline/postprocessors/text_defragmenter.py` (TASK-503) with continuation detection across nodes:
  - A node whose text ends with a trailing head (`word-`, `word...`) is paired with the next node in reading order (same page, or first node of the next page) whose text starts with a leading tail (`-tail`, `...tail`, or a lowercase continuation).
  - Merge the pair into one node: concatenate text with the hyphen or ellipsis marker removed (`"docu-"` + `"-ment"` -> `"document"`), union the bounding boxes per page (keep `merged_from` audit data as `merge_dom_nodes` does), and keep the earlier node id.
  - Skip pairs where either node is not a text type (`table_grid`, `figure`), or where the nodes are not adjacent in reading order.
- Mirror the detection in the viewer: highlight detected continuation pairs in the DOM list and offer a one-click "Merge continuation" action that reuses the existing merge flow and undo history (TASK-703).
- Detected pairs that the user rejects are remembered per node so they are not suggested again.

Add unit tests in `src/tests/test_text_defragmenter.py` for: matching pair on one page, pair across a page boundary, non-adjacent nodes, table and figure nodes, and a rejected pair.

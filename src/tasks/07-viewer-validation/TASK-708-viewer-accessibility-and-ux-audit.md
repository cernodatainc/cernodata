# TASK-708: Viewer accessibility, color palette, and keyboard workflow spec

People reviewing dozens of document pages in `/viewer` run into small UI friction points that add up quickly: red/green bounding box borders that look identical to colorblind users, small click targets on resize handles, and too much back-and-forth mouse movement between the canvas and right-hand inspector.

Create `docs/viewer_ux_and_shortcuts_spec.md` (under 180 lines) covering:

1. A colorblind-safe palette (hex codes + distinct border dash patterns) for the `DOMNodeType` overlays (`heading`, `paragraph`, `table_grid`, `figure`, `header_footer`, `multi_column_group`) and violation states in `src/visualization/viewer/viewer.css`.
2. A conflict-free keyboard shortcut map for page switching, zooming, jumping between flagged nodes, changing node types (`1`-`6`), splitting (`s`), merging (`m`), approving (`v`), and undo/redo.
3. A step-by-step walkthrough of repairing a sample 10-page document (fixing a merged heading, a broken table, and a repeating header) in as few clicks/keystrokes as possible.

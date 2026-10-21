# TASK-702: Split merged nodes in the viewer

The viewer supports merging two boxes (`decollide.js`) and deleting a box (`deleteDOMNode`), but parsers just as often make the opposite mistake: fusing a section heading and the paragraph below it into a single `DOMNode`. Right now the user has to delete the box and redraw two new ones by hand.

- Implement `DOMNode.split_at_offset` in `src/dom/node.py` to split a node's text and vertical bounding box (`y0`..`y_mid` and `y_mid`..`y1`) into two nodes.
- Create `src/visualization/viewer/js/node_split.js` (and register it in `src/visualization/viewer/scripts.py`) with `splitSelectedDOMNode(nodeId)`:
  - Splits `node.content.raw_text` at the current cursor position (`selectionStart`) in `.note-area` (or at the first newline if no cursor offset is active) and divides `node.bounding_box` vertically in proportion to the text split.
- Add a `[SPLIT] Split at Cursor` button in `renderSingleNodeEditorComponent` (`src/visualization/viewer/js/inspector_components.js` at the `TODO(TASK-702)` marker).

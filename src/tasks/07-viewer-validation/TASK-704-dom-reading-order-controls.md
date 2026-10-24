# TASK-704: DOM reading-order badges and reordering controls

In two-column layouts or pages with sidebars, a parser can get every bounding box right while sorting `dom.nodes` in the wrong reading order (reading across columns left-to-right instead of down column 1 then column 2). Downstream Markdown and RAG exporters iterate `dom.nodes` in array order, so users need to see and fix the reading order in `/viewer`.

- Show a small sequence number badge (`#1`, `#2`, `#3`...) on each SVG bounding box in `src/visualization/viewer/js/overlay.js` and on each card in `renderDOMTree` (`src/visualization/viewer/js/inspector.js`).
- Add `Move Up` and `Move Down` buttons to the single-node inspector and DOM tree cards to swap a node with the previous/next node on the same page.
- Add a `"Sort Page Reading Order (Top-to-Bottom / Columns)"` button to the page action bar in `src/visualization/viewer/html/inspector.html`.

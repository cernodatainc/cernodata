# TASK-713: Preact component integration for interactive viewer

Depends on: TASK-712

The viewer interface currently relies on imperative vanilla JavaScript DOM manipulation across multiple loosely coupled files (`inspector_components.js`, `table_editor.js`, `overlay.js`, `violations_components.js`, `controls.js`). As features expand (undo/redo stacks, table grid editing, visual diff overlays, node reordering, live markdown preview), manual DOM mutation becomes brittle and prone to state desynchronization.

Integrating Preact provides a lightweight (~3KB) reactive component model with fast virtual DOM updates and TypeScript support, while maintaining zero heavy runtime bloat.

- Add `preact` and `@preact/signals` to `src/visualization/viewer/package.json`.
- Implement centralized reactive state in `src/visualization/viewer/src/state/viewerState.ts` using Preact signals:
  - Track `activePage`, `selectedNodeId`, `hoveredNodeId`, `domData`, `violations`, `activeLayers`, `zoomLevel`, and `editHistory`.
- Refactor the UI into modular, typed Preact components:
  - `ViewerApp.tsx`: Top-level application shell with responsive layout, toolbar, zoom controls, and keyboard shortcut dispatcher.
  - `CanvasOverlay.tsx`: Interactive SVG/HTML canvas overlay rendering bounding boxes, reading-order badges, and violation markers with sub-pixel alignment.
  - `InspectorDrawer.tsx`: Tabbed panel hosting DOM tree view, violation review checklist, live output preview, and layout template hints.
  - `TableGridEditor.tsx`: Reactive spreadsheet-style grid for tabular nodes with cell editing, row/column addition and deletion, and markdown table serialization.
  - `ViolationPanel.tsx`: Filterable violation cards with jump-to-bounding-box navigation and one-click correction apply.
- Ensure bidirectional state sync: modifying nodes or accepting violation corrections in Preact components immediately updates the canvas overlay and marks the document session dirty for export.

Add component unit tests with Vitest in `src/visualization/viewer/tests/`.

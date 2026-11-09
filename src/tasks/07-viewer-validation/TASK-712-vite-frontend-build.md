# TASK-712: ViteJS-based frontend build for the visual viewer

The current viewer in `src/visualization/viewer/` relies on Python string concatenation (`src/visualization/viewer/scripts.py`, `src/visualization/bundler.py`) and regex template interpolation to assemble HTML, CSS, and JavaScript. This couples frontend asset packaging directly to the Python interpreter, blocks standard frontend tooling (TypeScript, package managers, modern module bundlers, tree-shaking, minification), and prevents modern Hot Module Replacement (HMR) during UI development.

- Create standard frontend package structure in `src/visualization/viewer/`:
  - `package.json` with dev dependencies (`vite`, `typescript`).
  - `vite.config.ts`: configure asset build targeting `src/visualization/viewer/dist/`.
  - `tsconfig.json`: strict TypeScript settings.
  - `index.html`: standard Vite HTML entrypoint loading `/src/main.ts`.
- Refactor script modules in `src/visualization/viewer/js/` into standard ES modules (`import`/`export`) instead of relying on global window mutations and manual file concatenation order in `JS_MODULE_ORDER`.
- Replace inline Python template injection (`window.VIEWER_DATA = ...`) with client-side dynamic data fetching against `/api/viewer-dataset` via modern typed fetch wrapper.
- Configure development proxy in `vite.config.ts` to forward `/api` and `/runs` requests to the Python server at `127.0.0.1:8000`.
- Update `src/pipeline/server/routes_static.py` to serve pre-built Vite assets from `src/visualization/viewer/dist/` in production.

Add unit tests in `src/tests/test_viewer_routes.py` to verify static asset delivery from the compiled bundle directory.

# TASK-1301: User-defined file groups in the Web Hub Explorer

Currently, documents in the Web Hub Explorer are grouped automatically by their parent directory (`derive_file_set` in `src/pipeline/server/run_mapping_helpers.py`). Users should be able to create their own named groups and organize files into those groups regardless of where the files live on disk.

- Extend persistent storage (`src/pipeline/server/run_mappings.py`) and schema models (`src/schemas/`) to store user-defined groups (`group_id`, `name`, `description`, member `file_paths`).
- Add server API routes (e.g. `GET/POST /api/groups`, `POST /api/groups/assign`, `POST /api/groups/remove`) using `api_router` in `src/pipeline/server/routes/`.
- Update `get_file_run_mappings` (`src/pipeline/server/run_mappings.py`) to include user-created groups alongside directory-derived file sets.
- Add UI controls in the Web Hub Explorer (`src/visualization/landing.html`, `src/visualization/landing/explorer.js`, `src/visualization/landing/context_menu.js`) to create, rename, and delete groups, and to move or assign files into groups.

Add unit and route tests in `src/tests/test_file_groups.py`.

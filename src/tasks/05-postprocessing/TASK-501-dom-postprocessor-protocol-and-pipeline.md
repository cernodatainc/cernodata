# TASK-501: DOM postprocessor interface and chain runner

After layout extraction and fallback retries finish, users often need to strip or clean up structural noise (repeating company letterheads, running headers/footers, watermarks, broken hyphenation, or contact info) before exporting.

Create `src/pipeline/postprocessors/__init__.py` and `src/pipeline/postprocessors/base.py`, and wire them into `run_postprocessing_steps` in `src/pipeline/pipeline_steps.py`:

- `PostprocessActionRecord` (dataclass): `step_name`, `action` (`"stripped_node"`, `"modified_text"`, `"merged_nodes"`), `node_id`, `page_index`, `reason`, and `original_node_dict` (so the viewer can preview or restore stripped nodes).
- `DOMPostprocessor` (`Protocol`): `name: str` and `process(self, dom: DocumentDOM) -> tuple[DocumentDOM, list[PostprocessActionRecord]]`.
- `PostprocessorChain`: runs a list of `DOMPostprocessor` steps in order and records the action history.

Add unit tests in `src/tests/test_postprocessor_chain.py`.

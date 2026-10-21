# TASK-802: DOM page reassembler (`merge_sliced_dom`)

`DOMNode` (`src/dom/node.py:16-17`) already has `global_page_index` and `temp_slice_index` fields for page-level fallback slicing (`Architecture_Specification.md` Section 4.1), and `DocumentDOM` (`src/dom/document.py:147`) has the `merge_sliced_dom` no-op stub.

Implement `DocumentDOM.merge_sliced_dom(self, sliced_dom: DocumentDOM, slice_to_global_map: Optional[dict[int, int]] = None) -> DocumentDOM` in `src/dom/document.py`:

- For each node in `sliced_dom.nodes`:
  - Record its slice-local page number in `node.temp_slice_index`.
  - Map `node.global_page_index` back to the original document page number using `slice_to_global_map` (e.g. `{1: 42}`).
  - Update `node.node_id` so it doesn't collide with existing IDs in `self.nodes`.
- Replace all nodes on the target `global_page_index` pages in `self.nodes` with the newly parsed nodes while keeping all other pages untouched and preserving page order.

Add unit tests in `src/tests/test_dom_reassembler.py`.

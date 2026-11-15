# TASK-510: Default-on uncovered region image detector

Primary parsers and OCR engines can miss visually distinct content regions on rendered pages (for example, low-contrast stamps, margin notes, sparse callouts, or tables/boxes skipped by layout detection). These missed areas leave gaps with clear contrast variation and foreground ink density that are not covered by any `DOMNode`.

Implement `UncoveredRegionPostprocessor` (`name = "uncovered_region_detector"`) in `src/pipeline/postprocessors/uncovered_region_detector.py` adhering to `DOMPostprocessor` (`TASK-501`), enabled by default in `run_postprocessing_steps`:

- Render (or inspect supplied) page images and mask out all existing `DOMNode` bounding boxes and extreme border margins.
- Detect contiguous uncovered regions exhibiting contrast variation (`contrast_std >= threshold`) and foreground ink density within bounds (`min_ink_density <= ink_density <= max_ink_density`), rejecting regions overlapping existing nodes beyond `max_overlap_ratio` or below minimum dimensions.
- Crop each detected region and run targeted OCR via `SectionOCRParser` (`parse_image`). If OCR extracts text, insert a new `DOMNode` containing the text and confidence; if OCR returns empty text, insert a flagged placeholder `DOMNode` (`is_incorrect_text=True`) carrying an `"uncovered_visual_region"` warning violation for viewer review.
- Track node provenance (`DOMNodeOrigin`: `"parsed"`, `"postprocessed"`, `"manual"`) via `DOMNode.origin` and `content["origin"]`, record an `"added_node"` `PostprocessActionRecord` in `dom.metadata["postprocess_actions"]`, and surface provenance badges in the interactive viewer.

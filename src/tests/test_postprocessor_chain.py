"""
src/tests/test_postprocessor_chain.py

Unit tests for TASK-501 (DOMPostprocessor, PostprocessActionRecord, PostprocessorChain),
TASK-510 (default-on UncoveredRegionPostprocessor), pipeline integration, and node provenance.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from src.dom import BoundingBox, DOMNode, DOMNodeOrigin, DOMNodeType, DocumentDOM
from src.parsers.section_ocr import SectionOCRParser
from src.pipeline.attempt_runner import AttemptRunner
from src.pipeline.pipeline_steps import run_postprocessing_steps
from src.pipeline.planner.models import IngestionConfig
from src.pipeline.postprocessors import (
    DOMPostprocessor,
    PostprocessActionRecord,
    PostprocessorChain,
    UncoveredRegionPostprocessor,
    detect_uncovered_regions_on_page,
)
from src.quality.violations import detect_quality_violations
from src.schemas.dom import DOMNodeSchema
from src.visualization.viewer.scripts import get_viewer_js


class _DummyStripperStep:
    """Test postprocessor stripping nodes matching a prefix."""

    name: str = "dummy_stripper"

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def process(self, dom: DocumentDOM) -> Tuple[DocumentDOM, List[PostprocessActionRecord]]:
        records: List[PostprocessActionRecord] = []
        kept: List[DOMNode] = []
        for node in dom.nodes:
            if node.text.startswith(self.prefix):
                records.append(
                    PostprocessActionRecord(
                        step_name=self.name,
                        action="stripped_node",
                        node_id=node.node_id,
                        page_index=node.global_page_index,
                        reason=f"Matched strip prefix '{self.prefix}'",
                        original_node_dict=node.to_dict(),
                    )
                )
            else:
                kept.append(node)
        dom.nodes = kept
        return dom, records


class _DummyTextNormalizerStep:
    """Test postprocessor normalizing whitespace across nodes."""

    name: str = "dummy_normalizer"

    def process(self, dom: DocumentDOM) -> Tuple[DocumentDOM, List[PostprocessActionRecord]]:
        records: List[PostprocessActionRecord] = []
        for node in dom.nodes:
            raw = str(node.content.get("raw_text", ""))
            cleaned = " ".join(raw.split())
            if cleaned != raw:
                orig = node.to_dict()
                node.content["raw_text"] = cleaned
                records.append(
                    PostprocessActionRecord(
                        step_name=self.name,
                        action="modified_text",
                        node_id=node.node_id,
                        page_index=node.global_page_index,
                        reason="Normalized repeated whitespace",
                        original_node_dict=orig,
                    )
                )
        return dom, records


def _draw_synthetic_ink_block(
    canvas: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> None:
    """Draws simulated dark horizontal text strokes inside a bounding rectangle."""
    for row in range(y0 + 3, y1 - 3, 6):
        canvas[row : row + 3, x0 + 4 : x1 - 4] = 20


def test_postprocess_action_record_roundtrip() -> None:
    record = PostprocessActionRecord(
        step_name="letterhead_stripper",
        action="stripped_node",
        node_id="node_p1_0",
        page_index=1,
        reason="Repeating header",
        original_node_dict={"node_id": "node_p1_0", "type": "header_footer"},
    )
    payload = record.to_dict()
    rebuilt = PostprocessActionRecord.from_dict(payload)
    assert rebuilt == record


def test_postprocessor_chain_protocol_and_audit_history() -> None:
    stripper = _DummyStripperStep("CONFIDENTIAL")
    normalizer = _DummyTextNormalizerStep()
    assert isinstance(stripper, DOMPostprocessor)
    assert isinstance(normalizer, DOMPostprocessor)

    dom = DocumentDOM(
        document_id="doc_chain",
        source_filename="chain.pdf",
        total_pages=1,
        nodes=[
            DOMNode(
                node_id="n1",
                type=DOMNodeType.HEADER_FOOTER.value,
                global_page_index=1,
                temp_slice_index=1,
                bounding_box=BoundingBox(50, 20, 200, 40),
                content={"raw_text": "CONFIDENTIAL HEADER"},
            ),
            DOMNode(
                node_id="n2",
                type=DOMNodeType.PARAGRAPH.value,
                global_page_index=1,
                temp_slice_index=1,
                bounding_box=BoundingBox(50, 100, 300, 140),
                content={"raw_text": "Hello   world"},
            ),
        ],
    )

    chain = PostprocessorChain([stripper])
    chain.add_step(normalizer)
    out_dom, actions = chain.run(dom)

    assert [n.node_id for n in out_dom.nodes] == ["n2"]
    assert out_dom.nodes[0].content["raw_text"] == "Hello world"
    assert len(actions) == 2
    assert actions[0].action == "stripped_node"
    assert actions[0].original_node_dict is not None
    assert actions[1].action == "modified_text"
    assert len(chain.history) == 2
    assert len(out_dom.metadata["postprocess_actions"]) == 2


def test_uncovered_region_detector_recovers_missed_region_with_ocr() -> None:
    canvas = np.full((792, 612, 3), 255, dtype=np.uint8)
    _draw_synthetic_ink_block(canvas, 60, 80, 260, 130)
    _draw_synthetic_ink_block(canvas, 80, 320, 340, 380)

    covered_node = DOMNode(
        node_id="node_p1_0",
        type=DOMNodeType.PARAGRAPH.value,
        global_page_index=1,
        temp_slice_index=1,
        bounding_box=BoundingBox(60, 80, 260, 130),
        content={"raw_text": "Primary parser paragraph."},
    )
    dom = DocumentDOM(
        document_id="doc_uncovered",
        source_filename="nonexistent.pdf",
        total_pages=1,
        nodes=[covered_node],
    )

    detected = detect_uncovered_regions_on_page(
        canvas,
        [covered_node.bounding_box],
        page_width_pt=612.0,
        page_height_pt=792.0,
    )
    assert len(detected) == 1
    assert detected[0].bounding_box.y0 >= 300.0
    assert detected[0].contrast_std >= 18.0

    def mock_engine(_arr: np.ndarray) -> List[Tuple[List[List[int]], str, float]]:
        return [([[0, 0], [100, 0], [100, 20], [0, 20]], "Recovered margin note", 0.91)]

    ocr_parser = SectionOCRParser(engine=mock_engine)
    step = UncoveredRegionPostprocessor(
        page_images={1: (canvas, 612.0, 792.0)},
        ocr_parser=ocr_parser,
    )

    chain = PostprocessorChain([step])
    processed_dom, records = chain.run(dom)

    assert len(processed_dom.nodes) == 2
    added = [n for n in processed_dom.nodes if n.node_id != "node_p1_0"][0]
    assert added.origin == DOMNodeOrigin.POSTPROCESSED.value
    assert added.content["origin"] == DOMNodeOrigin.POSTPROCESSED.value
    assert added.content["raw_text"] == "Recovered margin note"
    assert added.ocr_confidence == 0.91
    assert covered_node.origin is None
    assert len(records) == 1
    assert records[0].action == "added_node"
    assert records[0].step_name == "uncovered_region_detector"


def test_uncovered_region_detector_flags_placeholder_when_ocr_empty() -> None:
    canvas = np.full((792, 612, 3), 255, dtype=np.uint8)
    _draw_synthetic_ink_block(canvas, 100, 240, 280, 300)

    dom = DocumentDOM(
        document_id="doc_placeholder",
        source_filename="nonexistent.pdf",
        total_pages=1,
        nodes=[],
    )

    def empty_ocr_engine(_arr: np.ndarray) -> List[object]:
        return []

    ocr_parser = SectionOCRParser(engine=empty_ocr_engine)
    config = IngestionConfig(
        options={
            "uncovered_page_images": {1: (canvas, 612.0, 792.0)},
            "uncovered_ocr_parser": ocr_parser,
        }
    )

    processed_dom = run_postprocessing_steps(dom, config=config)
    assert len(processed_dom.nodes) == 1
    placeholder = processed_dom.nodes[0]
    assert placeholder.origin == DOMNodeOrigin.POSTPROCESSED.value
    assert placeholder.content["raw_text"] == ""
    assert placeholder.is_incorrect_text is True
    assert any(v.get("rule_type") == "uncovered_visual_region" for v in placeholder.violations)

    viols = detect_quality_violations(processed_dom, language="en")
    assert any(v.get("rule_type") == "uncovered_visual_region" for v in placeholder.violations)
    assert any(v.get("rule_type") == "uncovered_visual_region" for v in viols)


def test_run_postprocessing_steps_disabled_and_attempt_runner_wiring() -> None:
    canvas = np.full((792, 612, 3), 255, dtype=np.uint8)
    _draw_synthetic_ink_block(canvas, 90, 200, 290, 250)

    def mock_engine(_arr: np.ndarray) -> List[Tuple[List[List[int]], str, float]]:
        return [([[0, 0], [50, 0], [50, 15], [0, 15]], "Default-on hit", 0.88)]

    ocr_parser = SectionOCRParser(engine=mock_engine)

    def fake_parse(pdf_path: str, config: IngestionConfig) -> DocumentDOM:
        return DocumentDOM(document_id="d1", source_filename=pdf_path, total_pages=1, nodes=[])

    def fake_align(dom: DocumentDOM, pdf_path: str, align_skew: bool) -> DocumentDOM:
        return dom

    enabled_cfg = IngestionConfig(
        options={
            "uncovered_page_images": {1: (canvas, 612.0, 792.0)},
            "uncovered_ocr_parser": ocr_parser,
        }
    )
    runner = AttemptRunner(parse_fn=fake_parse, align_fn=fake_align)
    dom_out, _decision, _viols = runner.execute_attempt("dummy.pdf", enabled_cfg, 0.9, 0.8)
    assert len(dom_out.nodes) == 1
    assert dom_out.nodes[0].origin == DOMNodeOrigin.POSTPROCESSED.value
    assert dom_out.nodes[0].content["raw_text"] == "Default-on hit"

    disabled_cfg = IngestionConfig(
        options={
            "enable_postprocessing": False,
            "uncovered_page_images": {1: (canvas, 612.0, 792.0)},
            "uncovered_ocr_parser": ocr_parser,
        }
    )
    dom_disabled, _, _ = runner.execute_attempt("dummy.pdf", disabled_cfg, 0.9, 0.8)
    assert len(dom_disabled.nodes) == 0


def test_node_provenance_serialization_and_viewer_badges() -> None:
    node = DOMNode(
        node_id="n_post",
        type=DOMNodeType.PARAGRAPH.value,
        global_page_index=1,
        temp_slice_index=1,
        bounding_box=BoundingBox(10, 10, 100, 30),
        content={"raw_text": "Added snippet", "origin": DOMNodeOrigin.POSTPROCESSED.value},
        origin=DOMNodeOrigin.POSTPROCESSED.value,
    )
    as_dict = node.to_dict()
    assert as_dict["origin"] == "postprocessed"
    schema = DOMNodeSchema.model_validate(as_dict)
    assert schema.origin == "postprocessed"
    rebuilt = DOMNode.from_dict(as_dict)
    assert rebuilt.origin == "postprocessed"
    assert rebuilt.clone().origin == "postprocessed"

    js_bundle = get_viewer_js()
    assert "getNodeProvenanceBadgeHtml" in js_bundle
    assert "data-origin" in js_bundle
    assert "origin: 'manual'" in js_bundle
    assert "Postprocessed" in js_bundle
    assert "Original parse" in js_bundle

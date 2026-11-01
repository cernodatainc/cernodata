"""
src/tests/conftest.py

Shared test fixtures, DOM builders, pipeline I/O patchers, and ephemeral HTTP server helpers.
"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import ExitStack, contextmanager
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple
from unittest.mock import patch

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.pipeline.server import PipelineViewerHandler, PipelineViewerServer


def make_test_node(
    raw_text: str = "Sample text",
    node_id: str = "n1",
    node_type: str = "paragraph",
    page: int = 1,
    bbox: Optional[BoundingBox] = None,
    extra_content: Optional[Dict[str, Any]] = None,
) -> DOMNode:
    """Constructs a DOMNode with sensible defaults for unit testing."""
    content: Dict[str, Any] = {"raw_text": raw_text}
    if extra_content:
        content.update(extra_content)
    return DOMNode(
        node_id=node_id,
        type=node_type,
        global_page_index=page,
        temp_slice_index=page,
        bounding_box=bbox or BoundingBox(10.0, 10.0, 100.0, 50.0),
        content=content,
    )


def make_test_dom(
    raw_text: str = "Sample text",
    nodes: Optional[List[DOMNode]] = None,
    document_id: str = "doc_test",
    source_filename: str = "sample.pdf",
    total_pages: int = 1,
    node_id: str = "n1",
    node_type: str = "paragraph",
) -> DocumentDOM:
    """Constructs a DocumentDOM with either provided nodes or a single default text node."""
    resolved_nodes = nodes if nodes is not None else [
        make_test_node(raw_text=raw_text, node_id=node_id, node_type=node_type)
    ]
    return DocumentDOM(
        document_id=document_id,
        source_filename=source_filename,
        total_pages=total_pages,
        nodes=resolved_nodes,
    )


def make_test_page_nodes(
    page: int,
    texts: Sequence[str],
    prefix: str = "node",
    node_type: str = "paragraph",
) -> List[DOMNode]:
    """Generates a list of DOMNode elements for a specific page with sequential IDs and distinct bboxes."""
    nodes: List[DOMNode] = []
    for i, txt in enumerate(texts, 1):
        y_pos = float(i * 30.0)
        bbox = BoundingBox(10.0, y_pos, 200.0, y_pos + 20.0)
        nodes.append(
            make_test_node(
                raw_text=txt,
                node_id=f"{prefix}_p{page}_{i}",
                node_type=node_type,
                page=page,
                bbox=bbox,
            )
        )
    return nodes


def make_multipage_dom(
    page_texts: Mapping[int, Sequence[str]],
    document_id: str = "doc_multi",
    source_filename: str = "sample.pdf",
) -> DocumentDOM:
    """Constructs a multi-page DocumentDOM from a mapping of page index to text strings."""
    nodes: List[DOMNode] = []
    for page, texts in sorted(page_texts.items()):
        nodes.extend(make_test_page_nodes(page=page, texts=texts))
    total_pages = max(page_texts.keys(), default=1)
    return DocumentDOM(
        document_id=document_id,
        source_filename=source_filename,
        total_pages=total_pages,
        nodes=nodes,
    )


@contextmanager
def patch_pipeline_io(
    parse_return: Any = None,
    parse_side_effect: Any = None,
    eval_side_effect: Any = None,
) -> Iterator[None]:
    """Patches document parsing, skew alignment, and artifact rendering/exporting for pipeline unit tests."""
    with ExitStack() as stack:
        if parse_side_effect is not None:
            stack.enter_context(patch("src.pipeline.attempt_runner.parse_document", side_effect=parse_side_effect))
        else:
            stack.enter_context(patch("src.pipeline.attempt_runner.parse_document", return_value=parse_return))
        stack.enter_context(patch("src.pipeline.attempt_runner.align_document_skew", side_effect=lambda d, p, a: d))
        if eval_side_effect is not None:
            stack.enter_context(
                patch("src.pipeline.attempt_runner.evaluate_quality_and_decision_tree", side_effect=eval_side_effect)
            )
        stack.enter_context(patch("src.pipeline.artifact_pipeline.render_visual_overlays", return_value=[]))
        stack.enter_context(
            patch("src.pipeline.artifact_pipeline.export_pipeline_artifacts", return_value=("a.json", "b.json", "c.json"))
        )
        stack.enter_context(
            patch("src.pipeline.artifact_pipeline.export_interactive_html_viewer", return_value="viewer.html")
        )
        yield


def http_get(url: str, timeout: int = 5) -> Tuple[int, str, Dict[str, str]]:
    """Executes an HTTP GET request and returns (status_code, body_text, headers_dict)."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8"), dict(response.getheaders())
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8") if e.fp else ""
        return e.code, content, dict(e.headers)


def http_post_json(url: str, data: Dict[str, Any], timeout: int = 5) -> Tuple[int, Dict[str, Any]]:
    """Executes an HTTP POST request with a JSON payload and returns (status_code, parsed_json_dict)."""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_body = response.read().decode("utf-8")
            return response.status, (json.loads(res_body) if res_body else {})
    except urllib.error.HTTPError as e:
        res_body = e.read().decode("utf-8") if e.fp else "{}"
        return e.code, (json.loads(res_body) if res_body else {})


@contextmanager
def running_test_server(
    port: int = 0,
    session_context: Any = None,
    **server_attrs: Any,
) -> Iterator[Tuple[PipelineViewerServer, str]]:
    """Starts an ephemeral PipelineViewerServer on a background daemon thread and yields (server, base_url)."""
    server = PipelineViewerServer(("127.0.0.1", port), PipelineViewerHandler, session_context=session_context)
    for k, v in server_attrs.items():
        setattr(server, k, v)
    assigned_port = server.server_port
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{assigned_port}"
    finally:
        server.shutdown()
        server.server_close()


class EphemeralServerTestCase(unittest.TestCase):
    """Base test case managing an ephemeral PipelineViewerServer lifecycle on a daemon thread."""

    server: PipelineViewerServer
    server_thread: threading.Thread
    port: int
    base_url: str
    session_context: Optional[Any] = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = PipelineViewerServer(
            ("127.0.0.1", 0), PipelineViewerHandler, session_context=cls.session_context
        )
        cls.port = cls.server.server_port
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(
            target=lambda: cls.server.serve_forever(poll_interval=0.05), daemon=True
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

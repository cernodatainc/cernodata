"""
src/pipeline/server/http_utils.py

Low-level HTTP transport utilities, response writers, payload deserializers,
and static template file loaders for the cernodata web server.
"""

from __future__ import annotations

import json
import logging
import os
from http.server import SimpleHTTPRequestHandler
from typing import Any, Dict, Sequence, Union

logger = logging.getLogger("cernodata.server.http_utils")

SRC_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_ROOT: str = os.path.dirname(SRC_DIR)


def send_response_bytes(
    handler: SimpleHTTPRequestHandler,
    body: bytes,
    content_type: str,
    status_code: int = 200,
) -> bool:
    """
    Sends raw byte payload with Content-Type and Content-Length headers.

    Catches normal client socket disconnects (BrokenPipeError, ConnectionResetError)
    without raising uncaught exceptions in server workers.

    Args:
        handler: Active HTTP request handler instance.
        body: Encoded binary response body.
        content_type: MIME type header string.
        status_code: HTTP response status code.

    Returns:
        True if the response was sent or client disconnected safely.
    """
    try:
        handler.send_response(status_code)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected before response could be sent: %s", e)
        return True


def send_json_response(handler: SimpleHTTPRequestHandler, status_code: int, payload: Any) -> None:
    """
    Serializes payload into JSON and writes HTTP response.

    Args:
        handler: Active HTTP request handler instance.
        status_code: HTTP response status code.
        payload: JSON-serializable Python object.
    """
    body = json.dumps(payload).encode("utf-8")
    send_response_bytes(handler, body, content_type="application/json; charset=utf-8", status_code=status_code)


def read_json_payload(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    """
    Reads and deserializes JSON request body from HTTP request stream.

    Args:
        handler: Active HTTP request handler instance with open rfile.

    Returns:
        Parsed dictionary if body is valid JSON, or empty dictionary on failure.
    """
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except (ValueError, TypeError):
        return {}

    if content_length <= 0:
        return {}

    try:
        body = handler.rfile.read(content_length).decode("utf-8")
        parsed = json.loads(body) if body else {}
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Malformed JSON request payload received: %s", e)
        return {}
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected while reading request payload: %s", e)
        return {}


def send_text_response(
    handler: SimpleHTTPRequestHandler,
    content: Union[str, bytes],
    content_type: str = "text/html; charset=utf-8",
    status_code: int = 200,
) -> None:
    """
    Sends UTF-8 text, script, or stylesheet response with specified Content-Type.

    Args:
        handler: Active HTTP request handler instance.
        content: String or pre-encoded bytes.
        content_type: MIME type string.
        status_code: HTTP response status code.
    """
    body = content.encode("utf-8") if isinstance(content, str) else content
    send_response_bytes(handler, body, content_type=content_type, status_code=status_code)


def send_html_response(handler: SimpleHTTPRequestHandler, content: Union[str, bytes], status_code: int = 200) -> None:
    """
    Sends HTML response with Content-Type 'text/html; charset=utf-8'.

    Args:
        handler: Active HTTP request handler instance.
        content: HTML string or pre-encoded bytes.
        status_code: HTTP response status code.
    """
    send_text_response(handler, content, content_type="text/html; charset=utf-8", status_code=status_code)


def send_file_response(
    handler: SimpleHTTPRequestHandler,
    file_path: str,
    content_type: str,
    status_code: int = 200,
) -> bool:
    """
    Streams file contents to HTTP response with specified Content-Type.

    Args:
        handler: Active HTTP request handler instance.
        file_path: Path to existing file on disk.
        content_type: MIME type string.
        status_code: HTTP response status code.

    Returns:
        True if file exists and was written, False otherwise.
    """
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return send_response_bytes(handler, content, content_type=content_type, status_code=status_code)
    except OSError as e:
        logger.warning("Error reading file %s: %s", file_path, e)
        return False


def send_first_existing_file(
    handler: SimpleHTTPRequestHandler,
    candidate_paths: Sequence[str],
    content_type: str,
    status_code: int = 200,
) -> bool:
    """
    Sends the first accessible file among candidate paths.

    Args:
        handler: Active HTTP request handler instance.
        candidate_paths: Sequence of file paths in evaluation order.
        content_type: MIME type string.
        status_code: HTTP response status code.

    Returns:
        True if an existing file was sent, False if none were found.
    """
    for path in candidate_paths:
        if path and send_file_response(handler, path, content_type=content_type, status_code=status_code):
            return True
    return False


def copy_file_if_exists(src_path: str, dst_path: str) -> bool:
    """
    Copies binary file from src_path to dst_path if src_path exists on disk.

    Args:
        src_path: Path to source file.
        dst_path: Target destination path.

    Returns:
        True if file was copied, False otherwise.
    """
    if not os.path.exists(src_path):
        return False
    try:
        with open(src_path, "rb") as f_in:
            data = f_in.read()
        with open(dst_path, "wb") as f_out:
            f_out.write(data)
        return True
    except OSError as e:
        logger.warning("Could not copy asset from %s to %s: %s", src_path, dst_path, e)
        return False


def read_html_template(filename: str, fallback_title: str = "cernodata") -> str:
    """
    Reads HTML template file from src/visualization or returns fallback placeholder.

    Args:
        filename: Template filename in src/visualization.
        fallback_title: Document title to use if template is missing.

    Returns:
        HTML template text content.
    """
    src_path = os.path.join(SRC_DIR, "visualization", filename)
    if os.path.exists(src_path):
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            logger.warning("Could not read template %s: %s", src_path, e)
    return f"<html><body><h1>{fallback_title}</h1><p>Template missing.</p></body></html>"

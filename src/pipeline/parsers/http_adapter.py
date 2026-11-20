"""
src/pipeline/parsers/http_adapter.py

Parser preset adapter sending PDF payloads to remote or containerized HTTP OCR endpoints.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Mapping, Optional, Union

from src.dom import DOMNode, DocumentDOM
from src.pipeline.parsers.adapters import ParserExecutionOptions
from src.pipeline.parsers.custom_output import (
    convert_dom_dict_to_dom,
    convert_markdown_to_nodes,
    convert_plain_text_to_nodes,
)
from src.schemas.custom_preset import CustomPresetConfig, PresetBackendType
from src.utils import generate_document_id

logger = logging.getLogger("cernodata.pipeline.parsers.http_adapter")


class HttpPresetAdapter:
    """Adapter invoking an HTTP OCR or layout extraction service via urllib.request."""

    def __init__(
        self,
        config: Union[CustomPresetConfig, str],
        endpoint_url: Optional[str] = None,
        timeout_sec: int = 120,
        output_format: str = "text",
    ) -> None:
        if isinstance(config, CustomPresetConfig):
            if config.backend_type != PresetBackendType.HTTP_ENDPOINT:
                raise ValueError(
                    f"HttpPresetAdapter requires http_endpoint backend, got '{config.backend_type.value}'."
                )
            if not config.endpoint_url:
                raise ValueError(f"Custom preset '{config.preset_id}' is missing endpoint_url.")
            self.config = config
            self.preset_id = config.preset_id
            self.endpoint_url = config.endpoint_url
            self.timeout_sec = config.timeout_sec
            self.output_format = config.output_format
        else:
            if not endpoint_url:
                raise ValueError("endpoint_url is required when constructing HttpPresetAdapter by ID.")
            self.preset_id = str(config).strip()
            self.endpoint_url = str(endpoint_url).strip()
            self.timeout_sec = int(timeout_sec)
            self.output_format = output_format
            self.config = CustomPresetConfig(
                preset_id=self.preset_id,
                display_name=self.preset_id,
                backend_type=PresetBackendType.HTTP_ENDPOINT,
                endpoint_url=self.endpoint_url,
                timeout_sec=self.timeout_sec,
                output_format=self.output_format,
            )

    def can_handle(self, preset: str) -> bool:
        """Returns True only when the requested preset matches this adapter's preset_id."""
        return preset == self.preset_id

    def _build_request_payload(
        self,
        resolved_path: str,
        options: ParserExecutionOptions,
    ) -> Dict[str, Any]:
        with open(resolved_path, "rb") as fp:
            pdf_bytes = fp.read()
        payload: Dict[str, Any] = {
            "filename": os.path.basename(resolved_path),
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
            "preset": self.preset_id,
            "language": options.language or "en",
        }
        if options.extra_parameters:
            payload["parameters"] = dict(options.extra_parameters)
            for k, v in options.extra_parameters.items():
                payload.setdefault(str(k), v)
        return payload

    def _response_to_dom(
        self,
        response_data: Mapping[str, Any],
        resolved_path: str,
    ) -> DocumentDOM:
        if "nodes" in response_data and isinstance(response_data["nodes"], list):
            return convert_dom_dict_to_dom(
                response_data,
                resolved_path=resolved_path,
                preset_id=self.preset_id,
            )

        nodes: List[DOMNode] = []
        if "pages" in response_data and isinstance(response_data["pages"], list):
            for idx, page_entry in enumerate(response_data["pages"], start=1):
                if isinstance(page_entry, Mapping):
                    page_num = int(page_entry.get("page_index") or page_entry.get("page") or idx)
                    page_text = str(page_entry.get("text") or "")
                else:
                    page_num = idx
                    page_text = str(page_entry)
                if self.output_format == "markdown":
                    nodes.extend(
                        convert_markdown_to_nodes(page_text, page_index=page_num, preset_id=self.preset_id)
                    )
                else:
                    nodes.extend(
                        convert_plain_text_to_nodes(page_text, page_index=page_num, preset_id=self.preset_id)
                    )
        elif "text" in response_data:
            raw_text = str(response_data.get("text") or "")
            if self.output_format == "markdown":
                nodes = convert_markdown_to_nodes(raw_text, page_index=1, preset_id=self.preset_id)
            else:
                nodes = convert_plain_text_to_nodes(raw_text, page_index=1, preset_id=self.preset_id)
        else:
            raise ValueError(
                f"HTTP OCR preset '{self.preset_id}' returned unsupported JSON response keys: "
                f"{list(response_data.keys())}"
            )

        total_pages = max((n.global_page_index for n in nodes), default=1)
        return DocumentDOM(
            document_id=generate_document_id(resolved_path),
            source_filename=os.path.basename(resolved_path),
            total_pages=total_pages,
            nodes=nodes,
            metadata={"preset": self.preset_id, "endpoint_url": self.endpoint_url},
        )

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        """POSTs PDF payload as JSON to endpoint_url and builds a DocumentDOM from the JSON reply."""
        payload = self._build_request_payload(resolved_path, options)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        logger.info("Posting document '%s' to HTTP OCR preset '%s' (%s)", resolved_path, self.preset_id, self.endpoint_url)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw_body = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                f"HTTP OCR preset '{self.preset_id}' request to '{self.endpoint_url}' failed: {exc}"
            ) from exc

        try:
            decoded = json.loads(raw_body) if raw_body.strip() else {}
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"HTTP OCR preset '{self.preset_id}' returned invalid JSON from '{self.endpoint_url}': {exc}"
            ) from exc

        if not isinstance(decoded, Mapping):
            raise RuntimeError(
                f"HTTP OCR preset '{self.preset_id}' expected JSON object response."
            )
        return self._response_to_dom(decoded, resolved_path=resolved_path)


__all__ = ["HttpPresetAdapter"]

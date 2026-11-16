"""
src/schemas/custom_preset.py

Schema definitions, validation, and persistence helpers for user-defined
and community custom OCR/parsing presets.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.utils import save_json

logger = logging.getLogger("cernodata.schemas.custom_preset")

VALID_OUTPUT_FORMATS: frozenset[str] = frozenset({
    "text",
    "markdown",
    "hocr",
    "cernodata_dom_json",
})
VALID_HARDWARE_WEIGHTS: frozenset[str] = frozenset({
    "light_cpu",
    "heavy_cpu",
    "gpu_vram",
})


class PresetBackendType(str, Enum):
    """Execution backend types supported for custom OCR and parsing presets."""

    CLI_SUBPROCESS = "cli_subprocess"
    HTTP_ENDPOINT = "http_endpoint"
    PYTHON_CALLABLE = "python_callable"

    def __str__(self) -> str:
        return str(self.value)


@dataclass
class ParameterWiggleSpec:
    """Definition of a tunable OCR parameter and fallback values for Path B wiggling."""

    name: str
    default_value: Any = None
    fallback_values: List[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        cleaned = str(self.name).strip()
        if not cleaned:
            raise ValueError("ParameterWiggleSpec.name must be a non-empty string.")
        self.name = cleaned
        if not isinstance(self.fallback_values, list):
            raise ValueError("ParameterWiggleSpec.fallback_values must be a list.")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes this parameter wiggle spec into a JSON-compatible dict."""
        return {
            "name": self.name,
            "default_value": self.default_value,
            "fallback_values": list(self.fallback_values),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParameterWiggleSpec:
        """Constructs and validates a ParameterWiggleSpec from a mapping."""
        if not isinstance(data, Mapping):
            raise ValueError("ParameterWiggleSpec data must be a mapping.")
        raw_name = data.get("name") or data.get("param_name") or data.get("parameter_name") or ""
        name = str(raw_name).strip()
        if not name:
            raise ValueError("ParameterWiggleSpec requires a non-empty 'name'.")
        if "fallback_values" not in data:
            raw_fallbacks: Any = []
        else:
            raw_fallbacks = data.get("fallback_values")
        if not isinstance(raw_fallbacks, (list, tuple)):
            raise ValueError("ParameterWiggleSpec 'fallback_values' must be a list.")
        default_val = data.get("default_value", data.get("default"))
        return cls(
            name=name,
            default_value=default_val,
            fallback_values=list(raw_fallbacks),
        )


def _normalize_command_template(raw_cmd: Any) -> Optional[List[str]]:
    if raw_cmd is None:
        return None
    if isinstance(raw_cmd, str):
        stripped = raw_cmd.strip()
        if not stripped:
            return None
        return shlex.split(stripped, posix=(os.name != "nt"))
    if isinstance(raw_cmd, (list, tuple)):
        tokens = [str(tok) for tok in raw_cmd if str(tok) != ""]
        return tokens if tokens else None
    raise ValueError("command_template must be a list of strings or a command string.")


@dataclass
class CustomPresetConfig:
    """Manifest describing a custom OCR or document parsing preset."""

    preset_id: str
    display_name: str
    backend_type: PresetBackendType = PresetBackendType.CLI_SUBPROCESS
    command_template: Optional[List[str]] = None
    endpoint_url: Optional[str] = None
    output_format: str = "text"
    hardware_weight: str = "light_cpu"
    timeout_sec: int = 120
    wiggle_parameters: List[ParameterWiggleSpec] = field(default_factory=list)
    suitability_weights: Dict[str, float] = field(default_factory=dict)
    taxonomy_hints: List[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        self.preset_id = str(self.preset_id or "").strip()
        if not self.preset_id:
            raise ValueError("CustomPresetConfig.preset_id must be a non-empty string.")

        self.display_name = str(self.display_name or "").strip()
        if not self.display_name:
            raise ValueError("CustomPresetConfig.display_name must be a non-empty string.")

        if not isinstance(self.backend_type, PresetBackendType):
            try:
                self.backend_type = PresetBackendType(str(self.backend_type).strip())
            except ValueError as exc:
                allowed = ", ".join(b.value for b in PresetBackendType)
                raise ValueError(
                    f"Invalid backend_type '{self.backend_type}'. Expected one of: {allowed}"
                ) from exc

        self.output_format = str(self.output_format or "text").strip().lower()
        if self.output_format not in VALID_OUTPUT_FORMATS:
            allowed_fmt = ", ".join(sorted(VALID_OUTPUT_FORMATS))
            raise ValueError(
                f"Invalid output_format '{self.output_format}'. Expected one of: {allowed_fmt}"
            )

        self.hardware_weight = str(self.hardware_weight or "light_cpu").strip().lower()
        if self.hardware_weight not in VALID_HARDWARE_WEIGHTS:
            allowed_hw = ", ".join(sorted(VALID_HARDWARE_WEIGHTS))
            raise ValueError(
                f"Invalid hardware_weight '{self.hardware_weight}'. Expected one of: {allowed_hw}"
            )

        self.timeout_sec = int(self.timeout_sec)
        if self.timeout_sec <= 0:
            raise ValueError("CustomPresetConfig.timeout_sec must be greater than 0.")

        if self.command_template is not None:
            self.command_template = [str(tok) for tok in self.command_template if str(tok) != ""]

        if self.endpoint_url is not None:
            self.endpoint_url = str(self.endpoint_url).strip() or None

        if self.backend_type == PresetBackendType.CLI_SUBPROCESS:
            if not self.command_template:
                raise ValueError(
                    "cli_subprocess preset requires a non-empty 'command_template'."
                )
        elif self.backend_type == PresetBackendType.HTTP_ENDPOINT:
            if not self.endpoint_url or not (
                self.endpoint_url.startswith("http://") or self.endpoint_url.startswith("https://")
            ):
                raise ValueError(
                    "http_endpoint preset requires an 'endpoint_url' starting with 'http://' or 'https://'."
                )

        normalized_wiggles: List[ParameterWiggleSpec] = []
        for item in self.wiggle_parameters:
            if isinstance(item, ParameterWiggleSpec):
                normalized_wiggles.append(item)
            elif isinstance(item, Mapping):
                normalized_wiggles.append(ParameterWiggleSpec.from_dict(item))
            else:
                raise ValueError("wiggle_parameters entries must be ParameterWiggleSpec or mapping.")
        self.wiggle_parameters = normalized_wiggles

        self.suitability_weights = {
            str(k): float(v) for k, v in dict(self.suitability_weights).items()
        }
        self.taxonomy_hints = [str(t).strip() for t in self.taxonomy_hints if str(t).strip()]
        self.description = str(self.description or "").strip()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes this custom preset configuration to a dictionary."""
        res: Dict[str, Any] = {
            "preset_id": self.preset_id,
            "display_name": self.display_name,
            "backend_type": self.backend_type.value,
            "command_template": list(self.command_template) if self.command_template is not None else None,
            "endpoint_url": self.endpoint_url,
            "output_format": self.output_format,
            "hardware_weight": self.hardware_weight,
            "timeout_sec": self.timeout_sec,
            "wiggle_parameters": [w.to_dict() for w in self.wiggle_parameters],
        }
        if self.suitability_weights:
            res["suitability_weights"] = dict(self.suitability_weights)
        if self.taxonomy_hints:
            res["taxonomy_hints"] = list(self.taxonomy_hints)
        if self.description:
            res["description"] = self.description
        return res

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CustomPresetConfig:
        """Constructs and validates a CustomPresetConfig from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError("CustomPresetConfig data must be a mapping.")

        raw_cmd = data.get("command_template")
        if raw_cmd is None and data.get("command") is not None:
            raw_cmd = data.get("command")
        cmd_template = _normalize_command_template(raw_cmd)

        raw_wiggles = data.get("wiggle_parameters", [])
        if raw_wiggles is None:
            raw_wiggles = []
        if not isinstance(raw_wiggles, (list, tuple)):
            raise ValueError("wiggle_parameters must be a list.")

        raw_weights = data.get("suitability_weights") or {}
        if not isinstance(raw_weights, Mapping):
            raise ValueError("suitability_weights must be a mapping.")

        raw_hints = data.get("taxonomy_hints") or []
        if not isinstance(raw_hints, (list, tuple)):
            raise ValueError("taxonomy_hints must be a list.")

        raw_backend = data.get("backend_type", PresetBackendType.CLI_SUBPROCESS.value)
        raw_endpoint = data.get("endpoint_url") or data.get("url")

        return cls(
            preset_id=str(data.get("preset_id") or "").strip(),
            display_name=str(data.get("display_name") or data.get("preset_id") or "").strip(),
            backend_type=PresetBackendType(str(raw_backend).strip()),
            command_template=cmd_template,
            endpoint_url=str(raw_endpoint).strip() if raw_endpoint is not None else None,
            output_format=str(data.get("output_format") or "text"),
            hardware_weight=str(data.get("hardware_weight") or "light_cpu"),
            timeout_sec=int(data.get("timeout_sec", 120)),
            wiggle_parameters=[
                w if isinstance(w, ParameterWiggleSpec) else ParameterWiggleSpec.from_dict(w)
                for w in raw_wiggles
            ],
            suitability_weights={str(k): float(v) for k, v in raw_weights.items()},
            taxonomy_hints=[str(x) for x in raw_hints],
            description=str(data.get("description") or ""),
        )


DEFAULT_COMMUNITY_RECIPES: List[Dict[str, Any]] = [
    {
        "preset_id": "tesseract_multilang",
        "display_name": "Tesseract Multi-Language OCR",
        "backend_type": "cli_subprocess",
        "command_template": ["tesseract", "{input_path}", "{output_path}", "-l", "{language}", "--psm", "{psm}"],
        "endpoint_url": None,
        "output_format": "text",
        "hardware_weight": "light_cpu",
        "timeout_sec": 120,
        "wiggle_parameters": [
            {"name": "psm", "default_value": "3", "fallback_values": ["6", "11"]},
        ],
        "taxonomy_hints": ["scanned_form", "general_text"],
        "description": "Tesseract OCR with language parameter and page segmentation mode (--psm) wiggling.",
    },
    {
        "preset_id": "ocrmypdf_deskew",
        "display_name": "OCRmyPDF Deskew & Clean",
        "backend_type": "cli_subprocess",
        "command_template": ["ocrmypdf", "--deskew", "--clean", "--sidecar", "{output_path}", "{input_path}", "-"],
        "endpoint_url": None,
        "output_format": "text",
        "hardware_weight": "heavy_cpu",
        "timeout_sec": 180,
        "wiggle_parameters": [
            {"name": "oversample", "default_value": "200", "fallback_values": ["300"]},
        ],
        "taxonomy_hints": ["scanned_form", "financial_report"],
        "description": "ocrmypdf with automatic deskewing and background cleaning for skewed office scans.",
    },
    {
        "preset_id": "marker_scientific_md",
        "display_name": "Marker Scientific Markdown",
        "backend_type": "cli_subprocess",
        "command_template": ["marker_single", "{input_path}", "--output_dir", "{output_path}"],
        "endpoint_url": None,
        "output_format": "markdown",
        "hardware_weight": "gpu_vram",
        "timeout_sec": 300,
        "wiggle_parameters": [],
        "taxonomy_hints": ["multicolumn_article", "mixed_text_image"],
        "description": "marker_single conversion tailored for STEM PDFs with LaTeX equations and columns.",
    },
    {
        "preset_id": "paddleocr_cjk_http",
        "display_name": "PaddleOCR CJK Table Service (HTTP)",
        "backend_type": "http_endpoint",
        "command_template": None,
        "endpoint_url": "http://127.0.0.1:8866/predict/ocr_system",
        "output_format": "cernodata_dom_json",
        "hardware_weight": "gpu_vram",
        "timeout_sec": 120,
        "wiggle_parameters": [],
        "taxonomy_hints": ["tabular_ledger", "financial_report"],
        "description": "HTTP OCR endpoint template for Chinese, Japanese, and Korean dense tables.",
    },
    {
        "preset_id": "kraken_historical_handwriting",
        "display_name": "Kraken Historical & Fraktur OCR",
        "backend_type": "cli_subprocess",
        "command_template": ["kraken", "-i", "{input_path}", "{output_path}", "binarize", "segment", "ocr"],
        "endpoint_url": None,
        "output_format": "text",
        "hardware_weight": "heavy_cpu",
        "timeout_sec": 240,
        "wiggle_parameters": [],
        "taxonomy_hints": ["scanned_form", "general_text"],
        "description": "Kraken OCR template for historical archives, manuscripts, and Fraktur typefaces.",
    },
]


def _extract_preset_entries(raw: Any) -> List[Mapping[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)]
    if isinstance(raw, Mapping):
        for key in ("presets", "custom_presets", "recipes"):
            nested = raw.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, Mapping)]
        if "preset_id" in raw:
            return [raw]
    return []


def load_custom_presets_file(path: str) -> List[CustomPresetConfig]:
    """Loads custom preset configurations from a JSON file, returning [] if absent."""
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fp:
            raw = json.load(fp)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Failed to read custom presets file '%s': %s", path, exc)
        return []

    configs: List[CustomPresetConfig] = []
    for entry in _extract_preset_entries(raw):
        try:
            configs.append(CustomPresetConfig.from_dict(entry))
        except ValueError as exc:
            logger.warning("Skipping invalid custom preset entry in '%s': %s", path, exc)
    return configs


def save_custom_presets_file(
    path: str,
    presets: Sequence[CustomPresetConfig],
) -> str:
    """Persists a sequence of CustomPresetConfig objects to disk as JSON."""
    payload = [preset.to_dict() for preset in presets]
    return save_json(path, payload, indent=2)


def get_community_preset_recipes(
    recipes_path: Optional[str] = None,
) -> List[CustomPresetConfig]:
    """Returns community OCR preset recipes from examples JSON or built-in defaults."""
    default_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "examples",
        "custom_presets",
        "community_ocr_presets.json",
    )
    target_path = recipes_path or default_path
    loaded = load_custom_presets_file(target_path)
    if loaded:
        return loaded
    return [CustomPresetConfig.from_dict(item) for item in DEFAULT_COMMUNITY_RECIPES]


__all__ = [
    "CustomPresetConfig",
    "DEFAULT_COMMUNITY_RECIPES",
    "ParameterWiggleSpec",
    "PresetBackendType",
    "VALID_HARDWARE_WEIGHTS",
    "VALID_OUTPUT_FORMATS",
    "get_community_preset_recipes",
    "load_custom_presets_file",
    "save_custom_presets_file",
]

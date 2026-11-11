"""
src/parsers/ocr_flags.py

Parsing and PIL image preprocessing utilities for advanced section OCR custom flags.
"""

from __future__ import annotations

import logging
import re
import shlex
from typing import Dict, List, Optional, TypedDict

from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_KNOWN_BOOL_KEYS = {"binarize", "bw", "invert"}
_KNOWN_VALUE_KEYS = {"psm", "oem", "threshold", "contrast", "scale", "whitelist"}
_KNOWN_FLAG_KEYS = _KNOWN_BOOL_KEYS | _KNOWN_VALUE_KEYS
_NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


class OCRCustomFlags(TypedDict):
    """Normalized representation of advanced section OCR flags."""

    raw_flags: str
    psm: Optional[int]
    oem: Optional[int]
    binarize: bool
    threshold: int
    invert: bool
    contrast: Optional[float]
    scale: Optional[float]
    whitelist: Optional[str]
    tesseract_config: str


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in _TRUTHY_VALUES


def _parse_int(value: str) -> Optional[int]:
    try:
        return int(value.strip())
    except ValueError:
        return None


def _parse_float(value: str) -> Optional[float]:
    try:
        return float(value.strip())
    except ValueError:
        return None


def _is_flag_token(token: str) -> bool:
    return token.startswith("-") and not _NUMBER_RE.match(token)


def _tokenize_custom_flags(raw: str) -> List[str]:
    try:
        raw_tokens = shlex.split(raw)
    except ValueError:
        raw_tokens = raw.split()

    tokens: List[str] = []
    for idx, tok in enumerate(raw_tokens):
        if not tok:
            continue
        prev_is_whitelist = idx > 0 and raw_tokens[idx - 1].lstrip("-").lower() == "whitelist"
        lower_tok = tok.lower()
        is_whitelist_kv = any(
            lower_tok.startswith(prefix)
            for prefix in ("whitelist=", "--whitelist=", "-whitelist=", "tessedit_char_whitelist=")
        )
        if is_whitelist_kv or prev_is_whitelist:
            cleaned = tok[:-1] if (tok.endswith(",") and idx < len(raw_tokens) - 1) else tok
            if cleaned:
                tokens.append(cleaned)
        else:
            for part in tok.split(","):
                if part:
                    tokens.append(part)
    return tokens


def parse_ocr_custom_flags(custom_flags: Optional[str]) -> OCRCustomFlags:
    """
    Parses a free-form custom OCR flag string into structured preprocessing and engine options.

    Supports both CLI-style tokens (`--psm 6`, `--oem 1`, `--binarize`, `--invert`,
    `--threshold 150`, `--contrast 1.5`, `--scale 3.0`) and comma/space separated
    key=value pairs (`binarize=1, psm=6, contrast=1.4`).

    Args:
        custom_flags: Raw user-supplied custom flag string.

    Returns:
        Normalized OCRCustomFlags dictionary.
    """
    raw = str(custom_flags or "").strip()
    result: OCRCustomFlags = {
        "raw_flags": raw,
        "psm": None,
        "oem": None,
        "binarize": False,
        "threshold": 140,
        "invert": False,
        "contrast": None,
        "scale": None,
        "whitelist": None,
        "tesseract_config": "",
    }
    if not raw:
        return result

    tokens = _tokenize_custom_flags(raw)

    extra_tess_tokens: List[str] = []
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx].strip()
        if not tok:
            idx += 1
            continue

        key = ""
        val: Optional[str] = None
        if "=" in tok and not tok.startswith("-c"):
            left, right = tok.split("=", 1)
            key = left.lstrip("-").lower().strip()
            val = right.strip()
        elif tok.startswith("--"):
            key = tok[2:].lower().strip()
            if key not in _KNOWN_BOOL_KEYS and idx + 1 < len(tokens) and not _is_flag_token(tokens[idx + 1]):
                val = tokens[idx + 1]
                idx += 1
        elif tok == "-c" and idx + 1 < len(tokens):
            extra_tess_tokens.extend(["-c", tokens[idx + 1]])
            idx += 2
            continue
        elif tok.startswith("-"):
            key = tok[1:].lower().strip()
            if key not in _KNOWN_BOOL_KEYS and idx + 1 < len(tokens) and not _is_flag_token(tokens[idx + 1]):
                val = tokens[idx + 1]
                idx += 1

        if key == "psm" and val is not None:
            parsed_psm = _parse_int(val)
            if parsed_psm is not None and 0 <= parsed_psm <= 13:
                result["psm"] = parsed_psm
        elif key == "oem" and val is not None:
            parsed_oem = _parse_int(val)
            if parsed_oem is not None and 0 <= parsed_oem <= 3:
                result["oem"] = parsed_oem
        elif key in ("binarize", "bw"):
            result["binarize"] = True if val is None else _parse_bool(val)
        elif key == "threshold" and val is not None:
            parsed_thresh = _parse_int(val)
            if parsed_thresh is not None:
                result["threshold"] = max(1, min(254, parsed_thresh))
                result["binarize"] = True
        elif key == "invert":
            result["invert"] = True if val is None else _parse_bool(val)
        elif key == "contrast" and val is not None:
            parsed_contrast = _parse_float(val)
            if parsed_contrast is not None:
                result["contrast"] = max(0.2, min(5.0, parsed_contrast))
        elif key == "scale" and val is not None:
            parsed_scale = _parse_float(val)
            if parsed_scale is not None:
                result["scale"] = max(0.5, min(6.0, parsed_scale))
        elif key == "whitelist" and val is not None:
            result["whitelist"] = val
        elif tok.startswith("-") and key not in _KNOWN_FLAG_KEYS:
            extra_tess_tokens.append(tok)
            if val is not None:
                extra_tess_tokens.append(val)

        idx += 1

    tess_parts: List[str] = []
    if result["psm"] is not None:
        tess_parts.extend(["--psm", str(result["psm"])])
    if result["oem"] is not None:
        tess_parts.extend(["--oem", str(result["oem"])])
    if result["whitelist"]:
        wl_arg = f"tessedit_char_whitelist={result['whitelist']}"
        if any(ch.isspace() or ch in "\"'" for ch in result["whitelist"]):
            wl_arg = shlex.quote(wl_arg)
        tess_parts.extend(["-c", wl_arg])
    tess_parts.extend(extra_tess_tokens)
    result["tesseract_config"] = " ".join(tess_parts).strip()
    return result


def preprocess_ocr_image(
    pil_img: Image.Image,
    flags: OCRCustomFlags,
    apply_scale: bool = True,
) -> Image.Image:
    """
    Applies optional resolution scaling, contrast enhancement, binarization,
    and color inversion to a section PIL Image prior to OCR inference.

    Args:
        pil_img: Canonical RGB PIL Image.
        flags: Parsed OCRCustomFlags dictionary.
        apply_scale: Whether to rescale pixel dimensions when scale is specified.

    Returns:
        Preprocessed RGB PIL Image.
    """
    img = pil_img.convert("RGB")

    scale = flags["scale"]
    if apply_scale and scale is not None and abs(scale - 1.0) > 1e-3:
        new_w = max(1, int(round(img.width * scale)))
        new_h = max(1, int(round(img.height * scale)))
        resampling = getattr(Image, "Resampling", Image).BICUBIC
        img = img.resize((new_w, new_h), resample=resampling)

    contrast = flags["contrast"]
    if contrast is not None and abs(contrast - 1.0) > 1e-3:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    if flags["binarize"]:
        thresh = flags["threshold"]
        img = img.convert("L").point(lambda px: 255 if px >= thresh else 0).convert("RGB")

    if flags["invert"]:
        img = ImageOps.invert(img.convert("RGB"))

    return img


def summarize_applied_flags(flags: OCRCustomFlags) -> Dict[str, object]:
    """Returns a JSON-serializable summary of non-default OCR flags applied."""
    return {
        "raw_flags": flags["raw_flags"],
        "psm": flags["psm"],
        "oem": flags["oem"],
        "binarize": flags["binarize"],
        "threshold": flags["threshold"],
        "invert": flags["invert"],
        "contrast": flags["contrast"],
        "scale": flags["scale"],
        "whitelist": flags["whitelist"],
        "tesseract_config": flags["tesseract_config"],
    }

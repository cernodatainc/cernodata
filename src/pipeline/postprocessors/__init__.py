"""
src/pipeline/postprocessors/__init__.py

DOM postprocessor protocol, chain runner, and default postprocessor registry.
"""

from __future__ import annotations

from typing import Any, List, Optional

from src.pipeline.planner.models import IngestionConfig
from src.pipeline.postprocessors.base import (
    DOMPostprocessor,
    PostprocessActionRecord,
    PostprocessorChain,
)
from src.pipeline.postprocessors.uncovered_region_detector import (
    UncoveredRegionCandidate,
    UncoveredRegionPostprocessor,
    detect_uncovered_regions_on_page,
)


def build_default_postprocessor_chain(
    config: Optional[IngestionConfig] = None,
    pdf_path: Optional[str] = None,
) -> PostprocessorChain:
    """Builds the default DOM postprocessor chain from IngestionConfig options."""
    steps: List[DOMPostprocessor] = []
    detect_uncovered = True
    language: Optional[str] = "en"
    ocr_engine = "rapidocr"
    page_images: Any = None
    ocr_parser: Any = None
    extra_steps: Any = None

    if config is not None:
        detect_uncovered = bool(config.get_option("detect_uncovered_regions", True))
        language = config.language
        ocr_engine = str(config.get_option("uncovered_ocr_engine", "rapidocr"))
        page_images = config.get_option("uncovered_page_images")
        ocr_parser = config.get_option("uncovered_ocr_parser")
        extra_steps = config.get_option("postprocessors")

    if detect_uncovered:
        steps.append(
            UncoveredRegionPostprocessor(
                pdf_path=pdf_path,
                page_images=page_images,
                ocr_parser=ocr_parser,
                ocr_engine=ocr_engine,
                language=language,
            )
        )

    if isinstance(extra_steps, (list, tuple)):
        for step in extra_steps:
            if isinstance(step, DOMPostprocessor):
                steps.append(step)

    return PostprocessorChain(steps=steps)


__all__ = [
    "DOMPostprocessor",
    "PostprocessActionRecord",
    "PostprocessorChain",
    "UncoveredRegionCandidate",
    "UncoveredRegionPostprocessor",
    "build_default_postprocessor_chain",
    "detect_uncovered_regions_on_page",
]

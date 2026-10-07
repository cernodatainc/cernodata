"""
src/pipeline/server/routes/__init__.py

Modular API route handlers partitioned by domain responsibility.
"""

from __future__ import annotations

from src.pipeline.server.routes.base import BaseApiRoutesMixin
from src.pipeline.server.routes.config import ConfigRoutesMixin
from src.pipeline.server.routes.execution import ExecutionRoutesMixin
from src.pipeline.server.routes.ocr import OcrRoutesMixin
from src.pipeline.server.routes.persistence import PersistenceRoutesMixin
from src.pipeline.server.routes.planning import PlanningRoutesMixin


class ApiRoutesMixin(
    ConfigRoutesMixin,
    ExecutionRoutesMixin,
    PlanningRoutesMixin,
    PersistenceRoutesMixin,
    OcrRoutesMixin,
    BaseApiRoutesMixin,
):
    """
    Consolidated API routes mixin composing all domain-specific route mixins
    for pipeline execution, configuration, planning, DOM persistence, and OCR.
    """


__all__ = [
    "ApiRoutesMixin",
    "BaseApiRoutesMixin",
    "ConfigRoutesMixin",
    "ExecutionRoutesMixin",
    "OcrRoutesMixin",
    "PersistenceRoutesMixin",
    "PlanningRoutesMixin",
]

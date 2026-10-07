"""
src/pipeline/server/routes_api.py

Backwards-compatibility shim re-exporting ApiRoutesMixin from src.pipeline.server.routes.
"""

from __future__ import annotations

from src.pipeline.server.routes import (
    ApiRoutesMixin,
    BaseApiRoutesMixin,
    ConfigRoutesMixin,
    ExecutionRoutesMixin,
    OcrRoutesMixin,
    PersistenceRoutesMixin,
    PlanningRoutesMixin,
)

__all__ = [
    "ApiRoutesMixin",
    "BaseApiRoutesMixin",
    "ConfigRoutesMixin",
    "ExecutionRoutesMixin",
    "OcrRoutesMixin",
    "PersistenceRoutesMixin",
    "PlanningRoutesMixin",
]

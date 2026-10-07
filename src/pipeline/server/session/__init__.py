"""
src/pipeline/server/session/__init__.py

Thread-safe state container orchestrating server sessions, run artifacts,
and interactive visual viewer data.
"""

from __future__ import annotations

from src.pipeline.server.session.cache import PresetCacheMixin
from src.pipeline.server.session.documents import DocumentsMixin
from src.pipeline.server.session.hydration import ViewerHydrationMixin
from src.pipeline.server.session.loader import RunLoaderMixin
from src.pipeline.server.session.state import BaseSessionState


class ServerSessionContext(
    DocumentsMixin,
    RunLoaderMixin,
    ViewerHydrationMixin,
    PresetCacheMixin,
    BaseSessionState,
):
    """
    Thread-safe state container orchestrating pipeline sessions, loaded execution runs,
    real-time progress monitoring, and interactive viewer data hydration.
    """


__all__ = [
    "BaseSessionState",
    "DocumentsMixin",
    "PresetCacheMixin",
    "RunLoaderMixin",
    "ServerSessionContext",
    "ViewerHydrationMixin",
]

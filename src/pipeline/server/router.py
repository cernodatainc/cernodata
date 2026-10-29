"""
src/pipeline/server/router.py

Lightweight declarative HTTP API router for cernodata server.
Enables domain route mixins to register endpoints independently without
modifying central request dispatching switch blocks in handler.py.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence


class ApiRouter:
    """Thread-safe route registry mapping URL paths to handler callables."""

    def __init__(self) -> None:
        self._get_routes: Dict[str, Callable[[Any, Dict[str, List[str]]], None]] = {}
        self._post_routes: Dict[str, Callable[[Any, Dict[str, Any]], None]] = {}

    def get(self, *paths: str) -> Callable[..., Any]:
        """Decorator registering a GET endpoint for one or more paths."""
        def decorator(fn: Callable[[Any, Dict[str, List[str]]], None]) -> Callable[[Any, Dict[str, List[str]]], None]:
            for p in paths:
                self._get_routes[p] = fn
            return fn
        return decorator

    def post(self, *paths: str) -> Callable[..., Any]:
        """Decorator registering a POST endpoint for one or more paths."""
        def decorator(fn: Callable[[Any, Dict[str, Any]], None]) -> Callable[[Any, Dict[str, Any]], None]:
            for p in paths:
                self._post_routes[p] = fn
            return fn
        return decorator

    def register_get(self, paths: Sequence[str], fn: Callable[[Any, Dict[str, List[str]]], None]) -> None:
        """Registers a GET route mapping."""
        for p in paths:
            self._get_routes[p] = fn

    def register_post(self, paths: Sequence[str], fn: Callable[[Any, Dict[str, Any]], None]) -> None:
        """Registers a POST route mapping."""
        for p in paths:
            self._post_routes[p] = fn

    def dispatch_get(self, handler: Any, path: str, query_params: Dict[str, List[str]]) -> bool:
        """
        Dispatches GET request to registered route callable if matched.
        Returns True if handled, False otherwise.
        """
        fn = self._get_routes.get(path)
        if fn is not None:
            fn(handler, query_params)
            return True
        return False

    def dispatch_post(self, handler: Any, path: str, payload: Dict[str, Any]) -> bool:
        """
        Dispatches POST request to registered route callable if matched.
        Returns True if handled, False otherwise.
        """
        fn = self._post_routes.get(path)
        if fn is not None:
            fn(handler, payload)
            return True
        return False


api_router = ApiRouter()

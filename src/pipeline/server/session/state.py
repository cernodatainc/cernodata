"""
src/pipeline/server/session/state.py

Base session state container and progress tracker delegation methods.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from src.pipeline.execution_models import AttemptRecord
from src.pipeline.planner_models import DocumentPlan
from src.pipeline.server.artifacts import ViewerDataset
from src.pipeline.server.http_utils import REPO_ROOT, SRC_DIR
from src.pipeline.server.preset_cache import PresetCache
from src.pipeline.server.progress import ProgressTracker

logger = logging.getLogger("cernodata.server.session")


class BaseSessionState:
    """Core state container managing session attributes, thread lock, and progress tracker."""

    def __init__(
        self,
        pdf_path: str = "",
        language: str = "en",
        repo_root: Optional[str] = None,
        src_dir: Optional[str] = None,
        output_dir: str = "output",
    ) -> None:
        self._lock: threading.RLock = threading.RLock()
        self.pdf_path: str = pdf_path
        self.language: str = language
        self.repo_root: str = repo_root or REPO_ROOT
        self.src_dir: str = src_dir or SRC_DIR
        self.output_dir: str = output_dir.replace("\\", "/")
        self.active_step: Optional[int] = None
        self.viewer_data: Optional[ViewerDataset] = None
        self.current_result: Optional[Dict[str, Any]] = None
        self.preset_attempts: List[AttemptRecord] = []
        self.submitted_plan: Optional[DocumentPlan] = None

        self._progress_tracker: ProgressTracker = ProgressTracker(lock=self._lock)
        self._preset_cache: PresetCache = PresetCache(lock=self._lock)

    @property
    def progress_state(self) -> Dict[str, Any]:
        return self._progress_tracker.progress_state

    @progress_state.setter
    def progress_state(self, val: Dict[str, Any]) -> None:
        self._progress_tracker.progress_state = val

    @property
    def preset_results(self) -> Dict[str, Dict[str, Any]]:
        return self._preset_cache.preset_results

    @preset_results.setter
    def preset_results(self, val: Dict[str, Dict[str, Any]]) -> None:
        self._preset_cache.preset_results = val

    def get_progress(self) -> Dict[str, Any]:
        """Thread-safe retrieval of current progress state."""
        return self._progress_tracker.get_progress()

    def update_progress(
        self,
        progress: int,
        step_index: int,
        current_step: str,
        log: Optional[str] = None,
        status: str = "running",
        completed: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Thread-safe update of progress state and log history."""
        self._progress_tracker.update_progress(
            progress=progress,
            step_index=step_index,
            current_step=current_step,
            log=log,
            status=status,
            completed=completed,
            error=error,
        )

    def make_progress_callback(self) -> Callable[[int, str, str], None]:
        """Creates a standardized progress callback function wired to this session."""
        return self._progress_tracker.make_progress_callback()

    def add_log(self, message: str) -> None:
        """Thread-safe appending of a log message."""
        self._progress_tracker.add_log(message)

    def reset_progress(self, initial_step: str = "Starting...", log: Optional[str] = None) -> None:
        """Thread-safe reset of progress state to initiate a new run."""
        self._progress_tracker.reset_progress(initial_step=initial_step, log=log)

    def set_error(self, error_msg: str, log: Optional[str] = None) -> None:
        """Thread-safe recording of an execution error."""
        self._progress_tracker.set_error(error_msg=error_msg, log=log)

    def set_completed(
        self,
        status: str,
        confidence: float,
        violations_count: int,
        log: Optional[str] = None,
    ) -> None:
        """Thread-safe recording of a successful pipeline run completion."""
        self._progress_tracker.set_completed(
            status=status,
            confidence=confidence,
            violations_count=violations_count,
            log=log,
        )

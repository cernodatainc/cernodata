"""
src/pipeline/progress_notifier.py

Progress notification dispatcher and milestone event definitions for pipeline runs.
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger("cernodata.pipeline.progress_notifier")


class PipelineProgressNotifier:
    """Dispatches milestone progress events safely to optional user callback."""

    def __init__(self, callback: Optional[Callable[[int, str, str], None]] = None) -> None:
        self.callback = callback

    def notify(self, pct: int, step_desc: str, log_msg: str) -> None:
        """Sends progress event if a callback is registered, swallowing exceptions."""
        if self.callback is not None:
            try:
                self.callback(pct, step_desc, log_msg)
            except Exception as ex:
                logger.debug("Progress callback error: %s", ex)

    def notify_initiation(self, path: str, preset: str, lang: Optional[str]) -> None:
        self.notify(20, "Step 1: Document Validation & Subdivision", f"Ingestion initiated for '{path}' (Preset: {preset}, Lang: {lang}).")

    def notify_preset_execution(self, preset: str, pct: int = 40) -> None:
        self.notify(pct, f"running {preset}", f"Running extraction with preset '{preset}'...")

    def notify_verification(self) -> None:
        self.notify(65, "Step 3: Document Skew Alignment & Verification", "Document parsed. Analyzing layout geometry and quality rules...")

    def notify_parameter_wiggling(self, preset: str, reason: str = "") -> None:
        msg = reason if reason else f"Target threshold not met. Wiggling OCR parameters for '{preset}'..."
        self.notify(70, msg, msg)

    def notify_preset_switching(
        self,
        target_preset: str,
        reason: str = "",
        current_preset: Optional[str] = None,
        confidence: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> None:
        if current_preset and confidence is not None and threshold is not None:
            msg = f"{current_preset} confidence too low ({confidence:.2f} < {threshold:.2f}), starting {target_preset}"
        elif reason:
            msg = reason
        else:
            msg = f"Switching to fallback preset '{target_preset}'..."
        self.notify(75, msg, msg)

    def notify_exporting_artifacts(self) -> None:
        self.notify(88, "Step 5: Exporting Artifacts & Overlays", "Saving DocumentDOM, quality violations, and rendering visual overlays...")

    def notify_complete(self, status: str, confidence: float, violations_count: int) -> None:
        self.notify(100, f"Step 5: Decision Tree Complete ({status})", f"Run complete: Status '{status}', Confidence: {confidence:.4f}, Violations: {violations_count}.")

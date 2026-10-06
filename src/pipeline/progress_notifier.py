"""
src/pipeline/progress_notifier.py

Progress notification dispatcher and milestone event definitions for pipeline runs.
"""

from typing import Callable, Optional


class PipelineProgressNotifier:
    """Dispatches milestone progress events safely to optional user callback."""

    def __init__(self, callback: Optional[Callable[[int, str, str], None]] = None) -> None:
        self.callback = callback

    def notify(self, pct: int, step_desc: str, log_msg: str) -> None:
        """Sends progress event if a callback is registered, swallowing exceptions."""
        if self.callback is not None:
            try:
                self.callback(pct, step_desc, log_msg)
            except Exception:
                pass

    def notify_initiation(self, path: str, preset: str, lang: Optional[str]) -> None:
        self.notify(20, "Step 1: Document Validation & Subdivision", f"Ingestion initiated for '{path}' (Preset: {preset}, Lang: {lang}).")

    def notify_preset_execution(self, preset: str) -> None:
        self.notify(40, f"Step 2: Executing Preset '{preset}'", f"Running extraction with preset '{preset}'...")

    def notify_verification(self) -> None:
        self.notify(65, "Step 3: Document Skew Alignment & Verification", "Document parsed. Analyzing layout geometry and quality rules...")

    def notify_parameter_wiggling(self, preset: str) -> None:
        self.notify(70, "Step 4: Parameter Wiggling", f"Target threshold not met. Wiggling OCR parameters for '{preset}'...")

    def notify_preset_switching(self, target_preset: str, reason: str = "") -> None:
        msg = f"{reason} Switching to fallback preset '{target_preset}'..." if reason else f"Switching to fallback preset '{target_preset}'..."
        self.notify(75, "Step 4: Switching Preset", msg)

    def notify_exporting_artifacts(self) -> None:
        self.notify(88, "Step 5: Exporting Artifacts & Overlays", "Saving DocumentDOM, quality violations, and rendering visual overlays...")

    def notify_complete(self, status: str, confidence: float, violations_count: int) -> None:
        self.notify(100, f"Step 5: Decision Tree Complete ({status})", f"Run complete: Status '{status}', Confidence: {confidence:.4f}, Violations: {violations_count}.")

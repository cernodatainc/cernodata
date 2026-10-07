"""
src/pipeline/server/routes/planning.py

Data shape questionnaire scoring and DocumentPlan persistence API route handlers.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict

from src.pipeline.planner.models import DocumentPlan, PlannerCriteria
from src.pipeline.server.http_utils import send_json_response
from src.pipeline.server.routes.base import BaseApiRoutesMixin
from src.utils import mkdirs


class PlanningRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling data shape criteria scoring and document plan configuration."""

    def _handle_post_calculate_scores(self, payload: Dict[str, Any]) -> None:
        """
        Calculates preset scores based on data shape questionnaire criteria.

        Args:
            payload: Questionnaire criteria dictionary.
        """
        from src.pipeline.planner import PresetPlanner
        planner = getattr(self.server, "planner", None) or PresetPlanner()
        criteria = PlannerCriteria.from_dict(payload)
        scores = planner.calculate_scores(criteria=criteria)
        suggested = planner.suggest_preset_order(scores)

        send_json_response(self, 200, {  # type: ignore[arg-type]
            "success": True,
            "scores": scores,
            "suggested_order": suggested,
        })

    def _handle_post_submit_plan(self, payload: Dict[str, Any]) -> None:
        """
        Configures, validates, and persists a DocumentPlan.

        Args:
            payload: Plan parameters or serialized plan dictionary.
        """
        from src.pipeline.planner import PresetPlanner
        planner = getattr(self.server, "planner", None) or PresetPlanner()

        if "primary_preset" in payload or ("target_threshold" in payload and "steps" in payload):
            plan = DocumentPlan.from_dict(payload)
        else:
            default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path
            raw_doc = payload.get("document_path")
            document_path = raw_doc.strip() if isinstance(raw_doc, str) else ""
            document_path = document_path or default_doc or ""
            criteria = PlannerCriteria.from_dict(payload)
            raw_lang = payload.get("language")
            language = (
                raw_lang.strip()
                if (isinstance(raw_lang, str) and raw_lang.strip() and raw_lang.strip().lower() != "none")
                else None
            )
            try:
                default_thresh = getattr(self.server, "default_threshold", 0.82)
                target_threshold = float(payload.get("target_threshold", default_thresh))
            except (ValueError, TypeError):
                target_threshold = getattr(self.server, "default_threshold", 0.82)

            override_primary = payload.get("override_primary")
            override_order = payload.get("override_order")

            plan = planner.create_plan(
                document_path=document_path,
                criteria=criteria,
                language=language,
                target_threshold=target_threshold,
                override_primary=override_primary,
                override_order=override_order,
            )

        self.session.submitted_plan = plan
        setattr(self.server, "submitted_plan", plan)

        out_dir = getattr(self.server, "output_dir", None) or "output"
        if out_dir:
            mkdirs(out_dir)
            plan_file = os.path.join(out_dir, "plan.json")
            plan.save(plan_file)
        else:
            plan_file = ""

        resp_data: Dict[str, Any] = {
            "success": True,
            "plan_path": plan_file,
            "plan": plan.to_dict(),
            "message": (
                "Plan successfully configured and saved."
                if plan_file
                else "Plan successfully configured but not saved (no output directory)."
            ),
        }
        send_json_response(self, 200, resp_data)  # type: ignore[arg-type]

        if getattr(self.server, "shutdown_on_submit", False):
            threading.Thread(target=self.server.shutdown, daemon=True).start()

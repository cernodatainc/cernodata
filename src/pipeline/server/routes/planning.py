"""
src/pipeline/server/routes/planning.py

Data shape questionnaire scoring and DocumentPlan persistence API route handlers.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict

from src.pipeline.planner.models import DocumentPlan, PlannerCriteria
from src.pipeline.server.routes.base import BaseApiRoutesMixin
from src.schemas.requests import SubmitPlanRequest
from src.utils import mkdirs


class PlanningRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling data shape criteria scoring and document plan configuration."""

    def _evaluate_corpus_topic_balance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """No-op hook for evaluating multi-document topic skew for the Browser Wizard UI."""
        # TODO(TASK-603): Compute TopicSkewReport (TASK-602) when a multi-document folder is selected
        # and return data for the interactive 'Dataset Topic Balance' questionnaire card in the Wizard UI.
        _ = payload
        return {}

    def _build_downstream_setup_advice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """No-op hook returning visual downstream format and tool setup recommendations."""
        # TODO(TASK-305): Return DownstreamAdvisor chunking, export format, and external app setup
        # recommendations tailored to the user's selected Target Use-Case in the Web UI.
        _ = payload
        return {}

    def _handle_post_calculate_scores(self, payload: Dict[str, Any]) -> None:
        """
        Calculates preset scores based on data shape questionnaire criteria.

        Args:
            payload: Questionnaire criteria dictionary.
        """
        planner = self._get_active_planner()
        criteria = PlannerCriteria.from_dict(payload)
        scores = planner.calculate_scores(criteria=criteria)
        suggested = planner.suggest_preset_order(scores)

        self.send_ok({
            "scores": scores,
            "suggested_order": suggested,
            "corpus_balance": self._evaluate_corpus_topic_balance(payload),
            "downstream_advice": self._build_downstream_setup_advice(payload),
        })

    def _handle_post_submit_plan(self, payload: Dict[str, Any]) -> None:
        """
        Configures, validates, and persists a DocumentPlan.

        Args:
            payload: Plan parameters or serialized plan dictionary.
        """
        planner = self._get_active_planner()

        if "primary_preset" in payload or ("target_threshold" in payload and "steps" in payload):
            plan = DocumentPlan.from_dict(payload)
        else:
            req = SubmitPlanRequest.model_validate(payload)
            default_doc = self.server.default_doc or self.session.pdf_path or ""
            document_path = req.document_path or default_doc
            criteria = PlannerCriteria.from_dict(payload)
            target_threshold = (
                req.target_threshold
                if req.target_threshold is not None
                else self.server.default_threshold
            )

            plan = planner.create_plan(
                document_path=document_path,
                criteria=criteria,
                language=req.language,
                target_threshold=target_threshold,
                override_primary=req.override_primary,
                override_order=req.override_order,
                verification_layers=req.verification_layers,
            )

        self.session.submitted_plan = plan
        self.server.submitted_plan = plan

        out_dir = self.server.output_dir or "output"
        if out_dir:
            mkdirs(out_dir)
            plan_file = os.path.join(out_dir, "plan.json")
            plan.save(plan_file)
        else:
            plan_file = ""

        self.send_ok({
            "plan_path": plan_file,
            "plan": plan.to_dict(),
            "message": (
                "Plan successfully configured and saved."
                if plan_file
                else "Plan successfully configured but not saved (no output directory)."
            ),
        })

        if self.server.shutdown_on_submit:
            threading.Thread(target=self.server.shutdown, daemon=True).start()

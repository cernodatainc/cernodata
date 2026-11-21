"""
src/schemas/__init__.py

Pydantic schemas and contract definitions for decoupled component seams.
"""

from __future__ import annotations

from src.schemas.artifacts import (
    ValidatedRunArtifacts,
    load_validated_run_artifacts,
)
from src.schemas.custom_preset import (
    CustomPresetConfig,
    ParameterWiggleSpec,
    PresetBackendType,
)
from src.schemas.decision import (
    AttemptRecordSchema,
    DecisionTreeSchema,
)
from src.schemas.dom import (
    BoundingBoxSchema,
    DOMNodeSchema,
    DocumentDOMSchema,
)
from src.schemas.execution import (
    PipelineExecutionResultSchema,
)
from src.schemas.plan import (
    DocumentPlanSchema,
    PlannerCriteriaSchema,
)
from src.schemas.requests import (
    AddDocumentsRequest,
    DocumentTargetRequest,
    RemoveRunRequest,
    RerunPipelineRequest,
    RunPipelineRequest,
    SaveDomRequest,
    SubmitPlanRequest,
    VerifyLayersRequest,
)
from src.schemas.violations import (
    QualityViolationSchema,
    ViolationsReportSchema,
    parse_violations_payload,
)

__all__ = [
    "AddDocumentsRequest",
    "AttemptRecordSchema",
    "BoundingBoxSchema",
    "CustomPresetConfig",
    "DOMNodeSchema",
    "DecisionTreeSchema",
    "DocumentDOMSchema",
    "DocumentPlanSchema",
    "DocumentTargetRequest",
    "ParameterWiggleSpec",
    "PipelineExecutionResultSchema",
    "PlannerCriteriaSchema",
    "PresetBackendType",
    "QualityViolationSchema",
    "RemoveRunRequest",
    "RerunPipelineRequest",
    "RunPipelineRequest",
    "SaveDomRequest",
    "SubmitPlanRequest",
    "ValidatedRunArtifacts",
    "VerifyLayersRequest",
    "ViolationsReportSchema",
    "load_validated_run_artifacts",
    "parse_violations_payload",
]

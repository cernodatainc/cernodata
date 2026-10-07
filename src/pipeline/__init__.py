"""
src/pipeline package re-exports
"""
from src.pipeline.decision_tree import DecisionTreeEngine, DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.orchestrator import run_pipeline, PipelineOrchestrator
from src.pipeline.planner import DocumentPlan, PresetPlanner, PlannerCriteria, IngestionConfig
from src.pipeline.execution_models import PipelineExecutionResult, AttemptRecord
from src.pipeline.parsers import (
    DocumentParserDispatcher,
    ParserExecutionOptions,
    ParserPresetAdapter,
    ParserPresetRegistry,
    get_default_parser_registry,
    parse_document,
)
from src.pipeline.attempt_runner import AttemptRunner
from src.pipeline.fallback_handler import FallbackLoopHandler
from src.pipeline.progress_notifier import PipelineProgressNotifier
from src.pipeline.config_resolver import PipelineConfigResolver
from src.pipeline.artifact_pipeline import PipelineArtifactPipeline

__all__ = [
    "DecisionTreeEngine",
    "DEFAULT_TARGET_CONFIDENCE_THRESHOLD",
    "run_pipeline",
    "PipelineOrchestrator",
    "DocumentPlan",
    "PresetPlanner",
    "PlannerCriteria",
    "IngestionConfig",
    "PipelineExecutionResult",
    "AttemptRecord",
    "ParserExecutionOptions",
    "ParserPresetAdapter",
    "ParserPresetRegistry",
    "get_default_parser_registry",
    "parse_document",
    "DocumentParserDispatcher",
    "AttemptRunner",
    "FallbackLoopHandler",
    "PipelineProgressNotifier",
    "PipelineConfigResolver",
    "PipelineArtifactPipeline",
]

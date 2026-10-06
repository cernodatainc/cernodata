"""
src/pipeline/execution_models.py

Strongly-typed execution result and attempt tracking containers for pipeline runs.
"""

from typing import Dict, Any, List, Optional, TypedDict


class PipelineExecutionResult(TypedDict, total=False):
    """Strongly-typed execution result container for pipeline extraction runs."""
    dom: Dict[str, Any]
    decision: Dict[str, Any]
    violations: List[Dict[str, Any]]
    dom_json_path: str
    violations_json_path: str
    plan_result_path: Optional[str]
    html_viewer_path: Optional[str]
    rendered_images: List[str]
    plan: Optional[Dict[str, Any]]


class AttemptRecord(TypedDict, total=False):
    """Structured record tracking iteration history in pipeline fallback execution."""
    step: int
    preset: str
    overall_confidence: Optional[float]
    per_page_confidence: Optional[Dict[int, float]]
    status: Optional[str]
    is_accepted: bool
    violations_count: int
    action: Optional[str]
    reason: Optional[str]
    detail: Optional[str]
    parameters: Optional[Dict[str, Any]]

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowIssue(BaseModel):
    step: str
    code: str
    message: str
    recoverable: bool
    context: dict[str, Any] = Field(default_factory=dict)


class DiscoveryWorkflowState(BaseModel):
    tenant_id: UUID
    job_id: UUID
    correlation_id: UUID
    categories: list[str]
    status: Literal["queued", "running", "succeeded", "partial", "failed"] = "queued"
    raw_item_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[UUID] = Field(default_factory=list)
    analyzed_ids: list[UUID] = Field(default_factory=list)
    scored_ids: list[UUID] = Field(default_factory=list)
    recommendation_ids: list[UUID] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    warnings: list[WorkflowIssue] = Field(default_factory=list)
    errors: list[WorkflowIssue] = Field(default_factory=list)


class DiscoveryRunSummary(BaseModel):
    job_id: UUID
    correlation_id: UUID
    status: str
    raw_items: int
    candidates: int
    analyzed: int
    scored: int
    recommendations: int
    warning_count: int
    error_count: int
    top_recommendations: list[dict[str, Any]]

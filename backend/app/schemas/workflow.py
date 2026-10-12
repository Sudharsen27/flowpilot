from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.lead import LeadSource
from app.models.workflow import WorkflowAction, WorkflowRunStatus, WorkflowTrigger


def _name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


class WorkflowRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    trigger: WorkflowTrigger
    action: WorkflowAction
    source_filter: LeadSource | None = None
    follow_up_delay_hours: int | None = Field(default=None, ge=1, le=720)
    enabled: bool = False

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _name(value)


class WorkflowRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    trigger: WorkflowTrigger | None = None
    action: WorkflowAction | None = None
    source_filter: LeadSource | None = None
    follow_up_delay_hours: int | None = Field(default=None, ge=1, le=720)
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return None if value is None else _name(value)


class WorkflowRunCounts(BaseModel):
    pending: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0


class WorkflowRulePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    trigger: WorkflowTrigger
    action: WorkflowAction
    source_filter: LeadSource | None = None
    follow_up_delay_hours: int | None = None
    enabled: bool
    revision: int
    created_at: datetime
    updated_at: datetime
    run_counts: WorkflowRunCounts = Field(default_factory=WorkflowRunCounts)
    last_run_at: datetime | None = None


class WorkflowRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_id: str
    lead_id: str
    lead_name: str | None = None
    status: WorkflowRunStatus
    detail: str | None = None
    result_entity_id: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowRunListResponse(BaseModel):
    items: list[WorkflowRunPublic]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

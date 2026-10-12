from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.knowledge_entry import (
    KNOWLEDGE_CONTENT_MAX_LENGTH,
    KNOWLEDGE_TITLE_MAX_LENGTH,
    KnowledgeCategory,
    KnowledgeEntryStatus,
)


def _required_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


class KnowledgeEntryCreate(BaseModel):
    category: KnowledgeCategory
    title: str = Field(min_length=1, max_length=KNOWLEDGE_TITLE_MAX_LENGTH)
    content: str = Field(min_length=1, max_length=KNOWLEDGE_CONTENT_MAX_LENGTH)
    use_in_ai: bool = True

    @field_validator("title", "content")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _required_text(value)


class KnowledgeEntryUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    category: KnowledgeCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=KNOWLEDGE_TITLE_MAX_LENGTH)
    content: str | None = Field(
        default=None, min_length=1, max_length=KNOWLEDGE_CONTENT_MAX_LENGTH
    )
    use_in_ai: bool | None = None
    status: KnowledgeEntryStatus | None = None

    @field_validator("title", "content")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return None if value is None else _required_text(value)


class KnowledgeEntryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: KnowledgeCategory
    title: str
    content: str
    use_in_ai: bool
    status: KnowledgeEntryStatus
    revision: int
    created_at: datetime
    updated_at: datetime


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeEntryPublic]
    total: int = Field(ge=0)
    category_counts: dict[KnowledgeCategory, int]

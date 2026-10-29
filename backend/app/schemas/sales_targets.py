import calendar
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.money import CurrencyCode, Money, MoneyOut


def month_end(period_start: date) -> date:
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    return period_start.replace(day=last_day)


class SalesTargetUpsert(BaseModel):
    """Create or replace the target for one calendar month. Omit owner_user_id for the
    organization-wide target."""

    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date | None = None
    owner_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    amount: Money
    currency: CurrencyCode | None = None

    @model_validator(mode="after")
    def calendar_month(self) -> "SalesTargetUpsert":
        if self.period_start.day != 1:
            raise ValueError("period_start must be the first day of a calendar month")
        expected_end = month_end(self.period_start)
        if self.period_end is not None and self.period_end != expected_end:
            raise ValueError(
                f"period_end must be the last day of the same month ({expected_end.isoformat()})"
            )
        self.period_end = expected_end
        return self


class SalesTargetPublic(BaseModel):
    id: str
    owner_user_id: str | None
    owner_name: str | None
    period_start: date
    period_end: date
    amount: MoneyOut
    currency: str
    created_by_user_id: str | None
    updated_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class SalesTargetListResponse(BaseModel):
    items: list[SalesTargetPublic]
    limit: int
    offset: int
    total: int

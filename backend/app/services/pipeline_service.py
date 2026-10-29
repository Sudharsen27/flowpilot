from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.deal import (
    CLOSED_DEAL_STAGES,
    DEAL_STAGE_DEFAULT_PROBABILITY,
    Deal,
    DealStage,
    effective_probability,
)
from app.models.organization import Organization
from app.schemas.pipeline import (
    PipelineMonth,
    PipelineStageSummary,
    PipelineSummary,
    PipelineTotals,
    PipelineWeightedTotals,
)

_CENTS = Decimal("0.01")
_ZERO = Decimal("0")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_months(month: date, delta: int) -> date:
    index = month.year * 12 + (month.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


class PipelineService:
    """Read-only pipeline figures from persisted deals, in exact decimal arithmetic."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def summary(
        self, organization_id: str, *, months: int, now: datetime | None = None
    ) -> PipelineSummary:
        organization = self.session.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        current = (now or datetime.now(UTC)).astimezone(UTC)
        today = current.date()
        currency = organization.default_currency

        rows = self.session.execute(
            select(
                Deal.stage,
                Deal.probability,
                Deal.amount,
                Deal.currency,
                Deal.closed_at,
                Deal.expected_close_date,
            ).where(Deal.organization_id == organization_id)
        ).all()

        counts = {stage: 0 for stage in DealStage}
        totals = {stage: _ZERO for stage in DealStage}
        weighted = {stage: _ZERO for stage in DealStage}
        overdue_count, overdue_total = 0, _ZERO
        first_month = _shift_months(_month_start(today), -(months - 1))
        month_keys = [_shift_months(first_month, offset) for offset in range(months)]
        won_counts = {month: 0 for month in month_keys}
        won_totals = {month: _ZERO for month in month_keys}
        excluded = 0

        for stage_value, override, amount_value, deal_currency, closed_at, close_date in rows:
            if deal_currency != currency:
                # Never add amounts across currencies; there is no conversion.
                excluded += 1
                continue
            stage = DealStage(stage_value)
            amount = Decimal(amount_value)
            probability = effective_probability(stage, override)
            counts[stage] += 1
            totals[stage] += amount
            weighted[stage] += amount * probability / 100
            if stage not in CLOSED_DEAL_STAGES and close_date < today:
                overdue_count += 1
                overdue_total += amount
            if stage == DealStage.CLOSED_WON and closed_at is not None:
                closed = closed_at if closed_at.tzinfo else closed_at.replace(tzinfo=UTC)
                bucket = _month_start(closed.astimezone(UTC).date())
                if bucket in won_counts:
                    won_counts[bucket] += 1
                    won_totals[bucket] += amount

        open_stages = [stage for stage in DealStage if stage not in CLOSED_DEAL_STAGES]
        return PipelineSummary(
            currency=currency,
            generated_at=current,
            open=PipelineWeightedTotals(
                count=sum(counts[stage] for stage in open_stages),
                total_amount=_money(sum((totals[stage] for stage in open_stages), _ZERO)),
                weighted_amount=_money(sum((weighted[stage] for stage in open_stages), _ZERO)),
            ),
            won=PipelineTotals(
                count=counts[DealStage.CLOSED_WON],
                total_amount=_money(totals[DealStage.CLOSED_WON]),
            ),
            lost=PipelineTotals(
                count=counts[DealStage.CLOSED_LOST],
                total_amount=_money(totals[DealStage.CLOSED_LOST]),
            ),
            overdue_open=PipelineTotals(count=overdue_count, total_amount=_money(overdue_total)),
            by_stage=[
                PipelineStageSummary(
                    stage=stage,
                    count=counts[stage],
                    total_amount=_money(totals[stage]),
                    weighted_amount=_money(weighted[stage]),
                    default_probability=DEAL_STAGE_DEFAULT_PROBABILITY[stage],
                )
                for stage in DealStage
            ],
            won_by_month=[
                PipelineMonth(
                    month=month,
                    count=won_counts[month],
                    total_amount=_money(won_totals[month]),
                )
                for month in month_keys
            ],
            excluded_other_currency_count=excluded,
        )

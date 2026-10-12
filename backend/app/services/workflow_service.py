import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ProviderError,
    ProviderNotConfiguredError,
    UnprocessableError,
    ValidationError,
)
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.inbound_email import InboundEmail
from app.models.lead import Lead
from app.models.lead_follow_up import LeadFollowUpType
from app.models.membership import MembershipRole
from app.models.workflow import (
    ALLOWED_WORKFLOW_ACTIONS,
    WorkflowAction,
    WorkflowRule,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowTrigger,
)
from app.schemas.workflow import (
    WorkflowRuleCreate,
    WorkflowRulePublic,
    WorkflowRuleUpdate,
    WorkflowRunCounts,
    WorkflowRunListResponse,
    WorkflowRunPublic,
)
from app.services.activity_service import ActivityService

logger = logging.getLogger(__name__)

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
MAX_RULES_PER_ORGANIZATION = 25
RUN_LIST_MAX_LIMIT = 50
DEFAULT_FOLLOW_UP_DELAY_HOURS = 24
INTERRUPTED_DETAIL = (
    "Stopped before it finished. It was not retried, to avoid repeating AI work."
)


def _require_manager(role: str) -> None:
    try:
        parsed = MembershipRole(role)
    except ValueError as exc:
        raise ForbiddenError("Not allowed to manage workflows") from exc
    if parsed not in MANAGER_ROLES:
        raise ForbiddenError("Not allowed to manage workflows")


def _validate(rule: WorkflowRule) -> None:
    trigger = WorkflowTrigger(rule.trigger)
    action = WorkflowAction(rule.action)
    if action not in ALLOWED_WORKFLOW_ACTIONS[trigger]:
        raise ValidationError("This action is not available for the selected trigger")
    if rule.source_filter is not None and trigger is not WorkflowTrigger.LEAD_CREATED:
        raise ValidationError("A lead source filter only applies to the new lead trigger")
    if action is WorkflowAction.CREATE_FOLLOW_UP:
        if rule.follow_up_delay_hours is None:
            rule.follow_up_delay_hours = DEFAULT_FOLLOW_UP_DELAY_HOURS
    else:
        rule.follow_up_delay_hours = None


class WorkflowService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # Rules -----------------------------------------------------------------

    def list_rules(self, organization_id: str) -> list[WorkflowRulePublic]:
        rules = self.session.scalars(
            select(WorkflowRule)
            .where(WorkflowRule.organization_id == organization_id)
            .order_by(WorkflowRule.created_at, WorkflowRule.id)
        ).all()
        counts: dict[str, WorkflowRunCounts] = {rule.id: WorkflowRunCounts() for rule in rules}
        last_run: dict[str, datetime] = {}
        if rules:
            stmt = (
                select(
                    WorkflowRun.rule_id,
                    WorkflowRun.status,
                    func.count(),
                    func.max(WorkflowRun.created_at),
                )
                .where(WorkflowRun.organization_id == organization_id)
                .group_by(WorkflowRun.rule_id, WorkflowRun.status)
            )
            for rule_id, status, count, latest in self.session.execute(stmt):
                bucket = counts.get(rule_id)
                if bucket is None:
                    continue
                key = "pending" if status == WorkflowRunStatus.RUNNING else str(status).lower()
                setattr(bucket, key, getattr(bucket, key) + int(count))
                if latest is not None and (rule_id not in last_run or latest > last_run[rule_id]):
                    last_run[rule_id] = latest
        return [
            WorkflowRulePublic.model_validate(rule).model_copy(
                update={"run_counts": counts[rule.id], "last_run_at": last_run.get(rule.id)}
            )
            for rule in rules
        ]

    def get_rule(self, organization_id: str, rule_id: str) -> WorkflowRule:
        rule = self.session.scalar(
            select(WorkflowRule).where(
                WorkflowRule.organization_id == organization_id, WorkflowRule.id == rule_id
            )
        )
        if rule is None:
            raise NotFoundError("Workflow not found")
        return rule

    def get_rule_public(self, organization_id: str, rule_id: str) -> WorkflowRulePublic:
        self.get_rule(organization_id, rule_id)
        return next(rule for rule in self.list_rules(organization_id) if rule.id == rule_id)

    def create_rule(
        self, organization_id: str, *, role: str, user_id: str, payload: WorkflowRuleCreate
    ) -> WorkflowRulePublic:
        _require_manager(role)
        existing = int(
            self.session.scalar(
                select(func.count())
                .select_from(WorkflowRule)
                .where(WorkflowRule.organization_id == organization_id)
            )
            or 0
        )
        if existing >= MAX_RULES_PER_ORGANIZATION:
            raise ValidationError(
                f"A workspace can have at most {MAX_RULES_PER_ORGANIZATION} workflows"
            )
        rule = WorkflowRule(
            organization_id=organization_id,
            name=payload.name,
            trigger=payload.trigger,
            action=payload.action,
            source_filter=payload.source_filter,
            follow_up_delay_hours=payload.follow_up_delay_hours,
            enabled=payload.enabled,
            revision=1,
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
        )
        _validate(rule)
        self.session.add(rule)
        self.session.flush()
        self._record(rule, user_id, "Workflow created", "CREATED")
        self.session.commit()
        return self.get_rule_public(organization_id, rule.id)

    def update_rule(
        self,
        organization_id: str,
        rule_id: str,
        *,
        role: str,
        user_id: str,
        payload: WorkflowRuleUpdate,
    ) -> WorkflowRulePublic:
        _require_manager(role)
        rule = self.get_rule(organization_id, rule_id)
        if rule.revision != payload.expected_revision:
            raise ConflictError(
                "This workflow was changed by someone else. Reload it and try again.",
                {"detail": "Workflow revision conflict", "revision": rule.revision},
            )
        fields = payload.model_fields_set - {"expected_revision"}
        if not fields:
            return self.get_rule_public(organization_id, rule_id)
        previous_enabled = rule.enabled
        for field in fields:
            value = getattr(payload, field)
            if value is None and field in {"name", "trigger", "action", "enabled"}:
                continue
            setattr(rule, field, value)
        _validate(rule)
        rule.revision += 1
        rule.updated_by_user_id = user_id
        rule.updated_at = datetime.now(UTC)
        if rule.enabled != previous_enabled:
            title = "Workflow turned on" if rule.enabled else "Workflow turned off"
        else:
            title = "Workflow updated"
        self.session.flush()
        self._record(rule, user_id, title, f"REVISION:{rule.revision}")
        self.session.commit()
        return self.get_rule_public(organization_id, rule_id)

    def delete_rule(self, organization_id: str, rule_id: str, *, role: str, user_id: str) -> None:
        _require_manager(role)
        rule = self.get_rule(organization_id, rule_id)
        self._record(rule, user_id, "Workflow deleted", "DELETED")
        self.session.execute(
            delete(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.rule_id == rule_id,
            )
        )
        self.session.delete(rule)
        self.session.commit()

    def list_runs(
        self, organization_id: str, rule_id: str, *, limit: int, offset: int
    ) -> WorkflowRunListResponse:
        self.get_rule(organization_id, rule_id)
        conditions = (
            WorkflowRun.organization_id == organization_id,
            WorkflowRun.rule_id == rule_id,
        )
        rows = self.session.execute(
            select(WorkflowRun, Lead.name)
            .join(
                Lead,
                (Lead.organization_id == WorkflowRun.organization_id)
                & (Lead.id == WorkflowRun.lead_id),
            )
            .where(*conditions)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
            .limit(limit)
            .offset(offset)
        ).all()
        total = int(
            self.session.scalar(select(func.count()).select_from(WorkflowRun).where(*conditions))
            or 0
        )
        return WorkflowRunListResponse(
            items=[
                WorkflowRunPublic.model_validate(run).model_copy(update={"lead_name": name})
                for run, name in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    # Triggers ----------------------------------------------------------------

    def enqueue(
        self,
        *,
        organization_id: str,
        trigger: WorkflowTrigger,
        lead: Lead,
        trigger_key: str,
        inbound_email_id: str | None = None,
    ) -> int:
        """Queue one run per enabled matching rule inside the caller's transaction.

        Never raises: a workflow problem must not undo the event that triggered it.
        """
        try:
            with self.session.begin_nested():
                rules = self.session.scalars(
                    select(WorkflowRule).where(
                        WorkflowRule.organization_id == organization_id,
                        WorkflowRule.trigger == trigger,
                        WorkflowRule.enabled.is_(True),
                    )
                ).all()
                queued = 0
                for rule in rules:
                    if rule.source_filter is not None and rule.source_filter != lead.source:
                        continue
                    try:
                        with self.session.begin_nested():
                            self.session.add(
                                WorkflowRun(
                                    organization_id=organization_id,
                                    rule_id=rule.id,
                                    lead_id=lead.id,
                                    inbound_email_id=inbound_email_id,
                                    trigger_key=trigger_key,
                                    status=WorkflowRunStatus.PENDING,
                                )
                            )
                            self.session.flush()
                        queued += 1
                    except IntegrityError:
                        continue
                return queued
        except Exception:
            logger.exception(
                "workflow enqueue failed organization_id=%s trigger=%s", organization_id, trigger
            )
            return 0

    def _record(self, rule: WorkflowRule, user_id: str, title: str, marker: str) -> None:
        ActivityService(self.session).record(
            organization_id=rule.organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            actor_user_id=user_id,
            title=title,
            summary=rule.name[:200],
            entity_type=ActivityEntityType.WORKFLOW_RULE,
            entity_id=rule.id,
            status="ENABLED" if rule.enabled else "DISABLED",
            dedupe_key=f"workflow:{rule.id}:{marker}",
        )


class WorkflowRunner:
    """Executes one queued run. Owned by the worker; never called by the API."""

    def __init__(self, session: Session, provider: AIProvider | None) -> None:
        self.session = session
        self.provider = provider

    def claim(self, organization_id: str, run_id: str) -> bool:
        result = self.session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == run_id,
                WorkflowRun.status == WorkflowRunStatus.PENDING,
            )
            .values(status=WorkflowRunStatus.RUNNING, started_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        return getattr(result, "rowcount", 0) == 1

    def execute(self, organization_id: str, run_id: str) -> WorkflowRunStatus | None:
        if not self.claim(organization_id, run_id):
            return None
        run = self.session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id, WorkflowRun.id == run_id
            )
        )
        if run is None:
            return None
        try:
            status, detail, entity_id = self._perform(run)
        except (ProviderNotConfiguredError, ProviderError) as exc:
            self.session.rollback()
            status, detail, entity_id = WorkflowRunStatus.FAILED, _safe(exc), None
        except (ConflictError, UnprocessableError, ValidationError, NotFoundError) as exc:
            self.session.rollback()
            status, detail, entity_id = WorkflowRunStatus.SKIPPED, _safe(exc), None
        except Exception:
            self.session.rollback()
            logger.exception("workflow run failed run_id=%s", run_id)
            status, detail, entity_id = (
                WorkflowRunStatus.FAILED,
                "The step failed unexpectedly.",
                None,
            )
        self._finish(organization_id, run_id, status, detail, entity_id)
        return status

    def _perform(self, run: WorkflowRun) -> tuple[WorkflowRunStatus, str, str | None]:
        rule = self.session.scalar(
            select(WorkflowRule).where(
                WorkflowRule.organization_id == run.organization_id,
                WorkflowRule.id == run.rule_id,
            )
        )
        if rule is None or not rule.enabled:
            return WorkflowRunStatus.SKIPPED, "The workflow was turned off before it ran.", None
        lead = self.session.scalar(
            select(Lead).where(Lead.organization_id == run.organization_id, Lead.id == run.lead_id)
        )
        if lead is None:
            return WorkflowRunStatus.SKIPPED, "The lead no longer exists.", None

        action = WorkflowAction(rule.action)
        if action is WorkflowAction.CREATE_FOLLOW_UP:
            from app.services.lead_follow_up_service import LeadFollowUpService

            hours = rule.follow_up_delay_hours or DEFAULT_FOLLOW_UP_DELAY_HOURS
            follow_up = LeadFollowUpService(self.session).create(
                organization_id=run.organization_id,
                lead_id=lead.id,
                due_at=datetime.now(UTC) + timedelta(hours=hours),
                follow_up_type=LeadFollowUpType.MANUAL_FOLLOW_UP,
                notes=f"Created by workflow “{rule.name[:100]}”.",
                body_text=None,
                email_send_id=None,
                initiated_by_user_id=None,
            )
            return (
                WorkflowRunStatus.SUCCEEDED,
                f"Follow-up reminder scheduled in {hours} hours.",
                follow_up.id,
            )

        inbound = self._inbound(run)
        if action is WorkflowAction.ANALYZE_LEAD:
            from app.services.lead_qualification_service import LeadQualificationService

            service = LeadQualificationService(self.session, self.provider)
            if inbound is not None:
                row = service.qualify_inbound_email(
                    organization_id=run.organization_id,
                    lead_id=lead.id,
                    inbound_email_id=inbound.id,
                )
                return WorkflowRunStatus.SUCCEEDED, "The customer reply was analyzed.", row.id
            enquiry = (lead.enquiry or "").strip()
            if not enquiry:
                return WorkflowRunStatus.SKIPPED, "The lead has no enquiry to analyze.", None
            row = service.qualify(
                organization_id=run.organization_id, lead_id=lead.id, enquiry=enquiry
            )
            return WorkflowRunStatus.SUCCEEDED, "The enquiry was analyzed.", row.id

        from app.services.lead_response_draft_service import LeadResponseDraftService

        enquiry = ((inbound.body_text if inbound else None) or lead.enquiry or "").strip()
        if not enquiry:
            return WorkflowRunStatus.SKIPPED, "There is no message to reply to.", None
        draft = LeadResponseDraftService(self.session, self.provider).generate(
            organization_id=run.organization_id, lead_id=lead.id, enquiry=enquiry[:8000]
        )
        return (
            WorkflowRunStatus.SUCCEEDED,
            "A reply draft is ready for review. It has not been sent.",
            draft.id,
        )

    def _inbound(self, run: WorkflowRun) -> InboundEmail | None:
        if run.inbound_email_id is None:
            return None
        return self.session.scalar(
            select(InboundEmail).where(
                InboundEmail.organization_id == run.organization_id,
                InboundEmail.id == run.inbound_email_id,
            )
        )

    def _finish(
        self,
        organization_id: str,
        run_id: str,
        status: WorkflowRunStatus,
        detail: str,
        entity_id: str | None,
    ) -> None:
        self.session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == run_id,
                WorkflowRun.status == WorkflowRunStatus.RUNNING,
            )
            .values(
                status=status,
                detail=detail[:500],
                result_entity_id=entity_id,
                completed_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        self.session.commit()


def fail_interrupted_runs(session: Session, *, started_before: datetime) -> int:
    result = session.execute(
        update(WorkflowRun)
        .where(
            WorkflowRun.status == WorkflowRunStatus.RUNNING,
            WorkflowRun.started_at < started_before,
        )
        .values(
            status=WorkflowRunStatus.FAILED,
            detail=INTERRUPTED_DETAIL,
            completed_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def _safe(exc: Exception) -> str:
    if isinstance(exc, ProviderNotConfiguredError):
        return "The AI provider is not configured."
    if isinstance(exc, ProviderError):
        return "The AI provider request failed."
    if isinstance(exc, AppError):
        return exc.detail[:300]
    return "The step could not run."

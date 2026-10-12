import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.integrations.webhook_sender import (
    WebhookSender,
    WebhookTargetError,
    parse_webhook_url,
    send_webhook,
)
from app.models.activity_event import ActivityActorType, ActivityEntityType, ActivityEventType
from app.models.membership import MembershipRole
from app.models.webhook import (
    SUBSCRIBABLE_WEBHOOK_EVENTS,
    WebhookDelivery,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEventType,
)
from app.schemas.webhook import (
    WebhookDeliveryCounts,
    WebhookDeliveryListResponse,
    WebhookDeliveryPublic,
    WebhookEndpointCreate,
    WebhookEndpointPublic,
    WebhookEndpointUpdate,
    WebhookEndpointWithSecret,
)
from app.services.activity_service import ActivityService

logger = logging.getLogger(__name__)

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
MAX_ENDPOINTS_PER_ORGANIZATION = 10
DELIVERY_LIST_MAX_LIMIT = 50
MAX_ATTEMPTS = 5
RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
)
SIGNATURE_HEADER = "FlowPilot-Signature"


def _require_manager(role: str) -> None:
    try:
        parsed = MembershipRole(role)
    except ValueError as exc:
        raise ForbiddenError("Not allowed to manage integrations") from exc
    if parsed not in MANAGER_ROLES:
        raise ForbiddenError("Not allowed to manage integrations")


def signing_secret(endpoint: WebhookEndpoint) -> str:
    digest = hmac.new(
        settings.secret_key.encode(),
        f"webhook-signing:{endpoint.id}:{endpoint.secret_salt}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"whsec_{digest}"


def sign_payload(secret: str, timestamp: int, body: bytes) -> str:
    message = f"{timestamp}.".encode() + body
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _validate_url(url: str) -> str:
    try:
        parse_webhook_url(url)
    except WebhookTargetError as exc:
        raise ValidationError(str(exc)) from exc
    return url


def _validate_events(events: list[WebhookEventType]) -> list[str]:
    unique = list(dict.fromkeys(events))
    if any(event not in SUBSCRIBABLE_WEBHOOK_EVENTS for event in unique):
        raise ValidationError("Choose events from the list")
    return [str(event) for event in unique]


class WebhookService:
    def __init__(self, session: Session, sender: WebhookSender | None = None) -> None:
        self.session = session
        self.sender = sender or send_webhook

    # Endpoints ---------------------------------------------------------------

    def list_endpoints(self, organization_id: str) -> list[WebhookEndpointPublic]:
        rows = self.session.scalars(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.organization_id == organization_id)
            .order_by(WebhookEndpoint.created_at, WebhookEndpoint.id)
        ).all()
        counts = {row.id: WebhookDeliveryCounts() for row in rows}
        latest: dict[str, datetime] = {}
        if rows:
            stmt = (
                select(
                    WebhookDelivery.endpoint_id,
                    WebhookDelivery.status,
                    func.count(),
                    func.max(WebhookDelivery.created_at),
                )
                .where(WebhookDelivery.organization_id == organization_id)
                .group_by(WebhookDelivery.endpoint_id, WebhookDelivery.status)
            )
            for endpoint_id, status, count, last in self.session.execute(stmt):
                bucket = counts.get(endpoint_id)
                if bucket is None:
                    continue
                if status == WebhookDeliveryStatus.DELIVERED:
                    bucket.delivered += int(count)
                elif status == WebhookDeliveryStatus.FAILED:
                    bucket.failed += int(count)
                else:
                    bucket.pending += int(count)
                if last is not None and (endpoint_id not in latest or last > latest[endpoint_id]):
                    latest[endpoint_id] = last
        return [
            WebhookEndpointPublic.model_validate(row).model_copy(
                update={"delivery_counts": counts[row.id], "last_delivery_at": latest.get(row.id)}
            )
            for row in rows
        ]

    def get_endpoint(self, organization_id: str, endpoint_id: str) -> WebhookEndpoint:
        row = self.session.scalar(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == organization_id,
                WebhookEndpoint.id == endpoint_id,
            )
        )
        if row is None:
            raise NotFoundError("Webhook not found")
        return row

    def get_endpoint_public(self, organization_id: str, endpoint_id: str) -> WebhookEndpointPublic:
        self.get_endpoint(organization_id, endpoint_id)
        return next(
            row for row in self.list_endpoints(organization_id) if row.id == endpoint_id
        )

    def create_endpoint(
        self, organization_id: str, *, role: str, user_id: str, payload: WebhookEndpointCreate
    ) -> WebhookEndpointWithSecret:
        _require_manager(role)
        existing = int(
            self.session.scalar(
                select(func.count())
                .select_from(WebhookEndpoint)
                .where(WebhookEndpoint.organization_id == organization_id)
            )
            or 0
        )
        if existing >= MAX_ENDPOINTS_PER_ORGANIZATION:
            raise ValidationError(
                f"A workspace can have at most {MAX_ENDPOINTS_PER_ORGANIZATION} webhooks"
            )
        row = WebhookEndpoint(
            id=str(uuid4()),
            organization_id=organization_id,
            name=payload.name,
            url=_validate_url(payload.url),
            events=_validate_events(payload.events),
            enabled=True,
            secret_salt=secrets.token_hex(16),
            secret_hint="",
            revision=1,
            created_by_user_id=user_id,
        )
        secret = signing_secret(row)
        row.secret_hint = secret[-4:]
        self.session.add(row)
        self.session.flush()
        self._record(row, user_id, "Webhook added", "CREATED")
        self.session.commit()
        return WebhookEndpointWithSecret(
            endpoint=self.get_endpoint_public(organization_id, row.id), secret=secret
        )

    def update_endpoint(
        self,
        organization_id: str,
        endpoint_id: str,
        *,
        role: str,
        user_id: str,
        payload: WebhookEndpointUpdate,
    ) -> WebhookEndpointPublic:
        _require_manager(role)
        row = self.get_endpoint(organization_id, endpoint_id)
        self._check_revision(row, payload.expected_revision)
        previous_enabled = row.enabled
        if payload.name is not None:
            row.name = payload.name
        if payload.url is not None:
            row.url = _validate_url(payload.url)
        if payload.events is not None:
            row.events = _validate_events(payload.events)
        if payload.enabled is not None:
            row.enabled = payload.enabled
        row.revision += 1
        row.updated_at = datetime.now(UTC)
        if row.enabled != previous_enabled:
            title = "Webhook turned on" if row.enabled else "Webhook turned off"
        else:
            title = "Webhook updated"
        self.session.flush()
        self._record(row, user_id, title, f"REVISION:{row.revision}")
        self.session.commit()
        return self.get_endpoint_public(organization_id, endpoint_id)

    def rotate_secret(
        self,
        organization_id: str,
        endpoint_id: str,
        *,
        role: str,
        user_id: str,
        expected_revision: int,
    ) -> WebhookEndpointWithSecret:
        _require_manager(role)
        row = self.get_endpoint(organization_id, endpoint_id)
        self._check_revision(row, expected_revision)
        row.secret_salt = secrets.token_hex(16)
        secret = signing_secret(row)
        row.secret_hint = secret[-4:]
        row.revision += 1
        row.updated_at = datetime.now(UTC)
        self.session.flush()
        self._record(row, user_id, "Webhook signing secret replaced", f"REVISION:{row.revision}")
        self.session.commit()
        return WebhookEndpointWithSecret(
            endpoint=self.get_endpoint_public(organization_id, endpoint_id), secret=secret
        )

    def delete_endpoint(
        self, organization_id: str, endpoint_id: str, *, role: str, user_id: str
    ) -> None:
        _require_manager(role)
        row = self.get_endpoint(organization_id, endpoint_id)
        self._record(row, user_id, "Webhook deleted", "DELETED")
        self.session.execute(
            delete(WebhookDelivery).where(
                WebhookDelivery.organization_id == organization_id,
                WebhookDelivery.endpoint_id == endpoint_id,
            )
        )
        self.session.delete(row)
        self.session.commit()

    # Deliveries --------------------------------------------------------------

    def list_deliveries(
        self, organization_id: str, endpoint_id: str, *, limit: int, offset: int
    ) -> WebhookDeliveryListResponse:
        self.get_endpoint(organization_id, endpoint_id)
        conditions = (
            WebhookDelivery.organization_id == organization_id,
            WebhookDelivery.endpoint_id == endpoint_id,
        )
        rows = self.session.scalars(
            select(WebhookDelivery)
            .where(*conditions)
            .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id)
            .limit(limit)
            .offset(offset)
        ).all()
        total = int(
            self.session.scalar(
                select(func.count()).select_from(WebhookDelivery).where(*conditions)
            )
            or 0
        )
        return WebhookDeliveryListResponse(
            items=[WebhookDeliveryPublic.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def send_test(
        self, organization_id: str, endpoint_id: str, *, role: str, user_id: str
    ) -> WebhookDeliveryPublic:
        """Deliver one sample event now. The sample contains no customer data."""
        _require_manager(role)
        endpoint = self.get_endpoint(organization_id, endpoint_id)
        delivery = WebhookDelivery(
            organization_id=organization_id,
            endpoint_id=endpoint.id,
            event_type=WebhookEventType.TEST,
            event_key=f"test:{uuid4()}",
            payload=_envelope(
                organization_id,
                WebhookEventType.TEST,
                {"message": "This is a test event from FlowPilot."},
            ),
            status=WebhookDeliveryStatus.SENDING,
            attempts=1,
            last_attempt_at=datetime.now(UTC),
        )
        self.session.add(delivery)
        self.session.commit()
        WebhookDeliverer(self.session, self.sender).attempt(delivery, endpoint, final=True)
        self.session.refresh(delivery)
        return WebhookDeliveryPublic.model_validate(delivery)

    def retry_delivery(
        self, organization_id: str, endpoint_id: str, delivery_id: str, *, role: str
    ) -> WebhookDeliveryPublic:
        _require_manager(role)
        self.get_endpoint(organization_id, endpoint_id)
        row = self.session.scalar(
            select(WebhookDelivery).where(
                WebhookDelivery.organization_id == organization_id,
                WebhookDelivery.endpoint_id == endpoint_id,
                WebhookDelivery.id == delivery_id,
            )
        )
        if row is None:
            raise NotFoundError("Delivery not found")
        if row.status != WebhookDeliveryStatus.FAILED or row.event_type == WebhookEventType.TEST:
            raise ConflictError("Only failed event deliveries can be retried")
        row.status = WebhookDeliveryStatus.PENDING
        row.attempts = 0
        row.next_attempt_at = datetime.now(UTC)
        self.session.commit()
        self.session.refresh(row)
        return WebhookDeliveryPublic.model_validate(row)

    def enqueue(
        self,
        *,
        organization_id: str,
        event_type: WebhookEventType,
        event_key: str,
        data: Mapping[str, Any],
    ) -> int:
        """Queue a delivery for each subscribed endpoint in the caller's transaction.

        Never raises: a webhook problem must not undo the event itself.
        """
        try:
            with self.session.begin_nested():
                endpoints = self.session.scalars(
                    select(WebhookEndpoint).where(
                        WebhookEndpoint.organization_id == organization_id,
                        WebhookEndpoint.enabled.is_(True),
                    )
                ).all()
                payload = _envelope(organization_id, event_type, data)
                queued = 0
                for endpoint in endpoints:
                    if str(event_type) not in endpoint.events:
                        continue
                    try:
                        with self.session.begin_nested():
                            self.session.add(
                                WebhookDelivery(
                                    organization_id=organization_id,
                                    endpoint_id=endpoint.id,
                                    event_type=event_type,
                                    event_key=event_key,
                                    payload=payload,
                                    status=WebhookDeliveryStatus.PENDING,
                                    attempts=0,
                                    next_attempt_at=datetime.now(UTC),
                                )
                            )
                            self.session.flush()
                        queued += 1
                    except IntegrityError:
                        continue
                return queued
        except Exception:
            logger.exception(
                "webhook enqueue failed organization_id=%s event_type=%s",
                organization_id,
                event_type,
            )
            return 0

    def _check_revision(self, row: WebhookEndpoint, expected: int) -> None:
        if row.revision != expected:
            raise ConflictError(
                "This webhook was changed by someone else. Reload it and try again.",
                {"detail": "Webhook revision conflict", "revision": row.revision},
            )

    def _record(self, row: WebhookEndpoint, user_id: str, title: str, marker: str) -> None:
        ActivityService(self.session).record(
            organization_id=row.organization_id,
            event_type=ActivityEventType.HUMAN_ACTION,
            actor_type=ActivityActorType.USER,
            actor_user_id=user_id,
            title=title,
            summary=row.name[:200],
            entity_type=ActivityEntityType.WEBHOOK_ENDPOINT,
            entity_id=row.id,
            status="ENABLED" if row.enabled else "DISABLED",
            dedupe_key=f"webhook:{row.id}:{marker}",
        )


class WebhookDeliverer:
    """Sends one delivery attempt. Used by the worker and by "Send test event"."""

    def __init__(self, session: Session, sender: WebhookSender | None = None) -> None:
        self.session = session
        self.sender = sender or send_webhook

    def claim(self, organization_id: str, delivery_id: str, *, now: datetime) -> bool:
        result = self.session.execute(
            update(WebhookDelivery)
            .where(
                WebhookDelivery.organization_id == organization_id,
                WebhookDelivery.id == delivery_id,
                WebhookDelivery.status == WebhookDeliveryStatus.PENDING,
            )
            .values(
                status=WebhookDeliveryStatus.SENDING,
                attempts=WebhookDelivery.attempts + 1,
                last_attempt_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        return getattr(result, "rowcount", 0) == 1

    def deliver(self, organization_id: str, delivery_id: str) -> str | None:
        if not self.claim(organization_id, delivery_id, now=datetime.now(UTC)):
            return None
        delivery = self.session.scalar(
            select(WebhookDelivery).where(
                WebhookDelivery.organization_id == organization_id,
                WebhookDelivery.id == delivery_id,
            )
        )
        if delivery is None:
            return None
        self.session.refresh(delivery)
        endpoint = self.session.scalar(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == organization_id,
                WebhookEndpoint.id == delivery.endpoint_id,
            )
        )
        if endpoint is None or not endpoint.enabled:
            self._finish(delivery, WebhookDeliveryStatus.FAILED, None, "The webhook is turned off")
            return WebhookDeliveryStatus.FAILED
        return self.attempt(delivery, endpoint, final=delivery.attempts >= MAX_ATTEMPTS)

    def attempt(self, delivery: WebhookDelivery, endpoint: WebhookEndpoint, *, final: bool) -> str:
        body = json.dumps(
            {"id": delivery.id, **delivery.payload}, separators=(",", ":"), sort_keys=True
        ).encode()
        timestamp = int(time.time())
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FlowPilot-Webhooks/1",
            "FlowPilot-Event": str(delivery.event_type),
            "FlowPilot-Delivery": delivery.id,
            SIGNATURE_HEADER: sign_payload(signing_secret(endpoint), timestamp, body),
        }
        status_code: int | None = None
        error: str | None = None
        try:
            response = self.sender(endpoint.url, body, headers)
            status_code = response.status_code
            if not 200 <= status_code < 300:
                error = (
                    "Redirects are not followed"
                    if 300 <= status_code < 400
                    else f"The endpoint responded with HTTP {status_code}"
                )
        except WebhookTargetError as exc:
            error = str(exc)
        except Exception:
            logger.exception("webhook delivery raised delivery_id=%s", delivery.id)
            error = "The delivery failed unexpectedly"
        if error is None:
            self._finish(delivery, WebhookDeliveryStatus.DELIVERED, status_code, None)
            return WebhookDeliveryStatus.DELIVERED
        if final:
            self._finish(delivery, WebhookDeliveryStatus.FAILED, status_code, error)
            return WebhookDeliveryStatus.FAILED
        delay = RETRY_DELAYS[min(delivery.attempts, len(RETRY_DELAYS)) - 1]
        self._finish(
            delivery,
            WebhookDeliveryStatus.PENDING,
            status_code,
            error,
            next_attempt_at=datetime.now(UTC) + delay,
        )
        return WebhookDeliveryStatus.PENDING

    def _finish(
        self,
        delivery: WebhookDelivery,
        status: WebhookDeliveryStatus,
        status_code: int | None,
        error: str | None,
        *,
        next_attempt_at: datetime | None = None,
    ) -> None:
        now = datetime.now(UTC)
        delivery.status = status
        delivery.last_status_code = status_code
        delivery.last_error = error[:300] if error else None
        delivery.next_attempt_at = next_attempt_at
        if status == WebhookDeliveryStatus.DELIVERED:
            delivery.delivered_at = now
        self.session.commit()


def requeue_stuck_deliveries(session: Session, *, started_before: datetime) -> int:
    result = session.execute(
        update(WebhookDelivery)
        .where(
            WebhookDelivery.status == WebhookDeliveryStatus.SENDING,
            WebhookDelivery.last_attempt_at < started_before,
        )
        .values(status=WebhookDeliveryStatus.PENDING, next_attempt_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def _envelope(
    organization_id: str, event_type: WebhookEventType, data: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "type": str(event_type),
        "created_at": datetime.now(UTC).isoformat(),
        "organization_id": organization_id,
        "data": dict(data),
    }

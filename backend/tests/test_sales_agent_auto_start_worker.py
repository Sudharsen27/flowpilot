"""Sales Agent auto-start worker behaviour tests.

SQLite ignores ``FOR UPDATE SKIP LOCKED``. These tests prove discovery,
batching, failure isolation, shutdown, provider injection and coexistence
with the follow-up worker. Row locking remains covered by the existing
PostgreSQL claim tests.
"""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.openai_provider import OpenAIProvider
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.models.lead import LeadSalesAgentAutoStartStatus
from app.models.lead_follow_up import LeadFollowUp, LeadFollowUpStatus
from app.models.sales_run import SalesRun, SalesRunStatus
from app.services.sales_agent_auto_start_service import SalesAgentAutoStartService
from app.services.website_capture_service import WebsiteCaptureService
from app.worker.__main__ import main, run_combined_forever
from app.worker.follow_up_worker import FollowUpWorker
from app.worker.sales_agent_auto_start_worker import SalesAgentAutoStartWorker
from tests.conftest import TestingSessionLocal
from tests.test_follow_up_worker import _due, _org_lead
from tests.test_lead_email_send import FakeEmailProvider
from tests.test_lead_qualification import ENQUIRY
from tests.test_leads import _auth, _create
from tests.test_sales_agent_auto_start import _configure_org, _pending_website_lead
from tests.test_sales_run import SalesPipelineProvider, _ready_sales_agent


def _worker(
    provider: SalesPipelineProvider | None = None, **kwargs: object
) -> SalesAgentAutoStartWorker:
    factory = provider if provider is not None else SalesPipelineProvider()
    return SalesAgentAutoStartWorker(
        session_factory=TestingSessionLocal,
        provider_factory=lambda: factory,
        **kwargs,  # type: ignore[arg-type]
    )


def test_worker_discovers_pending_website_leads_from_database_rows(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="a@example.com", organization_name="Alpha")
    second = _auth(client, email="b@example.com", organization_name="Beta")
    first_org = first["organization"]["id"]
    second_org = second["organization"]["id"]
    pending = _pending_website_lead(db, first_org, name="Pending")
    other = _pending_website_lead(db, second_org, name="Other org")
    claimed = _pending_website_lead(db, first_org, name="Claimed")
    claimed.sales_agent_auto_start_status = LeadSalesAgentAutoStartStatus.CLAIMED
    db.commit()
    _create(client, first["access_token"], name="Manual", source="MANUAL")
    discovered = _worker().discover_pending(limit=20)
    assert (first_org, pending.id) in discovered
    assert (second_org, other.id) in discovered
    assert (first_org, claimed.id) not in discovered


def test_worker_respects_batch_size(client: TestClient, db: Session) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    leads = [_pending_website_lead(db, org_id, name=f"Lead {index}") for index in range(3)]
    discovered = _worker(batch_size=2).discover_pending(limit=2)
    assert len(discovered) == 2
    assert {lead_id for _org_id, lead_id in discovered} <= {row.id for row in leads}


def test_worker_calls_service_with_database_ids_and_configured_provider(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id)
    calls: list[tuple[str, str]] = []
    factories: list[object] = []
    original = SalesAgentAutoStartService.process
    provider = SalesPipelineProvider()

    def tracking(
        self: SalesAgentAutoStartService, organization_id: str, lead_id: str
    ) -> object:
        calls.append((organization_id, lead_id))
        assert self.provider is provider
        assert self.email_provider is None
        return original(self, organization_id, lead_id)

    def factory() -> SalesPipelineProvider:
        factories.append(provider)
        return provider

    monkeypatch.setattr(SalesAgentAutoStartService, "process", tracking)
    worker = SalesAgentAutoStartWorker(
        session_factory=TestingSessionLocal,
        provider_factory=factory,
    )
    result = worker.run_once()
    assert result.candidates == 1
    assert result.started == 1
    assert calls == [(org_id, lead.id)]
    assert factories == [provider]
    db.refresh(lead)
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED
    run = db.query(SalesRun).one()
    assert run.status == SalesRunStatus.WAITING_APPROVAL
    assert run.organization_id == org_id


def test_one_item_failure_does_not_stop_the_batch(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    first = _pending_website_lead(db, org_id, name="First")
    second = _pending_website_lead(db, org_id, name="Second")
    original = SalesAgentAutoStartService.process

    def flaky(
        self: SalesAgentAutoStartService, organization_id: str, lead_id: str
    ) -> object:
        if lead_id == first.id:
            raise RuntimeError("infrastructure blew up")
        return original(self, organization_id, lead_id)

    monkeypatch.setattr(SalesAgentAutoStartService, "process", flaky)
    result = _worker().run_once()
    assert result.candidates == 2
    assert result.errors == 1
    assert result.started == 1
    db.refresh(first)
    db.refresh(second)
    assert first.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING
    assert second.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED


def test_provider_failure_is_isolated_and_does_not_use_email(
    client: TestClient, db: Session
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    _pending_website_lead(db, org_id, enquiry=ENQUIRY)
    provider = SalesPipelineProvider(qualify_fail=ProviderError("upstream rejected"))
    result = _worker(provider).run_once()
    assert result.candidates == 1
    assert result.failed == 1
    assert result.errors == 0


def test_entrypoint_starts_only_enabled_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    follow_calls: list[str] = []
    auto_calls: list[str] = []
    combined: list[str] = []

    monkeypatch.setattr(
        FollowUpWorker,
        "install_signal_handlers",
        lambda self: follow_calls.append("signals"),
    )
    monkeypatch.setattr(
        FollowUpWorker,
        "run_forever",
        lambda self: follow_calls.append("run"),
    )
    monkeypatch.setattr(
        SalesAgentAutoStartWorker,
        "install_signal_handlers",
        lambda self: auto_calls.append("signals"),
    )
    monkeypatch.setattr(
        SalesAgentAutoStartWorker,
        "run_forever",
        lambda self: auto_calls.append("run"),
    )
    monkeypatch.setattr(
        "app.worker.__main__.run_combined_forever",
        lambda follow_up, auto_start: combined.append("combined"),
    )

    monkeypatch.setattr(settings, "follow_up_worker_enabled", True)
    monkeypatch.setattr(settings, "sales_agent_auto_start_worker_enabled", False)
    assert main() == 0
    assert follow_calls == ["signals", "run"]
    assert auto_calls == []
    assert combined == []

    follow_calls.clear()
    monkeypatch.setattr(settings, "follow_up_worker_enabled", False)
    monkeypatch.setattr(settings, "sales_agent_auto_start_worker_enabled", True)
    assert main() == 0
    assert follow_calls == []
    assert auto_calls == ["signals", "run"]
    assert combined == []

    auto_calls.clear()
    monkeypatch.setattr(settings, "follow_up_worker_enabled", True)
    monkeypatch.setattr(settings, "sales_agent_auto_start_worker_enabled", True)
    assert main() == 0
    assert follow_calls == []
    assert auto_calls == []
    assert combined == ["combined"]


def test_combined_loop_polls_both_workers_and_shares_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    follow = FollowUpWorker(session_factory=TestingSessionLocal)
    auto = _worker()
    monkeypatch.setattr(follow, "poll_interval_seconds", 0.01)
    monkeypatch.setattr(auto, "poll_interval_seconds", 0.01)
    counts = {"follow": 0, "auto": 0}
    original_follow = follow.run_once
    original_auto = auto.run_once

    def follow_once() -> object:
        counts["follow"] += 1
        if counts["follow"] >= 2:
            follow.request_stop()
        return original_follow()

    def auto_once() -> object:
        counts["auto"] += 1
        return original_auto()

    monkeypatch.setattr(follow, "run_once", follow_once)
    monkeypatch.setattr(auto, "run_once", auto_once)
    run_combined_forever(follow, auto)
    assert counts["follow"] >= 1
    assert counts["auto"] >= 1
    assert follow.is_stopping is True


def test_disabled_entrypoint_does_not_process_items(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id)
    monkeypatch.setattr(settings, "follow_up_worker_enabled", False)
    monkeypatch.setattr(settings, "sales_agent_auto_start_worker_enabled", False)
    assert main() == 0
    db.refresh(lead)
    assert lead.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.PENDING
    assert db.query(SalesRun).count() == 0


def test_run_forever_uses_configured_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    worker = _worker(poll_interval_seconds=0.01)
    polls: list[int] = []
    original = SalesAgentAutoStartWorker.run_once

    def counting(self: SalesAgentAutoStartWorker) -> object:
        polls.append(1)
        if len(polls) >= 2:
            self.request_stop()
        return original(self)

    monkeypatch.setattr(SalesAgentAutoStartWorker, "run_once", counting)
    worker.run_forever()
    assert len(polls) == 2
    assert worker.is_stopping is True
    assert worker.poll_interval_seconds == 0.01


def test_worker_does_not_submit_public_capture(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    _pending_website_lead(db, org_id)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("worker must not call public capture")

    monkeypatch.setattr(WebsiteCaptureService, "submit_public_enquiry", forbidden)
    result = _worker().run_once()
    assert result.started == 1


def test_worker_stops_before_remaining_items(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    for index in range(3):
        _pending_website_lead(db, org_id, name=f"Stop {index}")
    worker = _worker()
    original = SalesAgentAutoStartService.process

    def stop_then_process(
        self: SalesAgentAutoStartService, organization_id: str, lead_id: str
    ) -> object:
        worker.request_stop()
        return original(self, organization_id, lead_id)

    monkeypatch.setattr(SalesAgentAutoStartService, "process", stop_then_process)
    result = worker.run_once()
    assert result.candidates == 3
    assert result.started == 1
    assert worker.is_stopping is True
    assert db.query(SalesRun).count() == 1


def test_combined_loop_processes_follow_up_and_auto_start_work(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    _org, lead = _org_lead(client, db, token)
    follow_up = _due(client, token, str(lead["id"]))
    pending = _pending_website_lead(db, org_id, name="Auto start")
    email = FakeEmailProvider()
    follow_worker = FollowUpWorker(
        session_factory=TestingSessionLocal,
        provider_factory=lambda: email,
        poll_interval_seconds=0.01,
    )
    auto_worker = _worker(poll_interval_seconds=0.01)
    original_auto = auto_worker.run_once

    def auto_once() -> object:
        result = original_auto()
        follow_worker.request_stop()
        auto_worker.request_stop()
        return result

    monkeypatch.setattr(auto_worker, "run_once", auto_once)
    run_combined_forever(follow_worker, auto_worker)
    db.expire_all()
    row = db.get(LeadFollowUp, str(follow_up["id"]))
    assert row is not None
    assert row.status == LeadFollowUpStatus.COMPLETED
    db.refresh(pending)
    assert pending.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED
    assert len(email.messages) == 1


def test_combined_loop_survives_follow_up_batch_error(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    pending = _pending_website_lead(db, org_id)
    follow = FollowUpWorker(
        session_factory=TestingSessionLocal, poll_interval_seconds=0.01
    )
    auto = _worker(poll_interval_seconds=0.01)

    def boom() -> object:
        raise RuntimeError("follow-up batch exploded")

    original_auto = auto.run_once

    def auto_once() -> object:
        result = original_auto()
        follow.request_stop()
        auto.request_stop()
        return result

    monkeypatch.setattr(follow, "run_once", boom)
    monkeypatch.setattr(auto, "run_once", auto_once)
    run_combined_forever(follow, auto)
    db.refresh(pending)
    assert pending.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED


def test_follow_up_and_auto_start_workers_share_a_process(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "email_from_address", "noreply@example.com")
    created = _auth(client)
    org_id = created["organization"]["id"]
    token = created["access_token"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    _org, lead = _org_lead(client, db, token)
    follow_up = _due(client, token, str(lead["id"]))
    pending = _pending_website_lead(db, org_id, name="Auto start")
    email = FakeEmailProvider()
    follow_worker = FollowUpWorker(
        session_factory=TestingSessionLocal,
        provider_factory=lambda: email,
    )
    auto_result = _worker().run_once()
    follow_result = follow_worker.run_once()
    assert follow_result.sent == 1
    assert auto_result.started == 1
    db.expire_all()
    row = db.get(LeadFollowUp, str(follow_up["id"]))
    assert row is not None
    assert row.status == LeadFollowUpStatus.COMPLETED
    db.refresh(pending)
    assert pending.sales_agent_auto_start_status == LeadSalesAgentAutoStartStatus.STARTED


def test_worker_configuration_defaults() -> None:
    assert settings.sales_agent_auto_start_worker_enabled is False
    assert settings.sales_agent_auto_start_worker_poll_interval_seconds == 30
    assert settings.sales_agent_auto_start_worker_batch_size == 10
    worker = SalesAgentAutoStartWorker(session_factory=TestingSessionLocal)
    assert worker.poll_interval_seconds == 30
    assert worker.batch_size == 10
    assert worker.is_stopping is False
    assert worker._provider_factory is OpenAIProvider


def test_worker_logs_are_safe(
    client: TestClient,
    db: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = _auth(client)
    org_id = created["organization"]["id"]
    agent = _ready_sales_agent(db, org_id)
    _configure_org(db, org_id, agent_id=agent.id)
    lead = _pending_website_lead(db, org_id, enquiry=ENQUIRY)
    with caplog.at_level(logging.INFO, logger="app.worker.sales_agent_auto_start_worker"):
        _worker().run_once()
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "sales-agent auto-start worker polled candidates=1" in text
    assert lead.id in text
    assert ENQUIRY not in text
    assert "ada@example.com" not in text
    assert "Authorization" not in text

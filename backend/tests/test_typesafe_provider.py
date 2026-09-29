from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import SecretStr
from typesafe_sdk import Noul, NoulAnswer, TypeSafeClient, TypeSafeError

from app.ai import typesafe_provider
from app.ai.decision_provider import DecisionProvider, DecisionRequest, DecisionResult
from app.ai.typesafe_provider import TypeSafeDecisionProvider
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError, ValidationError


class FakeTypeSafeClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []
        self.error: Exception | None = None

    def system_one(
        self,
        *,
        state: object,
        questions: object,
        model: str,
    ) -> object:
        self.calls.append({"state": state, "questions": questions, "model": model})
        if self.error is not None:
            raise self.error
        return self.response


def make_response(probability: float) -> SimpleNamespace:
    return SimpleNamespace(
        answers={"escalate_to_human": NoulAnswer(noul=probability)},
    )


def make_request(
    *,
    decision_key: str = "escalate_to_human",
    trusted_context: str = "Escalate urgent leads.",
    untrusted_state: str = "The lead asked for a callback.",
) -> DecisionRequest:
    return DecisionRequest(
        decision_key=decision_key,
        trusted_context=trusted_context,
        untrusted_state=untrusted_state,
    )


@pytest.mark.parametrize(
    ("probability", "expected"),
    [(0.8, True), (0.5, True), (0.49, False), (0.2, False)],
)
def test_escalate_decision_maps_noul_probability(
    probability: float,
    expected: bool,
) -> None:
    client = FakeTypeSafeClient(make_response(probability))
    provider = TypeSafeDecisionProvider(
        api_key="test-only-key",
        client=cast(TypeSafeClient, client),
    )

    result = provider.decide(make_request())

    assert result == DecisionResult(value=expected)


def test_provider_forwards_context_as_data_and_uses_fixed_noul_question() -> None:
    client = FakeTypeSafeClient(make_response(0.6))
    provider = TypeSafeDecisionProvider(
        api_key="test-only-key",
        client=cast(TypeSafeClient, client),
    )
    request = make_request(
        trusted_context="Escalate when a lead explicitly requests a person.",
        untrusted_state="Please connect me to your sales team.",
    )

    provider.decide(request)

    call = client.calls[0]
    assert call["state"] == {
        "trusted_context": request.trusted_context,
        "untrusted_state": request.untrusted_state,
    }
    assert set(call["state"]) == {"trusted_context", "untrusted_state"}
    questions = call["questions"]
    assert isinstance(questions, dict)
    assert set(questions) == {"escalate_to_human"}
    question = questions["escalate_to_human"]
    assert isinstance(question, Noul)
    assert question.instructions == "Should this lead be escalated to a human?"


def test_unknown_decision_key_is_rejected_before_client_use() -> None:
    provider = TypeSafeDecisionProvider()

    with pytest.raises(ValidationError, match="Unsupported decision key"):
        provider.decide(make_request(decision_key="arbitrary_key"))


def test_missing_api_key_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "typesafe_api_key", None)
    provider = TypeSafeDecisionProvider()

    with pytest.raises(ProviderNotConfiguredError, match="TYPESAFE_API_KEY is not configured"):
        provider.decide(make_request())


def test_sdk_error_is_converted_without_exposing_key_or_raw_error() -> None:
    client = FakeTypeSafeClient(make_response(0.7))
    client.error = TypeSafeError("Authorization: Bearer test-only-secret")
    provider = TypeSafeDecisionProvider(
        api_key="test-only-secret",
        client=cast(TypeSafeClient, client),
    )

    with pytest.raises(ProviderError) as error:
        provider.decide(make_request())

    assert str(error.value) == "TypeSafe decision request failed"
    assert "test-only-secret" not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(answers={"wrong_answer_key": NoulAnswer(noul=0.7)}),
        SimpleNamespace(answers={"escalate_to_human": {"noul": 0.7}}),
        SimpleNamespace(answers={"escalate_to_human": NoulAnswer.model_construct(noul=1.1)}),
    ],
)
def test_malformed_sdk_result_is_rejected(response: object) -> None:
    client = FakeTypeSafeClient(response)
    provider = TypeSafeDecisionProvider(
        api_key="test-only-key",
        client=cast(TypeSafeClient, client),
    )

    with pytest.raises(ProviderError, match="invalid decision result"):
        provider.decide(make_request())


@pytest.mark.parametrize(
    ("configured_model", "override", "expected_model"),
    [
        ("jev-latest", None, "jev-latest"),
        ("custom-jev-model", None, "custom-jev-model"),
        ("jev-latest", "explicit-model", "explicit-model"),
    ],
)
def test_key_and_model_are_forwarded_to_official_client(
    monkeypatch: pytest.MonkeyPatch,
    configured_model: str,
    override: str | None,
    expected_model: str,
) -> None:
    client = FakeTypeSafeClient(make_response(0.6))
    constructed: dict[str, object] = {}

    def client_factory(*, api_key: str, model: str) -> FakeTypeSafeClient:
        constructed.update(api_key=api_key, model=model)
        return client

    monkeypatch.setattr(settings, "typesafe_api_key", SecretStr("test-only-key"))
    monkeypatch.setattr(settings, "jev_model", configured_model)
    monkeypatch.setattr(typesafe_provider, "TypeSafeClient", client_factory)
    provider = TypeSafeDecisionProvider(model=override)

    provider.decide(make_request())

    assert constructed == {"api_key": "test-only-key", "model": expected_model}
    assert client.calls[0]["model"] == expected_model


def test_provider_satisfies_decision_provider_protocol() -> None:
    provider = TypeSafeDecisionProvider(api_key="test-only-key")

    assert isinstance(provider, DecisionProvider)
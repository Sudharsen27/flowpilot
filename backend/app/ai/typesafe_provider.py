from collections.abc import Mapping
from math import isfinite

from typesafe_sdk import (
    Noul,
    NoulAnswer,
    TypeSafeAPIConnectionError,
    TypeSafeAPIError,
    TypeSafeAPIResponseValidationError,
    TypeSafeAuthenticationError,
    TypeSafeClient,
    TypeSafeError,
    TypeSafeRateLimitError,
)

from app.ai.decision_provider import DecisionProvider, DecisionRequest, DecisionResult
from app.core.config import settings
from app.core.exceptions import ProviderError, ProviderNotConfiguredError, ValidationError

_ESCALATE_DECISION_KEY = "escalate_to_human"
_ESCALATE_QUESTION = "Should this lead be escalated to a human?"


class TypeSafeDecisionProvider(DecisionProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: TypeSafeClient | None = None,
    ) -> None:
        configured_key = settings.typesafe_api_key
        self._api_key = (
            api_key
            if api_key is not None
            else configured_key.get_secret_value()
            if configured_key is not None
            else None
        )
        self._model = model or settings.jev_model
        self._client = client

    def decide(self, request: DecisionRequest) -> DecisionResult:
        if request.decision_key != _ESCALATE_DECISION_KEY:
            raise ValidationError("Unsupported decision key")
        if not self._api_key:
            raise ProviderNotConfiguredError("TYPESAFE_API_KEY is not configured")

        try:
            client = self._client
            if client is None:
                client = TypeSafeClient(api_key=self._api_key, model=self._model)
                self._client = client
            response = client.system_one(
                state={
                    "trusted_context": request.trusted_context,
                    "untrusted_state": request.untrusted_state,
                },
                questions={
                    _ESCALATE_DECISION_KEY: Noul(instructions=_ESCALATE_QUESTION),
                },
                model=self._model,
            )
        except TypeSafeAuthenticationError:
            raise ProviderError("TypeSafe authentication failed") from None
        except TypeSafeRateLimitError:
            raise ProviderError("TypeSafe rate limit exceeded") from None
        except TypeSafeAPIConnectionError:
            raise ProviderError("TypeSafe connection failed") from None
        except TypeSafeAPIResponseValidationError:
            raise ProviderError("TypeSafe returned an invalid response") from None
        except TypeSafeAPIError:
            raise ProviderError("TypeSafe API request failed") from None
        except TypeSafeError:
            raise ProviderError("TypeSafe decision request failed") from None
        except Exception:
            raise ProviderError("TypeSafe decision request failed") from None

        answers = getattr(response, "answers", None)
        if not isinstance(answers, Mapping):
            raise ProviderError("TypeSafe returned an invalid decision result")
        answer = answers.get(_ESCALATE_DECISION_KEY)
        if not isinstance(answer, NoulAnswer):
            raise ProviderError("TypeSafe returned an invalid decision result")

        probability = answer.noul
        if (
            isinstance(probability, bool)
            or not isinstance(probability, (int, float))
            or not isfinite(probability)
            or not 0 <= probability <= 1
        ):
            raise ProviderError("TypeSafe returned an invalid decision result")

        return DecisionResult(value=probability >= 0.5)
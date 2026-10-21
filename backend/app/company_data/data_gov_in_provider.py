from __future__ import annotations

import http.client
import json
import math
import ssl
import urllib.error
import urllib.parse
import urllib.request
from types import TracebackType
from typing import Any, Protocol, cast

import certifi

from app.company_data.provider import (
    CompanyDataAttribution,
    CompanyDataPage,
    CompanyDataProviderError,
    CompanyDataProviderNotConfigured,
    CompanyDataRecord,
)
from app.core.config import settings

ROC_RESOURCE_UUID = "4dbe5667-7b6b-41d7-82af-211562424d9a"
ROC_DATASET_NAME = "Registrars of Companies (RoC)-wise Company Master Data"
ROC_DATASET_ENDPOINT = f"https://api.data.gov.in/resource/{ROC_RESOURCE_UUID}"
ROC_DATASET_ATTRIBUTION = CompanyDataAttribution(
    provider="data.gov.in",
    dataset=ROC_DATASET_NAME,
    resource_uuid=ROC_RESOURCE_UUID,
    endpoint=ROC_DATASET_ENDPOINT,
    attribution=(
        "Government of India, Ministry of Corporate Affairs, via data.gov.in; "
        "Registrars of Companies (RoC)-wise Company Master Data."
    ),
    licensing_status="PENDING_WRITTEN_CLARIFICATION",
)

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_RECORD_FIELDS = 100
_MAX_FIELD_NAME_LENGTH = 200
_MAX_STRING_VALUE_LENGTH = 10_000


class _HTTPResponse(Protocol):
    status: int

    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> _HTTPResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class _OpenRequest(Protocol):
    def __call__(
        self,
        http_request: urllib.request.Request,
        *,
        timeout: float,
    ) -> _HTTPResponse: ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class DataGovInRocCompanyDataProvider:
    """Read-only adapter for the RoC dataset; it has no CRM side effects."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 10,
        max_page_size: int = 100,
        max_offset: int = 100_000,
        request: _OpenRequest | None = None,
    ) -> None:
        if not api_key:
            raise CompanyDataProviderNotConfigured("ROC_DATA_GOV_IN_API_KEY is not configured")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Timeout must be greater than 0 and at most 30 seconds")
        if not 1 <= max_page_size <= 100:
            raise ValueError("Maximum page size must be between 1 and 100")
        if not 0 <= max_offset <= 1_000_000:
            raise ValueError("Maximum offset must be between 0 and 1,000,000")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_page_size = max_page_size
        self._max_offset = max_offset
        if request is None:
            context = ssl.create_default_context(cafile=certifi.where())
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=context),
                _NoRedirectHandler,
            )

            def open_request(
                http_request: urllib.request.Request, *, timeout: float
            ) -> _HTTPResponse:
                return cast(_HTTPResponse, opener.open(http_request, timeout=timeout))

            self._request = open_request
        else:
            self._request = request

    def search(self, *, state_code: str, offset: int, limit: int) -> CompanyDataPage:
        normalized_state_code = self._validate_state_code(state_code)
        self._validate_pagination(offset, limit)
        query = urllib.parse.urlencode(
            [
                ("api-key", self._api_key),
                ("format", "json"),
                ("offset", str(offset)),
                ("limit", str(limit)),
                ("filters[CompanyStateCode]", normalized_state_code),
            ]
        )
        request = urllib.request.Request(
            f"{ROC_DATASET_ENDPOINT}?{query}",
            headers={"Accept": "application/json", "User-Agent": "FlowPilot/0.1"},
            method="GET",
        )
        try:
            with self._request(request, timeout=self._timeout_seconds) as response:
                status_code = response.status
                if status_code < 200 or status_code >= 300:
                    raise CompanyDataProviderError("Company-data provider request failed")
                raw_body = response.read(_MAX_RESPONSE_BYTES + 1)
        except CompanyDataProviderError:
            raise
        except TimeoutError:
            raise CompanyDataProviderError("Company-data provider request timed out") from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise CompanyDataProviderError("Company-data provider request timed out") from None
            raise CompanyDataProviderError("Company-data provider request failed") from None
        except (http.client.HTTPException, OSError):
            raise CompanyDataProviderError("Company-data provider request failed") from None

        if len(raw_body) > _MAX_RESPONSE_BYTES:
            raise CompanyDataProviderError("Company-data provider response exceeded the size limit")
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CompanyDataProviderError("Company-data provider returned invalid JSON") from exc
        records, total = self._validate_payload(payload, limit)
        return CompanyDataPage(
            records=records,
            total=total,
            offset=offset,
            limit=limit,
            attribution=ROC_DATASET_ATTRIBUTION,
        )

    def _validate_state_code(self, state_code: str) -> str:
        if not isinstance(state_code, str):
            raise ValueError("CompanyStateCode must be a string")
        normalized = state_code.strip()
        if not normalized or len(normalized) > 10:
            raise ValueError("CompanyStateCode must contain 1 to 10 characters")
        return normalized

    def _validate_pagination(self, offset: int, limit: int) -> None:
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("Offset must be an integer")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("Limit must be an integer")
        if offset < 0 or offset > self._max_offset:
            raise ValueError("Offset is outside the configured bounds")
        if not 1 <= limit <= self._max_page_size:
            raise ValueError("Limit is outside the configured bounds")

    @staticmethod
    def _validate_payload(
        payload: object, requested_limit: int
    ) -> tuple[tuple[CompanyDataRecord, ...], int | None]:
        if not isinstance(payload, dict):
            raise CompanyDataProviderError("Company-data provider returned invalid output")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list) or len(raw_records) > requested_limit:
            raise CompanyDataProviderError("Company-data provider returned invalid records")

        records: list[CompanyDataRecord] = []
        for raw_record in raw_records:
            if not isinstance(raw_record, dict) or len(raw_record) > _MAX_RECORD_FIELDS:
                raise CompanyDataProviderError("Company-data provider returned invalid records")
            record: CompanyDataRecord = {}
            for key, value in raw_record.items():
                if (
                    not isinstance(key, str)
                    or not key
                    or len(key) > _MAX_FIELD_NAME_LENGTH
                    or not isinstance(value, (str, int, float, bool, type(None)))
                    or isinstance(value, float)
                    and not math.isfinite(value)
                    or isinstance(value, str)
                    and len(value) > _MAX_STRING_VALUE_LENGTH
                ):
                    raise CompanyDataProviderError("Company-data provider returned invalid records")
                record[key] = value
            records.append(record)

        raw_total = payload.get("total")
        if raw_total is not None and (
            isinstance(raw_total, bool) or not isinstance(raw_total, int) or raw_total < 0
        ):
            raise CompanyDataProviderError("Company-data provider returned invalid pagination data")
        return tuple(records), raw_total


def get_roc_company_data_provider() -> DataGovInRocCompanyDataProvider:
    if not settings.roc_data_gov_in_provider_enabled:
        raise CompanyDataProviderNotConfigured("The RoC data provider is disabled")
    api_key = settings.roc_data_gov_in_api_key
    if api_key is None:
        raise CompanyDataProviderNotConfigured("ROC_DATA_GOV_IN_API_KEY is not configured")
    return DataGovInRocCompanyDataProvider(
        api_key=api_key.get_secret_value(),
        timeout_seconds=settings.roc_data_gov_in_request_timeout_seconds,
        max_page_size=settings.roc_data_gov_in_max_page_size,
        max_offset=settings.roc_data_gov_in_max_offset,
    )

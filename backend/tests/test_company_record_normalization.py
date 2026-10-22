from datetime import UTC, date, datetime

import pytest

from app.company_data.data_gov_in_provider import ROC_DATASET_ATTRIBUTION
from app.company_data.normalized_company import (
    NormalizedCompanyRecord,
    normalize_company_record,
)
from app.company_data.schemas import GovernmentCompanyDiscoveryResponse

RETRIEVED_AT = datetime(2026, 10, 22, 7, 52, 45, tzinfo=UTC)


def _normalize(record: dict[str, object]) -> NormalizedCompanyRecord:
    return normalize_company_record(
        record,
        attribution=ROC_DATASET_ATTRIBUTION,
        retrieved_at=RETRIEVED_AT,
    )


def test_normalizes_valid_source_fields_without_mutating_raw_record() -> None:
    record = {
        "CorporateIdentificationNumber": " u12345dl2001plc123456 ",
        "CompanyName": "  Example\t Registry \n Company  ",
        "CompanyStatus": " Active   ",
        "AuthorizedCapital": " 100000 ",
        "DateOfIncorporation": "01/01/2001",
        "CompanyStateCode": " DL ",
        "UnusedSourceField": "unchanged",
    }
    original = record.copy()

    normalized = _normalize(record)

    assert normalized.cin == "U12345DL2001PLC123456"
    assert normalized.company_name == "Example Registry Company"
    assert normalized.company_status == "Active"
    assert normalized.authorized_capital == "100000"
    assert normalized.date_of_incorporation == date(2001, 1, 1)
    assert normalized.company_state_code == "DL"
    assert normalized.attribution == ROC_DATASET_ATTRIBUTION
    assert normalized.retrieved_at == RETRIEVED_AT
    assert record == original


@pytest.mark.parametrize(
    ("source_value", "expected"),
    [
        ("01/02/2003", date(2003, 2, 1)),
        ("2003-02-01", date(2003, 2, 1)),
        ("01-02-2003", date(2003, 2, 1)),
    ],
)
def test_accepts_supported_registration_date_formats(
    source_value: str, expected: date
) -> None:
    assert _normalize({"DateOfIncorporation": source_value}).date_of_incorporation == expected


def test_incomplete_record_has_safe_empty_optional_fields() -> None:
    normalized = _normalize({})

    assert normalized.cin is None
    assert normalized.company_name is None
    assert normalized.date_of_incorporation is None
    assert normalized.company_state_code is None
    assert normalized.attribution.provider == "data.gov.in"
    assert normalized.retrieved_at == RETRIEVED_AT


def test_malformed_optional_fields_are_omitted_without_rejecting_record() -> None:
    normalized = _normalize(
        {
            "CorporateIdentificationNumber": "not-a-cin",
            "CompanyName": 123,
            "DateOfIncorporation": "31/02/2001",
            "CompanyStatus": {"unexpected": "object"},
            "AuthorizedCapital": 100000,
            "PaidUpCapital": float("nan"),
        }
    )

    assert normalized.cin is None
    assert normalized.company_name is None
    assert normalized.date_of_incorporation is None
    assert normalized.company_status is None
    assert normalized.authorized_capital == 100000
    assert normalized.paid_up_capital is None


def test_duplicate_looking_records_are_normalized_but_not_deduplicated() -> None:
    records = [
        {"CompanyName": "  Example   Company ", "CIN": "U12345DL2001PLC123456"},
        {"CompanyName": "Example Company", "CIN": "U12345DL2001PLC123456"},
    ]

    normalized = [_normalize(record) for record in records]

    assert len(normalized) == 2
    assert [record.company_name for record in normalized] == [
        "Example Company",
        "Example Company",
    ]
    assert normalized[0].cin == normalized[1].cin


def test_response_schema_accepts_legacy_raw_only_payloads() -> None:
    response = GovernmentCompanyDiscoveryResponse(
        source="GOVERNMENT",
        items=[{"CIN": "U12345DL2001PLC123456"}],
        total=1,
        offset=0,
        page_size=1,
        has_more=False,
        next_offset=None,
        attribution=ROC_DATASET_ATTRIBUTION,
    )

    assert response.items == [{"CIN": "U12345DL2001PLC123456"}]
    assert response.normalized_items == []

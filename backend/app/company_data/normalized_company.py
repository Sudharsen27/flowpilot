import math
import re
from collections.abc import Mapping
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.company_data.provider import CompanyDataAttribution, CompanyDataScalar

_CIN_PATTERN = re.compile(r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")
_DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


class NormalizedCompanyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cin: str | None
    company_name: str | None
    company_status: CompanyDataScalar
    company_class: CompanyDataScalar
    company_category: CompanyDataScalar
    company_sub_category: CompanyDataScalar
    authorized_capital: CompanyDataScalar
    paid_up_capital: CompanyDataScalar
    number_of_members: CompanyDataScalar
    date_of_incorporation: date | None
    registered_address: CompanyDataScalar
    company_state_code: CompanyDataScalar
    registrar_of_companies: CompanyDataScalar
    principal_business_activity: CompanyDataScalar
    industrial_classification_code: CompanyDataScalar
    attribution: CompanyDataAttribution
    retrieved_at: datetime


_SOURCE_FIELDS: dict[str, tuple[str, ...]] = {
    "cin": ("CorporateIdentificationNumber", "CIN"),
    "company_name": ("CompanyName",),
    "company_status": ("CompanyStatus",),
    "company_class": ("CompanyClass",),
    "company_category": ("CompanyCategory",),
    "company_sub_category": ("CompanySubCategory", "CompanySubcategory"),
    "authorized_capital": ("AuthorizedCapital",),
    "paid_up_capital": ("PaidUpCapital", "PaidupCapital"),
    "number_of_members": ("NumberOfMembers",),
    "date_of_incorporation": ("DateOfIncorporation",),
    "registered_address": ("RegisteredAddress",),
    "company_state_code": ("CompanyStateCode",),
    "registrar_of_companies": ("RegistrarOfCompanies", "CompanyROCCode"),
    "principal_business_activity": ("PrincipalBusinessActivity", "ActivityDescription"),
    "industrial_classification_code": (
        "IndustrialClassificationCode",
        "ActivityCode",
    ),
}


def _source_value(record: Mapping[str, object], field: str) -> object:
    for source_key in _SOURCE_FIELDS[field]:
        if source_key in record:
            return record[source_key]
    return None


def _normalized_scalar(value: object) -> CompanyDataScalar:
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized or None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return None


def _normalized_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _normalized_cin(value: object) -> str | None:
    normalized = _normalized_text(value)
    if normalized is None:
        return None
    normalized = normalized.upper()
    return normalized if _CIN_PATTERN.fullmatch(normalized) else None


def _normalized_date(value: object) -> date | None:
    normalized = _normalized_text(value)
    if normalized is None:
        return None
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(normalized, date_format).date()
        except ValueError:
            continue
    return None


def normalize_company_record(
    record: Mapping[str, object],
    *,
    attribution: CompanyDataAttribution,
    retrieved_at: datetime,
) -> NormalizedCompanyRecord:
    """Map source-reported fields without modifying the original provider record."""
    return NormalizedCompanyRecord(
        cin=_normalized_cin(_source_value(record, "cin")),
        company_name=_normalized_text(_source_value(record, "company_name")),
        company_status=_normalized_scalar(_source_value(record, "company_status")),
        company_class=_normalized_scalar(_source_value(record, "company_class")),
        company_category=_normalized_scalar(_source_value(record, "company_category")),
        company_sub_category=_normalized_scalar(_source_value(record, "company_sub_category")),
        authorized_capital=_normalized_scalar(_source_value(record, "authorized_capital")),
        paid_up_capital=_normalized_scalar(_source_value(record, "paid_up_capital")),
        number_of_members=_normalized_scalar(_source_value(record, "number_of_members")),
        date_of_incorporation=_normalized_date(
            _source_value(record, "date_of_incorporation")
        ),
        registered_address=_normalized_scalar(_source_value(record, "registered_address")),
        company_state_code=_normalized_scalar(_source_value(record, "company_state_code")),
        registrar_of_companies=_normalized_scalar(
            _source_value(record, "registrar_of_companies")
        ),
        principal_business_activity=_normalized_scalar(
            _source_value(record, "principal_business_activity")
        ),
        industrial_classification_code=_normalized_scalar(
            _source_value(record, "industrial_classification_code")
        ),
        attribution=attribution,
        retrieved_at=retrieved_at,
    )

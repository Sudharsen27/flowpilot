from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict

type CompanyDataScalar = str | int | float | bool | None
type CompanyDataRecord = dict[str, CompanyDataScalar]


class CompanyDataProviderError(Exception):
    """A company-data provider failed without exposing upstream details."""


class CompanyDataProviderNotConfigured(CompanyDataProviderError):
    """The provider is disabled or required server configuration is absent."""


class CompanyDataAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    dataset: str
    resource_uuid: str
    endpoint: str
    attribution: str
    licensing_status: str


@dataclass(frozen=True)
class CompanyDataPage:
    records: tuple[CompanyDataRecord, ...]
    total: int | None
    offset: int
    limit: int
    attribution: CompanyDataAttribution


class CompanyDataProvider(Protocol):
    def search(
        self,
        *,
        state_code: str,
        offset: int,
        limit: int,
    ) -> CompanyDataPage:
        """Return a bounded page of company records for one state code."""
        ...

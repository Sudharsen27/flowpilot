from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Protocol

from app.schemas.prospect_discovery import (
    ProspectDiscoveryBusinessResult,
    ProspectDiscoverySearchRequest,
    ProspectDiscoverySearchResponse,
)

_CURSOR_VERSION = 1
_MAX_CURSOR_PAGE = 10_000
_CURSOR_PART_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class DiscoveryCursorError(ValueError):
    """A search cursor is malformed, expired, or bound to another search."""


class DiscoveryProviderError(Exception):
    """A provider failed without exposing implementation details to API clients."""


@dataclass(frozen=True)
class DiscoveredBusiness:
    name: str
    industry: str
    country: str
    region: str
    employee_count: int
    description: str


SYNTHETIC_BUSINESSES: tuple[DiscoveredBusiness, ...] = (
    DiscoveredBusiness("Aster Forge Systems", "Manufacturing", "United States", "Texas", 180,
                       "Builds precision components for industrial equipment."),
    DiscoveredBusiness("Bluefern Clinical Group", "Healthcare", "United States", "New York", 95,
                       "Operates a fictional network of specialty care clinics."),
    DiscoveredBusiness("Cedarline Ledger", "Financial Services", "Canada", "Ontario", 240,
                       "Develops accounting and payment tools for small businesses."),
    DiscoveredBusiness("Cloudberry Metrics", "Software", "United Kingdom", "England", 68,
                       "Creates analytics software for subscription businesses."),
    DiscoveredBusiness("Copperleaf Studio", "Professional Services", "Australia", "Victoria", 32,
                       "Provides fictional operations consulting to regional companies."),
    DiscoveredBusiness("Dovetail Robotics", "Manufacturing", "United States", "California", 520,
                       "Designs automation equipment for warehouse operations."),
    DiscoveredBusiness("Emberwell Health", "Healthcare", "India", "Karnataka", 410,
                       "Builds care coordination tools for fictional health providers."),
    DiscoveredBusiness("Fablepoint Systems", "Software", "Canada", "British Columbia", 125,
                       "Builds workflow software for professional teams."),
    DiscoveredBusiness("Greenstone Advisory", "Professional Services", "United Kingdom", "Scotland",
                       47, "Offers fictional risk and compliance advisory services."),
    DiscoveredBusiness("Harborlight Payments", "Financial Services", "Australia", "New South Wales",
                       310, "Provides payment processing technology for merchants."),
    DiscoveredBusiness("Juniper Circuit Works", "Manufacturing", "India", "Maharashtra", 760,
                       "Produces fictional electronic assemblies for equipment makers."),
    DiscoveredBusiness("Kitepath Software", "Software", "United States", "New York", 22,
                       "Develops planning software for distributed teams."),
    DiscoveredBusiness("Lumenwell Practice", "Healthcare", "Canada", "Ontario", 74,
                       "Provides fictional outpatient and diagnostic services."),
    DiscoveredBusiness("Morrowfield Partners", "Professional Services", "United States", "Texas",
                       165, "Delivers fictional business process and strategy consulting."),
    DiscoveredBusiness("Northwind Ledgerworks", "Financial Services", "United Kingdom", "England",
                       88, "Builds fictional compliance software for financial institutions."),
    DiscoveredBusiness("Openridge Fabrication", "Manufacturing", "Australia", "Victoria", 290,
                       "Produces configurable equipment for commercial facilities."),
    DiscoveredBusiness("Pinecone Data Lab", "Software", "India", "Karnataka", 340,
                       "Builds data management tools for mid-sized organizations."),
    DiscoveredBusiness("Quarryside Health", "Healthcare", "United States", "California", 130,
                       "Operates fictional community health and wellness services."),
)


class DiscoveryProvider(Protocol):
    def search(
        self,
        filters: ProspectDiscoverySearchRequest,
        *,
        offset: int,
        limit: int,
    ) -> list[DiscoveredBusiness]: ...


class SyntheticDiscoveryProvider:
    """Stable, in-memory fixtures; this adapter never makes network requests."""

    def search(
        self,
        filters: ProspectDiscoverySearchRequest,
        *,
        offset: int,
        limit: int,
    ) -> list[DiscoveredBusiness]:
        matches = (
            business
            for business in SYNTHETIC_BUSINESSES
            if (filters.industry is None or business.industry == filters.industry)
            and (filters.country is None or business.country == filters.country)
            and (filters.region is None or business.region == filters.region)
            and (
                filters.minimum_employees is None
                or business.employee_count >= filters.minimum_employees
            )
            and (
                filters.maximum_employees is None
                or business.employee_count <= filters.maximum_employees
            )
        )
        return list(matches)[offset : offset + limit]


class ProspectDiscoveryService:
    def __init__(
        self,
        provider: DiscoveryProvider,
        *,
        secret_key: str,
        max_page_size: int,
        cursor_ttl_seconds: int = 900,
    ) -> None:
        self.provider = provider
        self.secret_key = secret_key
        self.max_page_size = max_page_size
        self.cursor_ttl_seconds = cursor_ttl_seconds

    def search(
        self, organization_id: str, request: ProspectDiscoverySearchRequest
    ) -> ProspectDiscoverySearchResponse:
        if request.page_size > self.max_page_size:
            raise ValueError("Page size exceeds the configured maximum")
        filters = request.model_dump(
            exclude={"page_size", "cursor"},
            mode="json",
        )
        page_index = self._decode_cursor(
            request.cursor, organization_id, filters, request.page_size
        )
        offset = page_index * request.page_size
        rows = self.provider.search(request, offset=offset, limit=request.page_size + 1)
        has_more = len(rows) > request.page_size
        page = rows[: request.page_size]
        results = [
            ProspectDiscoveryBusinessResult(
                name=business.name,
                industry=business.industry,
                country=business.country,
                region=business.region,
                employee_count=business.employee_count,
                description=business.description,
                match_explanations=self._explanations(request, business),
            )
            for business in page
        ]
        next_cursor = (
            self._encode_cursor(
                organization_id,
                filters,
                page_index + 1,
                request.page_size,
            )
            if has_more
            else None
        )
        return ProspectDiscoverySearchResponse(
            source="SYNTHETIC",
            items=results,
            page_size=request.page_size,
            has_more=has_more,
            next_cursor=next_cursor,
        )

    def _explanations(
        self, request: ProspectDiscoverySearchRequest, business: DiscoveredBusiness
    ) -> list[str]:
        explanations: list[str] = []
        if request.industry is not None:
            explanations.append(f"Industry matches {business.industry}.")
        if request.country is not None:
            location = business.country
            if request.region is not None:
                location = f"{business.region}, {location}"
            explanations.append(f"Geography matches {location}.")
        if request.minimum_employees is not None or request.maximum_employees is not None:
            explanations.append(
                f"Employee count ({business.employee_count}) is within the requested range."
            )
        if not explanations:
            explanations.append("Included in the fixed synthetic discovery dataset.")
        return explanations

    def _cursor_signing_key(self) -> bytes:
        return hmac.new(
            self.secret_key.encode("utf-8"),
            b"flowpilot:prospect-discovery:cursor:v1",
            hashlib.sha256,
        ).digest()

    def _encode_cursor(
        self,
        organization_id: str,
        filters: dict[str, object],
        page_index: int,
        page_size: int,
    ) -> str:
        payload = json.dumps(
            {
                "version": _CURSOR_VERSION,
                "organization_id": organization_id,
                "filters": filters,
                "page": page_index,
                "page_size": page_size,
                "expires_at": int(time.time()) + self.cursor_ttl_seconds,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
        signature = hmac.new(
            self._cursor_signing_key(), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        return f"{encoded_payload}.{encoded_signature}"

    def _decode_cursor(
        self,
        cursor: str | None,
        organization_id: str,
        filters: dict[str, object],
        page_size: int,
    ) -> int:
        if cursor is None:
            return 0
        if len(cursor) > 1024 or cursor.count(".") != 1:
            raise DiscoveryCursorError("Invalid discovery cursor")
        encoded_payload, encoded_signature = cursor.split(".", maxsplit=1)
        valid_parts = (
            _CURSOR_PART_PATTERN.fullmatch(encoded_payload)
            and _CURSOR_PART_PATTERN.fullmatch(encoded_signature)
        )
        if not valid_parts:
            raise DiscoveryCursorError("Invalid discovery cursor")
        expected_signature = hmac.new(
            self._cursor_signing_key(), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        try:
            supplied_signature = base64.b64decode(
                encoded_signature + "=" * (-len(encoded_signature) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise DiscoveryCursorError("Invalid discovery cursor") from exc
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise DiscoveryCursorError("Invalid discovery cursor")
        try:
            payload_bytes = base64.b64decode(
                encoded_payload + "=" * (-len(encoded_payload) % 4),
                altchars=b"-_",
                validate=True,
            )
            payload = json.loads(payload_bytes)
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise DiscoveryCursorError("Invalid discovery cursor") from exc
        if not isinstance(payload, dict):
            raise DiscoveryCursorError("Invalid discovery cursor")
        page_index = payload.get("page")
        expiry = payload.get("expires_at")
        if (
            payload.get("version") != _CURSOR_VERSION
            or payload.get("organization_id") != organization_id
            or payload.get("filters") != filters
            or payload.get("page_size") != page_size
            or isinstance(page_index, bool)
            or not isinstance(page_index, int)
            or not 1 <= page_index <= _MAX_CURSOR_PAGE
            or isinstance(expiry, bool)
            or not isinstance(expiry, int)
            or expiry <= int(time.time())
        ):
            raise DiscoveryCursorError("Invalid or expired discovery cursor")
        return page_index


def get_discovery_service() -> ProspectDiscoveryService:
    from app.core.config import settings

    return ProspectDiscoveryService(
        SyntheticDiscoveryProvider(),
        secret_key=settings.secret_key,
        max_page_size=settings.prospect_discovery_max_page_size,
        cursor_ttl_seconds=settings.prospect_discovery_cursor_ttl_seconds,
    )

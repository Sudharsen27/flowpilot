from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.company_prospect import CompanyProspect
from app.models.lead import Lead
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from app.schemas.company_duplicate_assessment import (
    CompanyDuplicateCandidateInput,
    DuplicateAssessmentOutcome,
)
from app.services.company_duplicate_assessment_service import (
    CompanyDuplicateAssessmentService,
    company_name_similarity,
    normalize_cin,
    normalize_company_name,
    normalize_website_domain,
)
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth


class MockPersistedRecord:
    def __init__(self, id: str, name: str, website_domain: str | None = None) -> None:
        self.id = id
        self.name = name
        self.website_domain = website_domain


def _assess_domain(
    candidates: list[dict[str, Any]],
    persisted: list[Any] | None = None,
) -> Any:
    service = CompanyDuplicateAssessmentService()
    candidate_inputs = [CompanyDuplicateCandidateInput.model_validate(c) for c in candidates]
    return service.assess_candidates(candidate_inputs, persisted or [])


# ---------------------------------------------------------------------------
# 1. Domain Normalization & Strict Validation Tests
# ---------------------------------------------------------------------------

def test_normalize_website_domain_strict_validation() -> None:
    # Valid canonical inputs
    assert normalize_website_domain("example.com") == "example.com"
    assert normalize_website_domain("  EXAMPLE.COM.  ") == "example.com"
    assert normalize_website_domain("sub.domain.example.co.uk") == "sub.domain.example.co.uk"

    # URL prefixes with supported schemes retain exact hostname identity
    assert normalize_website_domain("https://example.com") == "example.com"
    assert normalize_website_domain("http://example.com/") == "example.com"
    assert normalize_website_domain("https://www.example.com") == "www.example.com"
    assert (
        normalize_website_domain("http://www.example.com/about?query=1#hash")
        == "www.example.com"
    )

    # Hostname suffix confusion: must preserve exact equality, never suffix matching
    assert normalize_website_domain("example.com") != normalize_website_domain("notexample.com")
    assert normalize_website_domain("example.com") != normalize_website_domain("myexample.com")
    assert normalize_website_domain("example.com") != normalize_website_domain("sub.example.com")
    assert normalize_website_domain("example.com") != normalize_website_domain("www.example.com")

    # Strict rejection of ambiguous or malformed inputs
    # Without scheme: userinfo, ports, paths, and queries are rejected as matching evidence
    assert normalize_website_domain("user@example.com") is None
    assert normalize_website_domain("example.com:8080") is None
    assert normalize_website_domain("example.com/path") is None
    assert normalize_website_domain("example.com?query=1") is None
    assert normalize_website_domain("example.com#section") is None
    assert normalize_website_domain("example.com..") is None
    assert normalize_website_domain("example.com\t") is None

    # Unsupported schemes
    assert normalize_website_domain("ftp://example.com") is None
    assert normalize_website_domain("javascript:alert(1)") is None
    assert normalize_website_domain("file:///etc/hosts") is None

    # URLs with ambiguous userinfo or port
    assert normalize_website_domain("https://user:pass@example.com") is None
    assert normalize_website_domain("https://example.com:8080") is None
    assert normalize_website_domain("https://example.com:") is None
    assert normalize_website_domain("https://@example.com") is None
    assert normalize_website_domain("https://user@example.com") is None

    # Invalid host syntax
    assert normalize_website_domain("") is None
    assert normalize_website_domain("   ") is None
    assert normalize_website_domain(123) is None
    assert normalize_website_domain("http://") is None
    assert normalize_website_domain("https://") is None
    assert normalize_website_domain("192.168.1.1") is None
    assert normalize_website_domain("example..com") is None
    assert normalize_website_domain("a" * 255 + ".com") is None


def test_normalize_cin_validation() -> None:
    # Valid 21-char CINs
    assert normalize_cin("U12345DL2001PLC123456") == "U12345DL2001PLC123456"
    assert normalize_cin("  u12345dl2001plc123456  ") == "U12345DL2001PLC123456"
    assert normalize_cin("L99999MH2020PTC999999") == "L99999MH2020PTC999999"

    # Malformed / invalid CINs
    assert normalize_cin("not-a-cin") is None
    assert normalize_cin("12345") is None
    assert normalize_cin("U12345DL2001PLC12345") is None  # 20 chars
    assert normalize_cin("U12345DL2001PLC1234567") is None  # 22 chars
    assert normalize_cin("X12345DL2001PLC123456") is None  # Starts with X (must be L or U)
    assert normalize_cin("") is None
    assert normalize_cin(None) is None


def test_normalize_company_name_and_preservation_of_meaningful_terms() -> None:
    # Trailing legal suffixes stripped
    assert normalize_company_name("Acme Technologies Private Limited") == "acme technologies"
    assert normalize_company_name("Acme Corp Pvt Ltd") == "acme"
    assert normalize_company_name("Acme Solutions Inc.") == "acme solutions"
    assert normalize_company_name("Acme Services LLC") == "acme services"

    # Meaningful business terms are preserved
    name = normalize_company_name("Global Tech Solutions Enterprises Group")
    assert name == "global tech solutions enterprises group"

    # Empty / too short
    assert normalize_company_name("") is None
    assert normalize_company_name("   ") is None
    assert normalize_company_name("A") is None


# ---------------------------------------------------------------------------
# 2. Name Similarity Threshold & Boundary Tests
# ---------------------------------------------------------------------------

def test_company_name_similarity_boundary_thresholds() -> None:
    # Ratio 1.00: Identical normalized names
    n1 = normalize_company_name("Acme Technologies")
    n2 = normalize_company_name("Acme Technologies Ltd")
    assert n1 is not None and n2 is not None
    assert company_name_similarity(n1, n2) == 1.0

    # Ratio >= 0.85: Typo above threshold
    n_a = normalize_company_name("Acme Logistics Global")
    n_b = normalize_company_name("Acme Logistic Global")
    assert n_a is not None and n_b is not None
    sim_above = company_name_similarity(n_a, n_b)
    assert sim_above >= 0.85

    # Ratio < 0.85: Below threshold
    n_c = normalize_company_name("Acme Group")
    n_d = normalize_company_name("Acme Cloud")
    assert n_c is not None and n_d is not None
    sim_below = company_name_similarity(n_c, n_d)
    assert sim_below < 0.85


# ---------------------------------------------------------------------------
# 3. Domain Matching & Decision Precedence Tests
# ---------------------------------------------------------------------------

def test_exact_persisted_domain_match() -> None:
    persisted = [MockPersistedRecord(id="p-1", name="Acme Inc", website_domain="acme.com")]
    response = _assess_domain(
        [
            {
                "reference_id": "c-1",
                "company_name": "Different Label",
                "website_domain": "https://ACME.COM/path",
            }
        ],
        persisted=persisted,
    )
    assert response.total_evaluated == 1
    assert response.persisted_cin_available is False
    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.EXACT_MATCH
    assert item.reason_code == "PERSISTED_DOMAIN_MATCH"
    assert item.matching_fields == ["website_domain"]
    assert item.existing_match_references == ["p-1"]
    assert "Persisted CIN matching was not performed" in item.explanation


def test_persisted_domain_matching_preserves_www_hostname_difference() -> None:
    persisted = [
        MockPersistedRecord(id="p-www", name="Unrelated Name", website_domain="www.acme.com")
    ]
    response = _assess_domain(
        [
            {
                "reference_id": "c-apex",
                "company_name": "A Completely Different Company",
                "website_domain": "https://acme.com",
            }
        ],
        persisted=persisted,
    )

    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.NEW
    assert item.existing_match_references == []


def test_persisted_name_similarity_produces_possible_duplicate_never_exact() -> None:
    persisted = [
        MockPersistedRecord(id="p-1", name="Acme Technologies Pvt Ltd", website_domain="acme.com")
    ]
    # Identical company name, but no domain match
    response = _assess_domain(
        [
            {
                "reference_id": "c-1",
                "company_name": "Acme Technologies Limited",
                "website_domain": "other.com",
            }
        ],
        persisted=persisted,
    )
    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE
    assert item.reason_code == "PERSISTED_NAME_SIMILARITY"
    assert item.matching_fields == ["company_name"]
    assert item.existing_match_references == ["p-1"]


def test_missing_cin_evidence_never_causes_candidate_to_be_classified_as_new() -> None:
    persisted = [MockPersistedRecord(id="p-1", name="Alpha Solutions Ltd", website_domain=None)]
    # Candidate provides a valid CIN, but no domain. Persisted record lacks CIN.
    # Name matches persisted record -> MUST be POSSIBLE_DUPLICATE, NEVER NEW!
    response = _assess_domain(
        [
            {
                "reference_id": "c-1",
                "company_name": "Alpha Solutions",
                "cin": "U12345DL2001PLC123456",
                "website_domain": None,
            }
        ],
        persisted=persisted,
    )
    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE
    assert item.reason_code == "PERSISTED_NAME_SIMILARITY"
    assert item.existing_match_references == ["p-1"]


def test_in_batch_exact_cin_match_and_earliest_occurrence_reference() -> None:
    candidates = [
        {
            "reference_id": "c-first",
            "company_name": "First Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "first.com",
        },
        {
            "reference_id": "c-second",
            "company_name": "Second Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "first.com",
        },
        {
            "reference_id": "c-third",
            "company_name": "Third Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "first.com",
        },
    ]
    response = _assess_domain(candidates)
    assert response.assessments[0].outcome == DuplicateAssessmentOutcome.NEW
    # Second candidate matches first candidate
    assert response.assessments[1].outcome == DuplicateAssessmentOutcome.EXACT_MATCH
    assert response.assessments[1].reason_code == "IN_BATCH_CIN_AND_DOMAIN_MATCH"
    assert response.assessments[1].in_batch_match_reference == "c-first"
    # Third candidate deterministically references the earliest occurrence (c-first)
    assert response.assessments[2].outcome == DuplicateAssessmentOutcome.EXACT_MATCH
    assert response.assessments[2].in_batch_match_reference == "c-first"


def test_identical_in_batch_candidates_always_reference_the_first_match() -> None:
    candidates = [
        {
            "reference_id": f"c-{index}",
            "company_name": f"Candidate {index}",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "same.example.com",
        }
        for index in range(1, 5)
    ]

    response = _assess_domain(candidates)

    assert response.assessments[0].outcome == DuplicateAssessmentOutcome.NEW
    assert [item.outcome for item in response.assessments[1:]] == [
        DuplicateAssessmentOutcome.EXACT_MATCH,
        DuplicateAssessmentOutcome.EXACT_MATCH,
        DuplicateAssessmentOutcome.EXACT_MATCH,
    ]
    assert [item.reason_code for item in response.assessments[1:]] == [
        "IN_BATCH_CIN_AND_DOMAIN_MATCH",
        "IN_BATCH_CIN_AND_DOMAIN_MATCH",
        "IN_BATCH_CIN_AND_DOMAIN_MATCH",
    ]
    assert [item.in_batch_match_reference for item in response.assessments[1:]] == [
        "c-1",
        "c-1",
        "c-1",
    ]


def test_shared_exact_match_does_not_hide_a_conflicting_identifier() -> None:
    candidates = [
        {
            "reference_id": "c-first",
            "company_name": "First Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "first.example.com",
        },
        {
            "reference_id": "c-conflict",
            "company_name": "Conflicting Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "other.example.com",
        },
        {
            "reference_id": "c-repeat",
            "company_name": "Repeated Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "first.example.com",
        },
    ]

    response = _assess_domain(candidates)

    item = response.assessments[2]
    assert item.outcome == DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE
    assert item.reason_code == "CONFLICTING_IDENTIFIERS"
    assert item.in_batch_match_reference == "c-conflict"


def test_in_batch_resolution_is_deterministic_with_persisted_domain_matches() -> None:
    persisted = [
        MockPersistedRecord(id="p-z", name="Persisted Z", website_domain="other.example.com"),
        MockPersistedRecord(id="p-a", name="Persisted A", website_domain="same.example.com"),
    ]
    candidates = [
        {
            "reference_id": "c-first",
            "company_name": "First Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "same.example.com",
        },
        {
            "reference_id": "c-repeat",
            "company_name": "Repeated Candidate",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "same.example.com",
        },
    ]

    first = _assess_domain(candidates, persisted=persisted)
    second = _assess_domain(candidates, persisted=list(reversed(persisted)))

    for response in (first, second):
        assert [item.outcome for item in response.assessments] == [
            DuplicateAssessmentOutcome.EXACT_MATCH,
            DuplicateAssessmentOutcome.EXACT_MATCH,
        ]
        assert [item.existing_match_references for item in response.assessments] == [
            ["p-a"],
            ["p-a"],
        ]
        assert response.assessments[1].in_batch_match_reference is None


def test_conflicting_identifiers_in_batch_candidates() -> None:
    # Candidate 2 has same CIN as Candidate 1, but a conflicting domain
    candidates = [
        {
            "reference_id": "c-1",
            "company_name": "Entity One",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "one.com",
        },
        {
            "reference_id": "c-2",
            "company_name": "Entity Two",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "two.com",
        },
    ]
    response = _assess_domain(candidates)
    item = response.assessments[1]
    assert item.outcome == DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE
    assert item.reason_code == "CONFLICTING_IDENTIFIERS"
    assert item.in_batch_match_reference == "c-1"


def test_cross_record_conflict_persisted_domain_and_in_batch_cin() -> None:
    persisted = [MockPersistedRecord(id="p-1", name="Persisted Co", website_domain="persisted.com")]
    candidates = [
        {
            "reference_id": "c-1",
            "company_name": "Batch Co",
            "cin": "U12345DL2001PLC123456",
            "website_domain": "batch.com",
        },
        {
            "reference_id": "c-2",
            "company_name": "Conflicting Candidate",
            "cin": "U12345DL2001PLC123456",  # matches c-1
            "website_domain": "persisted.com",  # matches p-1
        },
    ]
    response = _assess_domain(candidates, persisted=persisted)
    item = response.assessments[1]
    assert item.outcome == DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE
    assert item.reason_code == "CONFLICTING_IDENTIFIERS"
    assert item.existing_match_references == ["p-1"]
    assert item.in_batch_match_reference == "c-1"


def test_multiple_persisted_name_matches() -> None:
    persisted = [
        MockPersistedRecord(id="p-1", name="Apex Logistics Inc"),
        MockPersistedRecord(id="p-2", name="Apex Logistics Pvt Ltd"),
    ]
    candidates = [
        {
            "reference_id": "c-1",
            "company_name": "Apex Logistics Limited",
            "website_domain": "apex-logistics.com",
        }
    ]
    response = _assess_domain(candidates, persisted=persisted)
    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE
    assert item.reason_code == "MULTIPLE_NAME_MATCHES"
    assert item.existing_match_references == ["p-1", "p-2"]  # sorted deterministically


def test_insufficient_evidence_when_identifiers_and_name_are_missing() -> None:
    candidates = [
        {
            "reference_id": "c-empty",
            "company_name": "   ",
            "website_domain": None,
            "cin": "not-a-cin",
        }
    ]
    response = _assess_domain(candidates)
    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.INSUFFICIENT_DATA
    assert item.reason_code == "INSUFFICIENT_EVIDENCE"
    assert item.matching_fields == []
    assert item.existing_match_references == []


def test_new_candidate_accurate_semantics() -> None:
    candidates = [
        {
            "reference_id": "c-new",
            "company_name": "Unheard Of Enterprises",
            "website_domain": "unheardof.com",
            "cin": "U99999MH2025PTC111111",
        }
    ]
    response = _assess_domain(candidates)
    item = response.assessments[0]
    assert item.outcome == DuplicateAssessmentOutcome.NEW
    assert item.reason_code == "NO_MATCHING_RECORDS"
    assert "No matching record was found using the supported evidence evaluated here" in (
        item.explanation
    )
    assert "does not establish that the company is definitively new" in item.explanation
    assert "Persisted CIN matching is unavailable" in item.explanation
    assert response.persisted_cin_available is False


# ---------------------------------------------------------------------------
# 4. API, Security & Side-Effect Tests
# ---------------------------------------------------------------------------

def test_api_unauthenticated_request_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={"candidates": [{"reference_id": "1", "company_name": "Test"}]},
    )
    assert response.status_code == 401


def test_api_tenant_isolation_cross_tenant_records_never_exposed(client: TestClient) -> None:
    tenant_a = _auth(client, email="tenant_a@example.com", organization_name="Tenant A")
    tenant_b = _auth(client, email="tenant_b@example.com", organization_name="Tenant B")

    # Tenant B creates a prospect
    create_resp = client.post(
        "/api/v1/company-prospects",
        json={"name": "Secret B Corp", "website_domain": "secret-b.example.com"},
        headers=_headers(tenant_b["access_token"]),
    )
    assert create_resp.status_code == 201
    tenant_b_prospect_id = create_resp.json()["id"]

    # Tenant A evaluates a candidate with secret-b.example.com
    eval_resp = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={
            "candidates": [
                {
                    "reference_id": "cand-test",
                    "company_name": "Secret B Corp",
                    "website_domain": "secret-b.example.com",
                }
            ]
        },
        headers=_headers(tenant_a["access_token"]),
    )
    assert eval_resp.status_code == 200
    body = eval_resp.json()
    assert body["total_evaluated"] == 1
    item = body["assessments"][0]
    # Tenant A must NOT match Tenant B's prospect
    assert item["outcome"] == "NEW"
    assert tenant_b_prospect_id not in item["existing_match_references"]
    assert item["existing_match_references"] == []


def test_api_validation_extra_fields_and_oversized_batches(client: TestClient) -> None:
    auth = _auth(client)
    token = auth["access_token"]

    # Forged organization_id / extra field
    resp_extra = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={
            "organization_id": "forged-id",
            "candidates": [{"reference_id": "1", "company_name": "Test"}],
        },
        headers=_headers(token),
    )
    assert resp_extra.status_code == 422

    # Extra field on candidate
    resp_cand_extra = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={
            "candidates": [
                {"reference_id": "1", "company_name": "Test", "unauthorized_key": "val"}
            ]
        },
        headers=_headers(token),
    )
    assert resp_cand_extra.status_code == 422

    # Empty candidates list
    resp_empty = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={"candidates": []},
        headers=_headers(token),
    )
    assert resp_empty.status_code == 422

    # Oversized batch (> 100 items)
    large_candidates = [
        {"reference_id": f"ref-{i}", "company_name": f"Company {i}"} for i in range(101)
    ]
    resp_large = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={"candidates": large_candidates},
        headers=_headers(token),
    )
    assert resp_large.status_code == 422


def test_api_read_only_side_effect_audit(client: TestClient, db: Session) -> None:
    auth = _auth(client)
    token = auth["access_token"]

    prospect_count_before = db.scalar(select(func.count()).select_from(CompanyProspect))
    lead_count_before = db.scalar(select(func.count()).select_from(Lead))
    activity_count_before = db.scalar(select(func.count()).select_from(ActivityEvent))
    webhook_count_before = db.scalar(select(func.count()).select_from(WebhookDelivery))
    workflow_count_before = db.scalar(select(func.count()).select_from(WorkflowRun))

    response = client.post(
        "/api/v1/company-prospects/duplicate-assessment",
        json={
            "candidates": [
                {
                    "reference_id": "cand-audit-1",
                    "company_name": "Audit Company 1",
                    "website_domain": "audit1.com",
                    "cin": "U12345DL2001PLC123456",
                },
                {
                    "reference_id": "cand-audit-2",
                    "company_name": "Audit Company 2",
                    "website_domain": "audit2.com",
                },
            ]
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["total_evaluated"] == 2

    # Verify zero database mutations
    assert db.scalar(select(func.count()).select_from(CompanyProspect)) == prospect_count_before
    assert db.scalar(select(func.count()).select_from(Lead)) == lead_count_before
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count_before
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count_before
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count_before


def test_api_single_prospect_duplicate_assessment_success_and_self_exclusion(
    client: TestClient,
) -> None:
    auth = _auth(client)
    token = auth["access_token"]

    # 1. Create a target prospect
    target_resp = client.post(
        "/api/v1/company-prospects",
        json={"name": "Acme Technologies Pvt Ltd", "website_domain": "acme.example.com"},
        headers=_headers(token),
    )
    assert target_resp.status_code == 201
    target_id = target_resp.json()["id"]

    # 2. Assess as the only record -> NEW proves the target never matches itself
    assess_new = client.get(
        f"/api/v1/company-prospects/{target_id}/duplicate-assessment",
        headers=_headers(token),
    )
    assert assess_new.status_code == 200
    body_new = assess_new.json()
    assert body_new["total_evaluated"] == 1
    assert body_new["assessments"][0]["reference_id"] == target_id
    assert body_new["assessments"][0]["outcome"] == "NEW"
    assert body_new["assessments"][0]["existing_match_references"] == []

    # 3. Create a similarly named prospect. Domains are unique per organization,
    # so a persisted duplicate can only surface through name similarity.
    similar_resp = client.post(
        "/api/v1/company-prospects",
        json={"name": "Acme Technologies Limited", "website_domain": "acme-tech.example.com"},
        headers=_headers(token),
    )
    assert similar_resp.status_code == 201
    similar_id = similar_resp.json()["id"]

    # 4. Assess again -> POSSIBLE_DUPLICATE referencing only the other prospect
    assess_match = client.get(
        f"/api/v1/company-prospects/{target_id}/duplicate-assessment",
        headers=_headers(token),
    )
    assert assess_match.status_code == 200
    body_match = assess_match.json()
    assert body_match["total_evaluated"] == 1
    item = body_match["assessments"][0]
    assert item["reference_id"] == target_id
    assert item["outcome"] == "POSSIBLE_DUPLICATE"
    assert item["reason_code"] == "PERSISTED_NAME_SIMILARITY"
    assert item["matching_fields"] == ["company_name"]
    assert item["existing_match_references"] == [similar_id]
    assert target_id not in item["existing_match_references"]


def test_api_single_prospect_duplicate_assessment_tenant_isolation(
    client: TestClient,
) -> None:
    tenant_a = _auth(client, email="a@example.com", organization_name="Org A")
    tenant_b = _auth(client, email="b@example.com", organization_name="Org B")

    # Org A creates a prospect
    resp_a = client.post(
        "/api/v1/company-prospects",
        json={"name": "Org A Co", "website_domain": "shared.example.com"},
        headers=_headers(tenant_a["access_token"]),
    )
    assert resp_a.status_code == 201
    id_a = resp_a.json()["id"]

    # Org B creates a prospect with same domain
    resp_b = client.post(
        "/api/v1/company-prospects",
        json={"name": "Org B Co", "website_domain": "shared.example.com"},
        headers=_headers(tenant_b["access_token"]),
    )
    assert resp_b.status_code == 201

    # 1. Org A assesses their prospect -> Should NOT match Org B's record
    assess_a = client.get(
        f"/api/v1/company-prospects/{id_a}/duplicate-assessment",
        headers=_headers(tenant_a["access_token"]),
    )
    assert assess_a.status_code == 200
    assert assess_a.json()["assessments"][0]["outcome"] == "NEW"

    # 2. Org B tries to access Org A's prospect assessment -> 404
    assess_cross = client.get(
        f"/api/v1/company-prospects/{id_a}/duplicate-assessment",
        headers=_headers(tenant_b["access_token"]),
    )
    assert assess_cross.status_code == 404


def test_api_single_prospect_duplicate_assessment_errors(client: TestClient) -> None:
    auth = _auth(client)
    token = auth["access_token"]

    # Unauthenticated
    assert client.get("/api/v1/company-prospects/some-id/duplicate-assessment").status_code == 401

    # Not Found
    assert client.get(
        "/api/v1/company-prospects/non-existent-id/duplicate-assessment",
        headers=_headers(token),
    ).status_code == 404


def test_api_single_prospect_duplicate_assessment_read_only_side_effect_audit(
    client: TestClient, db: Session
) -> None:
    auth = _auth(client)
    token = auth["access_token"]

    target_resp = client.post(
        "/api/v1/company-prospects",
        json={"name": "Audit Target Pvt Ltd", "website_domain": "audit-target.example.com"},
        headers=_headers(token),
    )
    assert target_resp.status_code == 201
    target_id = target_resp.json()["id"]

    similar_resp = client.post(
        "/api/v1/company-prospects",
        json={"name": "Audit Target Limited", "website_domain": "audit-other.example.com"},
        headers=_headers(token),
    )
    assert similar_resp.status_code == 201

    prospect_count_before = db.scalar(select(func.count()).select_from(CompanyProspect))
    lead_count_before = db.scalar(select(func.count()).select_from(Lead))
    activity_count_before = db.scalar(select(func.count()).select_from(ActivityEvent))
    webhook_count_before = db.scalar(select(func.count()).select_from(WebhookDelivery))
    workflow_count_before = db.scalar(select(func.count()).select_from(WorkflowRun))

    response = client.get(
        f"/api/v1/company-prospects/{target_id}/duplicate-assessment",
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["assessments"][0]["outcome"] == "POSSIBLE_DUPLICATE"

    # Verify zero database mutations
    assert db.scalar(select(func.count()).select_from(CompanyProspect)) == prospect_count_before
    assert db.scalar(select(func.count()).select_from(Lead)) == lead_count_before
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count_before
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count_before
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count_before

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.company_prospect import CompanyProspect, EvidenceQuality
from app.models.webhook import WebhookDelivery
from app.models.workflow import WorkflowRun
from app.schemas.company_prospect_scoring import CompanyProspectScoringInput
from app.schemas.ideal_customer_profile import IdealCustomerProfileUpdate
from app.services.lead_fit_scoring_service import score_company_prospect_fit
from tests.test_agent_runtime import _headers
from tests.test_leads import _auth


def _profile(
    *,
    industry_weight: int = 50,
    industry_terms: list[str] | None = None,
    minimum_employees: int | None = None,
    maximum_employees: int | None = None,
    company_size_weight: int = 50,
    geography_targets: list[dict[str, str | None]] | None = None,
    geography_weight: int = 50,
) -> dict[str, object]:
    return {
        "industry": {
            "terms": industry_terms or ["Software"],
            "weight": industry_weight,
        },
        "company_size": {
            "minimum_employees": minimum_employees,
            "maximum_employees": maximum_employees,
            "weight": company_size_weight,
        },
        "geography": {
            "targets": geography_targets or [],
            "weight": geography_weight,
        },
    }


def _score(
    prospect: dict[str, object],
    configuration: dict[str, object],
):
    typed_input = CompanyProspectScoringInput.model_validate(prospect)
    return score_company_prospect_fit(prospect=typed_input, configuration=configuration)


def test_industry_matches_exact_normalized_target_with_explanation() -> None:
    result = _score(
        {
            "industry": {
                "value": "  SOFTWARE   Services ",
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        _profile(industry_terms=["software services"]),
    )

    component = result.components[0]
    assert result.score == 100
    assert component.criterion == "industry"
    assert component.status == "MATCHED"
    assert "exactly matches" in component.explanation


def test_industry_mismatch_is_assessed_but_missing_is_unknown() -> None:
    mismatch = _score(
        {"industry": {"value": "Retail", "evidence_quality": "SOURCE_REPORTED"}},
        _profile(),
    )
    missing = _score({}, _profile())

    assert mismatch.components[0].status == "UNMATCHED"
    assert mismatch.score == 0
    assert missing.components[0].status == "UNKNOWN"
    assert missing.score is None
    assert "No company industry" in missing.components[0].explanation


@pytest.mark.parametrize(
    "evidence",
    [
        {"value": "Software", "taxonomy": "UNSUPPORTED", "evidence_quality": "SOURCE_REPORTED"},
        {"value": "Software", "ambiguous": True, "evidence_quality": "SOURCE_REPORTED"},
    ],
)
def test_unsupported_or_ambiguous_industry_remains_unknown(evidence: dict[str, object]) -> None:
    result = _score({"industry": evidence}, _profile())

    assert result.components[0].status == "UNKNOWN"
    assert result.score is None
    explanation = result.components[0].explanation
    assert "unsupported" in explanation or "ambiguous" in explanation


@pytest.mark.parametrize("count", [10, 100])
def test_employee_count_range_boundaries_are_inclusive(count: int) -> None:
    result = _score(
        {"company_size": {"employee_count": count, "evidence_quality": "SOURCE_REPORTED"}},
        _profile(industry_terms=[], minimum_employees=10, maximum_employees=100),
    )

    assert result.components[1].status == "MATCHED"


@pytest.mark.parametrize("count", [9, 101])
def test_employee_count_outside_range_is_unmatched(count: int) -> None:
    result = _score(
        {"company_size": {"employee_count": count, "evidence_quality": "SOURCE_REPORTED"}},
        _profile(industry_terms=[], minimum_employees=10, maximum_employees=100),
    )

    assert result.components[1].status == "UNMATCHED"


def test_employee_size_band_match_partial_overlap_and_disjoint_band() -> None:
    configuration = _profile(industry_terms=[], minimum_employees=10, maximum_employees=100)
    exact = _score(
        {
            "company_size": {
                "minimum_employees": 10,
                "maximum_employees": 100,
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        configuration,
    )
    fully_inside = _score(
        {
            "company_size": {
                "minimum_employees": 20,
                "maximum_employees": 80,
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        configuration,
    )
    partial = _score(
        {
            "company_size": {
                "minimum_employees": 80,
                "maximum_employees": 120,
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        configuration,
    )
    disjoint = _score(
        {
            "company_size": {
                "minimum_employees": 101,
                "maximum_employees": 200,
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        configuration,
    )

    assert exact.components[1].status == "MATCHED"
    assert fully_inside.components[1].status == "MATCHED"
    assert partial.components[1].status == "UNKNOWN"
    assert "partially overlaps" in partial.components[1].explanation
    assert disjoint.components[1].status == "UNMATCHED"


@pytest.mark.parametrize(
    "configuration",
    [
        {"minimum_employees": -1, "maximum_employees": 10, "weight": 50},
        {"minimum_employees": 20, "maximum_employees": 10, "weight": 50},
        {"minimum_employees": 10, "maximum_employees": 20, "weight": 0},
    ],
)
def test_invalid_company_size_configuration_is_rejected(configuration: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        IdealCustomerProfileUpdate.model_validate({"company_size": configuration})


@pytest.mark.parametrize(
    "prospect",
    [
        {"company_size": {"employee_count": -1, "evidence_quality": "SOURCE_REPORTED"}},
        {
            "company_size": {
                "minimum_employees": 50,
                "maximum_employees": 10,
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        {
            "company_size": {
                "employee_count": 20,
                "minimum_employees": 10,
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
    ],
)
def test_invalid_company_size_evidence_is_rejected(prospect: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CompanyProspectScoringInput.model_validate(prospect)


def test_country_and_country_region_targets_match_at_their_configured_precision() -> None:
    country = _score(
        {"geography": {"country": "  united   states ", "evidence_quality": "SOURCE_REPORTED"}},
        _profile(
            industry_terms=[],
            geography_targets=[{"country": "United States", "region": None}],
        ),
    )
    region = _score(
        {
            "geography": {
                "country": "United States",
                "region": " California ",
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        _profile(
            industry_terms=[],
            geography_targets=[{"country": "united states", "region": "california"}],
        ),
    )

    assert country.components[2].status == "MATCHED"
    assert region.components[2].status == "MATCHED"


def test_geography_mismatch_and_insufficient_region_precision() -> None:
    target = _profile(
        industry_terms=[],
        geography_targets=[{"country": "United States", "region": "California"}],
    )
    mismatch = _score(
        {
            "geography": {
                "country": "United States",
                "region": "New York",
                "evidence_quality": "SOURCE_REPORTED",
            }
        },
        target,
    )
    insufficient = _score(
        {"geography": {"country": "United States", "evidence_quality": "SOURCE_REPORTED"}},
        target,
    )

    assert mismatch.components[2].status == "UNMATCHED"
    assert insufficient.components[2].status == "UNKNOWN"
    assert "region is required" in insufficient.components[2].explanation


@pytest.mark.parametrize(
    "quality",
    [EvidenceQuality.ESTIMATED, EvidenceQuality.INFERRED, EvidenceQuality.UNKNOWN],
)
def test_non_source_reported_evidence_is_not_scored_as_fact(quality: EvidenceQuality) -> None:
    result = _score(
        {
            "industry": {"value": "Software", "evidence_quality": quality},
            "company_size": {"employee_count": 20, "evidence_quality": quality},
            "geography": {"country": "Canada", "evidence_quality": quality},
        },
        _profile(
            industry_weight=30,
            minimum_employees=10,
            maximum_employees=100,
            company_size_weight=30,
            geography_targets=[{"country": "Canada", "region": None}],
            geography_weight=40,
        ),
    )

    assert [component.status for component in result.components] == [
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
    ]
    assert result.score is None
    assert result.confidence == 0
    assert all(quality.value in component.explanation for component in result.components)


def test_mixed_weights_exclude_unknown_from_score_but_reduce_confidence() -> None:
    result = _score(
        {
            "industry": {"value": "Software", "evidence_quality": "SOURCE_REPORTED"},
            "company_size": {"employee_count": 500, "evidence_quality": "SOURCE_REPORTED"},
        },
        _profile(
            industry_weight=80,
            minimum_employees=10,
            maximum_employees=100,
            company_size_weight=40,
            geography_targets=[{"country": "Canada", "region": None}],
            geography_weight=30,
        ),
    )

    assert [component.status for component in result.components] == [
        "MATCHED",
        "UNMATCHED",
        "UNKNOWN",
    ]
    assert result.score == 67
    assert result.confidence == 80
    assert result.fit == "MODERATE"


@pytest.mark.parametrize(
    ("matched_weight", "unmatched_weight", "expected_score", "expected_fit"),
    [
        (75, 25, 75, "STRONG"),
        (74, 26, 74, "MODERATE"),
        (50, 50, 50, "MODERATE"),
        (49, 51, 49, "WEAK"),
    ],
)
def test_fit_band_boundaries(
    matched_weight: int,
    unmatched_weight: int,
    expected_score: int,
    expected_fit: str,
) -> None:
    result = _score(
        {
            "industry": {"value": "Software", "evidence_quality": "SOURCE_REPORTED"},
            "company_size": {"employee_count": 0, "evidence_quality": "SOURCE_REPORTED"},
        },
        _profile(
            industry_weight=matched_weight,
            minimum_employees=10,
            maximum_employees=100,
            company_size_weight=unmatched_weight,
        ),
    )

    assert result.score == expected_score
    assert result.fit == expected_fit


def test_score_rounding_is_half_up_and_duplicate_targets_do_not_duplicate_weight() -> None:
    profile = IdealCustomerProfileUpdate.model_validate(
        {
            "industry": {"terms": [" Software ", "software"], "weight": 1},
            "company_size": {
                "minimum_employees": 10,
                "maximum_employees": 100,
                "weight": 7,
            },
        }
    )
    result = score_company_prospect_fit(
        prospect=CompanyProspectScoringInput.model_validate(
            {
                "industry": {"value": "Software", "evidence_quality": "SOURCE_REPORTED"},
                "company_size": {"employee_count": 0, "evidence_quality": "SOURCE_REPORTED"},
            }
        ),
        configuration=profile.model_dump(mode="json"),
    )

    assert profile.industry.terms == ["Software"]
    assert result.score == 13
    assert [component.weight for component in result.components] == [1, 7, 50]


def test_no_assessable_criteria_and_legacy_profiles_keep_unknown_behavior() -> None:
    no_configuration = _score({}, {})
    legacy_profile = _score(
        {},
        {
            "company": {"terms": ["Acme"], "weight": 60},
            "enquiry": {"terms": ["analytics"], "weight": 40},
        },
    )

    assert no_configuration.score is None
    assert no_configuration.confidence == 0
    assert no_configuration.fit == "UNKNOWN"
    assert [component.status for component in no_configuration.components] == [
        "UNCONFIGURED",
        "UNCONFIGURED",
        "UNCONFIGURED",
    ]
    assert legacy_profile.configuration_valid is True
    assert legacy_profile.score is None


def test_company_prospect_scoring_input_rejects_unmodeled_provider_fields() -> None:
    with pytest.raises(ValidationError):
        CompanyProspectScoringInput.model_validate({"provider_payload": {"raw": "fixture"}})


def test_fit_score_api_uses_authenticated_profile_without_persisting_evidence(
    client: TestClient, db: Session
) -> None:
    first = _auth(client, email="first@example.com", organization_name="First")
    second = _auth(client, email="second@example.com", organization_name="Second")
    first_headers = _headers(first["access_token"])
    second_headers = _headers(second["access_token"])
    profile = client.patch(
        "/api/v1/organizations/current/ideal-customer-profile",
        json={
            "industry": {"terms": ["Software"], "weight": 60},
            "company_size": {
                "minimum_employees": 10,
                "maximum_employees": 100,
                "weight": 40,
            },
        },
        headers=first_headers,
    )
    created = client.post(
        "/api/v1/company-prospects",
        json={"name": "Synthetic Software Fixture", "website_domain": "fixture.example"},
        headers=first_headers,
    )
    assert profile.status_code == 200
    assert created.status_code == 201
    prospect_id = created.json()["id"]
    activity_count = db.scalar(select(func.count()).select_from(ActivityEvent))
    webhook_count = db.scalar(select(func.count()).select_from(WebhookDelivery))
    workflow_count = db.scalar(select(func.count()).select_from(WorkflowRun))
    prospect_count = db.scalar(select(func.count()).select_from(CompanyProspect))

    scored = client.post(
        f"/api/v1/company-prospects/{prospect_id}/fit-score",
        json={
            "industry": {
                "value": " software ",
                "evidence_quality": "SOURCE_REPORTED",
            },
            "company_size": {
                "employee_count": 500,
                "evidence_quality": "SOURCE_REPORTED",
            },
        },
        headers=first_headers,
    )
    foreign_score = client.post(
        f"/api/v1/company-prospects/{prospect_id}/fit-score",
        json={},
        headers=second_headers,
    )

    assert scored.status_code == 200
    assert scored.json()["score"] == 60
    assert scored.json()["confidence"] == 100
    assert [item["status"] for item in scored.json()["components"]] == [
        "MATCHED",
        "UNMATCHED",
        "UNCONFIGURED",
    ]
    assert foreign_score.status_code == 404
    assert db.scalar(select(func.count()).select_from(CompanyProspect)) == prospect_count
    assert db.scalar(select(func.count()).select_from(ActivityEvent)) == activity_count
    assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == webhook_count
    assert db.scalar(select(func.count()).select_from(WorkflowRun)) == workflow_count
    prospect = db.get(CompanyProspect, prospect_id)
    assert prospect is not None
    assert not hasattr(prospect, "industry")
    assert not hasattr(prospect, "employee_count")
    assert not hasattr(prospect, "country")
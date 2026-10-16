from app.services.lead_fit_scoring_service import score_lead_fit


def _configuration() -> dict[str, object]:
    return {
        "company": {"terms": ["Acme Inc"], "weight": 60},
        "enquiry": {"terms": ["analytics"], "weight": 40},
    }


def test_scores_exact_normalized_matches_and_returns_explanations() -> None:
    result = score_lead_fit(
        company="ACME, INC.",
        enquiry="Interested in ANALYTICS.",
        configuration=_configuration(),
    )

    assert result.score == 100
    assert result.confidence == 100
    assert result.fit == "STRONG"
    assert [component.status for component in result.components] == ["MATCHED", "MATCHED"]
    assert result.components[0].matched_terms == ["Acme Inc"]


def test_mismatch_is_not_treated_as_missing_and_scores_zero() -> None:
    result = score_lead_fit(
        company="Other Corp",
        enquiry="Interested in support",
        configuration=_configuration(),
    )

    assert result.score == 0
    assert result.fit == "WEAK"
    assert result.confidence == 100
    assert [component.status for component in result.components] == ["UNMATCHED", "UNMATCHED"]


def test_unknown_fields_are_excluded_from_score_and_reduce_confidence() -> None:
    result = score_lead_fit(
        company=None,
        enquiry="We need analytics",
        configuration=_configuration(),
    )

    assert result.score == 100
    assert result.confidence == 40
    assert [component.status for component in result.components] == ["UNKNOWN", "MATCHED"]


def test_no_assessable_evidence_is_unknown_and_unsupported_fields_are_declared() -> None:
    result = score_lead_fit(company="", enquiry=None, configuration=_configuration())

    assert result.score is None
    assert result.confidence == 0
    assert result.fit == "UNKNOWN"
    assert "industry" in result.unavailable_criteria
    assert "buyer_role" in result.unavailable_criteria


def test_malformed_non_text_lead_values_are_unknown() -> None:
    result = score_lead_fit(
        company=42,
        enquiry=["analytics"],
        configuration=_configuration(),
    )

    assert result.score is None
    assert result.confidence == 0
    assert [component.status for component in result.components] == ["UNKNOWN", "UNKNOWN"]
    assert result.components[0].explanation == "The recorded company data is unusable."


def test_empty_profile_and_malformed_profile_fail_closed() -> None:
    empty = score_lead_fit(company="Acme", enquiry="Analytics", configuration=None)
    malformed = score_lead_fit(
        company="Acme",
        enquiry="Analytics",
        configuration={"company": {"terms": "Acme", "weight": 50}},
    )

    assert empty.score is None
    assert empty.fit == "UNKNOWN"
    assert malformed.score is None
    assert malformed.configuration_valid is False
    assert malformed.fit == "UNKNOWN"


def test_score_is_bounded_and_weights_control_contribution() -> None:
    result = score_lead_fit(
        company="Acme",
        enquiry="No match",
        configuration={
            "company": {"terms": ["Acme"], "weight": 3},
            "enquiry": {"terms": ["analytics"], "weight": 1},
        },
    )

    assert result.score == 75
    assert 0 <= result.score <= 100


def test_keyword_match_respects_token_boundaries() -> None:
    result = score_lead_fit(
        company="Said Corp",
        enquiry=None,
        configuration={
            "company": {"terms": ["ai"], "weight": 100},
            "enquiry": {"terms": [], "weight": 0},
        },
    )

    assert result.score == 0
    assert result.components[0].status == "UNMATCHED"
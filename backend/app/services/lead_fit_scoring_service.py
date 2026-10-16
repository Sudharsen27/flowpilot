import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import ValidationError

from app.schemas.ideal_customer_profile import (
    IdealCustomerProfileUpdate,
    LeadFitComponent,
    LeadFitScore,
)

UNAVAILABLE_CRITERIA = {
    "industry": "Industry is not stored on CRM leads.",
    "employee_range": "Employee count or company size is not stored on CRM leads.",
    "geographic_region": "A geographic region is not stored on CRM leads.",
    "buyer_role": "Job title or buyer role is not stored on CRM leads.",
}


def _tokens(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)


def _contains_phrase(value_tokens: list[str], term_tokens: list[str]) -> bool:
    if not term_tokens or len(term_tokens) > len(value_tokens):
        return False
    width = len(term_tokens)
    return any(
        value_tokens[index : index + width] == term_tokens
        for index in range(len(value_tokens) - width + 1)
    )


def _component(
    *,
    criterion: Literal["company", "enquiry"],
    source_value: object,
    configured_terms: list[str],
    weight: int,
) -> LeadFitComponent:
    if not configured_terms or weight == 0:
        return LeadFitComponent(
            criterion=criterion,
            status="UNCONFIGURED",
            weight=weight,
            explanation="No matching terms are configured for this criterion.",
        )
    if not isinstance(source_value, str):
        explanation = f"The recorded {criterion} data is unusable."
        return LeadFitComponent(
            criterion=criterion,
            status="UNKNOWN",
            weight=weight,
            explanation=explanation,
        )
    if not source_value.strip():
        return LeadFitComponent(
            criterion=criterion,
            status="UNKNOWN",
            weight=weight,
            explanation=f"This lead has no {criterion} information to assess.",
        )

    value_tokens = _tokens(source_value)
    matched = [
        term
        for term in configured_terms
        if _contains_phrase(value_tokens, _tokens(term))
    ]
    if matched:
        return LeadFitComponent(
            criterion=criterion,
            status="MATCHED",
            weight=weight,
            matched_terms=matched,
            explanation=f"Matched configured {criterion} term(s): {', '.join(matched)}.",
        )
    return LeadFitComponent(
        criterion=criterion,
        status="UNMATCHED",
        weight=weight,
        explanation=f"The recorded {criterion} contains none of the configured terms.",
    )


def score_lead_fit(
    *,
    company: object,
    enquiry: object,
    configuration: Mapping[str, Any] | None,
) -> LeadFitScore:
    """Score only supported business text fields; malformed stored config fails closed."""
    try:
        profile = IdealCustomerProfileUpdate.model_validate(configuration or {})
    except (ValidationError, TypeError, ValueError):
        return LeadFitScore(
            score=None,
            confidence=0,
            fit="UNKNOWN",
            components=[
                LeadFitComponent(
                    criterion="company",
                    status="UNKNOWN",
                    weight=0,
                    explanation="ICP configuration is invalid and must be repaired.",
                ),
                LeadFitComponent(
                    criterion="enquiry",
                    status="UNKNOWN",
                    weight=0,
                    explanation="ICP configuration is invalid and must be repaired.",
                ),
            ],
            unavailable_criteria=UNAVAILABLE_CRITERIA,
            configuration_valid=False,
        )

    components = [
        _component(
            criterion="company",
            source_value=company,
            configured_terms=profile.company.terms,
            weight=profile.company.weight,
        ),
        _component(
            criterion="enquiry",
            source_value=enquiry,
            configured_terms=profile.enquiry.terms,
            weight=profile.enquiry.weight,
        ),
    ]
    active = [component for component in components if component.status != "UNCONFIGURED"]
    assessed = [component for component in active if component.status != "UNKNOWN"]
    active_weight = sum(component.weight for component in active)
    assessed_weight = sum(component.weight for component in assessed)
    if assessed_weight == 0:
        score = None
        fit: Literal["STRONG", "MODERATE", "WEAK", "UNKNOWN"] = "UNKNOWN"
    else:
        matched_weight = sum(
            component.weight for component in assessed if component.status == "MATCHED"
        )
        score = min(100, max(0, int(matched_weight * 100 / assessed_weight + 0.5)))
        fit = "STRONG" if score >= 75 else "MODERATE" if score >= 50 else "WEAK"
    confidence = (
        min(100, max(0, int(assessed_weight * 100 / active_weight + 0.5)))
        if active_weight
        else 0
    )
    return LeadFitScore(
        score=score,
        confidence=confidence,
        fit=fit,
        components=components,
        unavailable_criteria=UNAVAILABLE_CRITERIA,
    )
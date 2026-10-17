import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import ValidationError

from app.models.company_prospect import EvidenceQuality
from app.schemas.company_prospect_scoring import (
    CompanyProspectGeographyEvidence,
    CompanyProspectIndustryEvidence,
    CompanyProspectScoringInput,
    CompanyProspectSizeEvidence,
)
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
COMPANY_PROSPECT_UNAVAILABLE_CRITERIA = {
    "buyer_role": "Job title or buyer role is not available for deterministic scoring."
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


def _aggregate_components(
    components: list[LeadFitComponent],
    *,
    unavailable_criteria: dict[str, str],
    configuration_valid: bool = True,
) -> LeadFitScore:
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
        unavailable_criteria=unavailable_criteria,
        configuration_valid=configuration_valid,
    )


def _criterion_component(
    criterion: Literal["industry", "company_size", "geography"],
    *,
    weight: int,
    explanation: str,
    status: Literal["MATCHED", "UNMATCHED", "UNKNOWN", "UNCONFIGURED"],
) -> LeadFitComponent:
    return LeadFitComponent(
        criterion=criterion,
        status=status,
        weight=weight,
        explanation=explanation,
    )


def _industry_component(
    evidence: CompanyProspectIndustryEvidence, profile: IdealCustomerProfileUpdate
) -> LeadFitComponent:
    criterion: Literal["industry"] = "industry"
    config = profile.industry
    if not config.terms or config.weight == 0:
        return _criterion_component(
            criterion,
            weight=config.weight,
            status="UNCONFIGURED",
            explanation="No industry targets are configured.",
        )
    if evidence.value is None:
        explanation = "No company industry value is available to assess."
        status: Literal["MATCHED", "UNMATCHED", "UNKNOWN"] = "UNKNOWN"
    elif evidence.taxonomy is not None:
        explanation = f"Industry taxonomy '{evidence.taxonomy}' is unsupported."
        status = "UNKNOWN"
    elif evidence.ambiguous:
        explanation = f"Industry value '{evidence.value}' is ambiguous."
        status = "UNKNOWN"
    elif evidence.evidence_quality != EvidenceQuality.SOURCE_REPORTED:
        explanation = (
            f"Industry value '{evidence.value}' has {evidence.evidence_quality} evidence; "
            "only SOURCE_REPORTED values are scored."
        )
        status = "UNKNOWN"
    else:
        normalized_value = " ".join(evidence.value.split()).casefold()
        normalized_targets = {
            " ".join(term.split()).casefold() for term in config.terms if term.strip()
        }
        status = "MATCHED" if normalized_value in normalized_targets else "UNMATCHED"
        explanation = (
            f"SOURCE_REPORTED industry '{evidence.value}' exactly matches a configured target."
            if status == "MATCHED"
            else f"SOURCE_REPORTED industry '{evidence.value}' matches no configured target."
        )
    return _criterion_component(
        criterion,
        weight=config.weight,
        status=status,
        explanation=explanation,
    )


def _size_component(
    evidence: CompanyProspectSizeEvidence, profile: IdealCustomerProfileUpdate
) -> LeadFitComponent:
    criterion: Literal["company_size"] = "company_size"
    config = profile.company_size
    if config.minimum_employees is None and config.maximum_employees is None:
        return _criterion_component(
            criterion,
            weight=config.weight,
            status="UNCONFIGURED",
            explanation="No company-size range is configured.",
        )
    if (
        evidence.employee_count is None
        and evidence.minimum_employees is None
        and evidence.maximum_employees is None
    ):
        status: Literal["MATCHED", "UNMATCHED", "UNKNOWN"] = "UNKNOWN"
        explanation = "No employee count or supported size band is available to assess."
    elif evidence.evidence_quality != EvidenceQuality.SOURCE_REPORTED:
        value_label = (
            str(evidence.employee_count)
            if evidence.employee_count is not None
            else f"{evidence.minimum_employees}..{evidence.maximum_employees}"
        )
        status = "UNKNOWN"
        explanation = (
            f"Company-size evidence '{value_label}' has {evidence.evidence_quality} quality; "
            "only SOURCE_REPORTED counts or bands are scored."
        )
    else:
        target_min = config.minimum_employees if config.minimum_employees is not None else 0
        target_max = config.maximum_employees
        if evidence.employee_count is not None:
            matched = evidence.employee_count >= target_min and (
                target_max is None or evidence.employee_count <= target_max
            )
            status = "MATCHED" if matched else "UNMATCHED"
            explanation = (
                f"SOURCE_REPORTED employee count {evidence.employee_count} is "
                f"{'within' if matched else 'outside'} the inclusive configured range."
            )
        else:
            evidence_min = (
                evidence.minimum_employees if evidence.minimum_employees is not None else 0
            )
            evidence_max = evidence.maximum_employees
            fully_inside = evidence_min >= target_min and (
                target_max is None or (evidence_max is not None and evidence_max <= target_max)
            )
            disjoint = (target_max is not None and evidence_min > target_max) or (
                evidence_max is not None and evidence_max < target_min
            )
            if fully_inside:
                status = "MATCHED"
                explanation = (
                    "SOURCE_REPORTED size band is fully within the inclusive configured range."
                )
            elif disjoint:
                status = "UNMATCHED"
                explanation = (
                    "SOURCE_REPORTED size band does not overlap the inclusive configured range."
                )
            else:
                status = "UNKNOWN"
                explanation = (
                    "SOURCE_REPORTED size band only partially overlaps the configured range."
                )
    return _criterion_component(
        criterion,
        weight=config.weight,
        status=status,
        explanation=explanation,
    )


def _geography_component(
    evidence: CompanyProspectGeographyEvidence, profile: IdealCustomerProfileUpdate
) -> LeadFitComponent:
    criterion: Literal["geography"] = "geography"
    config = profile.geography
    if not config.targets or config.weight == 0:
        return _criterion_component(
            criterion,
            weight=config.weight,
            status="UNCONFIGURED",
            explanation="No country or country-region targets are configured.",
        )
    if evidence.country is None:
        status: Literal["MATCHED", "UNMATCHED", "UNKNOWN"] = "UNKNOWN"
        explanation = "No country is available to assess geographic targets."
    elif evidence.evidence_quality != EvidenceQuality.SOURCE_REPORTED:
        status = "UNKNOWN"
        explanation = (
            f"Geography '{evidence.country}' has {evidence.evidence_quality} evidence; "
            "only SOURCE_REPORTED locations are scored."
        )
    else:
        country = " ".join(evidence.country.split()).casefold()
        region = " ".join(evidence.region.split()).casefold() if evidence.region else None
        matched_target = any(
            country == " ".join(target.country.split()).casefold()
            and (
                target.region is None
                or (region is not None and region == " ".join(target.region.split()).casefold())
            )
            for target in config.targets
        )
        needs_region = any(
            country == " ".join(target.country.split()).casefold()
            and target.region is not None
            for target in config.targets
        )
        if matched_target:
            status = "MATCHED"
            label = (
                f"{evidence.country}, {evidence.region}"
                if evidence.region
                else evidence.country
            )
            explanation = f"SOURCE_REPORTED location '{label}' matches a configured target."
        elif needs_region and evidence.region is None:
            status = "UNKNOWN"
            explanation = (
                f"SOURCE_REPORTED country '{evidence.country}' is known, but region is "
                "required to assess the configured target."
            )
        else:
            status = "UNMATCHED"
            label = (
                f"{evidence.country}, {evidence.region}"
                if evidence.region
                else evidence.country
            )
            explanation = f"SOURCE_REPORTED location '{label}' matches no configured target."
    return _criterion_component(
        criterion,
        weight=config.weight,
        status=status,
        explanation=explanation,
    )


def score_company_prospect_fit(
    *,
    prospect: CompanyProspectScoringInput,
    configuration: Mapping[str, Any] | None,
) -> LeadFitScore:
    """Score ephemeral, source-reported CompanyProspect evidence deterministically."""
    try:
        profile = IdealCustomerProfileUpdate.model_validate(configuration or {})
    except (ValidationError, TypeError, ValueError):
        return LeadFitScore(
            score=None,
            confidence=0,
            fit="UNKNOWN",
            components=[
                _criterion_component(
                    criterion,
                    weight=0,
                    status="UNKNOWN",
                    explanation="ICP configuration is invalid and must be repaired.",
                )
                for criterion in ("industry", "company_size", "geography")
            ],
            unavailable_criteria=COMPANY_PROSPECT_UNAVAILABLE_CRITERIA,
            configuration_valid=False,
        )

    return _aggregate_components(
        [
            _industry_component(prospect.industry, profile),
            _size_component(prospect.company_size, profile),
            _geography_component(prospect.geography, profile),
        ],
        unavailable_criteria=COMPANY_PROSPECT_UNAVAILABLE_CRITERIA,
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
    return _aggregate_components(
        components,
        unavailable_criteria=UNAVAILABLE_CRITERIA,
    )
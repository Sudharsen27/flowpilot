import difflib
import re
from collections.abc import Sequence
from typing import Protocol
from urllib.parse import urlsplit

from app.schemas.company_duplicate_assessment import (
    CompanyDuplicateAssessmentItem,
    CompanyDuplicateAssessmentResponse,
    CompanyDuplicateCandidateInput,
    DuplicateAssessmentOutcome,
)

_CIN_PATTERN = re.compile(r"^[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$")
_DOMAIN_PATTERN = re.compile(
    r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z"
)
_LEGAL_SUFFIXES_PATTERN = re.compile(
    r"\b(pvt ltd|private limited|ltd|limited|inc|incorporated|corp|corporation|llc|llp|plc)\b$",
    re.IGNORECASE,
)

NAME_SIMILARITY_THRESHOLD = 0.85


def normalize_website_domain(value: object) -> str | None:
    """Normalize a candidate or persisted domain string into a canonical FQDN.

    Rejects ambiguous, malformed, or unsupported values as matching evidence.
    Does not use suffix matching; exact FQDN equality is preserved.
    """
    if not isinstance(value, str):
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    # Handle URL inputs when a scheme is explicitly provided
    if "://" in cleaned:
        try:
            split = urlsplit(cleaned)
            if split.scheme.lower() not in {"http", "https"} or not split.netloc:
                return None
            # Reject all userinfo and explicit port syntax, including empty ports.
            if "@" in split.netloc or ":" in split.netloc:
                return None
            host = split.hostname
            if not host or not host.isascii():
                return None
            cleaned = host
        except ValueError:
            return None
    else:
        # Without a scheme, reject inputs containing ambiguous userinfo, ports, paths, or queries
        if any(char in cleaned for char in ("@", ":", "/", "?", "#", " ", "\t", "\n")):
            return None
        if not cleaned.isascii():
            return None

    cleaned = cleaned.lower()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]

    if not _DOMAIN_PATTERN.fullmatch(cleaned):
        return None

    return cleaned


def normalize_cin(value: object) -> str | None:
    """Normalize and validate a Corporate Identification Number (CIN).

    Returns a valid normalized 21-character uppercase CIN or None if malformed/missing.
    """
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).upper()
    if _CIN_PATTERN.fullmatch(cleaned):
        return cleaned
    return None


def normalize_company_name(value: object) -> str | None:
    """Normalize a company name for similarity comparison without stripping meaningful terms."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).casefold()
    if not cleaned:
        return None

    # Replace punctuation with spaces to avoid joining adjacent words
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = " ".join(cleaned.split())

    # Strip common legal entity structure suffixes when present as trailing words
    while True:
        stripped = _LEGAL_SUFFIXES_PATTERN.sub("", cleaned).strip()
        stripped = " ".join(stripped.split())
        if stripped == cleaned or not stripped:
            break
        cleaned = stripped

    if len(cleaned) < 2:
        return None
    return cleaned


def company_name_similarity(name1: str, name2: str) -> float:
    """Calculate SequenceMatcher similarity ratio between two normalized company names."""
    return difflib.SequenceMatcher(None, name1, name2).ratio()


class PersistedCompanyLike(Protocol):
    id: str
    name: str
    website_domain: str | None


class _ProcessedCandidate:
    def __init__(
        self,
        raw: CompanyDuplicateCandidateInput,
        cin: str | None,
        domain: str | None,
        name: str | None,
    ) -> None:
        self.raw = raw
        self.cin = cin
        self.domain = domain
        self.name = name


class CompanyDuplicateAssessmentService:
    def assess_candidates(
        self,
        candidates: Sequence[CompanyDuplicateCandidateInput],
        persisted_records: Sequence[PersistedCompanyLike],
    ) -> CompanyDuplicateAssessmentResponse:
        processed_candidates = [
            _ProcessedCandidate(
                raw=cand,
                cin=normalize_cin(cand.cin),
                domain=normalize_website_domain(cand.website_domain),
                name=normalize_company_name(cand.company_name),
            )
            for cand in candidates
        ]

        # Pre-normalize persisted records using identical domain and name normalizers
        persisted_normalized: list[tuple[PersistedCompanyLike, str | None, str | None]] = [
            (
                rec,
                normalize_website_domain(rec.website_domain),
                normalize_company_name(rec.name),
            )
            for rec in persisted_records
        ]

        assessments: list[CompanyDuplicateAssessmentItem] = []
        prior_candidates: list[_ProcessedCandidate] = []

        for candidate in processed_candidates:
            assessment = self._assess_single_candidate(
                candidate=candidate,
                prior_candidates=prior_candidates,
                persisted_records=persisted_normalized,
            )
            assessments.append(assessment)
            prior_candidates.append(candidate)

        return CompanyDuplicateAssessmentResponse(
            assessments=assessments,
            total_evaluated=len(assessments),
            persisted_cin_available=False,
        )

    def _assess_single_candidate(
        self,
        candidate: _ProcessedCandidate,
        prior_candidates: list[_ProcessedCandidate],
        persisted_records: list[tuple[PersistedCompanyLike, str | None, str | None]],
    ) -> CompanyDuplicateAssessmentItem:
        ref_id = candidate.raw.reference_id

        # 1. Insufficient data check
        if candidate.cin is None and candidate.domain is None and candidate.name is None:
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.INSUFFICIENT_DATA,
                reason_code="INSUFFICIENT_EVIDENCE",
                explanation=(
                    "Candidate lacks reliable identifiers (valid CIN, valid website domain, "
                    "or company name) to perform duplicate assessment."
                ),
                matching_fields=[],
                existing_match_references=[],
                in_batch_match_reference=None,
            )

        # 2. Gather all matches across persisted records
        persisted_domain_matches: list[PersistedCompanyLike] = []
        persisted_name_matches: list[PersistedCompanyLike] = []

        for rec, norm_domain, norm_name in persisted_records:
            if candidate.domain is not None and norm_domain is not None:
                if candidate.domain == norm_domain:
                    persisted_domain_matches.append(rec)
            if candidate.name is not None and norm_name is not None:
                if company_name_similarity(candidate.name, norm_name) >= NAME_SIMILARITY_THRESHOLD:
                    persisted_name_matches.append(rec)

        # 3. Gather all matches across prior batch candidates
        in_batch_cin_matches: list[_ProcessedCandidate] = []
        in_batch_domain_matches: list[_ProcessedCandidate] = []
        in_batch_name_matches: list[_ProcessedCandidate] = []

        for prior in prior_candidates:
            if candidate.cin is not None and prior.cin is not None:
                if candidate.cin == prior.cin:
                    in_batch_cin_matches.append(prior)
            if candidate.domain is not None and prior.domain is not None:
                if candidate.domain == prior.domain:
                    in_batch_domain_matches.append(prior)
            if candidate.name is not None and prior.name is not None:
                if company_name_similarity(candidate.name, prior.name) >= NAME_SIMILARITY_THRESHOLD:
                    in_batch_name_matches.append(prior)

        # 4. Check every matching identifier before assigning an exact outcome.
        if persisted_domain_matches and in_batch_cin_matches:
            conflicting_cin_prior = next(
                (
                    prior
                    for prior in in_batch_cin_matches
                    if prior.domain is not None and prior.domain != candidate.domain
                ),
                None,
            )
            if conflicting_cin_prior is not None:
                return CompanyDuplicateAssessmentItem(
                    reference_id=ref_id,
                    outcome=DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE,
                    reason_code="CONFLICTING_IDENTIFIERS",
                    explanation=(
                        "Candidate website domain matches an existing prospect, but its CIN "
                        f"matches previous candidate '{conflicting_cin_prior.raw.reference_id}' "
                        "with a different domain."
                    ),
                    matching_fields=["cin", "website_domain"],
                    existing_match_references=sorted([p.id for p in persisted_domain_matches]),
                    in_batch_match_reference=conflicting_cin_prior.raw.reference_id,
                )

        conflicting_pair = next(
            (
                (cin_prior, domain_prior)
                for cin_prior in in_batch_cin_matches
                for domain_prior in in_batch_domain_matches
                if cin_prior is not domain_prior
            ),
            None,
        )
        if conflicting_pair is not None:
            cin_prior, domain_prior = conflicting_pair
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE,
                reason_code="CONFLICTING_IDENTIFIERS",
                explanation=(
                    f"Candidate CIN matches previous candidate '{cin_prior.raw.reference_id}', "
                    "but candidate website domain matches a different candidate "
                    f"'{domain_prior.raw.reference_id}'."
                ),
                matching_fields=["cin", "website_domain"],
                existing_match_references=[],
                in_batch_match_reference=cin_prior.raw.reference_id,
            )

        conflicting_cin_prior = next(
            (
                prior
                for prior in in_batch_cin_matches
                if candidate.domain is not None
                and prior.domain is not None
                and prior.domain != candidate.domain
            ),
            None,
        )
        if conflicting_cin_prior is not None:
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE,
                reason_code="CONFLICTING_IDENTIFIERS",
                explanation=(
                    f"Candidate CIN matches previous candidate "
                    f"'{conflicting_cin_prior.raw.reference_id}', but candidate website "
                    "domain conflicts with that candidate's domain."
                ),
                matching_fields=["cin", "website_domain"],
                existing_match_references=[],
                in_batch_match_reference=conflicting_cin_prior.raw.reference_id,
            )

        conflicting_domain_prior = next(
            (
                prior
                for prior in in_batch_domain_matches
                if candidate.cin is not None
                and prior.cin is not None
                and prior.cin != candidate.cin
            ),
            None,
        )
        if conflicting_domain_prior is not None:
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE,
                reason_code="CONFLICTING_IDENTIFIERS",
                explanation=(
                    "Candidate website domain matches previous candidate "
                    f"'{conflicting_domain_prior.raw.reference_id}', but candidate CIN "
                    "conflicts with that candidate's CIN."
                ),
                matching_fields=["cin", "website_domain"],
                existing_match_references=[],
                in_batch_match_reference=conflicting_domain_prior.raw.reference_id,
            )

        # 5. Exact match evaluation (conflict-free)
        # 5a. Persisted domain match
        if persisted_domain_matches:
            matched_ids = sorted([p.id for p in persisted_domain_matches])
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.EXACT_MATCH,
                reason_code="PERSISTED_DOMAIN_MATCH",
                explanation=(
                    f"Candidate website domain exactly matches existing prospect "
                    f"'{matched_ids[0]}'. Note: Persisted CIN matching was not performed "
                    "as existing company prospects do not store CIN."
                ),
                matching_fields=["website_domain"],
                existing_match_references=matched_ids,
                in_batch_match_reference=None,
            )

        # 5b. In-batch exact match
        if in_batch_cin_matches:
            earliest_cin = in_batch_cin_matches[0]
            fields = ["cin"]
            reason = "IN_BATCH_CIN_MATCH"
            if in_batch_domain_matches and in_batch_domain_matches[0] == earliest_cin:
                fields.append("website_domain")
                reason = "IN_BATCH_CIN_AND_DOMAIN_MATCH"

            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.EXACT_MATCH,
                reason_code=reason,
                explanation=(
                    "Candidate Corporate Identification Number (CIN) exactly matches previous "
                    f"candidate '{earliest_cin.raw.reference_id}' in this batch."
                ),
                matching_fields=fields,
                existing_match_references=[],
                in_batch_match_reference=earliest_cin.raw.reference_id,
            )

        if in_batch_domain_matches:
            earliest_domain = in_batch_domain_matches[0]
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.EXACT_MATCH,
                reason_code="IN_BATCH_DOMAIN_MATCH",
                explanation=(
                    f"Candidate website domain exactly matches previous candidate "
                    f"'{earliest_domain.raw.reference_id}' in this batch."
                ),
                matching_fields=["website_domain"],
                existing_match_references=[],
                in_batch_match_reference=earliest_domain.raw.reference_id,
            )

        # 6. Possible duplicate evaluation (name similarity)
        # Missing CIN evidence must never cause a candidate to be classified as NEW
        # when a company name matches
        if persisted_name_matches:
            matched_ids = sorted([p.id for p in persisted_name_matches])
            reason = (
                "PERSISTED_NAME_SIMILARITY" if len(matched_ids) == 1 else "MULTIPLE_NAME_MATCHES"
            )
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE,
                reason_code=reason,
                explanation=(
                    f"Candidate company name is similar to existing prospect '{matched_ids[0]}'. "
                    "Further review recommended; persisted CIN matching was unavailable."
                ),
                matching_fields=["company_name"],
                existing_match_references=matched_ids,
                in_batch_match_reference=None,
            )

        if in_batch_name_matches:
            earliest_name = in_batch_name_matches[0]
            return CompanyDuplicateAssessmentItem(
                reference_id=ref_id,
                outcome=DuplicateAssessmentOutcome.POSSIBLE_DUPLICATE,
                reason_code="IN_BATCH_NAME_SIMILARITY",
                explanation=(
                    f"Candidate company name is similar to previous candidate "
                    f"'{earliest_name.raw.reference_id}' in this batch."
                ),
                matching_fields=["company_name"],
                existing_match_references=[],
                in_batch_match_reference=earliest_name.raw.reference_id,
            )

        # 7. New candidate outcome
        # Accurate NEW semantics: no matching record found using supported evaluated fields
        return CompanyDuplicateAssessmentItem(
            reference_id=ref_id,
            outcome=DuplicateAssessmentOutcome.NEW,
            reason_code="NO_MATCHING_RECORDS",
            explanation=(
                "No matching record was found using the supported evidence evaluated here: "
                "exact website-domain matches and company-name similarity against existing "
                "prospects, and exact CIN/domain matches plus company-name similarity within "
                "this batch. Persisted CIN matching is unavailable, so this result does not "
                "establish that the company is definitively new."
            ),
            matching_fields=[],
            existing_match_references=[],
            in_batch_match_reference=None,
        )

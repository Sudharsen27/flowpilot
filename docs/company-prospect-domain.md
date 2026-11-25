# Company Prospect Domain

> **Current-state note:** The historical Phase 4 foundation below records the
> original scope. Current sections describe the implementation now; in
> particular, Company Prospects are no longer read-only.

## Historical domain foundation (Phase 4, Slice 1)

Company Prospects are a separate, tenant-owned record type and do not create or
modify Leads. The original domain foundation persisted a company name, an
optional operator-entered website domain, evidence-quality labels for those
values, lifecycle state, and timestamps. Domain identity is unique within one
organization; company names are not unique. A missing domain may have only
`UNKNOWN` evidence quality.

Evidence quality is one of `SOURCE_REPORTED`, `ESTIMATED`, `INFERRED`, or
`UNKNOWN`. The label records a confidence category only; the Company Prospect
record does not store a source identity, source excerpt, raw provider payload,
inferred firmographic data, or personal contact information. Names and domains
are accepted as user-supplied values, not fetched or enriched from an external
provider.

The initial migration was limited to provider-independent fields. It did not
provide CSV import, CRM import, lead workflows, webhooks, AI, drafting, email,
or outreach. Later additions are described below. There is still no CSV
importer for Company Prospects, automatic conversion to a Lead, or automated
outreach. The separate Prospect Discovery CSV preview/import endpoints import
CRM Leads, not Company Prospects. Any future persistence of provider-sourced
values or source evidence remains contingent on resolving the applicable data
use and retention terms.

## Current record access and lifecycle

Authenticated organization members can list and view their organization’s
Company Prospects. The API derives organization identity from the authenticated
membership; clients do not select a tenant by supplying an organization ID.
Company Prospect lookups, duplicate comparisons, and domain uniqueness are
organization-scoped.

The list API supports optional case-insensitive, whitespace-normalized search
across company name and website domain, optional lifecycle-status filtering,
and offset pagination ordered by `created_at DESC, id DESC`. The persisted
record contains only the name, optional normalized website domain, evidence
quality for each, lifecycle status, and timestamps. Names may repeat within an
organization, but a non-empty domain may not.

Owners and admins can manually create a Company Prospect and transition its
lifecycle. Creation requires a non-blank name and accepts an optional fully
qualified website domain without a URL path. The domain is normalized to
lowercase; if it is omitted, its evidence quality must be `UNKNOWN`. Creation
starts in `IDENTIFIED`.

The supported lifecycle transitions are:

- `IDENTIFIED` to `REVIEWED` or `ARCHIVED`.
- `REVIEWED` to `IDENTIFIED` or `ARCHIVED`.
- `ARCHIVED` to `IDENTIFIED` (restore).

Invalid transitions are rejected. Creation and status changes are recorded as
activity events, but lifecycle changes do not create or modify Leads and do not
trigger workflows, webhooks, or outreach. There is no general Company Prospect
edit endpoint; the API supports creation and lifecycle changes, not editing
the saved name or domain.

The Company Prospects workspace provides manual creation for owners/admins,
search, status filtering, and pagination. The detail page shows saved fields,
evidence labels, and lifecycle actions. Its duplicate review is read-only.

## Fit scoring

`POST /api/v1/company-prospects/{prospect_id}/fit-score` computes a deterministic
score against the authenticated organization’s Ideal Customer Profile (ICP).
The supported criteria are industry, company size, and geography (country or
country plus region). Buyer role is not supported.

Scoring evidence is supplied with the request and is ephemeral: industry,
employee count or size band, and geography are not written to the Company
Prospect. Only `SOURCE_REPORTED` evidence is scored. Industry is compared to
configured targets by exact value after whitespace and case normalization.
Employee counts are checked against the configured inclusive range; a reported
size band is matched only when fully inside that range, is unmatched when
disjoint, and is `UNKNOWN` when it only partially overlaps. Geography is
compared with configured country or country-region targets. Missing, ambiguous,
unsupported, or lower-confidence evidence is `UNKNOWN`, not a match.

The returned score is the weighted percentage of assessable criteria that
matched. Unknown criteria are excluded from that score but reduce confidence.
Confidence is the assessable active weight as a percentage of the configured
active weight.
Fit bands are `STRONG` at 75 or above, `MODERATE` from 50 through 74, and `WEAK`
below 50. If no criterion can be assessed, the score is null and fit is
`UNKNOWN`. The response is not persisted, and this endpoint does not update the
Company Prospect or produce automation side effects.

## Duplicate assessment

Two authenticated, organization-scoped endpoints are available:

- `POST /api/v1/company-prospects/duplicate-assessment` evaluates a batch of up
  to 100 candidates.
- `GET /api/v1/company-prospects/{prospect_id}/duplicate-assessment` evaluates
  one saved Company Prospect against other saved records in its organization.

Assessment is deterministic and read-only. Website domains are normalized and
compared by exact fully qualified domain; for example, `www.example.com` and
`example.com` are not treated as equal. Company names are normalized for
comparison, including common trailing legal suffixes, and a name similarity
ratio of at least 0.85 is reported as a possible duplicate rather than an exact
match.

Persisted Company Prospects do not store a Corporate Identification Number
(CIN), so persisted CIN matching is unavailable. A valid CIN supplied for
candidates can be compared exactly within the submitted batch only. Conflicting
identifiers may produce `POSSIBLE_DUPLICATE`. `INSUFFICIENT_DATA` means no
supported identifier or usable name was available. `NEW` means no match was
found using the evidence this assessment supports; it is not proof that a
company is definitively new. Duplicate assessment does not merge, create, or
modify records.

## Discovery and import

`POST /api/v1/prospect-discovery/search` searches a fixed in-memory set of
synthetic business examples. These examples are explicitly unverified, are not
real company records, and are not saved to the CRM.

`POST /api/v1/prospect-discovery/government/search` can query the optional
government company-data provider. It is unavailable unless the server-side
provider-enabled setting and API key are configured. This search capability
does not itself authorize importing the results.

The dedicated Company Prospect import endpoint is
`POST /api/v1/prospect-discovery/company-prospects/import`. Import is blocked
unless `PROSPECT_DISCOVERY_APPROVED_IMPORT_SOURCE` is explicitly configured and
the request’s source label exactly matches it. The setting is unset by default,
so imports are rejected with `409 SOURCE_NOT_APPROVED` by default, including
synthetic discovery data. A permitted request also requires an owner/admin
membership and the `X-Prospect-Import-Confirmed: true` confirmation header.
When enabled, accepted items are created through the normal Company Prospect
creation service; discovery industry, size, geography, descriptions, and
provider payloads are not persisted on the Company Prospect record.

The Discovery Workspace currently keeps its Company Prospect import control
disabled and describes government results as read-only. Enabling the server
source setting does not add an import action to that UI. The separate
`POST /api/v1/prospect-discovery/preview` and `/import` CSV endpoints are for
previewing and importing CRM Leads; they are not Company Prospect CSV-import
endpoints.

## Implementation and test references

- [Company Prospect API](../backend/app/api/v1/company_prospects.py) and
  [service](../backend/app/services/company_prospect_service.py)
- [record model](../backend/app/models/company_prospect.py) and
  [request/response schemas](../backend/app/schemas/company_prospect.py)
- [fit-scoring service](../backend/app/services/lead_fit_scoring_service.py)
  and [scoring input schema](../backend/app/schemas/company_prospect_scoring.py)
- [duplicate-assessment service](../backend/app/services/company_duplicate_assessment_service.py)
- [discovery and import API](../backend/app/api/v1/prospect_discovery.py)
- [Company Prospect API tests](../backend/tests/test_company_prospects.py),
  [fit-scoring tests](../backend/tests/test_company_prospect_fit_scoring.py),
  [duplicate-assessment tests](../backend/tests/test_company_duplicate_assessment.py),
  and [discovery-import tests](../backend/tests/test_prospect_company_import.py)

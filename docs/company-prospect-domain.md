# Company Prospect Domain (Phase 4, Slice 1)

Company Prospects are a separate, tenant-owned record type and do not create or
modify Leads. Slice 1 persists only a company name, an optional operator-entered
website domain, evidence-quality labels for those values, lifecycle state, and
timestamps. Domain identity is unique within one organization; company names are
not unique. A missing domain may have only `UNKNOWN` evidence quality.

Lifecycle starts at `IDENTIFIED`; it may move to `REVIEWED` or `ARCHIVED`.
`REVIEWED` may return to `IDENTIFIED` or move to `ARCHIVED`, and `ARCHIVED` may
be restored to `IDENTIFIED`. These transitions have no lead or automation side
effects.

Evidence quality is one of `SOURCE_REPORTED`, `ESTIMATED`, `INFERRED`, or
`UNKNOWN`. The label records confidence category only; this slice stores no
source identity, source excerpt, raw payload, inferred firmographic data, or
personal contact information. Names and domains are accepted as user-supplied
values, never fetched or enriched from an external provider.

The Alembic migration is limited to those provider-independent fields. No field
in the migration depends on unresolved provider licensing or retention terms.
If later slices propose storing provider-sourced values or source evidence, that
storage must remain blocked until the applicable data-use and retention terms
are resolved. No CSV preview/import behavior, CRM import, lead workflow, webhook,
AI, drafting, email, or outreach behavior is part of this domain foundation.

## Read-only workspace (Phase 6E, Slice 1)

Authenticated organization members can use `/company-prospects` to browse
their organization’s persisted CompanyProspects. The workspace uses the
existing tenant-scoped list and detail APIs. The list supports optional
case-insensitive, whitespace-normalized search across company name and website
domain, optional lifecycle-status filtering, and offset pagination ordered by
`created_at DESC, id DESC`.

The workspace displays only persisted company fields and evidence-quality
labels. It has no create, edit, lifecycle, import, provider, lead, workflow,
webhook, outreach, or automation action. Organization identity is derived from
the authenticated membership; no organization identifier is accepted from the
client.

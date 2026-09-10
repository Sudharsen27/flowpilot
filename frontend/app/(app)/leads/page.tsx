"use client";

import { Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { DraftLeadResponseDialog } from "@/components/leads/draft-lead-response-dialog";
import { LeadFormDialog } from "@/components/leads/lead-form-dialog";
import { LeadOverview } from "@/components/leads/lead-overview";
import { LeadsTable } from "@/components/leads/leads-table";
import { LeadsToolbar } from "@/components/leads/leads-toolbar";
import { QualificationReadiness } from "@/components/leads/qualification-readiness";
import { QualifyLeadDialog } from "@/components/leads/qualify-lead-dialog";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { getLeads } from "@/lib/api/leads";
import type { Lead, LeadListResponse, LeadSource, LeadStatus } from "@/types/api";

const PAGE_SIZE = 20;

const emptyCounts: Record<LeadStatus, number> = {
  NEW: 0,
  CONTACTED: 0,
  QUALIFIED: 0,
  UNQUALIFIED: 0,
  CONVERTED: 0,
};

export default function LeadsPage() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<LeadStatus | "">("");
  const [source, setSource] = useState<LeadSource | "">("");
  const [offset, setOffset] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [page, setPage] = useState<LeadListResponse | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Lead | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [qualifying, setQualifying] = useState<Lead | null>(null);
  const [qualifyOpen, setQualifyOpen] = useState(false);
  const [qualifyKey, setQualifyKey] = useState(0);
  const [drafting, setDrafting] = useState<Lead | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [draftKey, setDraftKey] = useState(0);
  const [reviewDraftId, setReviewDraftId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getLeads({
      q: query.trim() || undefined,
      status: status || undefined,
      source: source || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then((data) => {
        if (!cancelled) {
          setPage(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHasError(true);
          setPage(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [offset, query, retryKey, source, status]);

  function beginFetch() {
    setIsLoading(true);
    setHasError(false);
  }

  function clearFilters() {
    beginFetch();
    setQuery("");
    setStatus("");
    setSource("");
    setOffset(0);
  }

  const summary: LeadListResponse | null = page
    ? {
        ...page,
        status_counts: { ...emptyCounts, ...page.status_counts },
      }
    : null;
  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Leads"
        description="Capture and manage enquiries for this organization. AI can analyze an enquiry and draft a reply without sending it or changing CRM status."
        primaryAction={
          <Button
            type="button"
            onClick={() => {
              setEditing(null);
              setFormKey((value) => value + 1);
              setFormOpen(true);
            }}
          >
            <Plus aria-hidden="true" />
            Create lead
          </Button>
        }
      />
      <LeadFormDialog
        key={`lead-form-${formKey}`}
        open={formOpen}
        lead={editing}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(null);
        }}
        onSaved={() => {
          beginFetch();
          setRetryKey((value) => value + 1);
        }}
      />
      <QualifyLeadDialog
        key={`lead-qualify-${qualifyKey}`}
        open={qualifyOpen}
        lead={qualifying}
        onOpenChange={(open) => {
          setQualifyOpen(open);
          if (!open) setQualifying(null);
        }}
        onCompleted={() => {
          beginFetch();
          setRetryKey((value) => value + 1);
        }}
      />
      <DraftLeadResponseDialog
        key={`lead-draft-${draftKey}`}
        open={draftOpen}
        lead={drafting}
        draftId={reviewDraftId}
        onOpenChange={(open) => {
          setDraftOpen(open);
          if (!open) {
            setDrafting(null);
            setReviewDraftId(null);
          }
        }}
        onCompleted={() => {
          beginFetch();
          setRetryKey((value) => value + 1);
        }}
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Lead overview"
          description="Counts come from saved leads in this organization. Follow-up tracking is not implemented yet."
        />
        <LeadOverview summary={summary} loading={isLoading && page === null} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Lead directory"
          description="Search and review leads stored for the current organization."
        />
        <LeadsToolbar
          query={query}
          status={status}
          source={source}
        onQueryChange={(value) => {
            beginFetch();
            setQuery(value);
            setOffset(0);
          }}
          onStatusChange={(value) => {
            beginFetch();
            setStatus(value);
            setOffset(0);
          }}
          onSourceChange={(value) => {
            beginFetch();
            setSource(value);
            setOffset(0);
          }}
          onClearFilters={clearFilters}
        />
        {hasError ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Leads could not be loaded"
            description="The lead directory is unavailable right now. Retry to load the current organization's leads."
            action={
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  beginFetch();
                  setRetryKey((value) => value + 1);
                }}
              >
                Retry
              </Button>
            }
          />
        ) : (
          <>
            <LeadsTable
              leads={page?.items ?? []}
              loading={isLoading}
              onEdit={(lead) => {
                setEditing(lead);
                setFormKey((value) => value + 1);
                setFormOpen(true);
              }}
              onQualify={(lead) => {
                setQualifying(lead);
                setQualifyKey((value) => value + 1);
                setQualifyOpen(true);
              }}
              onDraftResponse={(lead) => {
                setReviewDraftId(null);
                setDrafting(lead);
                setDraftKey((value) => value + 1);
                setDraftOpen(true);
              }}
              onReviewDraft={(lead) => {
                setReviewDraftId(lead.latest_response_draft?.id ?? null);
                setDrafting(lead);
                setDraftKey((value) => value + 1);
                setDraftOpen(true);
              }}
            />
            {total > 0 ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-muted-foreground text-sm">
                  Showing {start}–{end} of {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={offset === 0 || isLoading}
                    onClick={() => {
                      beginFetch();
                      setOffset(Math.max(0, offset - PAGE_SIZE));
                    }}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={offset + PAGE_SIZE >= total || isLoading}
                    onClick={() => {
                      beginFetch();
                      setOffset(offset + PAGE_SIZE);
                    }}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="AI qualification"
          description="AI qualification is stored as analysis history. It is not the same as CRM pipeline status."
        />
        <QualificationReadiness />
      </section>
      <section className="grid gap-5">
        <SectionHeader
          title="AI response drafts"
          description="Generated replies are drafts only. Sending email or chat is not implemented."
        />
        <StatePanel
          kind="information"
          className="max-w-none"
          title="Nothing has been sent"
          description="Use Draft response to generate a reply, then edit, approve, or reject it. Approval does not send a message."
        />
      </section>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { formatTimestamp } from "@/components/agents/execution-status";
import { SalesRunStatusBadge } from "@/components/agents/sales-run-status-badge";
import { AiBadge } from "@/components/ai/ai-badge";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { FollowUpStatusBadge } from "@/components/leads/follow-up-status-badge";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/client";
import {
  getLeadFollowUp,
  getLeadQualification,
  getLeadResponseDraft,
} from "@/lib/api/leads";
import { getSalesRun, listLeadSalesRuns } from "@/lib/api/sales-runs";
import type {
  Lead,
  LeadFollowUp,
  LeadQualificationResult,
  LeadResponseDraftResult,
  SalesRun,
} from "@/types/api";

const PAGE_SIZE = 20;

const stageLabels: Record<SalesRun["stage"], string> = {
  MATCH_LEAD: "Match lead",
  QUALIFY: "Qualify",
  DRAFT: "Draft",
  AWAIT_APPROVAL: "Await approval",
  SEND: "Send",
  DONE: "Done",
};

type LeadSalesAgentHistoryProps = {
  open: boolean;
  lead: Lead | null;
  onOpenChange: (open: boolean) => void;
};

function listError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) {
    return "Your session has expired. Sign in again to view sales runs.";
  }
  return "Sales Agent history could not be loaded.";
}

function detailError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) {
    return "Your session has expired. Sign in again to view this sales run.";
  }
  if (cause instanceof ApiError && cause.status === 404) {
    return "This sales run could not be found.";
  }
  return "This sales run could not be loaded.";
}

export function LeadSalesAgentHistory({
  open,
  lead,
  onOpenChange,
}: LeadSalesAgentHistoryProps) {
  const [items, setItems] = useState<SalesRun[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SalesRun | null>(null);
  const [qualification, setQualification] = useState<LeadQualificationResult | null>(
    null,
  );
  const [draft, setDraft] = useState<LeadResponseDraftResult | null>(null);
  const [followUp, setFollowUp] = useState<LeadFollowUp | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailErrorMessage, setDetailErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !lead) return;
    let cancelled = false;
    void listLeadSalesRuns(lead.id, { limit: PAGE_SIZE, offset })
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setTotal(page.total);
        setError(null);
      })
      .catch((cause) => {
        if (cancelled) return;
        setItems([]);
        setTotal(0);
        setError(listError(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lead, offset, open, refreshKey]);

  async function loadDetail(run: SalesRun) {
    if (!lead) return;
    setSelectedId(run.id);
    setDetailLoading(true);
    setDetailErrorMessage(null);
    setDetail(null);
    setQualification(null);
    setDraft(null);
    setFollowUp(null);
    try {
      const detailed = await getSalesRun(run.agent_id, run.id);
      const [nextQualification, nextDraft, nextFollowUp] = await Promise.all([
        detailed.qualification_id
          ? getLeadQualification(lead.id, detailed.qualification_id)
          : Promise.resolve(null),
        detailed.response_draft_id
          ? getLeadResponseDraft(lead.id, detailed.response_draft_id)
          : Promise.resolve(null),
        detailed.follow_up_id
          ? getLeadFollowUp(lead.id, detailed.follow_up_id)
          : Promise.resolve(null),
      ]);
      setDetail(detailed);
      setQualification(nextQualification);
      setDraft(nextDraft);
      setFollowUp(nextFollowUp);
    } catch (cause) {
      setDetailErrorMessage(detailError(cause));
    } finally {
      setDetailLoading(false);
    }
  }

  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);
  const showingDetail = selectedId !== null;

  const columns: DataTableColumn<SalesRun>[] = [
    {
      key: "status",
      header: "Status",
      cell: (row) => (
        <span className="inline-flex flex-wrap items-center gap-2">
          <SalesRunStatusBadge status={row.status} />
          {row.status === "COMPLETED" && row.email_send?.status === "SENT" ? (
            <span className="text-muted-foreground text-xs">
              Email sent
              {row.email_send.completed_at
                ? ` ${formatTimestamp(row.email_send.completed_at)}`
                : ""}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "stage",
      header: "Stage",
      cell: (row) => stageLabels[row.stage],
    },
    {
      key: "created",
      header: "Created",
      cell: (row) => formatTimestamp(row.created_at) ?? "—",
    },
    {
      key: "updated",
      header: "Updated",
      cell: (row) => formatTimestamp(row.updated_at) ?? "—",
    },
    {
      key: "follow-up",
      header: "Follow-up",
      cell: (row) =>
        row.follow_up ? (
          <FollowUpStatusBadge
            followUp={{
              id: row.follow_up.id,
              lead_id: row.lead_id,
              type: row.follow_up.type,
              status: row.follow_up.status,
              due_at: row.follow_up.due_at,
              is_overdue: row.follow_up.is_overdue,
              notes: null,
              body_text: null,
              email_send_id: null,
              revision: 1,
              created_at: row.created_at,
              updated_at: row.updated_at,
              completed_at: null,
              cancelled_at: null,
            }}
          />
        ) : (
          "—"
        ),
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Sales Agent history</DialogTitle>
          <DialogDescription>
            {lead
              ? `Sales Agent runs for ${lead.name}. This is a record of existing work, not a live activity feed.`
              : "Sales Agent runs for this lead."}
          </DialogDescription>
        </DialogHeader>
        <p className="text-muted-foreground mt-3 text-sm">
          CRM status is separate from Sales Agent status. Standalone Analyze and
          Draft actions are not the same as a Sales Agent run.
        </p>
        {showingDetail ? (
          <div className="mt-4 grid gap-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="justify-self-start"
              onClick={() => {
                setSelectedId(null);
                setDetail(null);
                setQualification(null);
                setDraft(null);
                setFollowUp(null);
                setDetailErrorMessage(null);
              }}
            >
              All runs
            </Button>
            {detailLoading ? (
              <p className="text-muted-foreground text-sm" role="status">
                Loading sales run…
              </p>
            ) : null}
            {detailErrorMessage ? (
              <StatePanel
                kind="error"
                className="max-w-none"
                title="Sales run could not be loaded"
                description={detailErrorMessage}
                action={
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      const row = items.find((item) => item.id === selectedId);
                      if (row) void loadDetail(row);
                    }}
                  >
                    Retry
                  </Button>
                }
              />
            ) : null}
            {detail ? (
              <SalesRunHistoryDetail
                run={detail}
                qualification={qualification}
                draft={draft}
                followUp={followUp}
              />
            ) : null}
          </div>
        ) : error ? (
          <StatePanel
            kind="error"
            className="max-w-none mt-4"
            title="Sales Agent history could not be loaded"
            description={error}
            action={
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setLoading(true);
                  setRefreshKey((value) => value + 1);
                }}
              >
                Retry
              </Button>
            }
          />
        ) : (
          <div className="mt-4 grid gap-3">
            <DataTable
              className="max-w-none"
              columns={columns}
              rows={items}
              getRowKey={(row) => row.id}
              loading={loading}
              emptyTitle="No Sales Agent runs"
              emptyDescription="This lead has no Sales Agent runs yet. Standalone AI analysis or drafts may still exist separately."
              rowActions={(row) => (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void loadDetail(row)}
                >
                  View run
                </Button>
              )}
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
                    disabled={offset === 0 || loading}
                    onClick={() => {
                      setLoading(true);
                      setOffset(Math.max(0, offset - PAGE_SIZE));
                    }}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={offset + PAGE_SIZE >= total || loading}
                    onClick={() => {
                      setLoading(true);
                      setOffset(offset + PAGE_SIZE);
                    }}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        )}
        <DialogFooter>
          <DialogCancel>Close</DialogCancel>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SalesRunHistoryDetail({
  run,
  qualification,
  draft,
  followUp,
}: {
  run: SalesRun;
  qualification: LeadQualificationResult | null;
  draft: LeadResponseDraftResult | null;
  followUp: LeadFollowUp | null;
}) {
  const analysis = qualification?.analysis;
  const sentBody = draft?.latest_email_send?.body_text;

  return (
    <div className="grid gap-6">
      <section className="grid gap-3" aria-labelledby="sales-run-record-heading">
        <h3 id="sales-run-record-heading" className="text-sm font-medium">
          Sales run
        </h3>
        <dl className="grid gap-3">
          <DetailRow
            label="Status"
            value={<SalesRunStatusBadge status={run.status} />}
          />
          <DetailRow label="Stage" value={stageLabels[run.stage]} />
          <DetailRow
            label="Started"
            value={formatTimestamp(run.started_at) ?? "—"}
          />
          <DetailRow
            label="Completed"
            value={formatTimestamp(run.completed_at) ?? "—"}
          />
          <DetailRow
            label="Enquiry"
            value={run.enquiry?.trim() ? run.enquiry : "—"}
          />
          {run.error ? (
            <DetailRow label="Error" value={run.error} />
          ) : null}
        </dl>
      </section>

      <section className="grid gap-3" aria-labelledby="sales-run-qualification-heading">
        <div className="flex flex-wrap items-center gap-2">
          <h3 id="sales-run-qualification-heading" className="text-sm font-medium">
            Qualification for this run
          </h3>
          <AiBadge label="Analysis" />
        </div>
        {!run.qualification_id ? (
          <p className="text-muted-foreground text-sm">
            No qualification recorded for this run.
          </p>
        ) : analysis ? (
          <div className="grid gap-3 text-sm">
            <QualificationStatus status={analysis.qualification} />
            <p>{analysis.summary}</p>
            <p>
              Intent: {analysis.intent.replaceAll("_", " ").toLowerCase()}
            </p>
            <p>
              Self-reported model confidence (not calibrated):{" "}
              {analysis.confidence.toFixed(2)}
            </p>
            {analysis.qualification_reasons.length ? (
              <ul className="list-disc pl-5">
                {analysis.qualification_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : null}
            {analysis.missing_information.length ? (
              <div>
                <p className="font-medium">Missing information</p>
                <ul className="list-disc pl-5">
                  {analysis.missing_information.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysis.buying_signals.length ? (
              <div>
                <p className="font-medium">Buying signals</p>
                <ul className="list-disc pl-5">
                  {analysis.buying_signals.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">
            Qualification for this run is recorded but analysis is unavailable.
          </p>
        )}
      </section>

      <section className="grid gap-3" aria-labelledby="sales-run-draft-heading">
        <h3 id="sales-run-draft-heading" className="text-sm font-medium">
          Response draft for this run
        </h3>
        {!run.response_draft_id ? (
          <p className="text-muted-foreground text-sm">
            No response draft recorded for this run.
          </p>
        ) : draft ? (
          <dl className="grid gap-3">
            <DetailRow
              label="Review"
              value={draft.review_status ?? draft.status}
            />
            <DetailRow
              label="Response"
              value={draft.response?.trim() ? draft.response : "—"}
            />
          </dl>
        ) : (
          <p className="text-muted-foreground text-sm">
            Draft for this run could not be displayed.
          </p>
        )}
      </section>

      <section className="grid gap-3" aria-labelledby="sales-run-email-heading">
        <h3 id="sales-run-email-heading" className="text-sm font-medium">
          Email send for this run
        </h3>
        {!run.email_send_id && !run.email_send ? (
          <p className="text-muted-foreground text-sm">
            No email send recorded for this run.
          </p>
        ) : (
          <dl className="grid gap-3">
            <DetailRow
              label="Status"
              value={run.email_send?.status ?? "—"}
            />
            <DetailRow
              label="Sent"
              value={
                formatTimestamp(run.email_send?.completed_at ?? null) ?? "—"
              }
            />
            {sentBody ? <DetailRow label="Sent body" value={sentBody} /> : null}
          </dl>
        )}
      </section>

      <section className="grid gap-3" aria-labelledby="sales-run-follow-up-heading">
        <h3 id="sales-run-follow-up-heading" className="text-sm font-medium">
          Follow-up for this run
        </h3>
        {!run.follow_up_id ? (
          <p className="text-muted-foreground text-sm">
            No follow-up recorded for this run.
          </p>
        ) : followUp ? (
          <dl className="grid gap-3">
            <DetailRow
              label="Status"
              value={<FollowUpStatusBadge followUp={followUp} />}
            />
            <DetailRow
              label="Type"
              value={
                followUp.type === "EMAIL_FOLLOW_UP"
                  ? "Email follow-up"
                  : "Manual follow-up"
              }
            />
            <DetailRow
              label="Due"
              value={formatTimestamp(followUp.due_at) ?? "—"}
            />
          </dl>
        ) : (
          <p className="text-muted-foreground text-sm">
            Follow-up for this run could not be displayed.
          </p>
        )}
      </section>
    </div>
  );
}

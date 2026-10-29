"use client";

import { RefreshCw, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentExecutionDetailPanel } from "@/components/agents/agent-execution-detail";
import {
  EXECUTION_STATUS_LABELS,
  ExecutionStatusBadge,
  formatDuration,
  formatFailureCategory,
  historyErrorMessage,
} from "@/components/agents/execution-status";
import {
  OrganizationExecutionSummary,
  type ExecutionStatusCounts,
} from "@/components/agents/organization-execution-summary";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { EmptyState } from "@/components/empty-state";
import { Select } from "@/components/forms/select";
import { SectionHeader } from "@/components/layout/section-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  AGENT_EXECUTION_STATUSES,
  agentExecutionsUrlEquals,
  parseAgentExecutionsSearchParams,
  serializeAgentExecutionsSearchParams,
  type AgentExecutionsUrlState,
} from "@/lib/agent-executions-url";
import { getAgents, listOrganizationExecutions } from "@/lib/api/agents";
import type {
  Agent,
  AgentExecutionStatus,
  OrganizationExecutionListItem,
  OrganizationExecutionListResponse,
} from "@/types/api";

type LoadResult =
  | { key: string; page: OrganizationExecutionListResponse; error: null }
  | { key: string; page: null; error: string };

type SelectedExecution = { executionId: string; agentId: string };

const STALE_DESCRIPTION =
  "Still marked Running after the stale timeout. It may have stopped without reporting a result.";

function focusExecutionTrigger(executionId: string) {
  const triggers = Array.from(
    document.querySelectorAll<HTMLElement>(
      `[data-execution-trigger="${CSS.escape(executionId)}"]`,
    ),
  );
  const visible = triggers.find((element) => element.getClientRects().length > 0);
  (visible ?? triggers[0])?.focus();
}

function AgentCell({ row }: { row: OrganizationExecutionListItem }) {
  if (!row.agent_name) {
    return <span className="text-muted-foreground">Unknown agent</span>;
  }
  return (
    <Link
      href={`/agents/${encodeURIComponent(row.agent_id)}`}
      className="font-medium break-words underline-offset-4 hover:underline"
    >
      {row.agent_name}
    </Link>
  );
}

function LeadCell({ row }: { row: OrganizationExecutionListItem }) {
  if (!row.lead_id) {
    return (
      <span className="text-muted-foreground">
        <span aria-hidden="true">—</span>
        <span className="sr-only">No lead</span>
      </span>
    );
  }
  if (!row.lead_name) {
    return <span className="text-muted-foreground">Lead unavailable</span>;
  }
  return (
    <Link
      href={`/leads/${encodeURIComponent(row.lead_id)}`}
      className="break-words underline-offset-4 hover:underline"
    >
      {row.lead_name}
    </Link>
  );
}

function StatusCell({ row }: { row: OrganizationExecutionListItem }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <ExecutionStatusBadge status={row.status} />
      {row.is_stale ? (
        <span title={STALE_DESCRIPTION} className="inline-flex">
          <StatusBadge status="warning" label="Stale" />
          <span className="sr-only">: {STALE_DESCRIPTION}</span>
        </span>
      ) : null}
    </div>
  );
}

function FailureCell({ row }: { row: OrganizationExecutionListItem }) {
  const category = formatFailureCategory(row.failure_category);
  if (!category && !row.error_preview) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <div className="grid gap-0.5">
      {category ? <span className="text-xs font-medium">{category}</span> : null}
      {row.error_preview ? (
        <span className="text-danger-text line-clamp-2 text-xs leading-5 break-words">
          {row.error_preview}
        </span>
      ) : null}
    </div>
  );
}

function DurationCell({ row }: { row: OrganizationExecutionListItem }) {
  const duration = formatDuration(row.duration_ms);
  if (duration) return <span className="tabular-nums">{duration}</span>;
  if (row.status === "RUNNING" || row.status === "QUEUED") {
    return <span className="text-muted-foreground">In progress</span>;
  }
  return <span className="text-muted-foreground">—</span>;
}

const columns: DataTableColumn<OrganizationExecutionListItem>[] = [
  {
    key: "status",
    header: "Status",
    cell: (row) => <StatusCell row={row} />,
    className: "w-40",
  },
  {
    key: "agent",
    header: "Agent",
    cell: (row) => <AgentCell row={row} />,
  },
  {
    key: "lead",
    header: "Lead",
    cell: (row) => <LeadCell row={row} />,
  },
  {
    key: "input",
    header: "Input",
    cell: (row) =>
      row.input_preview ? (
        <span className="line-clamp-2 leading-5 break-words">{row.input_preview}</span>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
    className: "min-w-56",
  },
  {
    key: "failure",
    header: "Failure",
    cell: (row) => <FailureCell row={row} />,
  },
  {
    key: "duration",
    header: "Duration",
    cell: (row) => <DurationCell row={row} />,
    className: "whitespace-nowrap",
  },
  {
    key: "created",
    header: "Created",
    cell: (row) => <RelativeTime value={row.created_at} />,
    className: "whitespace-nowrap",
  },
];

export function OrganizationExecutionsWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlState = useMemo(
    () => parseAgentExecutionsSearchParams(searchParams),
    [searchParams],
  );
  const [retryKey, setRetryKey] = useState(0);
  // The open execution lives in the URL but never changes the list request.
  const listKey = serializeAgentExecutionsSearchParams({
    ...urlState,
    executionId: null,
  });
  const requestKey = `${listKey}#${retryKey}`;

  const [result, setResult] = useState<LoadResult | null>(null);
  const [counts, setCounts] = useState<ExecutionStatusCounts | null>(null);
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [agentsFailed, setAgentsFailed] = useState(false);
  // Agent of the row the user opened, for runs outside an agent filter.
  const [agentHint, setAgentHint] = useState<SelectedExecution | null>(null);

  const isLoading = result?.key !== requestKey;
  const page = !isLoading && result ? result.page : null;
  const error = !isLoading && result ? result.error : null;

  useEffect(() => {
    let cancelled = false;
    void getAgents()
      .then((data) => {
        if (!cancelled) setAgents(data);
      })
      .catch(() => {
        if (!cancelled) setAgentsFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void listOrganizationExecutions({
      status: urlState.status ?? undefined,
      agentId: urlState.agentId ?? undefined,
      leadId: urlState.leadId ?? undefined,
      limit: urlState.limit,
      offset: urlState.offset,
    })
      .then((data) => {
        if (cancelled) return;
        setResult({ key: requestKey, page: data, error: null });
        setCounts(data.status_counts);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setResult({
          key: requestKey,
          page: null,
          error: historyErrorMessage(
            cause,
            "Agent executions could not be loaded. Please try again.",
            "Agent executions could not be found.",
          ),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [
    requestKey,
    urlState.agentId,
    urlState.leadId,
    urlState.limit,
    urlState.offset,
    urlState.status,
  ]);

  const replaceUrl = useCallback(
    (next: AgentExecutionsUrlState) => {
      const serialized = serializeAgentExecutionsSearchParams(next);
      if (serialized === searchParams.toString()) return;
      router.replace(serialized ? `${pathname}?${serialized}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  /** Any URL change that does not set `executionId` closes the detail panel. */
  function patchUrl(patch: Partial<AgentExecutionsUrlState>) {
    const next = { ...urlState, executionId: null, ...patch };
    if (agentExecutionsUrlEquals(next, urlState)) return;
    replaceUrl(next);
  }

  function applyFilter(patch: Partial<AgentExecutionsUrlState>) {
    patchUrl({ ...patch, offset: 0 });
  }

  const hasFilters =
    urlState.status !== null || urlState.agentId !== null || urlState.leadId !== null;

  function clearFilters() {
    applyFilter({ status: null, agentId: null, leadId: null });
  }

  function refresh() {
    patchUrl({});
    setRetryKey((key) => key + 1);
  }

  function openExecution(row: OrganizationExecutionListItem) {
    setAgentHint({ executionId: row.id, agentId: row.agent_id });
    patchUrl({ executionId: row.id });
  }

  function closeExecution() {
    const closedId = urlState.executionId;
    patchUrl({ executionId: null });
    if (closedId) queueMicrotask(() => focusExecutionTrigger(closedId));
  }

  const items = page?.items ?? [];
  const total = page?.total ?? 0;
  const pageLimit = page?.limit || urlState.limit;
  const offset = page?.offset ?? urlState.offset;
  const lastPageOffset =
    total === 0 ? 0 : Math.floor((total - 1) / pageLimit) * pageLimit;
  const rangeStart = items.length === 0 ? 0 : offset + 1;
  const rangeEnd = items.length === 0 ? 0 : Math.min(offset + items.length, total);
  const canPrevious = offset > 0;
  const canNext = offset + pageLimit < total;
  const staleOnPage = items.filter((item) => item.is_stale).length;

  const openExecutionId = urlState.executionId;
  const openAgentId = openExecutionId
    ? (items.find((item) => item.id === openExecutionId)?.agent_id ??
      (agentHint?.executionId === openExecutionId ? agentHint.agentId : null) ??
      urlState.agentId)
    : null;
  const selected: SelectedExecution | null =
    openExecutionId && openAgentId
      ? { executionId: openExecutionId, agentId: openAgentId }
      : null;

  const agentNameFromRows =
    items.find((item) => item.agent_id === urlState.agentId)?.agent_name ?? null;
  const selectedAgentMissing =
    urlState.agentId !== null &&
    !(agents ?? []).some((agent) => agent.id === urlState.agentId);
  const leadName =
    items.find((item) => item.lead_id === urlState.leadId)?.lead_name ?? null;

  function goToOffset(nextOffset: number) {
    patchUrl({ offset: Math.min(Math.max(0, nextOffset), lastPageOffset) });
  }

  return (
    <div className="gap-section flex flex-col">
      <section className="grid gap-5" aria-labelledby="execution-status-overview-heading">
        <SectionHeader
          id="execution-status-overview-heading"
          title="Status overview"
          description="How agent runs have ended across your organization."
        />
        <OrganizationExecutionSummary
          counts={counts}
          loading={isLoading}
          activeStatus={urlState.status}
          onSelectStatus={(status) => applyFilter({ status })}
        />
      </section>

      <section className="grid gap-5" aria-labelledby="execution-list-heading">
        <SectionHeader
          id="execution-list-heading"
          title="Execution history"
          description="Newest runs first. Open a run to inspect its stored input, output and tool activity."
          action={
            <Button
              type="button"
              variant="outline"
              onClick={refresh}
              disabled={isLoading}
            >
              <RefreshCw aria-hidden="true" />
              Refresh
            </Button>
          }
        />

        <div
          className="grid gap-3 sm:grid-cols-[12rem_minmax(0,16rem)_minmax(0,1fr)] sm:items-center"
          role="group"
          aria-label="Execution filters"
        >
          <Select
            aria-label="Execution status"
            value={urlState.status ?? ""}
            onChange={(event) =>
              applyFilter({
                status: (event.target.value || null) as AgentExecutionStatus | null,
              })
            }
          >
            <option value="">All statuses</option>
            {AGENT_EXECUTION_STATUSES.map((status) => (
              <option key={status} value={status}>
                {EXECUTION_STATUS_LABELS[status]}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Agent"
            aria-describedby={agentsFailed ? "execution-agent-filter-error" : undefined}
            value={urlState.agentId ?? ""}
            disabled={agentsFailed && urlState.agentId === null}
            onChange={(event) => applyFilter({ agentId: event.target.value || null })}
          >
            <option value="">All agents</option>
            {selectedAgentMissing && urlState.agentId ? (
              <option value={urlState.agentId}>
                {agentNameFromRows ?? "Selected agent"}
              </option>
            ) : null}
            {(agents ?? []).map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </Select>
          <div className="flex flex-wrap items-center gap-2">
            {urlState.leadId ? (
              <span className="border-border bg-surface-subtle inline-flex h-8 max-w-full items-center gap-1 rounded-md border pr-1 pl-2.5 text-sm">
                <span className="truncate">
                  Lead: {leadName ?? "Selected lead"}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label="Remove lead filter"
                  onClick={() => applyFilter({ leadId: null })}
                >
                  <X aria-hidden="true" />
                </Button>
              </span>
            ) : null}
            {hasFilters ? (
              <Button type="button" variant="ghost" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : null}
          </div>
        </div>
        {agentsFailed ? (
          <p
            id="execution-agent-filter-error"
            className="text-muted-foreground text-xs"
          >
            Agents could not be loaded, so the agent filter is unavailable.
          </p>
        ) : null}

        {error ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            headingLevel={3}
            title="Agent executions could not be loaded"
            description={error}
            action={
              <Button type="button" onClick={refresh}>
                Retry
              </Button>
            }
          />
        ) : !isLoading && items.length === 0 ? (
          total > 0 ? (
            <StatePanel
              className="max-w-none"
              headingLevel={3}
              title="No executions on this page"
              description={`There are ${total} matching executions, but none on this page.`}
              action={
                <Button type="button" variant="outline" onClick={() => patchUrl({ offset: 0 })}>
                  Go to first page
                </Button>
              }
            />
          ) : hasFilters ? (
            <StatePanel
              className="max-w-none"
              headingLevel={3}
              title="No executions match these filters"
              description="Try a different status, agent or lead, or clear the filters to see every run."
              action={
                <Button type="button" variant="outline" onClick={clearFilters}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <EmptyState
              headingLevel={3}
              title="No agent executions yet"
              description="Runs appear here once an agent is run from its workspace, a lead, or the Command Center."
              action={
                <Link href="/agents" className={buttonVariants({ variant: "outline" })}>
                  Open AI Agents
                </Link>
              }
            />
          )
        ) : (
          <>
            {staleOnPage > 0 ? (
              <p
                className="border-warning/30 bg-warning/10 text-warning-text rounded-md border px-3 py-2 text-sm leading-6"
                role="note"
              >
                {staleOnPage === 1
                  ? "1 running execution on this page looks stale."
                  : `${staleOnPage} running executions on this page look stale.`}{" "}
                They are still marked Running after the stale timeout and may have
                stopped without reporting a result.
              </p>
            ) : null}
            <DataTable
              columns={columns}
              rows={items}
              loading={isLoading}
              getRowKey={(row) => row.id}
              rowActions={(row) => (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-execution-trigger={row.id}
                  aria-pressed={selected?.executionId === row.id}
                  aria-label={`View execution ${row.id}`}
                  onClick={() => openExecution(row)}
                >
                  View
                </Button>
              )}
            />
            {!isLoading ? (
              <nav
                className="flex flex-wrap items-center justify-between gap-3"
                aria-label="Execution history pagination"
              >
                <p className="text-muted-foreground text-sm" aria-live="polite">
                  Showing {rangeStart}–{rangeEnd} of {total}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canPrevious}
                    aria-label="Previous executions page"
                    onClick={() => goToOffset(offset - pageLimit)}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={!canNext}
                    aria-label="Next executions page"
                    onClick={() => goToOffset(offset + pageLimit)}
                  >
                    Next
                  </Button>
                </div>
              </nav>
            ) : null}
          </>
        )}

        {selected ? (
          <AgentExecutionDetailPanel
            key={`${selected.agentId}:${selected.executionId}`}
            agentId={selected.agentId}
            executionId={selected.executionId}
            onClose={closeExecution}
          />
        ) : openExecutionId && !isLoading ? (
          <StatePanel
            className="max-w-none"
            headingLevel={3}
            title="This execution could not be opened"
            description="The link does not say which agent ran it. Filter by agent or open it from the list."
            action={
              <Button type="button" variant="outline" onClick={closeExecution}>
                Close
              </Button>
            }
          />
        ) : null}
      </section>
    </div>
  );
}

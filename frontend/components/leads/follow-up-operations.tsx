"use client";

import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { FollowUpExecutionDialog } from "@/components/leads/follow-up-execution-dialog";
import { FollowUpsOverview } from "@/components/leads/follow-ups-overview";
import { FollowUpsTable } from "@/components/leads/follow-ups-table";
import { LeadFollowUpsDialog } from "@/components/leads/lead-follow-ups-dialog";
import { Button } from "@/components/ui/button";
import { getFollowUpOperations, getLead } from "@/lib/api/leads";
import type {
  FollowUpOperationsItem,
  FollowUpOperationsResponse,
  Lead,
  LeadFollowUpStatus,
} from "@/types/api";

const PAGE_SIZE = 20;

type DueFilter = "" | "overdue" | "scheduled";

/**
 * Follow-up operations view. Every number and row comes from the API; nothing
 * is optimistic. A follow-up only reads as sent once its execution is SENT.
 */
export function FollowUpOperations() {
  const [status, setStatus] = useState<LeadFollowUpStatus | "">("");
  const [due, setDue] = useState<DueFilter>("");
  const [offset, setOffset] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [page, setPage] = useState<FollowUpOperationsResponse | null>(null);
  const [historyItem, setHistoryItem] = useState<FollowUpOperationsItem | null>(
    null,
  );
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const [manageLead, setManageLead] = useState<Lead | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [manageKey, setManageKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getFollowUpOperations({
      status: status || undefined,
      overdue: due === "" ? undefined : due === "overdue",
      limit: PAGE_SIZE,
      offset,
    })
      .then((data) => {
        if (!cancelled) setPage(data);
      })
      .catch(() => {
        if (!cancelled) {
          setHasError(true);
          setPage(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [due, offset, refreshKey, status]);

  function reload() {
    setIsLoading(true);
    setHasError(false);
    setRefreshKey((value) => value + 1);
  }

  async function openManage(item: FollowUpOperationsItem) {
    try {
      const lead = await getLead(item.lead.id);
      setManageLead(lead);
      setManageKey((value) => value + 1);
      setManageOpen(true);
    } catch {
      setHasError(true);
    }
  }

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="grid gap-5">
      <FollowUpsOverview
        summary={page?.summary ?? null}
        loading={isLoading && page === null}
      />

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-full sm:w-44">
          <Label htmlFor="follow-up-status" className="sr-only">
            Follow-up status
          </Label>
          <Select
            id="follow-up-status"
            value={status}
            onChange={(event) => {
              setIsLoading(true);
              setHasError(false);
              setStatus(event.target.value as LeadFollowUpStatus | "");
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="PENDING">Pending</option>
            <option value="COMPLETED">Completed</option>
            <option value="CANCELLED">Cancelled</option>
          </Select>
        </div>
        <div className="w-full sm:w-44">
          <Label htmlFor="follow-up-due" className="sr-only">
            Due window
          </Label>
          <Select
            id="follow-up-due"
            value={due}
            onChange={(event) => {
              setIsLoading(true);
              setHasError(false);
              setDue(event.target.value as DueFilter);
              setOffset(0);
            }}
          >
            <option value="">Any due date</option>
            <option value="overdue">Overdue only</option>
            <option value="scheduled">Not yet due</option>
          </Select>
        </div>
      </div>

      {hasError ? (
        <StatePanel
          kind="error"
          className="max-w-none"
          title="Follow-ups could not be loaded"
          description="The follow-up list is unavailable right now. Retry to load the current organization's follow-ups."
          action={
            <Button type="button" variant="outline" onClick={reload}>
              Retry
            </Button>
          }
        />
      ) : (
        <>
          <FollowUpsTable
            items={page?.items ?? []}
            loading={isLoading}
            onViewHistory={(item) => {
              setHistoryItem(item);
              setHistoryKey((value) => value + 1);
              setHistoryOpen(true);
            }}
            onManage={(item) => {
              void openManage(item);
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
                    setIsLoading(true);
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
                    setIsLoading(true);
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

      <FollowUpExecutionDialog
        key={`follow-up-history-${historyKey}`}
        open={historyOpen}
        item={historyItem}
        onOpenChange={(open) => {
          setHistoryOpen(open);
          if (!open) setHistoryItem(null);
        }}
      />
      <LeadFollowUpsDialog
        key={`follow-up-manage-${manageKey}`}
        open={manageOpen}
        lead={manageLead}
        onOpenChange={(open) => {
          setManageOpen(open);
          if (!open) setManageLead(null);
        }}
        onChanged={reload}
      />
    </div>
  );
}

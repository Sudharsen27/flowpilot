"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  type ApprovalDecisionState,
} from "@/components/approvals/human-control";
import { ApprovalDetail } from "@/components/approvals/approval-detail";
import { ApprovalQueue } from "@/components/approvals/approval-queue";
import { StatePanel } from "@/components/data-display/state-panel";
import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getApprovals } from "@/lib/api/approvals";
import {
  APPROVALS_PAGE_SIZE,
  type ApprovalsUrlState,
  approvalsUrlEquals,
  parseApprovalsSearchParams,
  serializeApprovalsSearchParams,
} from "@/lib/approvals-url";
import { cn } from "@/lib/utils";
import type {
  ApprovalListResponse,
  ApprovalQueueItem,
  ApprovalQueueStatus,
} from "@/types/api";

type MobileApprovalView = "queue" | "detail";

type ApprovalsWorkspaceProps = {
  onSummary?: (
    page: ApprovalListResponse | null,
    status: ApprovalQueueStatus,
  ) => void;
  onDecisionChange?: (decision: ApprovalDecisionState) => void;
};

function decisionFromItem(
  item: ApprovalQueueItem | null,
): ApprovalDecisionState {
  if (!item) return "idle";
  if (item.email?.status === "SENT") return "sent";
  if (item.draft.review_status === "APPROVED") return "approved";
  if (item.draft.review_status === "REJECTED") return "rejected";
  if (item.needs_approval) return "pending";
  return "idle";
}

function listFilterKey(state: ApprovalsUrlState) {
  return serializeApprovalsSearchParams({ ...state, approvalId: null });
}

function listSkeleton() {
  return (
    <div className="grid gap-0" role="status">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="border-border space-y-2 border-b p-4">
          <div className="flex justify-between gap-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-12" />
          </div>
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-full" />
        </div>
      ))}
      <span className="sr-only">Loading approvals</span>
    </div>
  );
}

export function ApprovalsWorkspace({
  onSummary,
  onDecisionChange,
}: ApprovalsWorkspaceProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlState = useMemo(
    () => parseApprovalsSearchParams(searchParams),
    [searchParams],
  );
  const filterKey = listFilterKey(urlState);

  const [mobileView, setMobileView] = useState<MobileApprovalView>(
    urlState.approvalId ? "detail" : "queue",
  );
  const [queryInput, setQueryInput] = useState(urlState.q);
  const [trackedUrlQuery, setTrackedUrlQuery] = useState(urlState.q);
  const [trackedFilterKey, setTrackedFilterKey] = useState(filterKey);
  const [trackedApprovalId, setTrackedApprovalId] = useState(
    urlState.approvalId,
  );
  const [retryKey, setRetryKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<ApprovalListResponse | null>(null);
  const [selectedCache, setSelectedCache] = useState<ApprovalQueueItem | null>(
    null,
  );

  // Match InboxWorkspace: adjust local UI state when the URL changes.
  // Do not call onSummary (parent state) here — that must stay in fetch callbacks.
  if (urlState.q !== trackedUrlQuery) {
    setTrackedUrlQuery(urlState.q);
    setQueryInput(urlState.q);
  }
  if (filterKey !== trackedFilterKey) {
    setTrackedFilterKey(filterKey);
    setLoading(true);
    setError(null);
  }
  if (urlState.approvalId !== trackedApprovalId) {
    setTrackedApprovalId(urlState.approvalId);
    if (urlState.approvalId) {
      setMobileView("detail");
    } else {
      setSelectedCache(null);
    }
  }

  const replaceUrl = useCallback(
    (next: ApprovalsUrlState) => {
      const serialized = serializeApprovalsSearchParams(next);
      if (serialized === searchParams.toString()) return;
      router.replace(serialized ? `${pathname}?${serialized}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = queryInput.trim();
      if (trimmed === urlState.q) return;
      replaceUrl({ ...urlState, q: trimmed, offset: 0 });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [queryInput, replaceUrl, urlState]);

  useEffect(() => {
    let cancelled = false;
    void getApprovals({
      q: urlState.q || undefined,
      status: urlState.status,
      limit: APPROVALS_PAGE_SIZE,
      offset: urlState.offset,
    })
      .then((data) => {
        if (cancelled) return;
        setPage(data);
        onSummary?.(data, urlState.status);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setPage(null);
        onSummary?.(null, urlState.status);
        setError(
          cause instanceof ApiError && cause.status === 401
            ? "Your session has expired. Sign in again to view approvals."
            : "Couldn't load approvals.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    filterKey,
    onSummary,
    retryKey,
    urlState.offset,
    urlState.q,
    urlState.status,
  ]);

  function patchUrl(patch: Partial<ApprovalsUrlState>) {
    const next = { ...urlState, ...patch };
    if (approvalsUrlEquals(next, urlState)) return;
    replaceUrl(next);
  }

  function clearFilters() {
    setQueryInput("");
    setTrackedUrlQuery("");
    replaceUrl({
      ...urlState,
      q: "",
      status: "pending",
      offset: 0,
    });
  }

  function retryList() {
    setLoading(true);
    setError(null);
    setRetryKey((value) => value + 1);
  }

  const selectedFromPage =
    page?.items.find((item) => item.draft_id === urlState.approvalId) ?? null;
  const selected =
    selectedFromPage ??
    (selectedCache?.draft_id === urlState.approvalId ? selectedCache : null);

  function selectApproval(item: ApprovalQueueItem) {
    setSelectedCache(item);
    patchUrl({ approvalId: item.draft_id });
    setMobileView("detail");
  }

  function handleChanged(next: ApprovalQueueItem) {
    setSelectedCache(next);
    const review = next.draft.review_status;

    if (urlState.status === "pending" && review === "APPROVED") {
      setPage((current) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.filter((item) => item.draft_id !== next.draft_id),
          total: Math.max(0, current.total - 1),
        };
      });
      replaceUrl({
        ...urlState,
        status: "approved",
        approvalId: next.draft_id,
        offset: 0,
      });
      setMobileView("detail");
      return;
    }

    if (urlState.status === "pending" && review === "REJECTED") {
      setPage((current) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.filter((item) => item.draft_id !== next.draft_id),
          total: Math.max(0, current.total - 1),
        };
      });
      replaceUrl({
        ...urlState,
        status: "rejected",
        approvalId: next.draft_id,
        offset: 0,
      });
      setMobileView("detail");
      return;
    }

    setPage((current) => {
      if (!current) return current;
      return {
        ...current,
        items: current.items.map((item) =>
          item.draft_id === next.draft_id ? next : item,
        ),
      };
    });
    setRetryKey((value) => value + 1);
  }

  const hasFilters = urlState.q !== "" || urlState.status !== "pending";
  const canPrevious = urlState.offset > 0;
  const canNext = Boolean(
    page && urlState.offset + page.limit < page.total,
  );
  const decision = decisionFromItem(selected);

  useEffect(() => {
    onDecisionChange?.(decision);
  }, [decision, onDecisionChange]);

  return (
    <div className="grid gap-3">
      <FilterBar
        search={
          <SearchInput
            id="approval-search"
            label="Search approvals"
            placeholder="Search name, email, or company"
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
            onClear={() => setQueryInput("")}
          />
        }
        activeFilterCount={[urlState.q.trim() !== "", urlState.status !== "pending"].filter(Boolean).length}
        onClearFilters={hasFilters ? clearFilters : undefined}
      >
        <div className="min-w-0">
          <Label htmlFor="approval-status" className="sr-only">
            Approval status
          </Label>
          <Select
            id="approval-status"
            value={urlState.status}
            onChange={(event) =>
              patchUrl({
                status: event.target.value as ApprovalQueueStatus,
                offset: 0,
                approvalId: null,
              })
            }
          >
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Select>
        </div>
      </FilterBar>

      <div
        className="bg-muted grid grid-cols-2 gap-1 rounded-lg p-1 md:hidden"
        role="group"
        aria-label="Mobile approval view"
      >
        <Button
          type="button"
          variant={mobileView === "queue" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "queue"}
          aria-controls="approval-queue-pane"
          onClick={() => setMobileView("queue")}
        >
          Approval queue
        </Button>
        <Button
          type="button"
          variant={mobileView === "detail" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "detail"}
          aria-controls="approval-detail-pane"
          onClick={() => setMobileView("detail")}
        >
          Review detail
        </Button>
      </div>

      <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <Card
          as="section"
          id="approval-queue-pane"
          className={cn(
            "min-h-[38rem] min-w-0 overflow-hidden",
            mobileView === "queue" ? "block" : "hidden",
            "md:block",
          )}
          aria-labelledby="approval-queue-title"
        >
          <header className="px-4 pt-4 pb-3 sm:px-5">
            <h3
              id="approval-queue-title"
              className="text-base font-medium tracking-tight"
            >
              Approval queue
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              What does FlowPilot need you to decide before anything is sent?
            </p>
          </header>

          {error ? (
            <div className="p-4">
              <StatePanel
                kind="error"
                title="Couldn't load approvals."
                description="Try again."
                className="max-w-none"
                action={
                  <Button type="button" variant="outline" onClick={retryList}>
                    Retry
                  </Button>
                }
              />
            </div>
          ) : loading ? (
            listSkeleton()
          ) : (
            <>
              <ApprovalQueue
                approvals={page?.items ?? []}
                selectedId={urlState.approvalId}
                onSelect={selectApproval}
                emptyTitle={
                  urlState.status === "pending"
                    ? "You're all caught up."
                    : `No ${urlState.status} responses`
                }
                emptyDescription={
                  urlState.status === "pending"
                    ? "No responses are waiting for your review."
                    : `No ${urlState.status} responses match this filter.`
                }
                emptyAction={
                  urlState.status === "pending" ? (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          patchUrl({
                            status: "approved",
                            offset: 0,
                            approvalId: null,
                          })
                        }
                      >
                        View approved
                      </Button>
                      <Link
                        href="/inbox"
                        className={cn(
                          buttonVariants({ variant: "ghost", size: "sm" }),
                        )}
                      >
                        Open Inbox
                      </Link>
                    </div>
                  ) : undefined
                }
              />
              {page && page.total > page.limit ? (
                <footer className="border-border flex items-center justify-between gap-2 border-t px-4 py-3">
                  <p className="text-muted-foreground text-xs">
                    Showing {page.offset + 1}–
                    {Math.min(page.offset + page.items.length, page.total)} of{" "}
                    {page.total}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={!canPrevious}
                      onClick={() =>
                        patchUrl({
                          offset: Math.max(0, urlState.offset - APPROVALS_PAGE_SIZE),
                        })
                      }
                    >
                      Previous
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={!canNext}
                      onClick={() =>
                        patchUrl({
                          offset: urlState.offset + APPROVALS_PAGE_SIZE,
                        })
                      }
                    >
                      Next
                    </Button>
                  </div>
                </footer>
              ) : null}
            </>
          )}
        </Card>

        <div
          id="approval-detail-pane"
          className={cn(
            "min-w-0",
            mobileView === "detail" ? "block" : "hidden",
            "md:block",
          )}
        >
          <ApprovalDetail
            key={selected?.draft_id ?? "none"}
            approval={selected}
            loading={loading && Boolean(urlState.approvalId) && !selected}
            onBack={() => {
              setMobileView("queue");
              patchUrl({ approvalId: null });
            }}
            onChanged={handleChanged}
          />
        </div>
      </div>
    </div>
  );
}

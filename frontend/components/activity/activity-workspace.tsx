"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ActivityDetail } from "@/components/activity/activity-detail";
import { ActivityTimeline } from "@/components/activity/activity-timeline";
import { ActivityToolbar } from "@/components/activity/activity-toolbar";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getActivity, listActivity } from "@/lib/api/activity";
import {
  ACTIVITY_PAGE_SIZE,
  hasActivityFilters,
  parseActivitySearchParams,
  serializeActivitySearchParams,
  type ActivityUrlState,
} from "@/lib/activity-url";
import { cn } from "@/lib/utils";
import type {
  ActivityEntityType,
  ActivityEvent,
  ActivityEventType,
  ActivityListResponse,
} from "@/types/api";

type MobileActivityView = "timeline" | "detail";

type ActivityWorkspaceProps = {
  onSummary?: (page: ActivityListResponse | null) => void;
};

export function ActivityWorkspace({ onSummary }: ActivityWorkspaceProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlState = useMemo(
    () => parseActivitySearchParams(searchParams),
    [searchParams],
  );
  const filtersActive = hasActivityFilters(urlState);

  const [mobileView, setMobileView] = useState<MobileActivityView>(
    urlState.eventId ? "detail" : "timeline",
  );
  const [queryInput, setQueryInput] = useState(urlState.q);
  const [trackedQuery, setTrackedQuery] = useState(urlState.q);
  const [retryKey, setRetryKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<ActivityListResponse | null>(null);
  const [selected, setSelected] = useState<ActivityEvent | null>(null);
  const [detailLoading, setDetailLoading] = useState(Boolean(urlState.eventId));
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailRetryKey, setDetailRetryKey] = useState(0);
  const detailHeadingRef = useRef<HTMLHeadingElement>(null);
  const detailRequestRef = useRef(0);
  const selectedIdRef = useRef<string | null>(urlState.eventId);

  const filterKey = [
    urlState.q,
    urlState.type,
    urlState.entityType,
    urlState.offset,
    retryKey,
  ].join("|");
  const [trackedFilterKey, setTrackedFilterKey] = useState(filterKey);
  const detailKey = `${urlState.eventId ?? ""}|${detailRetryKey}`;
  const [trackedDetailKey, setTrackedDetailKey] = useState(detailKey);

  // Match ApprovalsWorkspace: adjust local UI state when the URL changes.
  if (urlState.q !== trackedQuery) {
    setTrackedQuery(urlState.q);
    setQueryInput(urlState.q);
  }
  if (filterKey !== trackedFilterKey) {
    setTrackedFilterKey(filterKey);
    setLoading(true);
    setError(null);
  }
  if (detailKey !== trackedDetailKey) {
    setTrackedDetailKey(detailKey);
    if (urlState.eventId) {
      setDetailLoading(true);
      setDetailError(null);
      setMobileView("detail");
    }
  }

  const replaceUrl = useCallback(
    (next: ActivityUrlState) => {
      const serialized = serializeActivitySearchParams(next);
      if (serialized === searchParams.toString()) {
        return;
      }
      router.replace(serialized ? `${pathname}?${serialized}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  function patchUrl(patch: Partial<ActivityUrlState>) {
    replaceUrl({ ...urlState, ...patch });
  }

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = queryInput.trim();
      if (trimmed === urlState.q) {
        return;
      }
      replaceUrl({
        ...urlState,
        q: trimmed,
        offset: 0,
        eventId: null,
      });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [queryInput, replaceUrl, urlState]);

  useEffect(() => {
    let cancelled = false;
    void listActivity({
      q: urlState.q || undefined,
      type: urlState.type || undefined,
      entity_type: urlState.entityType || undefined,
      limit: ACTIVITY_PAGE_SIZE,
      offset: urlState.offset,
    })
      .then((data) => {
        if (cancelled) return;
        if (
          selectedIdRef.current &&
          !data.items.some((item) => item.id === selectedIdRef.current) &&
          selectedIdRef.current !== urlState.eventId
        ) {
          detailRequestRef.current += 1;
          selectedIdRef.current = null;
          setSelected(null);
          setDetailLoading(false);
          setDetailError(null);
          setMobileView("timeline");
        }
        setPage(data);
        onSummary?.(data);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setPage(null);
        onSummary?.(null);
        setError(
          cause instanceof ApiError && cause.status === 401
            ? "Your session has expired. Sign in again to view activity."
            : "Activity could not be loaded.",
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
    urlState.entityType,
    urlState.eventId,
    urlState.offset,
    urlState.q,
    urlState.type,
  ]);

  useEffect(() => {
    if (!urlState.eventId) {
      return;
    }
    const requestId = ++detailRequestRef.current;
    void getActivity(urlState.eventId)
      .then((detail) => {
        if (requestId !== detailRequestRef.current) return;
        selectedIdRef.current = detail.id;
        setSelected(detail);
      })
      .catch(() => {
        if (requestId !== detailRequestRef.current) return;
        setDetailError("Retry to load the complete recorded event.");
      })
      .finally(() => {
        if (requestId === detailRequestRef.current) setDetailLoading(false);
      });
  }, [detailKey, urlState.eventId]);

  const selectedId = selected?.id;

  useEffect(() => {
    if (mobileView === "detail" && selectedId) {
      detailHeadingRef.current?.focus();
    }
  }, [mobileView, selectedId]);

  function clearSelection() {
    detailRequestRef.current += 1;
    selectedIdRef.current = null;
    setSelected(null);
    setDetailLoading(false);
    setDetailError(null);
    setMobileView("timeline");
  }

  function selectEvent(event: ActivityEvent) {
    selectedIdRef.current = event.id;
    setSelected(event);
    setMobileView("detail");
    patchUrl({ eventId: event.id });
  }

  function clearFilters() {
    clearSelection();
    setQueryInput("");
    replaceUrl({
      q: "",
      type: "",
      entityType: "",
      offset: 0,
      eventId: null,
    });
  }

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : urlState.offset + 1;
  const end = Math.min(urlState.offset + ACTIVITY_PAGE_SIZE, total);

  return (
    <div className="grid gap-3">
      <div
        className="bg-muted grid grid-cols-2 gap-1 rounded-lg p-1 md:hidden"
        role="group"
        aria-label="Mobile activity view"
      >
        <Button
          type="button"
          variant={mobileView === "timeline" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "timeline"}
          aria-controls="activity-timeline-pane"
          onClick={() => setMobileView("timeline")}
        >
          Timeline
        </Button>
        <Button
          type="button"
          variant={mobileView === "detail" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "detail"}
          aria-controls="activity-detail-pane"
          onClick={() => setMobileView("detail")}
        >
          Event detail
        </Button>
      </div>

      <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
        <Card
          as="section"
          id="activity-timeline-pane"
          className={cn(
            "min-h-[40rem] min-w-0 overflow-hidden",
            mobileView === "timeline" ? "block" : "hidden",
            "md:block",
          )}
          aria-labelledby="activity-timeline-title"
        >
          <header className="px-4 pt-4 pb-3 sm:px-5">
            <h3
              id="activity-timeline-title"
              className="text-base font-medium tracking-tight"
            >
              Activity timeline
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Newest events across this organization.
            </p>
          </header>
          <div className="border-border border-t p-4">
            <ActivityToolbar
              query={queryInput}
              eventType={urlState.type}
              entityType={urlState.entityType}
              onQueryChange={setQueryInput}
              onEventTypeChange={(value: ActivityEventType | "") => {
                clearSelection();
                patchUrl({ type: value, offset: 0, eventId: null });
              }}
              onEntityTypeChange={(value: ActivityEntityType | "") => {
                clearSelection();
                patchUrl({ entityType: value, offset: 0, eventId: null });
              }}
              onClearFilters={clearFilters}
            />
          </div>
          {error ? (
            <div className="p-4">
              <StatePanel
                kind="error"
                title="Activity could not be loaded"
                description={error}
                action={
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setRetryKey((value) => value + 1)}
                  >
                    Retry
                  </Button>
                }
              />
            </div>
          ) : loading && page === null ? (
            <div className="grid gap-3 p-4" role="status">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <span className="sr-only">Loading activity</span>
            </div>
          ) : !loading && page && page.total === 0 && filtersActive ? (
            <div className="p-4">
              <StatePanel
                title="No matching activity"
                description="Nothing matches the current search or filters."
                action={
                  <Button type="button" variant="outline" onClick={clearFilters}>
                    Clear filters
                  </Button>
                }
              />
            </div>
          ) : (
            <ActivityTimeline
              events={page?.items ?? []}
              selectedId={selected?.id}
              onSelect={selectEvent}
            />
          )}
          {total > 0 ? (
            <div className="border-border flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
              <p className="text-muted-foreground text-sm">
                Showing {start}–{end} of {total}
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={urlState.offset === 0 || loading}
                  onClick={() => {
                    clearSelection();
                    patchUrl({
                      offset: Math.max(0, urlState.offset - ACTIVITY_PAGE_SIZE),
                      eventId: null,
                    });
                  }}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    urlState.offset + ACTIVITY_PAGE_SIZE >= total || loading
                  }
                  onClick={() => {
                    clearSelection();
                    patchUrl({
                      offset: urlState.offset + ACTIVITY_PAGE_SIZE,
                      eventId: null,
                    });
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </Card>

        <div
          id="activity-detail-pane"
          className={cn(
            "min-w-0",
            mobileView === "detail" ? "block" : "hidden",
            "md:block",
          )}
        >
          <ActivityDetail
            event={selected}
            loading={detailLoading}
            error={detailError}
            onRetry={
              urlState.eventId
                ? () => setDetailRetryKey((value) => value + 1)
                : undefined
            }
            onBack={() => setMobileView("timeline")}
            headingRef={detailHeadingRef}
          />
        </div>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { ActivityDetail } from "@/components/activity/activity-detail";
import { ActivityTimeline } from "@/components/activity/activity-timeline";
import { ActivityToolbar } from "@/components/activity/activity-toolbar";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";
import { getActivity, listActivity } from "@/lib/api/activity";
import type {
  ActivityEntityType,
  ActivityEvent,
  ActivityEventType,
  ActivityListResponse,
} from "@/types/api";

const PAGE_SIZE = 20;

type MobileActivityView = "timeline" | "detail";

type ActivityWorkspaceProps = {
  onSummary?: (page: ActivityListResponse | null) => void;
};

export function ActivityWorkspace({ onSummary }: ActivityWorkspaceProps) {
  const [mobileView, setMobileView] = useState<MobileActivityView>("timeline");
  const [query, setQuery] = useState("");
  const [eventType, setEventType] = useState<ActivityEventType | "">("");
  const [entityType, setEntityType] = useState<ActivityEntityType | "">("");
  const [offset, setOffset] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<ActivityListResponse | null>(null);
  const [selected, setSelected] = useState<ActivityEvent | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void listActivity({
      q: query.trim() || undefined,
      type: eventType || undefined,
      entity_type: entityType || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then((data) => {
        if (cancelled) return;
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
  }, [entityType, eventType, offset, onSummary, query, retryKey]);

  function beginFetch() {
    setLoading(true);
    setError(null);
  }

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);

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
              query={query}
              eventType={eventType}
              entityType={entityType}
              onQueryChange={(value) => {
                beginFetch();
                setQuery(value);
                setOffset(0);
              }}
              onEventTypeChange={(value) => {
                beginFetch();
                setEventType(value);
                setOffset(0);
              }}
              onEntityTypeChange={(value) => {
                beginFetch();
                setEntityType(value);
                setOffset(0);
              }}
              onClearFilters={() => {
                beginFetch();
                setQuery("");
                setEventType("");
                setEntityType("");
                setOffset(0);
              }}
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
                    onClick={() => {
                      beginFetch();
                      setRetryKey((value) => value + 1);
                    }}
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
          ) : !loading && page && page.total === 0 && (query.trim() || eventType || entityType) ? (
            <div className="p-4">
              <StatePanel
                title="No matching activity"
                description="Nothing matches the current search or filters."
              />
            </div>
          ) : (
            <ActivityTimeline
              events={page?.items ?? []}
              selectedId={selected?.id}
              onSelect={(event) => {
                setSelected(event);
                setMobileView("detail");
                setDetailLoading(true);
                void getActivity(event.id)
                  .then((detail) => setSelected(detail))
                  .catch(() => setSelected(event))
                  .finally(() => setDetailLoading(false));
              }}
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
                  disabled={offset === 0 || loading}
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
                  disabled={offset + PAGE_SIZE >= total || loading}
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
            onBack={() => setMobileView("timeline")}
          />
        </div>
      </div>
    </div>
  );
}

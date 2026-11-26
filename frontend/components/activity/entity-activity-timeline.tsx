"use client";

import { useEffect, useRef, useState } from "react";

import { ActivityDetail } from "@/components/activity/activity-detail";
import { ActivityTimeline } from "@/components/activity/activity-timeline";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getActivity, listActivity } from "@/lib/api/activity";
import type {
  ActivityEntityType,
  ActivityEvent,
  ActivityListResponse,
} from "@/types/api";

const PAGE_SIZE = 20;

type EntityActivityTimelineProps = {
  entityType: Extract<ActivityEntityType, "CONTACT" | "COMPANY">;
  entityId: string;
};

type ListState =
  | {
      scopeKey: string;
      offset: number;
      status: "ready";
      page: ActivityListResponse;
    }
  | {
      scopeKey: string;
      offset: number;
      status: "error";
      message: string;
    };

type SelectedActivity = {
  scopeKey: string;
  eventId: string;
  event: ActivityEvent;
  loading: boolean;
  error: string | null;
};

export function EntityActivityTimeline({
  entityType,
  entityId,
}: EntityActivityTimelineProps) {
  const scopeKey = JSON.stringify([entityType, entityId]);
  const [uiState, setUiState] = useState<{
    scopeKey: string;
    offset: number;
    selected: SelectedActivity | null;
    detailRetryKey: number;
  }>(() => ({
    scopeKey,
    offset: 0,
    selected: null,
    detailRetryKey: 0,
  }));
  if (uiState.scopeKey !== scopeKey) {
    setUiState({
      scopeKey,
      offset: 0,
      selected: null,
      detailRetryKey: 0,
    });
  }
  const offset = uiState.offset;
  const [listState, setListState] = useState<ListState | null>(null);
  const [listRetryKey, setListRetryKey] = useState(0);
  const listRequestId = useRef(0);
  const detailRequestId = useRef(0);

  const currentListState =
    listState?.scopeKey === scopeKey && listState.offset === offset
      ? listState
      : null;
  const currentPage =
    currentListState?.status === "ready" ? currentListState.page : null;
  const selectedActivity = uiState.selected;
  const selectedEventId = selectedActivity?.eventId;

  useEffect(() => {
    const controller = new AbortController();
    const requestId = ++listRequestId.current;

    void listActivity(
      {
        entity_type: entityType,
        entity_id: entityId,
        limit: PAGE_SIZE,
        offset,
      },
      { signal: controller.signal },
    )
      .then((page) => {
        if (controller.signal.aborted || requestId !== listRequestId.current) {
          return;
        }
        setListState({ scopeKey, offset, status: "ready", page });
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted || requestId !== listRequestId.current) {
          return;
        }
        setListState({
          scopeKey,
          offset,
          status: "error",
          message:
            cause instanceof ApiError && cause.status === 401
              ? "Your session has expired. Sign in again to view activity."
              : "Activity could not be loaded.",
        });
      });

    return () => controller.abort();
  }, [entityId, entityType, listRetryKey, offset, scopeKey]);

  useEffect(() => {
    if (!selectedEventId) return;

    const controller = new AbortController();
    const requestId = ++detailRequestId.current;

    void getActivity(selectedEventId, { signal: controller.signal })
      .then((event) => {
        if (
          controller.signal.aborted ||
          requestId !== detailRequestId.current
        ) {
          return;
        }
        setUiState((current) =>
          current.scopeKey === scopeKey &&
          current.selected?.eventId === selectedEventId
            ? {
                ...current,
                selected: {
                  ...current.selected,
                  event,
                  loading: false,
                  error: null,
                },
              }
            : current,
        );
      })
      .catch(() => {
        if (
          controller.signal.aborted ||
          requestId !== detailRequestId.current
        ) {
          return;
        }
        setUiState((current) =>
          current.scopeKey === scopeKey &&
          current.selected?.eventId === selectedEventId
            ? {
                ...current,
                selected: {
                  ...current.selected,
                  loading: false,
                  error: "Event details could not be loaded.",
                },
              }
            : current,
        );
      });

    return () => controller.abort();
  }, [scopeKey, selectedEventId, uiState.detailRetryKey]);

  function selectEvent(event: ActivityEvent) {
    if (selectedActivity?.eventId === event.id) return;

    setUiState((current) => ({
      ...current,
      selected: {
        scopeKey,
        eventId: event.id,
        event,
        loading: true,
        error: null,
      },
    }));
  }

  function retryList() {
    setListState(null);
    setListRetryKey((value) => value + 1);
  }

  function retryDetail() {
    setUiState((current) =>
      current.selected
        ? {
            ...current,
            detailRetryKey: current.detailRetryKey + 1,
            selected: {
              ...current.selected,
              loading: true,
              error: null,
            },
          }
        : current,
    );
  }

  function changePage(nextOffset: number) {
    setUiState((current) => ({
      ...current,
      offset: Math.max(0, nextOffset),
      selected: null,
    }));
  }

  const loading = currentListState === null;
  const error =
    currentListState?.status === "error" ? currentListState.message : null;
  const total = currentPage?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
      <Card
        as="section"
        className="min-w-0 overflow-hidden"
        aria-labelledby="entity-activity-title"
      >
        <header className="px-4 pt-4 pb-3 sm:px-5">
          <h2
            id="entity-activity-title"
            className="text-base font-medium tracking-tight"
          >
            Activity timeline
          </h2>
        </header>

        {error ? (
          <div className="p-4">
            <StatePanel
              kind="error"
              title="Activity could not be loaded"
              description={error}
              action={
                <Button type="button" variant="outline" onClick={retryList}>
                  Retry
                </Button>
              }
            />
          </div>
        ) : loading ? (
          <div className="grid gap-3 p-4" role="status" aria-busy="true">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <span className="sr-only">Loading activity</span>
          </div>
        ) : (
          <ActivityTimeline
            events={currentPage?.items ?? []}
            selectedId={selectedActivity?.eventId}
            onSelect={selectEvent}
          />
        )}

        {currentPage && total > 0 ? (
          <div className="border-border flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
            <p className="text-muted-foreground text-sm">
              Showing {start}–{end} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={offset === 0 || loading}
                onClick={() => changePage(offset - PAGE_SIZE)}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={offset + PAGE_SIZE >= total || loading}
                onClick={() => changePage(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </Card>

      <ActivityDetail
        event={selectedActivity?.event}
        loading={selectedActivity?.loading ?? false}
        error={selectedActivity?.error}
        onRetry={selectedActivity ? retryDetail : undefined}
      />
    </div>
  );
}

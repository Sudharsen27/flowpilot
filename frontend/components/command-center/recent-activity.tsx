"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ActivityTypeBadge } from "@/components/activity/activity-type-badge";
import { formatTimestamp } from "@/components/agents/execution-status";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { listActivity } from "@/lib/api/activity";
import type { ActivityEvent } from "@/types/api";

const RECENT_LIMIT = 8;

export function RecentActivity() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [items, setItems] = useState<ActivityEvent[]>([]);

  useEffect(() => {
    let cancelled = false;
    void listActivity({ limit: RECENT_LIMIT, offset: 0 })
      .then((page) => {
        if (!cancelled) setItems(page.items);
      })
      .catch(() => {
        if (!cancelled) {
          setItems([]);
          setError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

  return (
    <section className="grid gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-section-title font-medium tracking-tight">
            Recent activity
          </h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Newest organization events from live records.
          </p>
        </div>
        <Link
          href="/activity"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          View all activity
        </Link>
      </div>
      {loading ? (
        <div className="grid gap-3" role="status">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <span className="sr-only">Loading recent activity</span>
        </div>
      ) : error ? (
        <StatePanel
          kind="error"
          title="Recent activity could not be loaded"
          description="Retry to load the latest organization events."
          action={
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setLoading(true);
                setError(false);
                setRetryKey((value) => value + 1);
              }}
            >
              Retry
            </Button>
          }
        />
      ) : items.length === 0 ? (
        <StatePanel
          kind="information"
          title="No activity yet"
          description="Events will appear here after leads, Sales Agent work, email, or follow-ups are recorded."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul aria-label="Recent activity" className="divide-border divide-y">
              {items.map((event) => (
                <li key={event.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                  <ActivityTypeBadge type={event.type} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{event.title}</p>
                    <p className="text-muted-foreground text-xs">
                      {formatTimestamp(event.occurred_at) ?? "—"}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </section>
  );
}

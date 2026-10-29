"use client";

import { AlarmClock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DealStageBadge } from "@/components/deals/deal-stage-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { listDeals } from "@/lib/api/deals";
import { isClosedStage } from "@/lib/deals";
import { buildDealHref } from "@/lib/deals-url";
import { formatDateOnly, formatMoney } from "@/lib/money";
import type { Deal, PipelineSummary } from "@/types/api";

type Load = { status: "loading" } | { status: "ready"; deals: Deal[] } | { status: "error" };

type DealListKind = "recent" | "overdue";

function yesterday(): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

function fetchDeals(kind: DealListKind): Promise<Deal[]> {
  if (kind === "recent") return listDeals({ limit: 5 }).then((page) => page.items);
  return listDeals({ closeDateTo: yesterday(), limit: 50 }).then((page) =>
    page.items.filter((deal) => !isClosedStage(deal.stage)).slice(0, 5),
  );
}

function useDeals(kind: DealListKind, refreshKey: number) {
  const [state, setState] = useState<Load>({ status: "loading" });
  const [retryKey, setRetryKey] = useState(0);
  useEffect(() => {
    let cancelled = false;
    void fetchDeals(kind)
      .then((deals) => {
        if (!cancelled) setState({ status: "ready", deals });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [kind, refreshKey, retryKey]);
  return { state, retry: () => setRetryKey((key) => key + 1) };
}

function DealRows({ deals, emphasizeClose }: { deals: Deal[]; emphasizeClose?: boolean }) {
  return (
    <ul className="divide-border divide-y">
      {deals.map((deal) => (
        <li key={deal.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
          <div className="min-w-0 flex-1">
            <Link
              href={buildDealHref(deal.id)}
              className="block truncate text-sm font-medium underline-offset-4 hover:underline"
            >
              {deal.name}
            </Link>
            <p className="text-muted-foreground truncate text-xs">
              {deal.owner_name ?? "Unassigned"}
              {emphasizeClose ? (
                <> · due {formatDateOnly(deal.expected_close_date)}</>
              ) : (
                <>
                  {" "}
                  · updated <RelativeTime value={deal.updated_at} />
                </>
              )}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className="text-sm font-medium tabular-nums">{formatMoney(deal.amount, deal.currency)}</span>
            <DealStageBadge stage={deal.stage} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Frame({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  const id = `dashboard-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <Card as="section" aria-labelledby={id} className="grid content-start gap-4 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 id={id} className="text-sm font-medium">
            {title}
          </h2>
          <p className="text-muted-foreground mt-0.5 text-xs">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}

function Body({
  state,
  retry,
  empty,
  render,
}: {
  state: Load;
  retry: () => void;
  empty: string;
  render: (deals: Deal[]) => React.ReactNode;
}) {
  if (state.status === "loading") {
    return (
      <div className="grid gap-2" role="status">
        <Skeleton className="h-10" />
        <Skeleton className="h-10" />
        <span className="sr-only">Loading deals</span>
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <StatePanel
        kind="error"
        className="max-w-none border-0 p-0 shadow-none"
        headingLevel={3}
        title="Deals could not be loaded"
        description="Other dashboard sections are unaffected."
        action={
          <Button type="button" variant="outline" size="sm" onClick={retry}>
            Retry
          </Button>
        }
      />
    );
  }
  return state.deals.length === 0 ? (
    <p className="text-muted-foreground text-sm">{empty}</p>
  ) : (
    render(state.deals)
  );
}

export function RecentDeals({ refreshKey }: { refreshKey: number }) {
  const { state, retry } = useDeals("recent", refreshKey);
  return (
    <Frame
      title="Recent deals"
      description="Newest deals in your pipeline"
      action={
        <Link href="/deals" className={buttonVariants({ variant: "outline", size: "sm" })}>
          View all
        </Link>
      }
    >
      <Body
        state={state}
        retry={retry}
        empty="No deals yet. Create one from Deals or from a lead."
        render={(deals) => <DealRows deals={deals} />}
      />
    </Frame>
  );
}

/**
 * Open deals whose expected close date has passed. The count comes from the
 * pipeline summary (exact); the list shows the first few for quick action.
 */
export function DealsNeedingAttention({
  refreshKey,
  summary,
}: {
  refreshKey: number;
  summary: PipelineSummary | null | undefined;
}) {
  const { state, retry } = useDeals("overdue", refreshKey);
  const overdue = summary?.overdue_open;
  return (
    <Frame
      title="Deals needing attention"
      description={
        overdue
          ? overdue.count === 0
            ? "No open deals are past their expected close date"
            : `${overdue.count} open ${overdue.count === 1 ? "deal is" : "deals are"} past expected close · ${formatMoney(overdue.total_amount, summary.currency)}`
          : "Open deals past their expected close date"
      }
      action={<AlarmClock className="text-warning-text size-4" aria-hidden="true" />}
    >
      <Body
        state={state}
        retry={retry}
        empty="Nothing overdue. Every open deal is on schedule."
        render={(deals) => <DealRows deals={deals} emphasizeClose />}
      />
    </Frame>
  );
}

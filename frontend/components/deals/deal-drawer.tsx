"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DealHistoryList } from "@/components/deals/deal-history";
import { DealProbability, DealStageBadge } from "@/components/deals/deal-stage-badge";
import { ForecastCategoryBadge } from "@/components/deals/forecast-category-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button, buttonVariants } from "@/components/ui/button";
import { RelativeTime } from "@/components/ui/relative-time";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { getDealHistory } from "@/lib/api/deals";
import { buildDealHref } from "@/lib/deals-url";
import { buildLeadHref } from "@/lib/lead-url";
import { formatDateOnly, formatMoney } from "@/lib/money";
import type { Deal, DealHistoryEvent } from "@/types/api";

type HistoryState = { status: "loading" } | { status: "ready"; items: DealHistoryEvent[] } | { status: "error" };

/** Quick look at a deal without leaving the board; edits happen on the full page. */
export function DealDrawer({
  deal,
  onOpenChange,
}: {
  deal: Deal | null;
  onOpenChange: (open: boolean) => void;
}) {
  const [history, setHistory] = useState<HistoryState>({ status: "loading" });
  const [retryKey, setRetryKey] = useState(0);
  const dealId = deal?.id;

  useEffect(() => {
    if (!dealId) return;
    let cancelled = false;
    void getDealHistory(dealId, { limit: 50 })
      .then((page) => {
        if (!cancelled) setHistory({ status: "ready", items: page.items });
      })
      .catch(() => {
        if (!cancelled) setHistory({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [dealId, retryKey]);

  const leadHref = deal?.lead_id ? buildLeadHref(deal.lead_id) : null;

  return (
    <Sheet open={deal !== null} onOpenChange={onOpenChange}>
      <SheetContent>
        {deal ? (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <DealStageBadge stage={deal.stage} />
              </div>
              <SheetTitle>{deal.name}</SheetTitle>
              <SheetDescription>
                {formatMoney(deal.amount, deal.currency)} · closes {formatDateOnly(deal.expected_close_date)}
              </SheetDescription>
            </SheetHeader>
            <SheetBody className="grid content-start gap-6">
              <dl className="grid gap-4 sm:grid-cols-2">
                <DetailRow label="Probability" value={<DealProbability deal={deal} />} />
                <DetailRow
                  label="Forecast category"
                  value={<ForecastCategoryBadge stage={deal.stage} category={deal.forecast_category} />}
                />
                <DetailRow label="Owner" value={deal.owner_name ?? "Unassigned"} muted={!deal.owner_name} />
                <DetailRow
                  label="Lead"
                  value={
                    leadHref && deal.lead_name ? (
                      <Link href={leadHref} className="underline-offset-4 hover:underline">
                        {deal.lead_name}
                      </Link>
                    ) : (
                      "Not linked"
                    )
                  }
                  muted={!deal.lead_name}
                />
                <DetailRow label="In stage since" value={<RelativeTime value={deal.stage_entered_at} />} />
              </dl>
              <div className="grid gap-3">
                <h3 className="text-sm font-medium">History</h3>
                {history.status === "loading" ? (
                  <Skeleton className="h-24" />
                ) : history.status === "error" ? (
                  <StatePanel
                    kind="error"
                    className="max-w-none"
                    headingLevel={4}
                    title="History could not be loaded"
                    description="The deal details above are current."
                    action={
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setHistory({ status: "loading" });
                          setRetryKey((key) => key + 1);
                        }}
                      >
                        Retry
                      </Button>
                    }
                  />
                ) : (
                  <DealHistoryList events={history.items} currency={deal.currency} />
                )}
              </div>
            </SheetBody>
            <div className="border-border flex justify-end gap-2 border-t p-4">
              <Link href={buildDealHref(deal.id)} className={buttonVariants({ variant: "default" })}>
                Open deal
                <ExternalLink aria-hidden="true" />
              </Link>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

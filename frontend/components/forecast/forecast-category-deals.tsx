"use client";

import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { useId, useState, type ReactNode } from "react";

import { DealProbability, DealStageBadge } from "@/components/deals/deal-stage-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { CATEGORY_HINTS, Swatch } from "@/components/forecast/forecast-categories";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useForecastCategoryDeals } from "@/hooks/use-forecast-category-deals";
import { ApiError } from "@/lib/api/client";
import { formatAbsoluteTimestamp } from "@/lib/datetime";
import { FORECAST_CATEGORY_LABELS } from "@/lib/deals";
import { buildDealHref } from "@/lib/deals-url";
import {
  dealCount,
  FORECAST_DEALS_PAGE_SIZE,
  formatForecastPeriod,
  type ForecastDealsSelection,
  type ForecastUrlState,
} from "@/lib/forecast";
import { formatDateOnly, formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ForecastCategoryDeal, ForecastCategoryDeals, PipelineForecast } from "@/types/api";

const WHOLE_HORIZON = "";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    return "This period is no longer in the forecast horizon. Choose another period or reload the forecast.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have access to this organization's forecast.";
  }
  return "The deals could not be loaded. Your deals are unaffected.";
}

function rangeLabel(forecast: PipelineForecast, periodStart: string | null): string {
  const period = forecast.periods.find((row) => row.period_start === periodStart);
  if (period) return formatForecastPeriod(period, forecast.granularity);
  return `${formatDateOnly(forecast.horizon_start)} – ${formatDateOnly(forecast.horizon_end)}`;
}

function Figure({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid min-w-0 content-start gap-1">
      <dt className="text-muted-foreground text-xs font-medium">{term}</dt>
      {/* Amounts up to 999,999,999,999.99 wrap rather than overflow a narrow panel. */}
      <dd className="text-base font-semibold tabular-nums wrap-anywhere">{children}</dd>
    </div>
  );
}

function Fact({ term, children, muted }: { term: string; children: ReactNode; muted?: boolean }) {
  return (
    <div className="grid min-w-0 content-start gap-0.5">
      <dt className="text-muted-foreground text-xs">{term}</dt>
      <dd className={muted ? "text-muted-foreground text-sm" : "text-sm break-words"}>{children}</dd>
    </div>
  );
}

function DealItem({ deal }: { deal: ForecastCategoryDeal }) {
  return (
    <li className="grid gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <h4 className="min-w-0 text-sm font-medium break-words">
          <Link href={buildDealHref(deal.id)} className="underline-offset-4 hover:underline">
            {deal.name}
          </Link>
        </h4>
        <p className="text-sm font-semibold whitespace-nowrap tabular-nums">
          {formatMoney(deal.amount, deal.currency)}{" "}
          <span className="text-muted-foreground text-xs font-normal">{deal.currency}</span>
        </p>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        <Fact term="Stage">
          <DealStageBadge stage={deal.stage} />
        </Fact>
        <Fact term="Effective probability">
          <DealProbability deal={deal} />
        </Fact>
        <Fact term="Probability override" muted={deal.probability === null}>
          {deal.probability === null ? "None" : <span className="tabular-nums">{deal.probability}%</span>}
        </Fact>
        <Fact term="Weighted (est.)">
          <span className="tabular-nums">{formatMoney(deal.weighted_amount, deal.currency)}</span>
        </Fact>
        <Fact term="Expected close">{formatDateOnly(deal.expected_close_date)}</Fact>
        <Fact term="Owner" muted={!deal.owner_name}>
          {deal.owner_name ?? "Unassigned"}
        </Fact>
      </dl>
    </li>
  );
}

/**
 * Where to go when a refreshed page came back empty although its offset is past zero:
 * deals left the selection (e.g. after a deal changed) and the page is beyond the end.
 * That is the new last page, or the first when none are left. Always below the current
 * offset, so corrections cannot loop; null when the page is fine.
 */
export function correctedOffset(page: ForecastCategoryDeals, offset: number): number | null {
  if (page.offset !== offset || offset === 0 || page.items.length > 0) return null;
  const last =
    page.total === 0
      ? 0
      : Math.floor((page.total - 1) / FORECAST_DEALS_PAGE_SIZE) * FORECAST_DEALS_PAGE_SIZE;
  return last < offset ? last : null;
}

function DealsLoading() {
  return (
    <div className="grid gap-3" role="status">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-36 w-full" />
      <Skeleton className="h-36 w-full" />
      <span className="sr-only">Loading deals</span>
    </div>
  );
}

/** One category and period: API totals across every page, then the current page. */
function DrillDownBody({
  forecast,
  state,
  selection,
  onSelectionChange,
}: {
  forecast: PipelineForecast;
  state: ForecastUrlState;
  selection: ForecastDealsSelection;
  onSelectionChange: (next: ForecastDealsSelection) => void;
}) {
  // notBefore: after a correction, pages fetched before it are outdated (see below).
  const [{ offset, notBefore }, setPagination] = useState({ offset: 0, notBefore: 0 });
  const query = useForecastCategoryDeals(state, selection, offset, notBefore);
  // Outdated pages are fetched again and shown as loading, never as current figures.
  const page = query.data && query.dataUpdatedAt >= notBefore ? query.data : null;
  const showingPrevious = query.isPlaceholderData;
  const target = page && !showingPrevious ? correctedOffset(page, offset) : null;
  if (target !== null) {
    // Adjusting state while rendering: React re-renders before anything is shown, so
    // the empty page is never displayed. Pages cached before this response are outdated.
    setPagination({ offset: target, notBefore: query.dataUpdatedAt });
  }
  const setOffset = (next: number) => setPagination((current) => ({ ...current, offset: next }));
  const error = !page && query.isError && !query.isFetching ? errorMessage(query.error) : null;
  const label = FORECAST_CATEGORY_LABELS[selection.category];
  const listHeadingId = useId();
  const periodId = useId();

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : (page?.offset ?? offset) + 1;
  const end = Math.min((page?.offset ?? offset) + (page?.items.length ?? 0), total);

  return (
    <SheetBody className="grid content-start gap-5">
      <div className="grid gap-2 sm:max-w-sm">
        <Label htmlFor={periodId}>Period</Label>
        <Select
          id={periodId}
          value={selection.periodStart ?? WHOLE_HORIZON}
          onChange={(event) =>
            onSelectionChange({ ...selection, periodStart: event.target.value || null })
          }
        >
          <option value={WHOLE_HORIZON}>Whole horizon</option>
          {forecast.periods.map((period) => (
            <option key={period.period_start} value={period.period_start}>
              {formatForecastPeriod(period, forecast.granularity)}
            </option>
          ))}
        </Select>
      </div>

      {error ? (
        <StatePanel
          kind="error"
          className="max-w-none"
          headingLevel={3}
          title="Deals unavailable"
          description={error}
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => void query.refetch()}>
              Retry
            </Button>
          }
        />
      ) : !page ? (
        <DealsLoading />
      ) : (
        <>
          <section
            aria-label={`${label} totals`}
            className="border-border bg-surface-subtle grid gap-3 rounded-lg border p-4"
          >
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-[minmax(3rem,auto)_minmax(0,1fr)_minmax(0,1fr)]">
              <Figure term="Deals">{page.totals.count}</Figure>
              <Figure term="Full amount">{formatMoney(page.totals.total_amount, page.currency)}</Figure>
              <Figure term="Weighted (est.)">
                {formatMoney(page.totals.weighted_amount, page.currency)}
              </Figure>
            </dl>
            <p className="text-muted-foreground text-xs leading-5" aria-live="polite">
              {query.isFetching ? (
                <span className="inline-flex items-center gap-1.5">
                  <RefreshCw className="size-3 motion-safe:animate-spin" aria-hidden="true" />
                  Refreshing…
                </span>
              ) : query.isError ? (
                <span className="text-warning-text inline-flex flex-wrap items-center gap-x-2">
                  Could not refresh. Showing figures as of {formatAbsoluteTimestamp(page.as_of) ?? page.as_of}.
                  <Button
                    type="button"
                    variant="link"
                    size="xs"
                    className="h-auto px-0"
                    onClick={() => void query.refetch()}
                  >
                    Try again
                  </Button>
                </span>
              ) : (
                <>
                  Totals cover all {dealCount(page.totals.count)}, not only this page. Amounts in{" "}
                  {page.currency}. As of {formatAbsoluteTimestamp(page.as_of) ?? page.as_of}.
                </>
              )}
            </p>
          </section>

          {page.items.length === 0 && page.total === 0 ? (
            <StatePanel
              className="max-w-none"
              headingLevel={3}
              title={`No ${label} deals`}
              description={`No open ${page.currency} deals in ${label} are expected to close in ${rangeLabel(forecast, selection.periodStart)}.`}
            />
          ) : (
            <section aria-labelledby={listHeadingId} aria-busy={showingPrevious || undefined} className="grid gap-3">
              <h3 id={listHeadingId} className="sr-only">
                {label} deals on this page
              </h3>
              <ul
                className={cn(
                  "border-border bg-card divide-border divide-y rounded-lg border",
                  showingPrevious && "opacity-60",
                )}
              >
                {page.items.map((deal) => (
                  <DealItem key={deal.id} deal={deal} />
                ))}
              </ul>
              <nav
                className="flex flex-wrap items-center justify-between gap-3"
                aria-label={`${label} deals pagination`}
              >
                <p className="text-muted-foreground text-sm" aria-live="polite">
                  Showing {start}–{end} of {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={offset === 0 || showingPrevious}
                    aria-label={`Previous page of ${label} deals`}
                    onClick={() => setOffset(Math.max(0, offset - FORECAST_DEALS_PAGE_SIZE))}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={offset + FORECAST_DEALS_PAGE_SIZE >= total || showingPrevious}
                    aria-label={`Next page of ${label} deals`}
                    onClick={() => setOffset(offset + FORECAST_DEALS_PAGE_SIZE)}
                  >
                    Next
                  </Button>
                </div>
              </nav>
            </section>
          )}
        </>
      )}
    </SheetBody>
  );
}

/**
 * The deals behind a forecast category total, in a side panel. Uses the page's
 * granularity and horizon; the period can be narrowed to one of the forecast's periods.
 */
export function ForecastCategoryDealsSheet({
  forecast,
  state,
  selection,
  onSelectionChange,
}: {
  forecast: PipelineForecast;
  state: ForecastUrlState;
  selection: ForecastDealsSelection | null;
  onSelectionChange: (next: ForecastDealsSelection | null) => void;
}) {
  return (
    <Sheet open={selection !== null} onOpenChange={(open) => (open ? null : onSelectionChange(null))}>
      <SheetContent className="max-w-2xl">
        {selection ? (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <Swatch category={selection.category} />
                <span className="text-muted-foreground text-xs font-medium">
                  {CATEGORY_HINTS[selection.category]}
                </span>
              </div>
              <SheetTitle>{FORECAST_CATEGORY_LABELS[selection.category]} deals</SheetTitle>
              <SheetDescription>
                Open deals in {FORECAST_CATEGORY_LABELS[selection.category]} expected to close in{" "}
                {rangeLabel(forecast, selection.periodStart)}. Past-due and beyond-horizon deals are
                not included.
              </SheetDescription>
            </SheetHeader>
            <DrillDownBody
              // A new category or period starts again at its first page.
              key={`${selection.category}:${selection.periodStart ?? "horizon"}`}
              forecast={forecast}
              state={state}
              selection={selection}
              onSelectionChange={onSelectionChange}
            />
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

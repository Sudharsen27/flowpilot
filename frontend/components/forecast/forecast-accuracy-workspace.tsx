"use client";

import { TrendingUp } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { Checkbox } from "@/components/forms/checkbox";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { ForecastAccuracyLeads } from "@/components/forecast/forecast-accuracy-leads";
import { ForecastAccuracyMethodology } from "@/components/forecast/forecast-accuracy-methodology";
import { ForecastAccuracyChart, ForecastAccuracyTable } from "@/components/forecast/forecast-accuracy-months";
import { ForecastAccuracySummary } from "@/components/forecast/forecast-accuracy-summary";
import { ForecastStatus } from "@/components/forecast/forecast-workspace";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useForecastAccuracy } from "@/hooks/use-forecast-accuracy";
import { ApiError } from "@/lib/api/client";
import { formatAbsoluteTimestamp } from "@/lib/datetime";
import { FORECAST_PATH } from "@/lib/forecast";
import {
  ACCURACY_BASES,
  ACCURACY_BASIS_HINTS,
  ACCURACY_BASIS_LABELS,
  ACCURACY_LEADS,
  ACCURACY_RANGE_LABELS,
  ACCURACY_RANGE_OPTIONS,
  accuracyBasisLabel,
  accuracyLeadLabel,
  accuracyLeadShortLabel,
  accuracyMonthRange,
  currencyMismatchMonths,
  hasMonthsBeforeTracking,
  parseForecastAccuracySearchParams,
  serializeForecastAccuracySearchParams,
  type ForecastAccuracyUrlState,
} from "@/lib/forecast-accuracy";
import { formatMonth } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ForecastAccuracy } from "@/types/api";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have access to this organization's forecast.";
  }
  if (error instanceof ApiError && error.status === 404) {
    return "Forecast accuracy is not available on this server yet. Try again once the server has been updated.";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "This range is not supported. Choose a different range.";
  }
  return "Forecast accuracy could not be loaded. Your deals are unaffected.";
}

/** Single-choice button group, as used for the forecast's month/quarter switch. */
function Segmented<T extends string | number>({
  id,
  label,
  options,
  value,
  onChange,
}: {
  id: string;
  label: string;
  options: { value: T; label: string; title?: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="grid gap-2">
      <span id={id} className="text-sm leading-none font-medium">
        {label}
      </span>
      <div
        role="group"
        aria-labelledby={id}
        className="border-border bg-muted inline-flex w-fit max-w-full flex-wrap rounded-lg border p-0.5"
      >
        {options.map((option) => {
          const selected = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={selected}
              title={option.title}
              onClick={() => {
                if (!selected) onChange(option.value);
              }}
              className={cn(
                "focus-visible:ring-ring h-8 rounded-md px-3 text-sm font-medium outline-none focus-visible:ring-2",
                selected
                  ? "bg-background text-foreground shadow-card"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AccuracyControls({
  state,
  onChange,
  status,
}: {
  state: ForecastAccuracyUrlState;
  onChange: (next: ForecastAccuracyUrlState) => void;
  status: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
      <div className="grid gap-2 sm:w-52">
        <Label htmlFor="forecast-accuracy-range">Range</Label>
        <Select
          id="forecast-accuracy-range"
          value={String(state.range)}
          onChange={(event) => onChange({ ...state, range: Number.parseInt(event.target.value, 10) })}
        >
          {ACCURACY_RANGE_OPTIONS.map((range) => (
            <option key={range} value={range}>
              {ACCURACY_RANGE_LABELS[range]}
            </option>
          ))}
        </Select>
      </div>
      <label className="flex h-9 items-center gap-2 text-sm">
        <Checkbox
          checked={state.includeCurrent}
          onChange={(event) => onChange({ ...state, includeCurrent: event.target.checked })}
        />
        Include current month
      </label>
      <Segmented
        id="forecast-accuracy-lead-label"
        label="Forecast saved at"
        value={state.lead}
        onChange={(lead) => onChange({ ...state, lead })}
        options={ACCURACY_LEADS.map((lead) => ({
          value: lead,
          label: accuracyLeadShortLabel(lead),
          title: accuracyLeadLabel(lead),
        }))}
      />
      <Segmented
        id="forecast-accuracy-basis-label"
        label="Basis"
        value={state.basis}
        onChange={(basis) => onChange({ ...state, basis })}
        options={ACCURACY_BASES.map((basis) => ({
          value: basis,
          label: ACCURACY_BASIS_LABELS[basis],
          title: ACCURACY_BASIS_HINTS[basis],
        }))}
      />
      <div className="text-muted-foreground min-h-5 text-xs sm:ml-auto sm:pb-2.5 sm:text-right" aria-live="polite">
        {status}
      </div>
    </div>
  );
}

function AccuracyLoading() {
  return (
    <div className="grid gap-4" role="status">
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-64 w-full" />
      <span className="sr-only">Loading forecast accuracy</span>
    </div>
  );
}

function AccuracyNotices({ accuracy, lead }: { accuracy: ForecastAccuracy; lead: number }) {
  const mismatched = currencyMismatchMonths(accuracy).length;
  const started = accuracy.first_captured_at;
  return (
    <>
      {started && hasMonthsBeforeTracking(accuracy, lead) ? (
        <StatePanel
          className="max-w-none"
          title="Some months predate forecast tracking"
          description={`FlowPilot started saving forecasts on ${formatAbsoluteTimestamp(started) ?? started}. Months whose cutoff came earlier have no saved forecast to compare; accuracy fills in as each month closes.`}
        />
      ) : null}
      {mismatched > 0 ? (
        <StatePanel
          kind="unavailable"
          className="max-w-none"
          title="Some saved forecasts are in another currency"
          description={`${mismatched} ${mismatched === 1 ? "month has" : "months have"} a saved forecast in a currency other than ${accuracy.currency}. Those forecasts are not compared or converted.`}
        />
      ) : null}
    </>
  );
}

function AccuracyBody({
  accuracy,
  state,
  onChange,
}: {
  accuracy: ForecastAccuracy;
  state: ForecastAccuracyUrlState;
  onChange: (next: ForecastAccuracyUrlState) => void;
}) {
  if (accuracy.first_captured_at === null) {
    return (
      <>
        <StatePanel
          title="Forecast tracking has not started"
          description="FlowPilot saves a forecast snapshot once a day. Accuracy appears for each month after it closes, compared with the forecast saved before it began."
          action={
            <Link href={FORECAST_PATH} className={buttonVariants({ variant: "outline", size: "sm" })}>
              <TrendingUp aria-hidden="true" />
              View current forecast
            </Link>
          }
        />
        <ForecastAccuracyMethodology accuracy={accuracy} />
      </>
    );
  }
  return (
    <>
      <AccuracyNotices accuracy={accuracy} lead={state.lead} />
      <section className="grid gap-3" aria-labelledby="forecast-accuracy-summary-heading">
        <SectionHeader
          id="forecast-accuracy-summary-heading"
          title="Summary"
          description={`${accuracyLeadLabel(state.lead)}, ${accuracyBasisLabel(state.basis).toLowerCase()} basis, ${formatMonth(accuracy.from_month)} – ${formatMonth(accuracy.to_month)}. Closed months only; the month in progress is never scored.`}
        />
        <ForecastAccuracySummary accuracy={accuracy} lead={state.lead} basis={state.basis} />
      </section>
      <ForecastAccuracyLeads
        accuracy={accuracy}
        lead={state.lead}
        basis={state.basis}
        onSelect={(lead, basis) => onChange({ ...state, lead, basis })}
      />
      <ForecastAccuracyChart accuracy={accuracy} lead={state.lead} basis={state.basis} />
      <ForecastAccuracyTable accuracy={accuracy} lead={state.lead} basis={state.basis} />
      <ForecastAccuracyMethodology accuracy={accuracy} />
    </>
  );
}

export function ForecastAccuracyWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const state = useMemo(() => parseForecastAccuracySearchParams(searchParams), [searchParams]);
  // Fixed for the visit, so a range keeps one cache entry while the page is open.
  const [now] = useState(() => new Date());
  const range = useMemo(() => accuracyMonthRange(state, now), [state, now]);
  const query = useForecastAccuracy(range);

  // Data belongs to the current range only; a failed range shows its error until a
  // retry is in flight, then loads again.
  const accuracy = query.data ?? null;
  const error = !accuracy && query.isError && !query.isFetching ? errorMessage(query.error) : null;

  function changeState(next: ForecastAccuracyUrlState) {
    const serialized = serializeForecastAccuracySearchParams(next);
    if (serialized === searchParams.toString()) return;
    router.replace(serialized ? `${pathname}?${serialized}` : pathname, { scroll: false });
  }

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Forecast accuracy"
        description="How the forecasts FlowPilot saved each day compared with the revenue actually won. Calculated from stored snapshots and closed won deals, not by AI."
        secondaryActions={
          <Link href={FORECAST_PATH} className={buttonVariants({ variant: "outline" })}>
            <TrendingUp aria-hidden="true" />
            Back to forecast
          </Link>
        }
      />

      <AccuracyControls
        state={state}
        onChange={changeState}
        status={
          <ForecastStatus
            asOf={accuracy?.as_of ?? null}
            refreshing={Boolean(accuracy) && query.isFetching}
            refreshFailed={Boolean(accuracy) && query.isError}
            onRetry={() => void query.refetch()}
          />
        }
      />

      {error ? (
        <StatePanel
          kind="error"
          title="Forecast accuracy unavailable"
          description={error}
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => void query.refetch()}>
              Retry
            </Button>
          }
        />
      ) : accuracy ? (
        <AccuracyBody accuracy={accuracy} state={state} onChange={changeState} />
      ) : (
        <AccuracyLoading />
      )}
    </div>
  );
}

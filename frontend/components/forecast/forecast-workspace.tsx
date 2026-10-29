"use client";

import { Columns3, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, type ReactNode } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { ForecastKpis } from "@/components/forecast/forecast-kpis";
import { ForecastMethodology } from "@/components/forecast/forecast-methodology";
import { ForecastOutsideHorizon } from "@/components/forecast/forecast-outside-horizon";
import { ForecastChart, ForecastPeriodTable } from "@/components/forecast/forecast-periods";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePipelineForecast } from "@/hooks/use-pipeline-forecast";
import { ApiError } from "@/lib/api/client";
import { formatAbsoluteTimestamp } from "@/lib/datetime";
import {
  FORECAST_PERIOD_RULES,
  forecastHorizonLabel,
  forecastPeriodOptions,
  isForecastEmpty,
  parseForecastSearchParams,
  serializeForecastSearchParams,
  type ForecastUrlState,
} from "@/lib/forecast";
import { cn } from "@/lib/utils";
import type { ForecastGranularity } from "@/types/api";

const GRANULARITIES: { value: ForecastGranularity; label: string }[] = [
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    return "This forecast horizon is not supported. Choose a shorter horizon.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have access to this organization's forecast.";
  }
  return "The forecast could not be loaded. Your deals are unaffected.";
}

function ForecastControls({
  state,
  onChange,
  status,
}: {
  state: ForecastUrlState;
  onChange: (next: ForecastUrlState) => void;
  status: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
      <div className="grid gap-2">
        <span id="forecast-granularity-label" className="text-sm leading-none font-medium">
          View by
        </span>
        <div
          role="group"
          aria-labelledby="forecast-granularity-label"
          className="border-border bg-muted inline-flex w-fit rounded-lg border p-0.5"
        >
          {GRANULARITIES.map((option) => {
            const selected = option.value === state.granularity;
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={selected}
                onClick={() => {
                  if (selected) return;
                  // Each granularity has its own default horizon (4 quarters, 12 months).
                  onChange({
                    granularity: option.value,
                    periods: FORECAST_PERIOD_RULES[option.value].defaultPeriods,
                  });
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
      <div className="grid gap-2 sm:w-44">
        <Label htmlFor="forecast-periods">Horizon</Label>
        <Select
          id="forecast-periods"
          value={String(state.periods)}
          onChange={(event) =>
            onChange({ ...state, periods: Number.parseInt(event.target.value, 10) })
          }
        >
          {forecastPeriodOptions(state.granularity, state.periods).map((count) => (
            <option key={count} value={count}>
              {forecastHorizonLabel(state.granularity, count)}
            </option>
          ))}
        </Select>
      </div>
      <div className="text-muted-foreground min-h-5 text-xs sm:ml-auto sm:pb-2.5 sm:text-right" aria-live="polite">
        {status}
      </div>
    </div>
  );
}

/** As-of time, a quiet "Refreshing" while cached figures are re-checked, or a failed refresh. */
function ForecastStatus({
  asOf,
  refreshing,
  refreshFailed,
  onRetry,
}: {
  asOf: string | null;
  refreshing: boolean;
  refreshFailed: boolean;
  onRetry: () => void;
}) {
  if (!asOf) return null;
  const time = formatAbsoluteTimestamp(asOf) ?? asOf;
  if (refreshing) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <RefreshCw className="size-3 motion-safe:animate-spin" aria-hidden="true" />
        As of {time} · Refreshing…
      </span>
    );
  }
  if (refreshFailed) {
    return (
      <span className="text-warning-text inline-flex flex-wrap items-center gap-x-2">
        Could not refresh. Showing figures as of {time}.
        <Button type="button" variant="link" size="xs" className="h-auto px-0" onClick={onRetry}>
          Try again
        </Button>
      </span>
    );
  }
  return <span>As of {time}</span>;
}

function ForecastLoading() {
  return (
    <div className="grid gap-4" role="status">
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-48 w-full" />
      <span className="sr-only">Loading forecast</span>
    </div>
  );
}

export function ForecastWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlState = useMemo(() => parseForecastSearchParams(searchParams), [searchParams]);
  const query = usePipelineForecast(urlState);

  // Data belongs to the current key only (no placeholder from another horizon). A
  // failed horizon shows its error until a retry is in flight, then loads again.
  const forecast = query.data ?? null;
  const error = !forecast && query.isError && !query.isFetching ? errorMessage(query.error) : null;
  const isLoading = !forecast && !error;

  function changeState(next: ForecastUrlState) {
    const serialized = serializeForecastSearchParams(next);
    if (serialized === searchParams.toString()) return;
    router.replace(serialized ? `${pathname}?${serialized}` : pathname, { scroll: false });
  }

  const empty = forecast ? isForecastEmpty(forecast) : false;
  const excluded = forecast?.excluded_other_currency_count ?? 0;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Forecast"
        description="Won revenue and stage-probability-weighted pipeline from your saved deals. Weighted figures are estimates, not committed revenue."
        secondaryActions={
          <Link href="/deals/pipeline" className={buttonVariants({ variant: "outline" })}>
            <Columns3 aria-hidden="true" />
            Open pipeline
          </Link>
        }
      />

      <ForecastControls
        state={urlState}
        onChange={changeState}
        status={
          <ForecastStatus
            asOf={forecast?.as_of ?? null}
            refreshing={Boolean(forecast) && query.isFetching}
            refreshFailed={Boolean(forecast) && query.isError}
            onRetry={() => void query.refetch()}
          />
        }
      />

      {error ? (
        <StatePanel
          kind="error"
          title="Forecast unavailable"
          description={error}
          action={
            <Button type="button" variant="outline" size="sm" onClick={() => void query.refetch()}>
              Retry
            </Button>
          }
        />
      ) : (
        <>
          {excluded > 0 && forecast ? (
            <StatePanel
              kind="unavailable"
              className="max-w-none"
              title="Some deals are not included"
              description={`${excluded} ${excluded === 1 ? "deal uses" : "deals use"} a currency other than ${forecast.currency}. They are excluded from every figure on this page, not converted.`}
            />
          ) : null}

          <section className="grid gap-4" aria-labelledby="forecast-summary-heading" aria-busy={isLoading || undefined}>
            <h2 id="forecast-summary-heading" className="sr-only">
              Forecast summary
            </h2>
            <ForecastKpis forecast={forecast} />
          </section>

          {isLoading || !forecast ? (
            <ForecastLoading />
          ) : empty ? (
            <StatePanel
              title="No deals to forecast yet"
              description={`There are no open ${forecast.currency} deals and none were won in this horizon. Create a deal to start forecasting.`}
              action={
                <Link href="/deals?create=1" className={buttonVariants({ variant: "default", size: "sm" })}>
                  <Plus aria-hidden="true" />
                  New deal
                </Link>
              }
            />
          ) : (
            <>
              <ForecastChart forecast={forecast} />
              <ForecastPeriodTable forecast={forecast} />
              <ForecastOutsideHorizon forecast={forecast} />
            </>
          )}

          {forecast ? <ForecastMethodology forecast={forecast} /> : null}
        </>
      )}
    </div>
  );
}

import { CircleDollarSign, Scale, Target, Trophy } from "lucide-react";

import { MoneyValue } from "@/components/dashboard/dashboard-kpis";
import { MetricCard } from "@/components/data-display/metric-card";
import { MetricStrip } from "@/components/data-display/metric-strip";
import { dealCount } from "@/lib/forecast";
import { formatDateOnly } from "@/lib/money";
import type { PipelineForecast } from "@/types/api";

/**
 * Headline forecast figures, exactly as returned by the API. In-horizon figures come
 * first, all-horizon pipeline figures second, so the two scopes never sit side by side
 * as if they added up.
 */
export function ForecastKpis({ forecast }: { forecast: PipelineForecast | null }) {
  const loading = forecast === null;
  const money = (amount: string) =>
    forecast ? <MoneyValue amount={amount} currency={forecast.currency} /> : undefined;
  return (
    <MetricStrip className="sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        headingLevel={3}
        label="Won revenue (actual)"
        icon={<Trophy />}
        loading={loading}
        value={forecast ? money(forecast.won_in_horizon.total_amount) : undefined}
        description={
          forecast ? `${dealCount(forecast.won_in_horizon.count)} closed won in this horizon.` : undefined
        }
      />
      <MetricCard
        headingLevel={3}
        label="Projected revenue (in horizon)"
        icon={<Target />}
        loading={loading}
        value={forecast ? money(forecast.projected_in_horizon_amount) : undefined}
        description={
          forecast
            ? `Estimate: won plus weighted deals due ${formatDateOnly(forecast.horizon_start)} – ${formatDateOnly(forecast.horizon_end)}.`
            : undefined
        }
      />
      <MetricCard
        headingLevel={3}
        label="Open pipeline value"
        icon={<CircleDollarSign />}
        loading={loading}
        value={forecast ? money(forecast.open_pipeline.total_amount) : undefined}
        description={forecast ? `${dealCount(forecast.open_pipeline.count)} open, unweighted.` : undefined}
      />
      <MetricCard
        headingLevel={3}
        label="Weighted open pipeline (all horizons)"
        icon={<Scale />}
        loading={loading}
        // open_pipeline spans past-due, in-horizon and beyond-horizon deals; the API
        // has no in-horizon-only weighted total, so it is labelled as all horizons.
        value={forecast ? money(forecast.open_pipeline.weighted_amount) : undefined}
        description={
          forecast
            ? `Estimate across ${dealCount(forecast.open_pipeline.count)} open: past-due, in-horizon and beyond-horizon.`
            : undefined
        }
      />
    </MetricStrip>
  );
}

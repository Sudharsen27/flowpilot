import { CalendarClock, CalendarX2 } from "lucide-react";
import type { ReactNode } from "react";

import { SectionHeader } from "@/components/layout/section-header";
import { Card } from "@/components/ui/card";
import { dealCount } from "@/lib/forecast";
import { formatDateOnly, formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ForecastOpenTotals, PipelineForecast } from "@/types/api";

type BucketProps = {
  id: string;
  title: string;
  description: string;
  icon: ReactNode;
  /** Tint the icon to flag work that needs attention, without alarming colour elsewhere. */
  attention?: boolean;
  totals: ForecastOpenTotals;
  currency: string;
  extra?: ReactNode;
};

function Bucket({ id, title, description, icon, attention = false, totals, currency, extra }: BucketProps) {
  return (
    <Card as="section" aria-labelledby={id} className="grid content-start gap-3 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-md [&_svg]:size-4",
            attention ? "bg-warning/15 text-warning-text" : "bg-muted text-muted-foreground",
          )}
          aria-hidden="true"
        >
          {icon}
        </span>
        <div className="min-w-0">
          <h3 id={id} className="text-sm font-medium">
            {title}
          </h3>
          <p className="text-muted-foreground mt-0.5 text-xs leading-5">{description}</p>
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt className="text-muted-foreground text-xs">Open deals</dt>
          <dd className="font-medium tabular-nums">{totals.count}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Open value</dt>
          <dd className="font-medium tabular-nums">{formatMoney(totals.total_amount, currency)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Weighted value</dt>
          <dd className="font-medium tabular-nums">{formatMoney(totals.weighted_amount, currency)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Manual probability overrides</dt>
          <dd className="font-medium tabular-nums">{totals.override_count}</dd>
        </div>
        {extra}
      </dl>
    </Card>
  );
}

/** Open deals the forecast deliberately leaves out of its periods. */
export function ForecastOutsideHorizon({ forecast }: { forecast: PipelineForecast }) {
  const { past_due: pastDue, beyond_horizon: beyond, currency } = forecast;
  return (
    <section className="grid gap-3" aria-labelledby="forecast-outside-heading">
      <SectionHeader
        id="forecast-outside-heading"
        title="Pipeline outside the forecast periods"
        description="These open deals are not forecast into any period above."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Bucket
          id="forecast-past-due-heading"
          title="Past due"
          description={
            pastDue.count > 0
              ? `${dealCount(pastDue.count)} still open after the expected close date. Update the close date or stage to include them.`
              : "No open deals are past their expected close date."
          }
          icon={<CalendarX2 />}
          attention={pastDue.count > 0}
          totals={pastDue}
          currency={currency}
          extra={
            <div className="col-span-2">
              <dt className="text-muted-foreground text-xs">Oldest expected close</dt>
              <dd className="font-medium">{formatDateOnly(pastDue.oldest_expected_close_date)}</dd>
            </div>
          }
        />
        <Bucket
          id="forecast-beyond-heading"
          title="Beyond the horizon"
          description={`Open deals expected to close after ${formatDateOnly(forecast.horizon_end)}.`}
          icon={<CalendarClock />}
          totals={beyond}
          currency={currency}
        />
      </div>
    </section>
  );
}

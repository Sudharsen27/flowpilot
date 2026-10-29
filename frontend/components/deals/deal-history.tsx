import { DealStageBadge } from "@/components/deals/deal-stage-badge";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import { DEAL_STAGE_LABELS, FORECAST_CATEGORY_LABELS, forecastCategoryLabel } from "@/lib/deals";
import { formatDateOnly, formatMoney } from "@/lib/money";
import type { DealHistoryEvent } from "@/types/api";

/** An override value, or the stage default when there is none. */
function probabilityLabel(value: number | null | undefined): string {
  return value === null || value === undefined ? "the stage default" : `${value}% (override)`;
}

function describe(event: DealHistoryEvent, currency: string): string[] {
  if (event.changes.includes("CREATED")) {
    const created = [
      `Created in ${DEAL_STAGE_LABELS[event.new_stage]} at ${formatMoney(event.new_amount, currency)}, closing ${formatDateOnly(event.new_expected_close_date)}.`,
    ];
    // Deals created before forecast categories existed have none recorded.
    if (event.new_forecast_category) {
      created.push(`Forecast category: ${FORECAST_CATEGORY_LABELS[event.new_forecast_category]}.`);
    }
    return created;
  }
  const lines: string[] = [];
  if (event.changes.includes("STAGE") && event.previous_stage) {
    lines.push(
      `Stage moved from ${DEAL_STAGE_LABELS[event.previous_stage]} to ${DEAL_STAGE_LABELS[event.new_stage]}.`,
    );
  }
  if (event.changes.includes("AMOUNT")) {
    lines.push(
      `Amount ${event.is_correction ? "corrected" : "changed"} from ${formatMoney(event.previous_amount, currency)} to ${formatMoney(event.new_amount, currency)}.`,
    );
  }
  if (event.changes.includes("EXPECTED_CLOSE_DATE")) {
    lines.push(
      `Expected close moved from ${formatDateOnly(event.previous_expected_close_date)} to ${formatDateOnly(event.new_expected_close_date)}.`,
    );
  }
  // Rows from before probability history was recorded have no PROBABILITY change.
  if (event.changes.includes("PROBABILITY")) {
    lines.push(
      `Probability changed from ${probabilityLabel(event.previous_probability)} to ${probabilityLabel(event.new_probability)}.`,
    );
  }
  // Each side is read with its own stage: a closed deal is "Closed" or "Not forecast".
  if (event.changes.includes("FORECAST_CATEGORY")) {
    const from = event.previous_stage
      ? forecastCategoryLabel(event.previous_stage, event.previous_forecast_category)
      : "—";
    lines.push(
      `Forecast category changed from ${from} to ${forecastCategoryLabel(event.new_stage, event.new_forecast_category)}.`,
    );
  }
  // Never render an empty entry, e.g. for a change type this screen does not know yet.
  return lines.length > 0 ? lines : ["Deal details were updated."];
}

export function DealHistoryList({
  events,
  currency,
}: {
  events: DealHistoryEvent[];
  currency: string;
}) {
  if (events.length === 0) {
    return <p className="text-muted-foreground text-sm">No changes have been recorded yet.</p>;
  }
  return (
    <ol className="border-border grid gap-0 border-l pl-5" aria-label="Deal history, oldest first">
      {events.map((event) => (
        <li key={event.id} className="relative pb-5 last:pb-0">
          <span
            className="bg-border absolute top-1.5 -left-[1.6rem] size-2.5 rounded-full ring-4 ring-background"
            aria-hidden="true"
          />
          <div className="flex flex-wrap items-center gap-2">
            <DealStageBadge stage={event.new_stage} />
            {event.is_correction ? <StatusBadge status="warning" label="Correction" /> : null}
            <RelativeTime value={event.created_at} />
            <span className="text-muted-foreground text-xs">
              by {event.changed_by_name ?? "a former member"}
            </span>
          </div>
          <ul className="mt-1.5 grid gap-0.5 text-sm">
            {describe(event, currency).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {event.change_reason ? (
            <p className="text-muted-foreground mt-1 text-sm">
              {event.is_correction ? "Correction reason" : "Reason"}: {event.change_reason}
            </p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

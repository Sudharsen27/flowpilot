import { DealStageBadge } from "@/components/deals/deal-stage-badge";
import { RelativeTime } from "@/components/ui/relative-time";
import { DEAL_STAGE_LABELS } from "@/lib/deals";
import { formatDateOnly, formatMoney } from "@/lib/money";
import type { DealHistoryEvent } from "@/types/api";

function describe(event: DealHistoryEvent, currency: string): string[] {
  if (event.changes.includes("CREATED")) {
    return [
      `Created in ${DEAL_STAGE_LABELS[event.new_stage]} at ${formatMoney(event.new_amount, currency)}, closing ${formatDateOnly(event.new_expected_close_date)}.`,
    ];
  }
  const lines: string[] = [];
  if (event.changes.includes("STAGE") && event.previous_stage) {
    lines.push(
      `Stage moved from ${DEAL_STAGE_LABELS[event.previous_stage]} to ${DEAL_STAGE_LABELS[event.new_stage]}.`,
    );
  }
  if (event.changes.includes("AMOUNT")) {
    lines.push(
      `Amount changed from ${formatMoney(event.previous_amount, currency)} to ${formatMoney(event.new_amount, currency)}.`,
    );
  }
  if (event.changes.includes("EXPECTED_CLOSE_DATE")) {
    lines.push(
      `Expected close moved from ${formatDateOnly(event.previous_expected_close_date)} to ${formatDateOnly(event.new_expected_close_date)}.`,
    );
  }
  return lines;
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
            <p className="text-muted-foreground mt-1 text-sm">Reason: {event.change_reason}</p>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

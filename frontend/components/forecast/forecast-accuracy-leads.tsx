import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { SectionHeader } from "@/components/layout/section-header";
import {
  ACCURACY_BASES,
  ACCURACY_BASIS_LABELS,
  accuracyLeadLabel,
  formatAccuracyPercent,
  summaryOf,
  type AccuracyLead,
} from "@/lib/forecast-accuracy";
import { cn } from "@/lib/utils";
import type { ForecastAccuracy, ForecastAccuracyBasis, ForecastAccuracySummary } from "@/types/api";

/** The cell's figure, or why there is none. */
function cellText(summary: ForecastAccuracySummary | undefined): { value: string; note: string } {
  if (!summary || summary.status === "NO_COMPARABLE_MONTHS") {
    return { value: "—", note: "No comparable months" };
  }
  const months = `${summary.months_compared} ${summary.months_compared === 1 ? "month" : "months"}`;
  if (summary.status === "NO_ACTUAL_REVENUE" || summary.weighted_accuracy_percent === null) {
    return { value: "—", note: `No revenue won · ${months}` };
  }
  return { value: formatAccuracyPercent(summary.weighted_accuracy_percent) ?? "—", note: months };
}

/**
 * Weighted accuracy for every lead time and basis, from one response. A table rather
 * than bars: accuracy is unbounded below and can be negative. Choosing a cell selects
 * that lead and basis for the rest of the page.
 */
export function ForecastAccuracyLeads({
  accuracy,
  lead,
  basis,
  onSelect,
}: {
  accuracy: ForecastAccuracy;
  lead: number;
  basis: ForecastAccuracyBasis;
  onSelect: (lead: AccuracyLead, basis: ForecastAccuracyBasis) => void;
}) {
  const leads = accuracy.lead_days as AccuracyLead[];
  const columns: DataTableColumn<AccuracyLead>[] = [
    {
      key: "lead",
      header: "Forecast saved at",
      cell: (row) => <span className="font-medium">{accuracyLeadLabel(row)}</span>,
    },
    ...ACCURACY_BASES.map(
      (column): DataTableColumn<AccuracyLead> => ({
        key: column,
        header: ACCURACY_BASIS_LABELS[column],
        className: "text-right",
        cell: (row) => {
          const summary = summaryOf(accuracy, row, column);
          const { value, note } = cellText(summary);
          const selected = row === lead && column === basis;
          return (
            <button
              type="button"
              aria-pressed={selected}
              aria-label={`${accuracyLeadLabel(row)}, ${ACCURACY_BASIS_LABELS[column]}: weighted accuracy ${value === "—" ? "not available" : value}; ${note}`}
              onClick={() => onSelect(row, column)}
              className={cn(
                "focus-visible:ring-ring -my-1 grid w-full justify-items-end rounded-md px-2 py-1 text-right tabular-nums outline-none focus-visible:ring-2",
                selected ? "bg-muted ring-border ring-1" : "hover:bg-muted/60",
              )}
            >
              <span className={cn("font-medium", value === "—" && "text-muted-foreground")}>{value}</span>
              <span className="text-muted-foreground text-xs">{note}</span>
            </button>
          );
        },
      }),
    ),
  ];
  return (
    <section className="grid gap-3" aria-labelledby="forecast-accuracy-leads-heading">
      <SectionHeader
        id="forecast-accuracy-leads-heading"
        title="Accuracy by lead time"
        description="Weighted accuracy of the forecast saved at each lead time before the month started, over the closed months compared. Select a figure to show it below."
      />
      <DataTable
        columns={columns}
        rows={leads}
        getRowKey={(row) => String(row)}
        headingLevel={3}
        tableClassName="min-w-[40rem]"
        emptyTitle="No lead times"
        emptyDescription="The server returned no lead times for this range."
      />
    </section>
  );
}

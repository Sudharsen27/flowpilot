import Link from "next/link";

import { DealProbability, DealStageBadge } from "@/components/deals/deal-stage-badge";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { RelativeTime } from "@/components/ui/relative-time";
import { buildDealHref } from "@/lib/deals-url";
import { buildLeadHref } from "@/lib/lead-url";
import { formatDateOnly, formatMoney } from "@/lib/money";
import type { Deal } from "@/types/api";

const empty = <span className="text-muted-foreground">—</span>;

function LeadCell({ deal }: { deal: Deal }) {
  if (!deal.lead_id) return empty;
  const href = buildLeadHref(deal.lead_id);
  if (!deal.lead_name || !href) {
    return <span className="text-muted-foreground">Lead unavailable</span>;
  }
  return (
    <Link href={href} className="break-words underline-offset-4 hover:underline">
      {deal.lead_name}
    </Link>
  );
}

const columns: DataTableColumn<Deal>[] = [
  {
    key: "name",
    header: "Deal",
    cell: (deal) => (
      <Link
        href={buildDealHref(deal.id)}
        className="font-medium break-words underline-offset-4 hover:underline"
      >
        {deal.name}
      </Link>
    ),
    className: "min-w-48",
  },
  { key: "lead", header: "Lead", cell: (deal) => <LeadCell deal={deal} /> },
  {
    key: "owner",
    header: "Owner",
    cell: (deal) =>
      deal.owner_name ?? <span className="text-muted-foreground">Unassigned</span>,
  },
  {
    key: "amount",
    header: "Amount",
    cell: (deal) => (
      <span className="tabular-nums">{formatMoney(deal.amount, deal.currency)}</span>
    ),
    className: "text-right whitespace-nowrap",
  },
  { key: "stage", header: "Stage", cell: (deal) => <DealStageBadge stage={deal.stage} /> },
  {
    key: "probability",
    header: "Probability",
    cell: (deal) => <DealProbability deal={deal} />,
    className: "whitespace-nowrap",
  },
  {
    key: "close",
    header: "Expected close",
    cell: (deal) => formatDateOnly(deal.expected_close_date),
    className: "whitespace-nowrap",
  },
  {
    key: "updated",
    header: "Updated",
    cell: (deal) => <RelativeTime value={deal.updated_at} />,
    className: "whitespace-nowrap",
  },
];

export function DealsTable({ deals, loading }: { deals: Deal[]; loading: boolean }) {
  return (
    <DataTable
      columns={columns}
      rows={deals}
      loading={loading}
      getRowKey={(deal) => deal.id}
      emptyTitle="No deals yet"
      emptyDescription="Create a deal to start tracking revenue in your pipeline."
    />
  );
}

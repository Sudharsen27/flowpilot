import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { Button } from "@/components/ui/button";
import type { Lead, LeadSource } from "@/types/api";

const sourceLabels: Record<LeadSource, string> = {
  MANUAL: "Manual",
  WEBSITE: "Website",
  EMAIL: "Email",
  CHAT: "Chat",
  API: "API",
  IMPORT: "Import",
};

function formatUpdatedAt(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

const leadColumns: DataTableColumn<Lead>[] = [
  {
    key: "lead",
    header: "Lead",
    cell: (lead) => (
      <div>
        <p className="font-medium">{lead.name}</p>
        {lead.email ? (
          <p className="text-muted-foreground mt-0.5 text-xs">{lead.email}</p>
        ) : null}
      </div>
    ),
  },
  {
    key: "company",
    header: "Company",
    cell: (lead) => lead.company ?? "—",
  },
  {
    key: "status",
    header: "Status",
    cell: (lead) => <LeadStatusBadge status={lead.status} />,
  },
  {
    key: "qualification",
    header: "AI qualification",
    cell: () => <QualificationStatus status="unavailable" />,
  },
  {
    key: "source",
    header: "Source",
    cell: (lead) => sourceLabels[lead.source],
  },
  {
    key: "updated",
    header: "Updated",
    cell: (lead) => formatUpdatedAt(lead.updated_at),
  },
];

type LeadsTableProps = {
  leads: Lead[];
  loading?: boolean;
  onEdit?: (lead: Lead) => void;
};

export function LeadsTable({
  leads,
  loading = false,
  onEdit,
}: LeadsTableProps) {
  return (
    <DataTable
      className="max-w-none"
      columns={leadColumns}
      rows={leads}
      getRowKey={(lead) => lead.id}
      loading={loading}
      emptyTitle="No leads yet"
      emptyDescription="Create a lead to start capturing enquiries, or wait until a connected channel sends one."
      rowActions={
        onEdit
          ? (lead) => (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onEdit(lead)}
              >
                Edit
              </Button>
            )
          : undefined
      }
    />
  );
}

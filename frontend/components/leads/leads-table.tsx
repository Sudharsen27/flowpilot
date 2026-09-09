import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import {
  LeadStatusBadge,
  type LeadStatus,
} from "@/components/leads/lead-status-badge";
import {
  QualificationStatus,
  type QualificationState,
} from "@/components/leads/qualification-status";

export type LeadListItem = {
  id: string;
  name: string;
  email?: string;
  company?: string;
  status: LeadStatus;
  qualification: {
    status: QualificationState;
    score?: number;
    explanation?: string;
  };
  source?: string;
  lastActivity?: string;
};

const leadColumns: DataTableColumn<LeadListItem>[] = [
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
    cell: (lead) => <QualificationStatus {...lead.qualification} />,
  },
  {
    key: "source",
    header: "Source",
    cell: (lead) => lead.source ?? "—",
  },
  {
    key: "last-activity",
    header: "Last activity",
    cell: (lead) => lead.lastActivity ?? "—",
  },
  {
    key: "actions",
    header: "Actions",
    cell: () => (
      <span className="text-muted-foreground text-xs">Not available</span>
    ),
  },
];

type LeadsTableProps = {
  leads: LeadListItem[];
  loading?: boolean;
};

export function LeadsTable({ leads, loading = false }: LeadsTableProps) {
  return (
    <DataTable
      className="max-w-none"
      columns={leadColumns}
      rows={leads}
      getRowKey={(lead) => lead.id}
      loading={loading}
      emptyTitle="No leads yet"
      emptyDescription="Leads will appear here after forms, inboxes, or integrations are connected and begin sending enquiries to FlowPilot."
    />
  );
}

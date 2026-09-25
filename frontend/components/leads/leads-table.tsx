import { MoreHorizontal } from "lucide-react";
import Link from "next/link";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { SalesAgentStatus } from "@/components/leads/sales-agent-status";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Lead, LeadSource } from "@/types/api";

function qualificationState(lead: Lead) {
  const latest = lead.latest_qualification;
  if (!latest) return "not-assessed" as const;
  if (latest.status === "FAILED") return "failed" as const;
  return latest.qualification ?? ("not-assessed" as const);
}

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
    className: "min-w-[10rem]",
    cell: (lead) => (
      <div className="min-w-0">
        <p className="font-medium tracking-tight">
          <Link
            href={`/leads/${lead.id}`}
            aria-label={lead.name}
            title={`Open ${lead.name}`}
            className="text-foreground hover:text-foreground rounded-sm font-semibold underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {lead.name}
          </Link>
        </p>
        {lead.email ? (
          <p className="text-muted-foreground mt-1 truncate text-[11px] leading-5">
            {lead.email}
          </p>
        ) : null}
      </div>
    ),
  },
  {
    key: "company",
    header: "Company",
    className: "min-w-[7rem]",
    cell: (lead) => (
      <span className="text-muted-foreground truncate text-sm">
        {lead.company ?? "—"}
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    className: "whitespace-nowrap",
    cell: (lead) => <LeadStatusBadge status={lead.status} />,
  },
  {
    key: "qualification",
    header: "AI qualification",
    className: "min-w-[9rem]",
    cell: (lead) => (
      <div className="flex items-start justify-start">
        <QualificationStatus status={qualificationState(lead)} />
      </div>
    ),
  },
  {
    key: "sales-agent",
    header: "Sales Agent",
    className: "whitespace-nowrap",
    cell: (lead) => (
      <div className="flex items-start justify-start">
        <SalesAgentStatus summary={lead.latest_sales_run} />
      </div>
    ),
  },
  {
    key: "source",
    header: "Source",
    className: "whitespace-nowrap",
    cell: (lead) => sourceLabels[lead.source],
  },
  {
    key: "updated",
    header: "Updated",
    className: "whitespace-nowrap",
    cell: (lead) => formatUpdatedAt(lead.updated_at),
  },
];

type LeadsTableProps = {
  leads: Lead[];
  loading?: boolean;
  onEdit?: (lead: Lead) => void;
  onQualify?: (lead: Lead) => void;
  onDraftResponse?: (lead: Lead) => void;
  onReviewDraft?: (lead: Lead) => void;
  onFollowUps?: (lead: Lead) => void;
  onSalesAgentHistory?: (lead: Lead) => void;
};

function LeadRowActions({
  lead,
  onEdit,
  onQualify,
  onDraftResponse,
  onReviewDraft,
  onFollowUps,
  onSalesAgentHistory,
}: {
  lead: Lead;
  onEdit?: (lead: Lead) => void;
  onQualify?: (lead: Lead) => void;
  onDraftResponse?: (lead: Lead) => void;
  onReviewDraft?: (lead: Lead) => void;
  onFollowUps?: (lead: Lead) => void;
  onSalesAgentHistory?: (lead: Lead) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            aria-label={`Open actions for ${lead.name}`}
          />
        }
      >
        <MoreHorizontal aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-48">
        {onQualify ? (
          <DropdownMenuItem onClick={() => onQualify(lead)}>
            Analyze with AI
          </DropdownMenuItem>
        ) : null}
        {onDraftResponse ? (
          <DropdownMenuItem onClick={() => onDraftResponse(lead)}>
            Draft response
          </DropdownMenuItem>
        ) : null}
        {onReviewDraft && lead.latest_response_draft ? (
          <DropdownMenuItem onClick={() => onReviewDraft(lead)}>
            Review draft
          </DropdownMenuItem>
        ) : null}
        {onFollowUps ? (
          <DropdownMenuItem onClick={() => onFollowUps(lead)}>
            Follow-ups
          </DropdownMenuItem>
        ) : null}
        {onSalesAgentHistory ? (
          <DropdownMenuItem onClick={() => onSalesAgentHistory(lead)}>
            Sales Agent history
          </DropdownMenuItem>
        ) : null}
        {onEdit ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onEdit(lead)}>Edit</DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function LeadsTable({
  leads,
  loading = false,
  onEdit,
  onQualify,
  onDraftResponse,
  onReviewDraft,
  onFollowUps,
  onSalesAgentHistory,
}: LeadsTableProps) {
  const hasActions = Boolean(
    onEdit ||
      onQualify ||
      onDraftResponse ||
      onReviewDraft ||
      onFollowUps ||
      onSalesAgentHistory,
  );

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
        hasActions
          ? (lead) => (
              <LeadRowActions
                lead={lead}
                onEdit={onEdit}
                onQualify={onQualify}
                onDraftResponse={onDraftResponse}
                onReviewDraft={onReviewDraft}
                onFollowUps={onFollowUps}
                onSalesAgentHistory={onSalesAgentHistory}
              />
            )
          : undefined
      }
    />
  );
}

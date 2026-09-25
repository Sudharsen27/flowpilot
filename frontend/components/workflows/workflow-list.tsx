import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import {
  WorkflowStatusBadge,
  type WorkflowStatus,
} from "@/components/workflows/workflow-status-badge";
import { EmptyState } from "@/components/empty-state";
import { ArrowRight, Bot } from "lucide-react";
import Link from "next/link";

export type WorkflowListItem = {
  id: string;
  name: string;
  description: string;
  trigger: string;
  status: WorkflowStatus;
  connectedAgent?: string;
  lastRun?: string;
};

const workflowColumns: DataTableColumn<WorkflowListItem>[] = [
  {
    key: "workflow",
    header: "Workflow",
    cell: (workflow) => (
      <div>
        <p className="font-medium">{workflow.name}</p>
        <p className="text-muted-foreground mt-0.5 max-w-sm text-xs leading-5">
          {workflow.description}
        </p>
      </div>
    ),
  },
  {
    key: "trigger",
    header: "Trigger",
    cell: (workflow) => workflow.trigger,
  },
  {
    key: "status",
    header: "Status",
    cell: (workflow) => <WorkflowStatusBadge status={workflow.status} />,
  },
  {
    key: "agent",
    header: "Connected agent",
    cell: (workflow) => workflow.connectedAgent ?? "Not connected",
  },
  {
    key: "last-run",
    header: "Last run",
    cell: (workflow) => workflow.lastRun ?? "Unavailable",
  },
  {
    key: "actions",
    header: "Actions",
    cell: () => (
      <span className="text-muted-foreground text-xs">Unavailable</span>
    ),
  },
];

type WorkflowListProps = {
  workflows: WorkflowListItem[];
  loading?: boolean;
};

export function WorkflowList({
  workflows,
  loading = false,
}: WorkflowListProps) {
  if (!loading && workflows.length === 0) {
    return (
      <EmptyState
        className="max-w-none"
        title="No workflows configured"
        description="Workflow creation is planned and is not available yet. This page explains the planned workflow model."
        action={
          <Link
            href="/agents"
            className="bg-primary text-primary-foreground hover:bg-primary/80 focus-visible:ring-ring inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
          >
            <Bot aria-hidden="true" />
            Review AI Agents
            <ArrowRight aria-hidden="true" />
          </Link>
        }
      />
    );
  }

  return (
    <DataTable
      className="max-w-none"
      columns={workflowColumns}
      rows={workflows}
      getRowKey={(workflow) => workflow.id}
      loading={loading}
      emptyTitle="No workflows configured"
      emptyDescription="Workflows will automate how FlowPilot responds to business events. Once configuration is available, they can connect triggers, AI agents, conditions, approvals, and actions."
    />
  );
}

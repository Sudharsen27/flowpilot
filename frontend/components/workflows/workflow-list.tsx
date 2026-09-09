import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import {
  WorkflowStatusBadge,
  type WorkflowStatus,
} from "@/components/workflows/workflow-status-badge";

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

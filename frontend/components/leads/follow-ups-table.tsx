"use client";

import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { formatDuration } from "@/components/agents/execution-status";
import {
  FollowUpExecutionStatusBadge,
  FollowUpStatusBadge,
  followUpTypeLabel,
} from "@/components/leads/follow-up-status-badge";
import { Button } from "@/components/ui/button";
import type { FollowUpOperationsItem } from "@/types/api";

type FollowUpsTableProps = {
  items: FollowUpOperationsItem[];
  loading?: boolean;
  onManage?: (item: FollowUpOperationsItem) => void;
  onViewHistory?: (item: FollowUpOperationsItem) => void;
};

function formatDue(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function LastExecution({ item }: { item: FollowUpOperationsItem }) {
  const execution = item.latest_execution;
  if (!execution) {
    // Absence of an execution is meaningful: nothing has been emailed.
    return (
      <span className="text-muted-foreground text-sm">
        {item.follow_up.type === "EMAIL_FOLLOW_UP"
          ? "Not sent yet"
          : "Manual, no email"}
      </span>
    );
  }
  const duration = formatDuration(execution.duration_ms);
  return (
    <div className="grid gap-1">
      <FollowUpExecutionStatusBadge status={execution.status} />
      <span className="text-muted-foreground text-xs">
        Attempt {execution.attempt}
        {duration ? ` · ${duration}` : ""}
      </span>
    </div>
  );
}

export function FollowUpsTable({
  items,
  loading = false,
  onManage,
  onViewHistory,
}: FollowUpsTableProps) {
  const columns: DataTableColumn<FollowUpOperationsItem>[] = [
    {
      key: "customer",
      header: "Customer",
      cell: (item) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{item.lead.name}</p>
          {item.lead.email ? (
            <p className="text-muted-foreground truncate text-xs">
              {item.lead.email}
            </p>
          ) : (
            <p className="text-muted-foreground text-xs">No email address</p>
          )}
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      cell: (item) => (
        <span className="text-sm">{followUpTypeLabel(item.follow_up.type)}</span>
      ),
    },
    {
      key: "due",
      header: "Due",
      cell: (item) => (
        <span className="text-sm tabular-nums">
          {formatDue(item.follow_up.due_at)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (item) => <FollowUpStatusBadge followUp={item.follow_up} />,
    },
    {
      key: "last-execution",
      header: "Last execution",
      mobileLabel: "Last execution",
      cell: (item) => <LastExecution item={item} />,
    },
  ];

  return (
    <DataTable
      columns={columns}
      rows={items}
      getRowKey={(item) => item.follow_up.id}
      loading={loading}
      emptyTitle="No follow-ups yet"
      emptyDescription="Create a follow-up from a lead to track the next customer action."
      rowActions={
        onManage || onViewHistory
          ? (item) => (
              <div className="flex justify-end gap-2">
                {onViewHistory ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onViewHistory(item)}
                  >
                    History
                  </Button>
                ) : null}
                {onManage ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onManage(item)}
                  >
                    Manage
                  </Button>
                ) : null}
              </div>
            )
          : undefined
      }
    />
  );
}

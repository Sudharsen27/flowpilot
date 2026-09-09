import type { ReactNode } from "react";

import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
  mobileLabel?: string;
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  rowActions?: (row: T) => ReactNode;
  loading?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  className?: string;
};

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  rowActions,
  loading = false,
  emptyTitle = "No records yet",
  emptyDescription = "Records will appear here when they become available.",
  className,
}: DataTableProps<T>) {
  if (!loading && rows.length === 0) {
    return (
      <EmptyState
        className={className}
        title={emptyTitle}
        description={emptyDescription}
      />
    );
  }

  return (
    <div
      data-slot="data-table"
      className={cn(
        "border-border bg-card overflow-hidden rounded-lg border",
        className,
      )}
      aria-busy={loading || undefined}
    >
      <table className="hidden w-full border-collapse text-left text-sm md:table">
        <thead className="bg-surface-subtle text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn(
                  "px-4 py-3 text-xs font-medium",
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
            {rowActions ? (
              <th scope="col" className="w-12 px-4 py-3">
                <span className="sr-only">Actions</span>
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody className="divide-border divide-y">
          {loading
            ? Array.from({ length: 3 }, (_, rowIndex) => (
                <tr key={`loading-${rowIndex}`}>
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-4">
                      <Skeleton className="h-4 w-4/5" />
                    </td>
                  ))}
                  {rowActions ? (
                    <td className="px-4 py-4">
                      <Skeleton className="size-7" />
                    </td>
                  ) : null}
                </tr>
              ))
            : rows.map((row) => (
                <tr key={getRowKey(row)} className="hover:bg-surface-subtle/70">
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn("px-4 py-4 align-middle", column.className)}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                  {rowActions ? (
                    <td className="px-4 py-4 text-right">{rowActions(row)}</td>
                  ) : null}
                </tr>
              ))}
        </tbody>
      </table>

      <div className="md:hidden">
        {loading ? (
          <div className="space-y-3 p-4" role="status">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <span className="sr-only">Loading records</span>
          </div>
        ) : (
          <ul className="divide-border divide-y">
            {rows.map((row) => (
              <li key={getRowKey(row)} className="p-4">
                <dl className="grid gap-3">
                  {columns.map((column) => (
                    <div
                      key={column.key}
                      className="grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)] gap-3"
                    >
                      <dt className="text-muted-foreground text-xs font-medium">
                        {column.mobileLabel ?? column.header}
                      </dt>
                      <dd className="min-w-0 text-sm">{column.cell(row)}</dd>
                    </div>
                  ))}
                </dl>
                {rowActions ? (
                  <div className="border-border mt-4 flex justify-end border-t pt-3">
                    {rowActions(row)}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

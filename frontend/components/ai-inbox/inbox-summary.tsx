import { Clock3, FolderOpen, MessageCircle } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { InboxConversationState } from "@/types/api";

type InboxSummaryProps = {
  loading?: boolean;
  stateCounts?: Partial<Record<InboxConversationState, number>>;
  needsApprovalCount?: number;
};

type Metric = {
  key: string;
  label: string;
  value: number | undefined;
  hint: string;
  icon: typeof MessageCircle;
  emphasize?: boolean;
};

export function InboxSummary({
  loading = false,
  stateCounts,
  needsApprovalCount,
}: InboxSummaryProps) {
  const metrics: Metric[] = [
    {
      key: "open",
      label: "Open",
      value: stateCounts?.OPEN,
      hint: "In progress",
      icon: MessageCircle,
    },
    {
      key: "needs",
      label: "Needs approval",
      value: stateCounts?.NEEDS_APPROVAL ?? needsApprovalCount,
      hint: "Human review required",
      icon: Clock3,
      emphasize: true,
    },
    {
      key: "closed",
      label: "Closed",
      value: stateCounts?.CLOSED,
      hint: "Completed or resolved",
      icon: FolderOpen,
    },
  ];

  return (
    <div
      className="border-border bg-card grid gap-0 overflow-hidden rounded-lg border sm:grid-cols-3"
      data-slot="inbox-summary"
      aria-label="Inbox summary"
    >
      {metrics.map((metric, index) => {
        const Icon = metric.icon;
        const hasValue =
          metric.value !== undefined && metric.value !== null;
        return (
          <div
            key={metric.key}
            className={cn(
              "flex min-h-24 flex-col justify-between gap-3 px-5 py-4",
              index > 0 && "border-border border-t sm:border-t-0 sm:border-l",
              metric.emphasize && "bg-warning/5",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                {metric.label}
              </p>
              <span
                className={cn(
                  "flex size-7 items-center justify-center rounded-md",
                  metric.emphasize
                    ? "bg-warning/15 text-warning-text"
                    : "bg-muted text-muted-foreground",
                )}
                aria-hidden="true"
              >
                <Icon className="size-3.5" />
              </span>
            </div>
            {loading ? (
              <div role="status">
                <Skeleton className="h-7 w-12" />
                <span className="sr-only">Loading {metric.label}</span>
              </div>
            ) : (
              <div>
                <p
                  className={cn(
                    "text-2xl font-semibold tracking-tight tabular-nums",
                    !hasValue && "text-muted-foreground",
                    metric.emphasize && hasValue && "text-warning-text",
                  )}
                >
                  {hasValue ? metric.value : "—"}
                </p>
                <p className="text-muted-foreground mt-1 text-xs">{metric.hint}</p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

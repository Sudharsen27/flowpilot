import {
  Bot,
  CheckCheck,
  CircleDot,
  Plug,
  UserRound,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";

export type ActivityEventType =
  | "ai-action"
  | "workflow"
  | "approval"
  | "integration"
  | "human-action"
  | "system-event";

type ActivityTypeBadgeProps = {
  type: ActivityEventType;
};

const typePresentation = {
  "ai-action": {
    label: "AI action",
    icon: Bot,
    className: "border-ai-border bg-ai/10 text-ai-text",
  },
  workflow: {
    label: "Workflow",
    icon: Workflow,
    className: "border-primary/20 bg-primary/10 text-primary",
  },
  approval: {
    label: "Approval",
    icon: CheckCheck,
    className: "border-warning/30 bg-warning/10 text-warning-text",
  },
  integration: {
    label: "Integration",
    icon: Plug,
    className: "border-success/25 bg-success/10 text-success-text",
  },
  "human-action": {
    label: "Human action",
    icon: UserRound,
    className: "border-border bg-muted text-foreground",
  },
  "system-event": {
    label: "System event",
    icon: CircleDot,
    className: "border-border bg-surface-subtle text-muted-foreground",
  },
} as const;

export function ActivityTypeBadge({ type }: ActivityTypeBadgeProps) {
  const presentation = typePresentation[type];
  const Icon = presentation.icon;

  return (
    <span
      data-slot="activity-type-badge"
      data-event-type={type}
      className={cn(
        "inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        presentation.className,
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {presentation.label}
    </span>
  );
}

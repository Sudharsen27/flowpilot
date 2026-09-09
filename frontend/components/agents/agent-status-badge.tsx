import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type AgentStatus =
  "draft" | "ready" | "active" | "paused" | "needs-attention";

type AgentStatusBadgeProps = {
  status: AgentStatus;
};

const statusPresentation: Record<
  AgentStatus,
  { status: StatusValue; label: string }
> = {
  draft: { status: "draft", label: "Draft" },
  ready: { status: "pending", label: "Ready" },
  active: { status: "active", label: "Active" },
  paused: { status: "paused", label: "Paused" },
  "needs-attention": { status: "warning", label: "Needs attention" },
};

export function AgentStatusBadge({ status }: AgentStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

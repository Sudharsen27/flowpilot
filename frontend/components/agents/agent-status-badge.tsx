import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type AgentStatus =
  "draft" | "ready" | "active" | "paused" | "needs-attention";

type AgentStatusBadgeProps = {
  status: AgentStatus;
};

const statusLabels: Record<AgentStatus, string> = {
  draft: "Draft",
  ready: "Ready",
  active: "Active",
  paused: "Paused",
  "needs-attention": "Needs attention",
};

export function AgentStatusBadge({ status }: AgentStatusBadgeProps) {
  const presentation = statusPresentation(status, statusLabels[status]);
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

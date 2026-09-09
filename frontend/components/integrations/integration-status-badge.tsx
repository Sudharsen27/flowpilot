import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type IntegrationStatus =
  "connected" | "not-connected" | "needs-attention" | "coming-soon";

type IntegrationStatusBadgeProps = {
  status: IntegrationStatus;
};

const statusPresentation: Record<
  IntegrationStatus,
  { status: StatusValue; label: string }
> = {
  connected: { status: "active", label: "Connected" },
  "not-connected": { status: "draft", label: "Not connected" },
  "needs-attention": { status: "warning", label: "Needs attention" },
  "coming-soon": { status: "draft", label: "Coming soon" },
};

export function IntegrationStatusBadge({
  status,
}: IntegrationStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

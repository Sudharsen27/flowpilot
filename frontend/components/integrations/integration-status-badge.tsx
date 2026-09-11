import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type IntegrationStatus =
  "connected" | "not-connected" | "needs-attention" | "coming-soon";

type IntegrationStatusBadgeProps = {
  status: IntegrationStatus;
};

const integrationPresentation: Record<
  IntegrationStatus,
  { code: string; label: string; fallback?: "active" | "draft" }
> = {
  connected: { code: "CONNECTED", label: "Connected", fallback: "active" },
  "not-connected": { code: "DRAFT", label: "Not connected" },
  "needs-attention": { code: "NEEDS_ATTENTION", label: "Needs attention" },
  "coming-soon": { code: "DRAFT", label: "Coming soon" },
};

export function IntegrationStatusBadge({
  status,
}: IntegrationStatusBadgeProps) {
  const item = integrationPresentation[status];
  const presentation = statusPresentation(
    item.code,
    item.label,
    item.fallback ?? "draft",
  );
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

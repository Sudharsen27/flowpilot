import { StatusBadge } from "@/components/ui/status-badge";
import type { CompanyProspectStatus, EvidenceQuality } from "@/types/api";

const statusLabels: Record<CompanyProspectStatus, string> = {
  IDENTIFIED: "Identified",
  REVIEWED: "Reviewed",
  ARCHIVED: "Archived",
};

const evidenceLabels: Record<EvidenceQuality, string> = {
  SOURCE_REPORTED: "Source reported",
  ESTIMATED: "Estimated",
  INFERRED: "Inferred",
  UNKNOWN: "Unknown",
};

export function CompanyProspectStatusBadge({
  status,
}: {
  status: CompanyProspectStatus;
}) {
  return (
    <StatusBadge
      status={
        status === "REVIEWED"
          ? "success"
          : status === "ARCHIVED"
            ? "paused"
            : "pending"
      }
      label={statusLabels[status]}
    />
  );
}

export function EvidenceQualityBadge({
  quality,
}: {
  quality: EvidenceQuality;
}) {
  return (
    <StatusBadge
      status={
        quality === "SOURCE_REPORTED"
          ? "success"
          : quality === "ESTIMATED"
            ? "warning"
            : quality === "INFERRED"
              ? "medium"
              : "draft"
      }
      label={evidenceLabels[quality]}
    />
  );
}

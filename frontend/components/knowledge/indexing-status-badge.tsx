import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type IndexingStatus =
  "ready" | "processing" | "needs-attention" | "not-indexed";

type IndexingStatusBadgeProps = {
  status: IndexingStatus;
};

/**
 * Indexing "ready" means indexed successfully, not agent READY (pending).
 */
const indexingPresentation: Record<
  IndexingStatus,
  { code: string; label: string; fallback?: "success" | "pending" | "draft" }
> = {
  ready: { code: "INDEXED_READY", label: "Ready", fallback: "success" },
  processing: { code: "RUNNING", label: "Processing" },
  "needs-attention": { code: "NEEDS_ATTENTION", label: "Needs attention" },
  "not-indexed": { code: "DRAFT", label: "Not indexed" },
};

export function IndexingStatusBadge({ status }: IndexingStatusBadgeProps) {
  const item = indexingPresentation[status];
  const presentation = statusPresentation(
    item.code,
    item.label,
    item.fallback ?? "draft",
  );
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

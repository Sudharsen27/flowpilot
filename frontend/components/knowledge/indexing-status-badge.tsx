import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type IndexingStatus =
  "ready" | "processing" | "needs-attention" | "not-indexed";

type IndexingStatusBadgeProps = {
  status: IndexingStatus;
};

const statusPresentation: Record<
  IndexingStatus,
  { status: StatusValue; label: string }
> = {
  ready: { status: "success", label: "Ready" },
  processing: { status: "pending", label: "Processing" },
  "needs-attention": { status: "warning", label: "Needs attention" },
  "not-indexed": { status: "draft", label: "Not indexed" },
};

export function IndexingStatusBadge({ status }: IndexingStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

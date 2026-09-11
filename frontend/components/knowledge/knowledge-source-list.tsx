import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import {
  IndexingStatusBadge,
  type IndexingStatus,
} from "@/components/knowledge/indexing-status-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type KnowledgeSourceType =
  "document" | "faq" | "website" | "product" | "policy" | "company";

export type KnowledgeSourceStatus = "setup" | "connected" | "needs-attention";

export type KnowledgeSourceListItem = {
  id: string;
  name: string;
  type: KnowledgeSourceType;
  status: KnowledgeSourceStatus;
  lastUpdated?: string;
  indexingStatus: IndexingStatus;
};

const typeLabels: Record<KnowledgeSourceType, string> = {
  document: "Document",
  faq: "FAQ",
  website: "Website",
  product: "Product information",
  policy: "Policy",
  company: "Company information",
};

const sourceStatusCodes: Record<KnowledgeSourceStatus, string> = {
  setup: "DRAFT",
  connected: "CONNECTED",
  "needs-attention": "NEEDS_ATTENTION",
};

const sourceStatusLabels: Record<KnowledgeSourceStatus, string> = {
  setup: "Setup",
  connected: "Connected",
  "needs-attention": "Needs attention",
};

const sourceColumns: DataTableColumn<KnowledgeSourceListItem>[] = [
  {
    key: "source",
    header: "Source name",
    cell: (source) => <span className="font-medium">{source.name}</span>,
  },
  {
    key: "type",
    header: "Type",
    cell: (source) => typeLabels[source.type],
  },
  {
    key: "status",
    header: "Status",
    cell: (source) => {
      const presentation = statusPresentation(
        sourceStatusCodes[source.status],
        sourceStatusLabels[source.status],
        source.status === "connected" ? "active" : "draft",
      );
      return (
        <StatusBadge status={presentation.status} label={presentation.label} />
      );
    },
  },
  {
    key: "last-updated",
    header: "Last updated",
    cell: (source) => source.lastUpdated ?? "Unavailable",
  },
  {
    key: "indexing",
    header: "Content / indexing",
    cell: (source) => <IndexingStatusBadge status={source.indexingStatus} />,
  },
  {
    key: "actions",
    header: "Actions",
    cell: () => (
      <span className="text-muted-foreground text-xs">Unavailable</span>
    ),
  },
];

type KnowledgeSourceListProps = {
  sources: KnowledgeSourceListItem[];
  loading?: boolean;
};

export function KnowledgeSourceList({
  sources,
  loading = false,
}: KnowledgeSourceListProps) {
  return (
    <DataTable
      className="max-w-none"
      columns={sourceColumns}
      rows={sources}
      getRowKey={(source) => source.id}
      loading={loading}
      emptyTitle="Give your agents the context they need"
      emptyDescription="Knowledge sources will appear here after ingestion is implemented. Businesses will eventually be able to provide company information, products and services, FAQs, policies, documents, and website content."
    />
  );
}

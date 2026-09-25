import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import {
  IndexingStatusBadge,
  type IndexingStatus,
} from "@/components/knowledge/indexing-status-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { RelativeTime } from "@/components/ui/relative-time";
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

export function filterKnowledgeSources(
  sources: KnowledgeSourceListItem[],
  query: string,
) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return sources;

  return sources.filter((source) =>
    [
      source.name,
      typeLabels[source.type],
      sourceStatusLabels[source.status],
    ].some((value) => value.toLowerCase().includes(normalizedQuery)),
  );
}

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
    cell: (source) => (
      <span
        className="block max-w-[18rem] truncate font-medium"
        title={source.name}
      >
        {source.name}
      </span>
    ),
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
    cell: (source) =>
      source.lastUpdated ? (
        <RelativeTime value={source.lastUpdated} />
      ) : (
        <span className="text-muted-foreground">Unavailable</span>
      ),
  },
  {
    key: "indexing",
    header: "Planned indexing",
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
  error?: string | null;
  searchQuery?: string;
};

export function KnowledgeSourceList({
  sources,
  loading = false,
  error = null,
  searchQuery = "",
}: KnowledgeSourceListProps) {
  if (error) {
    return (
      <StatePanel
        kind="error"
        className="max-w-none"
        title="Knowledge sources could not be loaded"
        description={error}
      />
    );
  }

  const filteredSources = filterKnowledgeSources(sources, searchQuery);
  const hasSearch = searchQuery.trim().length > 0 && sources.length > 0;

  return (
    <DataTable
      className="max-w-none"
      columns={sourceColumns}
      rows={filteredSources}
      getRowKey={(source) => source.id}
      loading={loading}
      emptyTitle={
        hasSearch ? "No matching sources" : "No Knowledge sources connected"
      }
      emptyDescription={
        hasSearch
          ? "No supplied Knowledge sources match this local search."
          : "Sources will appear here when Knowledge source management is available."
      }
    />
  );
}

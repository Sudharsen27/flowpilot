import { Archive, ArchiveRestore, Pencil, Trash2 } from "lucide-react";

import { knowledgeCategoryLabels } from "@/components/knowledge/knowledge-labels";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import type { KnowledgeEntry } from "@/types/api";

type KnowledgeEntryListProps = {
  entries: readonly KnowledgeEntry[];
  canManage: boolean;
  busyEntryId: string | null;
  onEdit: (entry: KnowledgeEntry) => void;
  onToggleArchive: (entry: KnowledgeEntry) => void;
  onDelete: (entry: KnowledgeEntry) => void;
};

export function KnowledgeEntryList({
  entries,
  canManage,
  busyEntryId,
  onEdit,
  onToggleArchive,
  onDelete,
}: KnowledgeEntryListProps) {
  return (
    <ul className="grid gap-3" aria-label="Knowledge entries">
      {entries.map((entry) => {
        const archived = entry.status === "ARCHIVED";
        const busy = busyEntryId === entry.id;
        return (
          <li key={entry.id}>
            <Card as="article" aria-labelledby={`knowledge-${entry.id}-title`}>
              <CardContent className="grid gap-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid min-w-0 gap-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge
                        status={archived ? "paused" : "active"}
                        label={knowledgeCategoryLabels[entry.category]}
                      />
                      {!entry.use_in_ai ? (
                        <StatusBadge status="draft" label="Not used by AI" />
                      ) : null}
                      {archived ? (
                        <StatusBadge status="paused" label="Archived" />
                      ) : null}
                    </div>
                    <h3
                      id={`knowledge-${entry.id}-title`}
                      className="text-base font-medium tracking-tight break-words"
                    >
                      {entry.title}
                    </h3>
                  </div>
                  <span className="text-muted-foreground text-xs">
                    Updated <RelativeTime value={entry.updated_at} />
                  </span>
                </div>
                <p className="text-muted-foreground line-clamp-3 text-sm leading-6 whitespace-pre-line">
                  {entry.content}
                </p>
                {canManage ? (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => onEdit(entry)}
                      aria-label={`Edit ${entry.title}`}
                    >
                      <Pencil aria-hidden="true" />
                      Edit
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() => onToggleArchive(entry)}
                      aria-label={`${archived ? "Restore" : "Archive"} ${entry.title}`}
                    >
                      {archived ? (
                        <ArchiveRestore aria-hidden="true" />
                      ) : (
                        <Archive aria-hidden="true" />
                      )}
                      {archived ? "Restore" : "Archive"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => onDelete(entry)}
                      aria-label={`Delete ${entry.title}`}
                    >
                      <Trash2 aria-hidden="true" />
                      Delete
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}

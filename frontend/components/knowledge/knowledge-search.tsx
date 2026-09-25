"use client";

import { SearchInput } from "@/components/forms/search-input";

type KnowledgeSearchProps = {
  query: string;
  onQueryChange: (value: string) => void;
  resultCount: number;
  sourceCount: number;
};

export function KnowledgeSearch({
  query,
  onQueryChange,
  resultCount,
  sourceCount,
}: KnowledgeSearchProps) {
  return (
    <div className="border-border bg-surface-subtle grid gap-2 rounded-lg border p-4">
      <SearchInput
        id="knowledge-search"
        label="Search knowledge sources"
        placeholder="Search knowledge sources"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onClear={() => onQueryChange("")}
        aria-describedby="knowledge-search-note"
      />
      <p id="knowledge-search-note" className="text-muted-foreground text-xs">
        Search applies locally to supplied source rows only. It does not query
        connected Knowledge sources.
      </p>
      <p className="sr-only" role="status" aria-live="polite">
        {query.trim()
          ? `${resultCount} supplied source${resultCount === 1 ? "" : "s"} match${resultCount === 1 ? "es" : ""} the search.`
          : `${sourceCount} supplied source${sourceCount === 1 ? "" : "s"}.`}
      </p>
    </div>
  );
}

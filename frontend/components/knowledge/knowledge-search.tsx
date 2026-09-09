"use client";

import { useState } from "react";

import { SearchInput } from "@/components/forms/search-input";

export function KnowledgeSearch() {
  const [query, setQuery] = useState("");

  return (
    <div className="border-border bg-surface-subtle grid gap-2 rounded-lg border p-4">
      <SearchInput
        id="knowledge-search"
        label="Search knowledge sources"
        placeholder="Search knowledge sources"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onClear={() => setQuery("")}
        aria-describedby="knowledge-search-note"
      />
      <p id="knowledge-search-note" className="text-muted-foreground text-xs">
        Search is UI-only and will become available when knowledge sources are
        connected.
      </p>
    </div>
  );
}

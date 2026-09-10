"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import type { LeadSource, LeadStatus } from "@/types/api";

type LeadsToolbarProps = {
  query: string;
  status: LeadStatus | "";
  source: LeadSource | "";
  onQueryChange: (value: string) => void;
  onStatusChange: (value: LeadStatus | "") => void;
  onSourceChange: (value: LeadSource | "") => void;
  onClearFilters: () => void;
};

export function LeadsToolbar({
  query,
  status,
  source,
  onQueryChange,
  onStatusChange,
  onSourceChange,
  onClearFilters,
}: LeadsToolbarProps) {
  const activeFilterCount = [
    query.trim() !== "",
    status !== "",
    source !== "",
  ].filter(Boolean).length;

  return (
    <div className="grid gap-2">
      <FilterBar
        search={
          <SearchInput
            id="lead-search"
            label="Search leads"
            placeholder="Search leads"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onClear={() => onQueryChange("")}
          />
        }
        activeFilterCount={activeFilterCount}
        onClearFilters={onClearFilters}
      >
        <div className="w-full sm:w-40">
          <Label htmlFor="lead-status" className="sr-only">
            Lead status
          </Label>
          <Select
            id="lead-status"
            value={status}
            onChange={(event) =>
              onStatusChange(event.target.value as LeadStatus | "")
            }
          >
            <option value="">All statuses</option>
            <option value="NEW">New</option>
            <option value="CONTACTED">Contacted</option>
            <option value="QUALIFIED">Qualified</option>
            <option value="UNQUALIFIED">Unqualified</option>
            <option value="CONVERTED">Converted</option>
          </Select>
        </div>
        <div className="w-full sm:w-40">
          <Label htmlFor="lead-source" className="sr-only">
            Lead source
          </Label>
          <Select
            id="lead-source"
            value={source}
            onChange={(event) =>
              onSourceChange(event.target.value as LeadSource | "")
            }
          >
            <option value="">All sources</option>
            <option value="MANUAL">Manual</option>
            <option value="WEBSITE">Website</option>
            <option value="EMAIL">Email</option>
            <option value="CHAT">Chat</option>
            <option value="API">API</option>
            <option value="IMPORT">Import</option>
          </Select>
        </div>
      </FilterBar>
    </div>
  );
}

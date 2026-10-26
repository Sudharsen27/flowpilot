"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import type { CompanyProspectStatus } from "@/types/api";

type CompanyProspectsToolbarProps = {
  query: string;
  status: CompanyProspectStatus | "";
  onQueryChange: (value: string) => void;
  onStatusChange: (value: CompanyProspectStatus | "") => void;
  onClearFilters: () => void;
};

export function CompanyProspectsToolbar({
  query,
  status,
  onQueryChange,
  onStatusChange,
  onClearFilters,
}: CompanyProspectsToolbarProps) {
  const activeFilterCount = [query.trim() !== "", status !== ""].filter(Boolean).length;

  return (
    <FilterBar
      search={
        <SearchInput
          id="company-prospect-search"
          label="Search company prospects"
          placeholder="Search name or domain"
          maxLength={200}
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onClear={() => onQueryChange("")}
        />
      }
      activeFilterCount={activeFilterCount}
      onClearFilters={onClearFilters}
    >
      <div className="w-full sm:w-40">
        <Label htmlFor="company-prospect-status" className="sr-only">
          Lifecycle status
        </Label>
        <Select
          id="company-prospect-status"
          value={status}
          onChange={(event) =>
            onStatusChange(event.target.value as CompanyProspectStatus | "")
          }
        >
          <option value="">All statuses</option>
          <option value="IDENTIFIED">Identified</option>
          <option value="REVIEWED">Reviewed</option>
          <option value="ARCHIVED">Archived</option>
        </Select>
      </div>
    </FilterBar>
  );
}

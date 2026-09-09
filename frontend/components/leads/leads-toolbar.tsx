"use client";

import { useState } from "react";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";

export function LeadsToolbar() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [source, setSource] = useState("all");
  const [qualification, setQualification] = useState("all");

  const activeFilterCount = [
    query.trim() !== "",
    status !== "all",
    source !== "all",
    qualification !== "all",
  ].filter(Boolean).length;

  function clearFilters() {
    setQuery("");
    setStatus("all");
    setSource("all");
    setQualification("all");
  }

  return (
    <div className="grid gap-2">
      <FilterBar
        search={
          <SearchInput
            id="lead-search"
            label="Search leads"
            placeholder="Search leads"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onClear={() => setQuery("")}
            aria-describedby="lead-filters-note"
          />
        }
        activeFilterCount={activeFilterCount}
        onClearFilters={clearFilters}
      >
        <div className="w-full sm:w-40">
          <Label htmlFor="lead-status" className="sr-only">
            Lead status
          </Label>
          <Select
            id="lead-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            aria-describedby="lead-filters-note"
          >
            <option value="all">All statuses</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="unqualified">Unqualified</option>
            <option value="converted">Converted</option>
          </Select>
        </div>
        <div className="w-full sm:w-40">
          <Label htmlFor="lead-source" className="sr-only">
            Lead source
          </Label>
          <Select
            id="lead-source"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            aria-describedby="lead-filters-note"
          >
            <option value="all">All sources</option>
            <option value="form">Forms</option>
            <option value="inbox">Inboxes</option>
            <option value="integration">Integrations</option>
          </Select>
        </div>
        <div className="w-full sm:w-48">
          <Label htmlFor="lead-qualification" className="sr-only">
            AI qualification
          </Label>
          <Select
            id="lead-qualification"
            value={qualification}
            onChange={(event) => setQualification(event.target.value)}
            aria-describedby="lead-filters-note"
          >
            <option value="all">All qualification</option>
            <option value="not-assessed">Not assessed</option>
            <option value="pending">Pending</option>
            <option value="qualified">Qualified</option>
            <option value="unqualified">Unqualified</option>
          </Select>
        </div>
      </FilterBar>
      <p id="lead-filters-note" className="text-muted-foreground text-xs">
        Filters are ready for use when a lead data source is connected.
      </p>
    </div>
  );
}

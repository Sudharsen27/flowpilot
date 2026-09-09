"use client";

import { useState } from "react";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";

export function ActivityToolbar() {
  const [query, setQuery] = useState("");
  const [eventType, setEventType] = useState("all");
  const [actor, setActor] = useState("all");
  const [status, setStatus] = useState("all");

  const activeFilterCount = [
    query.trim() !== "",
    eventType !== "all",
    actor !== "all",
    status !== "all",
  ].filter(Boolean).length;

  function clearFilters() {
    setQuery("");
    setEventType("all");
    setActor("all");
    setStatus("all");
  }

  return (
    <div className="grid gap-2">
      <FilterBar
        className="!grid grid-cols-2"
        searchClassName="col-span-2"
        search={
          <SearchInput
            id="activity-search"
            label="Search activity"
            placeholder="Search activity"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onClear={() => setQuery("")}
            aria-describedby="activity-filters-note"
          />
        }
        activeFilterCount={activeFilterCount}
        onClearFilters={clearFilters}
      >
        <div className="min-w-0">
          <Label htmlFor="activity-event-type" className="sr-only">
            Event type
          </Label>
          <Select
            id="activity-event-type"
            value={eventType}
            onChange={(event) => setEventType(event.target.value)}
            aria-describedby="activity-filters-note"
          >
            <option value="all">All event types</option>
            <option value="ai-action">AI action</option>
            <option value="workflow">Workflow</option>
            <option value="approval">Approval</option>
            <option value="integration">Integration</option>
            <option value="human-action">Human action</option>
            <option value="system-event">System event</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="activity-actor" className="sr-only">
            Actor or source
          </Label>
          <Select
            id="activity-actor"
            value={actor}
            onChange={(event) => setActor(event.target.value)}
            aria-describedby="activity-filters-note"
          >
            <option value="all">All actors</option>
            <option value="agent">AI agent</option>
            <option value="workflow">Workflow</option>
            <option value="person">Team member</option>
            <option value="system">System</option>
          </Select>
        </div>
        <div className="col-span-2 min-w-0">
          <Label htmlFor="activity-status" className="sr-only">
            Event status
          </Label>
          <Select
            id="activity-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            aria-describedby="activity-filters-note"
          >
            <option value="all">All statuses</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
            <option value="information">Information</option>
          </Select>
        </div>
      </FilterBar>
      <p id="activity-filters-note" className="text-muted-foreground text-xs">
        Filters are ready for use when an activity event source is connected.
      </p>
    </div>
  );
}

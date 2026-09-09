"use client";

import { useState } from "react";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";

export function InboxToolbar() {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [handling, setHandling] = useState("all");
  const [channel, setChannel] = useState("all");

  const activeFilterCount = [
    query.trim() !== "",
    status !== "all",
    handling !== "all",
    channel !== "all",
  ].filter(Boolean).length;

  function clearFilters() {
    setQuery("");
    setStatus("all");
    setHandling("all");
    setChannel("all");
  }

  return (
    <div className="grid gap-2">
      <FilterBar
        className="!grid grid-cols-2"
        searchClassName="col-span-2"
        search={
          <SearchInput
            id="conversation-search"
            label="Search conversations"
            placeholder="Search conversations"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onClear={() => setQuery("")}
            aria-describedby="inbox-filters-note"
          />
        }
        activeFilterCount={activeFilterCount}
        onClearFilters={clearFilters}
      >
        <div className="min-w-0">
          <Label htmlFor="conversation-status" className="sr-only">
            Conversation status
          </Label>
          <Select
            id="conversation-status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            aria-describedby="inbox-filters-note"
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="waiting">Waiting</option>
            <option value="resolved">Resolved</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="conversation-handling" className="sr-only">
            Conversation handling
          </Label>
          <Select
            id="conversation-handling"
            value={handling}
            onChange={(event) => setHandling(event.target.value)}
            aria-describedby="inbox-filters-note"
          >
            <option value="all">All handling</option>
            <option value="ai">AI handled</option>
            <option value="human">Human handled</option>
            <option value="unassigned">Unassigned</option>
          </Select>
        </div>
        <div className="col-span-2 min-w-0">
          <Label htmlFor="conversation-channel" className="sr-only">
            Conversation channel
          </Label>
          <Select
            id="conversation-channel"
            value={channel}
            onChange={(event) => setChannel(event.target.value)}
            aria-describedby="inbox-filters-note"
          >
            <option value="all">All channels</option>
            <option value="inbox">Inbox</option>
            <option value="chat">Web chat</option>
            <option value="integration">Integration</option>
          </Select>
        </div>
      </FilterBar>
      <p id="inbox-filters-note" className="text-muted-foreground text-xs">
        Filters are ready for use when a conversation channel is connected.
      </p>
    </div>
  );
}

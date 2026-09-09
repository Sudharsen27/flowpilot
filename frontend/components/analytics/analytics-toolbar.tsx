"use client";

import { useState } from "react";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";

export function AnalyticsToolbar() {
  const [range, setRange] = useState("30");
  const [agent, setAgent] = useState("all");
  const [workflow, setWorkflow] = useState("all");
  const [channel, setChannel] = useState("all");

  const activeFilterCount = [
    range !== "30",
    agent !== "all",
    workflow !== "all",
    channel !== "all",
  ].filter(Boolean).length;

  function clearFilters() {
    setRange("30");
    setAgent("all");
    setWorkflow("all");
    setChannel("all");
  }

  return (
    <div className="grid gap-2">
      <FilterBar
        className="!grid grid-cols-2 xl:grid-cols-4"
        activeFilterCount={activeFilterCount}
        onClearFilters={clearFilters}
      >
        <div className="min-w-0">
          <Label htmlFor="analytics-date-range" className="sr-only">
            Date range
          </Label>
          <Select
            id="analytics-date-range"
            value={range}
            onChange={(event) => setRange(event.target.value)}
            aria-describedby="analytics-filters-note"
          >
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="analytics-agent" className="sr-only">
            Agent
          </Label>
          <Select
            id="analytics-agent"
            value={agent}
            onChange={(event) => setAgent(event.target.value)}
            aria-describedby="analytics-filters-note"
          >
            <option value="all">All agents</option>
            <option value="sales">Sales agent</option>
            <option value="support">Support agent</option>
            <option value="operations">Operations agent</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="analytics-workflow" className="sr-only">
            Workflow
          </Label>
          <Select
            id="analytics-workflow"
            value={workflow}
            onChange={(event) => setWorkflow(event.target.value)}
            aria-describedby="analytics-filters-note"
          >
            <option value="all">All workflows</option>
            <option value="qualification">Qualification</option>
            <option value="follow-up">Follow-up</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="analytics-channel" className="sr-only">
            Channel or source
          </Label>
          <Select
            id="analytics-channel"
            value={channel}
            onChange={(event) => setChannel(event.target.value)}
            aria-describedby="analytics-filters-note"
          >
            <option value="all">All channels</option>
            <option value="form">Forms</option>
            <option value="inbox">Inbox</option>
            <option value="integration">Integrations</option>
          </Select>
        </div>
      </FilterBar>
      <p id="analytics-filters-note" className="text-muted-foreground text-xs">
        Date range and filters are UI-only. They do not query analytics data.
      </p>
    </div>
  );
}

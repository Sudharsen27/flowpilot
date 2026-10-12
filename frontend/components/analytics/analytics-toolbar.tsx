"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import type { AnalyticsRangeDays, LeadSource } from "@/types/api";

export const leadSourceLabels: Record<LeadSource, string> = {
  MANUAL: "Manual",
  WEBSITE: "Website",
  EMAIL: "Email",
  CHAT: "Chat",
  API: "API",
  IMPORT: "Import",
};

type AnalyticsToolbarProps = {
  rangeDays: AnalyticsRangeDays;
  source: LeadSource | null;
  onRangeDaysChange: (value: AnalyticsRangeDays) => void;
  onSourceChange: (value: LeadSource | null) => void;
};

export function AnalyticsToolbar({
  rangeDays,
  source,
  onRangeDaysChange,
  onSourceChange,
}: AnalyticsToolbarProps) {
  return (
    <div className="grid gap-2">
      <FilterBar className="!grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
        <div className="min-w-0">
          <Label htmlFor="analytics-date-range">Date range</Label>
          <Select
            id="analytics-date-range"
            value={String(rangeDays)}
            onChange={(event) =>
              onRangeDaysChange(Number(event.target.value) as AnalyticsRangeDays)
            }
          >
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="analytics-source">Lead source</Label>
          <Select
            id="analytics-source"
            value={source ?? "all"}
            onChange={(event) =>
              onSourceChange(
                event.target.value === "all" ? null : (event.target.value as LeadSource),
              )
            }
          >
            <option value="all">All sources</option>
            {Object.entries(leadSourceLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
      </FilterBar>
      <p className="text-muted-foreground text-xs">
        Days are counted in UTC. The source filter limits every number to leads from that
        source.
      </p>
    </div>
  );
}

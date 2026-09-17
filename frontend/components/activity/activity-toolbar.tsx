"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import type { ActivityEntityType, ActivityEventType } from "@/types/api";

type ActivityToolbarProps = {
  query: string;
  eventType: ActivityEventType | "";
  entityType: ActivityEntityType | "";
  onQueryChange: (value: string) => void;
  onEventTypeChange: (value: ActivityEventType | "") => void;
  onEntityTypeChange: (value: ActivityEntityType | "") => void;
  onClearFilters: () => void;
};

export function ActivityToolbar({
  query,
  eventType,
  entityType,
  onQueryChange,
  onEventTypeChange,
  onEntityTypeChange,
  onClearFilters,
}: ActivityToolbarProps) {
  const activeFilterCount = [
    query.trim() !== "",
    eventType !== "",
    entityType !== "",
  ].filter(Boolean).length;

  return (
    <FilterBar
      className="!grid grid-cols-2"
      searchClassName="col-span-2"
      search={
        <SearchInput
          id="activity-search"
          label="Search activity"
          placeholder="Search activity"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onClear={() => onQueryChange("")}
        />
      }
      activeFilterCount={activeFilterCount}
      onClearFilters={onClearFilters}
    >
      <div className="min-w-0">
        <Label htmlFor="activity-event-type" className="sr-only">
          Event type
        </Label>
        <Select
          id="activity-event-type"
          value={eventType}
          onChange={(event) =>
            onEventTypeChange(event.target.value as ActivityEventType | "")
          }
        >
          <option value="">All event types</option>
          <option value="AI_ACTION">AI action</option>
          <option value="APPROVAL">Approval</option>
          <option value="HUMAN_ACTION">Human action</option>
          <option value="SYSTEM_EVENT">System event</option>
        </Select>
      </div>
      <div className="min-w-0">
        <Label htmlFor="activity-entity-type" className="sr-only">
          Entity type
        </Label>
        <Select
          id="activity-entity-type"
          value={entityType}
          onChange={(event) =>
            onEntityTypeChange(event.target.value as ActivityEntityType | "")
          }
        >
          <option value="">All entities</option>
          <option value="LEAD">Lead</option>
          <option value="SALES_RUN">Sales Run</option>
          <option value="LEAD_EMAIL_SEND">Email</option>
          <option value="LEAD_FOLLOW_UP">Follow-up</option>
          <option value="LEAD_FOLLOW_UP_EXECUTION">Follow-up execution</option>
          <option value="LEAD_RESPONSE_DRAFT">Response draft</option>
          <option value="LEAD_QUALIFICATION">Qualification</option>
          <option value="AGENT_EXECUTION">Agent execution</option>
        </Select>
      </div>
    </FilterBar>
  );
}

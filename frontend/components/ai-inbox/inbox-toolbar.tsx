"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import type { InboxConversationState, LeadSource } from "@/types/api";

export type NeedsApprovalFilter = "" | "true" | "false";

type InboxToolbarProps = {
  query: string;
  conversationState: InboxConversationState | "";
  source: LeadSource | "";
  needsApproval: NeedsApprovalFilter;
  onQueryChange: (value: string) => void;
  onConversationStateChange: (value: InboxConversationState | "") => void;
  onSourceChange: (value: LeadSource | "") => void;
  onNeedsApprovalChange: (value: NeedsApprovalFilter) => void;
  onClearFilters: () => void;
};

export function InboxToolbar({
  query,
  conversationState,
  source,
  needsApproval,
  onQueryChange,
  onConversationStateChange,
  onSourceChange,
  onNeedsApprovalChange,
  onClearFilters,
}: InboxToolbarProps) {
  const activeFilterCount = [
    query.trim() !== "",
    conversationState !== "",
    source !== "",
    needsApproval !== "",
  ].filter(Boolean).length;

  return (
    <div className="grid gap-2">
      <FilterBar
        className="!grid grid-cols-2"
        searchClassName="col-span-2"
        search={
          <SearchInput
            id="conversation-search"
            label="Search conversations"
            placeholder="Search name, email, or company"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onClear={() => onQueryChange("")}
            aria-describedby="inbox-filters-note"
          />
        }
        activeFilterCount={activeFilterCount}
        onClearFilters={onClearFilters}
      >
        <div className="min-w-0">
          <Label htmlFor="conversation-status" className="sr-only">
            Conversation status
          </Label>
          <Select
            id="conversation-status"
            value={conversationState}
            onChange={(event) =>
              onConversationStateChange(
                event.target.value as InboxConversationState | "",
              )
            }
            aria-describedby="inbox-filters-note"
          >
            <option value="">All statuses</option>
            <option value="OPEN">Open</option>
            <option value="NEEDS_APPROVAL">Needs approval</option>
            <option value="CLOSED">Closed</option>
          </Select>
        </div>
        <div className="min-w-0">
          <Label htmlFor="conversation-needs-approval" className="sr-only">
            Needs approval
          </Label>
          <Select
            id="conversation-needs-approval"
            value={needsApproval}
            onChange={(event) =>
              onNeedsApprovalChange(event.target.value as NeedsApprovalFilter)
            }
            aria-describedby="inbox-filters-note"
          >
            <option value="">All approval states</option>
            <option value="true">Needs approval</option>
            <option value="false">No approval needed</option>
          </Select>
        </div>
        <div className="col-span-2 min-w-0">
          <Label htmlFor="conversation-source" className="sr-only">
            Lead source
          </Label>
          <Select
            id="conversation-source"
            value={source}
            onChange={(event) =>
              onSourceChange(event.target.value as LeadSource | "")
            }
            aria-describedby="inbox-filters-note"
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
      <p id="inbox-filters-note" className="text-muted-foreground text-xs">
        Filters apply to sales conversation history for this organization.
      </p>
    </div>
  );
}

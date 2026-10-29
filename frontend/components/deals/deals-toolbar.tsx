"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import { DEAL_STAGES, DEAL_STAGE_LABELS } from "@/lib/deals";
import type { DealStage, MemberPublic } from "@/types/api";

type DealsToolbarProps = {
  query: string;
  stage: DealStage | null;
  ownerUserId: string | null;
  closeDateFrom: string | null;
  closeDateTo: string | null;
  members: MemberPublic[];
  onQueryChange: (value: string) => void;
  onStageChange: (value: DealStage | null) => void;
  onOwnerChange: (value: string | null) => void;
  onCloseDateFromChange: (value: string | null) => void;
  onCloseDateToChange: (value: string | null) => void;
  onClearFilters: () => void;
};

export function DealsToolbar({
  query,
  stage,
  ownerUserId,
  closeDateFrom,
  closeDateTo,
  members,
  onQueryChange,
  onStageChange,
  onOwnerChange,
  onCloseDateFromChange,
  onCloseDateToChange,
  onClearFilters,
}: DealsToolbarProps) {
  const activeFilterCount = [
    query.trim() !== "",
    stage !== null,
    ownerUserId !== null,
    closeDateFrom !== null,
    closeDateTo !== null,
  ].filter(Boolean).length;
  const rangeInvalid = Boolean(closeDateFrom && closeDateTo && closeDateFrom > closeDateTo);

  return (
    <div className="grid gap-2">
      <FilterBar
        search={
          <SearchInput
            id="deal-search"
            label="Search deals"
            placeholder="Search deal name"
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
          <Label htmlFor="deal-stage-filter" className="sr-only">
            Stage
          </Label>
          <Select
            id="deal-stage-filter"
            value={stage ?? ""}
            onChange={(event) =>
              onStageChange((event.target.value || null) as DealStage | null)
            }
          >
            <option value="">All stages</option>
            {DEAL_STAGES.map((value) => (
              <option key={value} value={value}>
                {DEAL_STAGE_LABELS[value]}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-full sm:w-44">
          <Label htmlFor="deal-owner-filter" className="sr-only">
            Owner
          </Label>
          <Select
            id="deal-owner-filter"
            value={ownerUserId ?? ""}
            onChange={(event) => onOwnerChange(event.target.value || null)}
          >
            <option value="">All owners</option>
            {ownerUserId && !members.some((member) => member.user.id === ownerUserId) ? (
              <option value={ownerUserId}>Selected owner</option>
            ) : null}
            {members.map((member) => (
              <option key={member.user.id} value={member.user.id}>
                {member.user.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex w-full items-center gap-2 sm:w-auto">
          <Label htmlFor="deal-close-from" className="text-muted-foreground shrink-0 text-xs">
            Closing
          </Label>
          <Input
            id="deal-close-from"
            type="date"
            aria-label="Expected close from"
            className="sm:w-36"
            value={closeDateFrom ?? ""}
            onChange={(event) => onCloseDateFromChange(event.target.value || null)}
            aria-invalid={rangeInvalid || undefined}
            aria-describedby={rangeInvalid ? "deal-close-range-error" : undefined}
          />
          <span className="text-muted-foreground text-xs" aria-hidden="true">
            to
          </span>
          <Input
            id="deal-close-to"
            type="date"
            aria-label="Expected close to"
            className="sm:w-36"
            value={closeDateTo ?? ""}
            onChange={(event) => onCloseDateToChange(event.target.value || null)}
            aria-invalid={rangeInvalid || undefined}
            aria-describedby={rangeInvalid ? "deal-close-range-error" : undefined}
          />
        </div>
      </FilterBar>
      {rangeInvalid ? (
        <p id="deal-close-range-error" className="text-danger-text text-xs" role="alert">
          The start of the close-date range must be on or before the end.
        </p>
      ) : null}
    </div>
  );
}

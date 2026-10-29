"use client";

import { FilterBar } from "@/components/forms/filter-bar";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import {
  DEAL_STAGES,
  DEAL_STAGE_LABELS,
  FORECAST_CATEGORIES,
  FORECAST_CATEGORY_LABELS,
} from "@/lib/deals";
import type { DealStage, ForecastCategory, MemberPublic } from "@/types/api";

type DealsToolbarProps = {
  query: string;
  stage: DealStage | null;
  forecastCategory: ForecastCategory | null;
  ownerUserId: string | null;
  closeDateFrom: string | null;
  closeDateTo: string | null;
  members: MemberPublic[];
  onQueryChange: (value: string) => void;
  onStageChange: (value: DealStage | null) => void;
  onForecastCategoryChange: (value: ForecastCategory | null) => void;
  onOwnerChange: (value: string | null) => void;
  onCloseDateFromChange: (value: string | null) => void;
  onCloseDateToChange: (value: string | null) => void;
  onClearFilters: () => void;
};

export function DealsToolbar({
  query,
  stage,
  forecastCategory,
  ownerUserId,
  closeDateFrom,
  closeDateTo,
  members,
  onQueryChange,
  onStageChange,
  onForecastCategoryChange,
  onOwnerChange,
  onCloseDateFromChange,
  onCloseDateToChange,
  onClearFilters,
}: DealsToolbarProps) {
  const activeFilterCount = [
    query.trim() !== "",
    stage !== null,
    forecastCategory !== null,
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
        <div className="w-full sm:w-40">
          <Label htmlFor="deal-category-filter" className="sr-only">
            Forecast category
          </Label>
          <Select
            id="deal-category-filter"
            value={forecastCategory ?? ""}
            onChange={(event) =>
              onForecastCategoryChange((event.target.value || null) as ForecastCategory | null)
            }
          >
            <option value="">All categories</option>
            {FORECAST_CATEGORIES.map((value) => (
              <option key={value} value={value}>
                {FORECAST_CATEGORY_LABELS[value]}
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
        {/* Two pairs that wrap onto separate lines on narrow screens, so the native date
            inputs keep their full width instead of clipping. */}
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-nowrap">
          <div className="flex min-w-48 flex-1 items-center gap-2 sm:min-w-0 sm:flex-none">
            <Label htmlFor="deal-close-from" className="text-muted-foreground shrink-0 text-xs">
              Closing
            </Label>
            <Input
              id="deal-close-from"
              type="date"
              aria-label="Expected close from"
              className="min-w-0 flex-1 sm:w-36 sm:flex-none"
              value={closeDateFrom ?? ""}
              onChange={(event) => onCloseDateFromChange(event.target.value || null)}
              aria-invalid={rangeInvalid || undefined}
              aria-describedby={rangeInvalid ? "deal-close-range-error" : undefined}
            />
          </div>
          <div className="flex min-w-48 flex-1 items-center gap-2 sm:min-w-0 sm:flex-none">
            <span className="text-muted-foreground text-xs" aria-hidden="true">
              to
            </span>
            <Input
              id="deal-close-to"
              type="date"
              aria-label="Expected close to"
              className="min-w-0 flex-1 sm:w-36 sm:flex-none"
              value={closeDateTo ?? ""}
              onChange={(event) => onCloseDateToChange(event.target.value || null)}
              aria-invalid={rangeInvalid || undefined}
              aria-describedby={rangeInvalid ? "deal-close-range-error" : undefined}
            />
          </div>
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

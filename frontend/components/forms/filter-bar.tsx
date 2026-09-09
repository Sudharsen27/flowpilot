import { Filter, X } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type FilterBarProps = {
  search?: ReactNode;
  children?: ReactNode;
  activeFilterCount?: number;
  onOpenFilters?: () => void;
  onClearFilters?: () => void;
  className?: string;
};

export function FilterBar({
  search,
  children,
  activeFilterCount = 0,
  onOpenFilters,
  onClearFilters,
  className,
}: FilterBarProps) {
  return (
    <div
      data-slot="filter-bar"
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center",
        className,
      )}
    >
      {search ? <div className="min-w-0 flex-1">{search}</div> : null}
      {children}
      {onOpenFilters ? (
        <Button type="button" variant="outline" onClick={onOpenFilters}>
          <Filter aria-hidden="true" />
          Filters
          {activeFilterCount > 0 ? (
            <span className="bg-primary text-primary-foreground flex min-w-5 items-center justify-center rounded-full px-1 text-[0.6875rem]">
              {activeFilterCount}
              <span className="sr-only"> active</span>
            </span>
          ) : null}
        </Button>
      ) : null}
      {activeFilterCount > 0 && onClearFilters ? (
        <Button type="button" variant="ghost" onClick={onClearFilters}>
          <X aria-hidden="true" />
          Clear filters
        </Button>
      ) : null}
    </div>
  );
}

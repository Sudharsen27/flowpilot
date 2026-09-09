"use client";

import { Search, X } from "lucide-react";
import type { ComponentProps } from "react";

import { Input } from "@/components/forms/input";
import { cn } from "@/lib/utils";

type SearchInputProps = Omit<ComponentProps<"input">, "type"> & {
  label?: string;
  onClear?: () => void;
};

export function SearchInput({
  label = "Search",
  onClear,
  className,
  value,
  ...props
}: SearchInputProps) {
  const hasValue = typeof value === "string" && value.length > 0;

  return (
    <div className={cn("relative w-full sm:max-w-sm", className)}>
      <label className="sr-only" htmlFor={props.id}>
        {label}
      </label>
      <Search
        aria-hidden="true"
        className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
      />
      <Input
        type="search"
        value={value}
        aria-label={!props.id ? label : undefined}
        className={cn("pr-9 pl-9", hasValue && onClear && "pr-10")}
        {...props}
      />
      {hasValue && onClear ? (
        <button
          type="button"
          aria-label="Clear search"
          onClick={onClear}
          className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 flex size-7 -translate-y-1/2 items-center justify-center rounded-md"
        >
          <X className="size-3.5" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}

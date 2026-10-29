"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Single-series bar charts (dataviz method): one accent hue (--chart-1, validated
 * for light and dark), bars <= 24px thick with a 4px rounded data end and a square
 * baseline, values labelled at the tip in text tokens, hover/focus tooltips, and a
 * visually hidden table so every value is reachable without the pointer.
 *
 * `magnitude` is used only to size bars. Displayed values are the caller's exact
 * strings, so money never passes through floating point.
 */
export type BarDatum = {
  key: string;
  label: string;
  /** Display value at the tip, e.g. "₹12.5L". */
  value: string;
  /** Geometry only: relative length of the bar. */
  magnitude: number;
  /** Extra tooltip lines, e.g. exact amount and deal count. */
  details?: string[];
};

type ChartProps = {
  data: BarDatum[];
  /** Name of the measure for the table header and screen readers. */
  valueLabel: string;
  categoryLabel: string;
  emptyMessage?: string;
};

function ratio(value: number, max: number) {
  if (!Number.isFinite(value) || value <= 0 || max <= 0) return 0;
  return Math.max(value / max, 0.015);
}

function DataTable({ data, valueLabel, categoryLabel, caption }: ChartProps & { caption: string }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">{categoryLabel}</th>
          <th scope="col">{valueLabel}</th>
          <th scope="col">Details</th>
        </tr>
      </thead>
      <tbody>
        {data.map((item) => (
          <tr key={item.key}>
            <th scope="row">{item.label}</th>
            <td>{item.value}</td>
            <td>{item.details?.join("; ") ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Tooltip({ item }: { item: BarDatum }) {
  return (
    <div
      role="tooltip"
      className="bg-popover text-popover-foreground shadow-overlay border-border pointer-events-none absolute z-10 min-w-36 rounded-md border px-2.5 py-1.5 text-xs"
    >
      <p className="font-semibold tabular-nums">{item.value}</p>
      <p className="text-muted-foreground">{item.label}</p>
      {item.details?.map((line) => (
        <p key={line} className="text-muted-foreground tabular-nums">
          {line}
        </p>
      ))}
    </div>
  );
}

/** Horizontal bars: categories down the side, length = magnitude. */
export function BarListChart({ data, valueLabel, categoryLabel, emptyMessage }: ChartProps) {
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(0, ...data.map((item) => item.magnitude));
  if (data.length === 0 || max <= 0) {
    return <p className="text-muted-foreground py-6 text-center text-sm">{emptyMessage ?? "No data yet."}</p>;
  }
  return (
    <div>
      <ul className="grid gap-2.5" aria-hidden="true">
        {data.map((item) => (
          <li
            key={item.key}
            className="grid grid-cols-[6.5rem_minmax(0,1fr)] items-center gap-3 text-xs sm:grid-cols-[8rem_minmax(0,1fr)]"
          >
            <span className="text-muted-foreground truncate">{item.label}</span>
            <div className="relative flex items-center gap-2">
              <div
                onPointerEnter={() => setActive(item.key)}
                onPointerLeave={() => setActive(null)}
                className="relative flex h-5 min-w-0 flex-1 items-center"
              >
                <span
                  className="bg-chart-1 block h-full rounded-r-[4px]"
                  style={{ width: `${ratio(item.magnitude, max) * 100}%` }}
                />
                {active === item.key ? (
                  <div className="absolute top-6 left-0">
                    <Tooltip item={item} />
                  </div>
                ) : null}
              </div>
              <span className="text-foreground w-20 shrink-0 text-right font-medium tabular-nums">
                {item.value}
              </span>
            </div>
          </li>
        ))}
      </ul>
      <DataTable
        data={data}
        valueLabel={valueLabel}
        categoryLabel={categoryLabel}
        caption={`${valueLabel} by ${categoryLabel.toLowerCase()}`}
      />
    </div>
  );
}

/** Vertical columns over time, with keyboard-reachable tooltips. */
export function ColumnChart({ data, valueLabel, categoryLabel, emptyMessage }: ChartProps) {
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(0, ...data.map((item) => item.magnitude));
  const hasData = data.length > 0 && max > 0;
  return (
    <div>
      <div
        className="grid h-40 items-end gap-0.5"
        style={{ gridTemplateColumns: `repeat(${Math.max(data.length, 1)}, minmax(0, 1fr))` }}
        role="group"
        aria-label={`${valueLabel} by ${categoryLabel.toLowerCase()}`}
      >
        {data.map((item) => (
          <div key={item.key} className="relative flex h-full flex-col items-center justify-end">
            <button
              type="button"
              aria-label={`${item.label}: ${item.value}${item.details ? `, ${item.details.join(", ")}` : ""}`}
              onPointerEnter={() => setActive(item.key)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(item.key)}
              onBlur={() => setActive(null)}
              className="focus-visible:ring-ring flex h-full w-full items-end justify-center rounded-sm outline-none focus-visible:ring-2"
            >
              <span
                className={cn(
                  "bg-chart-1 block w-full max-w-6 rounded-t-[4px] transition-opacity",
                  active && active !== item.key ? "opacity-60" : undefined,
                )}
                style={{ height: hasData ? `${ratio(item.magnitude, max) * 100}%` : "0%" }}
              />
            </button>
            {active === item.key ? (
              <div className="absolute bottom-full mb-1">
                <Tooltip item={item} />
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <div
        className="border-border text-muted-foreground mt-1 grid gap-0.5 border-t pt-1.5 text-center text-[0.6875rem]"
        style={{ gridTemplateColumns: `repeat(${Math.max(data.length, 1)}, minmax(0, 1fr))` }}
        aria-hidden="true"
      >
        {data.map((item) => (
          <span key={item.key} className="truncate">
            {item.label}
          </span>
        ))}
      </div>
      {!hasData ? (
        <p className="text-muted-foreground mt-2 text-center text-xs">{emptyMessage ?? "No data yet."}</p>
      ) : null}
      <DataTable
        data={data}
        valueLabel={valueLabel}
        categoryLabel={categoryLabel}
        caption={`${valueLabel} by ${categoryLabel.toLowerCase()}`}
      />
    </div>
  );
}

/** Bar length from an API decimal string. Geometry only; never shown or summed. */
export function magnitudeOf(amount: string): number {
  const value = Number(amount);
  return Number.isFinite(value) ? value : 0;
}

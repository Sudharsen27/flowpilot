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
      {item.label ? <p className="text-muted-foreground">{item.label}</p> : null}
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

export type ColumnSeries = {
  key: string;
  label: string;
  /** Mark styling, e.g. "bg-chart-1". Pair hue with a second cue (fill vs outline). */
  markClassName: string;
};

export type GroupedColumnDatum = {
  key: string;
  /** Axis label, e.g. "Q4 2026". */
  label: string;
  /** Full name for tooltips and screen readers, e.g. "Q4 2026 (Oct 1 – Dec 31)". */
  fullLabel: string;
  /** One entry per series, in series order. */
  values: { value: string; magnitude: number }[];
};

type GroupedColumnChartProps = {
  series: ColumnSeries[];
  data: GroupedColumnDatum[];
  /** Accessible name of the plot, e.g. "Won revenue and weighted forecast by quarter". */
  label: string;
  emptyMessage?: string;
};

/**
 * Side-by-side columns per category, one hue per series with a shared scale. Each
 * group is one keyboard stop whose accessible name lists every series value.
 */
export function GroupedColumnChart({ series, data, label, emptyMessage }: GroupedColumnChartProps) {
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(0, ...data.flatMap((item) => item.values.map((entry) => entry.magnitude)));
  const hasData = data.length > 0 && max > 0;
  const columns = { gridTemplateColumns: `repeat(${Math.max(data.length, 1)}, minmax(0, 1fr))` };
  return (
    <div>
      <ul className="text-muted-foreground mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Legend">
        {series.map((entry) => (
          <li key={entry.key} className="flex items-center gap-1.5">
            <span className={cn("block size-2.5 rounded-[2px]", entry.markClassName)} aria-hidden="true" />
            {entry.label}
          </li>
        ))}
      </ul>
      <div className="grid h-44 items-end gap-1" style={columns} role="group" aria-label={label}>
        {data.map((item) => (
          <div key={item.key} className="relative flex h-full flex-col items-center justify-end">
            <button
              type="button"
              aria-label={`${item.fullLabel}: ${series
                .map((entry, index) => `${entry.label} ${item.values[index]?.value ?? "—"}`)
                .join(", ")}`}
              onPointerEnter={() => setActive(item.key)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(item.key)}
              onBlur={() => setActive(null)}
              className={cn(
                "focus-visible:ring-ring flex h-full w-full items-end justify-center gap-0.5 rounded-sm outline-none focus-visible:ring-2",
                active && active !== item.key ? "opacity-60" : undefined,
              )}
            >
              {series.map((entry, index) => {
                const share = hasData ? ratio(item.values[index]?.magnitude ?? 0, max) : 0;
                return (
                  <span
                    key={entry.key}
                    // A zero value draws nothing, not even an outlined sliver.
                    className={cn("block w-full max-w-6 rounded-t-[4px]", entry.markClassName, share === 0 && "invisible")}
                    style={{ height: `${share * 100}%` }}
                  />
                );
              })}
            </button>
            {active === item.key ? (
              <div className="absolute bottom-full mb-1">
                <Tooltip
                  item={{
                    key: item.key,
                    label: "",
                    value: item.fullLabel,
                    magnitude: 0,
                    details: series.map(
                      (entry, index) => `${entry.label}: ${item.values[index]?.value ?? "—"}`,
                    ),
                  }}
                />
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <div
        className="border-border text-muted-foreground mt-1 grid gap-1 border-t pt-1.5 text-center text-[0.6875rem]"
        style={columns}
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
    </div>
  );
}

export type StackedBarDatum = {
  key: string;
  /** Row label, e.g. "Q4 2026". */
  label: string;
  /** Full name for tooltips and screen readers. */
  fullLabel: string;
  /** Exact total shown at the bar's end, as returned by the API. */
  total: string;
  /** One entry per series, in series order. */
  values: { value: string; magnitude: number }[];
};

type StackedBarChartProps = {
  series: ColumnSeries[];
  data: StackedBarDatum[];
  /** Accessible name of the plot, e.g. "Open pipeline by category and quarter". */
  label: string;
  /** Header of the row column in the data table, e.g. "Quarter". */
  categoryLabel: string;
  emptyMessage?: string;
};

/**
 * Horizontal bars split into one segment per series, on a scale shared by every row.
 * Segments are separated by a 2px gap, each row is one keyboard stop naming every
 * value, and a visually hidden table carries the same figures.
 */
export function StackedBarChart({ series, data, label, categoryLabel, emptyMessage }: StackedBarChartProps) {
  const [active, setActive] = useState<string | null>(null);
  const rowMagnitude = (item: StackedBarDatum) =>
    item.values.reduce((sum, entry) => sum + Math.max(entry.magnitude, 0), 0);
  const max = Math.max(0, ...data.map(rowMagnitude));
  const hasData = data.length > 0 && max > 0;
  const describe = (item: StackedBarDatum) =>
    series.map((entry, index) => `${entry.label} ${item.values[index]?.value ?? "—"}`).join(", ");
  return (
    <div>
      <ul className="text-muted-foreground mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label={`Legend: ${label}`}>
        {series.map((entry) => (
          <li key={entry.key} className="flex items-center gap-1.5">
            <span className={cn("block size-2.5 rounded-[2px]", entry.markClassName)} aria-hidden="true" />
            {entry.label}
          </li>
        ))}
      </ul>
      {hasData ? (
        <ul className="grid gap-2.5" role="group" aria-label={label}>
          {data.map((item) => {
            const share = ratio(rowMagnitude(item), max);
            return (
              <li
                key={item.key}
                className="grid grid-cols-[5rem_minmax(0,1fr)] items-center gap-3 text-xs sm:grid-cols-[6.5rem_minmax(0,1fr)]"
              >
                <span className="text-muted-foreground truncate" aria-hidden="true">
                  {item.label}
                </span>
                <div className="relative flex items-center gap-2">
                  <button
                    type="button"
                    aria-label={`${item.fullLabel}: total ${item.total}; ${describe(item)}`}
                    onPointerEnter={() => setActive(item.key)}
                    onPointerLeave={() => setActive(null)}
                    onFocus={() => setActive(item.key)}
                    onBlur={() => setActive(null)}
                    className={cn(
                      "focus-visible:ring-ring flex h-5 min-w-0 flex-1 items-center rounded-sm outline-none focus-visible:ring-2",
                      active && active !== item.key ? "opacity-60" : undefined,
                    )}
                  >
                    <span className="flex h-full gap-0.5" style={{ width: `${share * 100}%` }}>
                      {series.map((entry, index) => {
                        const magnitude = item.values[index]?.magnitude ?? 0;
                        // A zero value draws nothing, so no empty gap appears in the bar.
                        if (!(magnitude > 0)) return null;
                        return (
                          <span
                            key={entry.key}
                            data-series={entry.key}
                            className={cn("block h-full min-w-[2px] last:rounded-r-[4px]", entry.markClassName)}
                            style={{ flexGrow: magnitude, flexBasis: 0 }}
                          />
                        );
                      })}
                    </span>
                  </button>
                  <span className="text-foreground w-20 shrink-0 text-right font-medium tabular-nums" aria-hidden="true">
                    {item.total}
                  </span>
                  {active === item.key ? (
                    <div className="absolute top-6 left-0">
                      <Tooltip
                        item={{
                          key: item.key,
                          label: "",
                          value: `${item.fullLabel}: ${item.total}`,
                          magnitude: 0,
                          details: series.map(
                            (entry, index) => `${entry.label}: ${item.values[index]?.value ?? "—"}`,
                          ),
                        }}
                      />
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-muted-foreground py-6 text-center text-sm">{emptyMessage ?? "No data yet."}</p>
      )}
      {/* sr-only sits on a wrapper: a table sizes to its columns and ignores width: 1px,
          so on its own it would widen the page at 320px. */}
      <div className="sr-only">
        <table>
          <caption>{label}</caption>
          <thead>
            <tr>
              <th scope="col">{categoryLabel}</th>
              {series.map((entry) => (
                <th key={entry.key} scope="col">
                  {entry.label}
                </th>
              ))}
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr key={item.key}>
                <th scope="row">{item.fullLabel}</th>
                {series.map((entry, index) => (
                  <td key={entry.key}>{item.values[index]?.value ?? "—"}</td>
                ))}
                <td>{item.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Bar length from an API decimal string. Geometry only; never shown or summed. */
export function magnitudeOf(amount: string): number {
  const value = Number(amount);
  return Number.isFinite(value) ? value : 0;
}

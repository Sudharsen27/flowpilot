import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type MetricTrend = {
  value: string;
  direction: "up" | "down" | "neutral";
  label?: string;
};

type MetricCardProps = {
  label: string;
  value?: ReactNode;
  description?: string;
  icon?: ReactNode;
  trend?: MetricTrend;
  loading?: boolean;
  unavailableLabel?: string;
  headingLevel?: 2 | 3;
  className?: string;
};

const trendIcons = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  neutral: Minus,
} as const;

export function MetricCard({
  label,
  value,
  description,
  icon,
  trend,
  loading = false,
  unavailableLabel = "No data yet",
  headingLevel = 2,
  className,
}: MetricCardProps) {
  const hasValue = value !== undefined && value !== null && value !== "";
  const TrendIcon = trend ? trendIcons[trend.direction] : null;
  const Heading = headingLevel === 3 ? "h3" : "h2";

  return (
    <Card as="article" className={className} aria-busy={loading || undefined}>
      <CardContent className="flex min-h-36 flex-col justify-between">
        <div className="flex items-start justify-between gap-3">
          <Heading className="text-muted-foreground text-metric-label font-medium">
            {label}
          </Heading>
          {icon ? (
            <span
              className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md [&_svg]:size-4"
              aria-hidden="true"
            >
              {icon}
            </span>
          ) : null}
        </div>
        {loading ? (
          <div className="mt-6" role="status">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="mt-2 h-4 w-32" />
            <span className="sr-only">Loading {label}</span>
          </div>
        ) : (
          <div className="mt-6">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p
                className={cn(
                  "text-metric font-semibold tracking-tight tabular-nums",
                  !hasValue && "text-muted-foreground",
                )}
              >
                {hasValue ? value : "—"}
              </p>
              {hasValue && trend && TrendIcon ? (
                <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
                  <TrendIcon className="size-3.5" aria-hidden="true" />
                  <span>{trend.value}</span>
                  {trend.label ? <span>{trend.label}</span> : null}
                </span>
              ) : null}
            </div>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
              {hasValue ? description : unavailableLabel}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

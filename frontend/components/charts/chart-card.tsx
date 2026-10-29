import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type ChartCardProps = {
  title: string;
  description?: string;
  /** Headline figure shown under the title, e.g. the total the chart breaks down. */
  figure?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** Card frame for a single chart: title, optional headline figure, then the plot. */
export function ChartCard({ title, description, figure, action, children, className }: ChartCardProps) {
  const id = `chart-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <Card as="section" aria-labelledby={id} className={cn("grid content-start gap-4 p-4 sm:p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={id} className="text-sm font-medium">
            {title}
          </h2>
          {description ? <p className="text-muted-foreground mt-0.5 text-xs">{description}</p> : null}
          {figure ? <div className="mt-2">{figure}</div> : null}
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}

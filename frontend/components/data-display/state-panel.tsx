import { AlertCircle, CircleOff, Info } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type StatePanelProps = {
  title: string;
  description: string;
  kind?: "error" | "unavailable" | "information";
  action?: ReactNode;
  className?: string;
};

const icons = {
  error: AlertCircle,
  unavailable: CircleOff,
  information: Info,
} as const;

export function StatePanel({
  title,
  description,
  kind = "information",
  action,
  className,
}: StatePanelProps) {
  const Icon = icons[kind];

  return (
    <Card
      as="section"
      data-slot="state-panel"
      className={cn("flex max-w-2xl gap-4 p-5", className)}
      aria-live={kind === "error" ? "polite" : undefined}
    >
      <div
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md",
          kind === "error"
            ? "bg-destructive/10 text-danger-text"
            : kind === "unavailable"
              ? "bg-warning/15 text-warning-text"
              : "bg-info/10 text-info-text",
        )}
        aria-hidden="true"
      >
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <h2 className="text-sm font-medium">{title}</h2>
        <p className="text-muted-foreground mt-1 text-sm leading-6">
          {description}
        </p>
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
    </Card>
  );
}

import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
  headingLevel?: 2 | 3 | 4;
  className?: string;
};

export function EmptyState({
  title,
  description,
  icon,
  action,
  compact = false,
  headingLevel = 2,
  className,
}: EmptyStateProps) {
  const Heading = headingLevel === 4 ? "h4" : headingLevel === 3 ? "h3" : "h2";

  return (
    <Card
      as="section"
      data-slot="empty-state"
      className={cn(
        "flex w-full max-w-2xl flex-col items-start",
        compact ? "px-5 py-5" : "px-6 py-8 sm:px-8",
        className,
      )}
    >
      {icon ? (
        <div
          aria-hidden="true"
          className="bg-muted text-muted-foreground mb-4 flex size-9 items-center justify-center rounded-md [&_svg]:size-4"
        >
          {icon}
        </div>
      ) : null}
      <Heading className="text-foreground text-base font-medium tracking-tight">
        {title}
      </Heading>
      <p className="text-muted-foreground mt-1.5 max-w-xl text-sm leading-6">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </Card>
  );
}

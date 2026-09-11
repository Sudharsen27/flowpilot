import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type DetailRowProps = {
  label: string;
  value: ReactNode;
  muted?: boolean;
  icon?: ReactNode;
  className?: string;
};

export function DetailRow({
  label,
  value,
  muted = false,
  icon,
  className,
}: DetailRowProps) {
  return (
    <div
      data-slot="detail-row"
      className={cn(
        "grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-3",
        className,
      )}
    >
      <dt className="text-muted-foreground inline-flex items-center gap-1.5 text-xs font-medium">
        {icon ? (
          <span className="inline-flex size-3.5 shrink-0 items-center justify-center [&_svg]:size-3.5" aria-hidden="true">
            {icon}
          </span>
        ) : null}
        {label}
      </dt>
      <dd
        className={cn(
          "min-w-0 text-sm break-words",
          muted && "text-muted-foreground",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

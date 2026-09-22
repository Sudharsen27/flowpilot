import { formatAbsoluteTimestamp, formatRelativeTimestamp } from "@/lib/datetime";
import { cn } from "@/lib/utils";

type RelativeTimeProps = {
  value: string | null | undefined;
  className?: string;
  now?: Date;
};

export function RelativeTime({ value, className, now }: RelativeTimeProps) {
  const absolute = formatAbsoluteTimestamp(value);
  const relative = formatRelativeTimestamp(value, now);
  if (!relative || !absolute) return null;

  return (
    <time
      dateTime={value ?? undefined}
      title={absolute}
      aria-label={absolute}
      className={cn("text-muted-foreground text-xs tabular-nums", className)}
    >
      {relative}
    </time>
  );
}

import { cn } from "@/lib/utils";

type BrandLockupProps = {
  size?: "sm" | "md";
  className?: string;
};

export function BrandLockup({ size = "md", className }: BrandLockupProps) {
  const compact = size === "sm";

  return (
    <span className={cn("inline-flex max-w-full items-center", compact ? "gap-2.5" : "gap-3", className)}>
      <span
        className={cn(
          "bg-foreground text-background flex shrink-0 items-center justify-center leading-none font-semibold",
          compact ? "size-8 rounded-md text-sm" : "size-10 rounded-lg text-base",
        )}
      >
        F
      </span>
      <span className="min-w-0">
        <span
          className={cn(
            "text-foreground block font-semibold tracking-[-0.02em]",
            compact ? "text-sm leading-4" : "text-lg leading-5",
          )}
        >
          FlowPilot
        </span>
        <span
          className={cn(
            "text-foreground/60 block font-normal",
            compact ? "mt-0.5 text-xs leading-4" : "mt-0.5 text-sm leading-5",
          )}
        >
          AI sales workspace
        </span>
      </span>
    </span>
  );
}

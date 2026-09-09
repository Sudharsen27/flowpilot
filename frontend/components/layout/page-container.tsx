import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type PageContainerProps = ComponentProps<"div"> & {
  size?: "default" | "wide" | "full";
};

const sizes = {
  default: "max-w-6xl",
  wide: "max-w-7xl",
  full: "max-w-none",
} as const;

export function PageContainer({
  className,
  size = "default",
  ...props
}: PageContainerProps) {
  return (
    <div
      data-slot="page-container"
      className={cn(
        "mx-auto w-full px-4 sm:px-6 lg:px-8",
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}

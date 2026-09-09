import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type CardProps = ComponentProps<"div"> & {
  as?: "div" | "section" | "article";
  variant?: "default" | "subtle" | "information" | "status" | "interactive";
};

const variants = {
  default: "bg-card",
  subtle: "bg-surface-subtle",
  information: "bg-info/5 border-info/20",
  status: "bg-card border-l-2 border-l-primary",
  interactive:
    "bg-card transition-colors hover:border-foreground/20 focus-within:border-ring",
} as const;

export function Card({
  as: Component = "div",
  className,
  variant = "default",
  ...props
}: CardProps) {
  return (
    <Component
      data-slot="card"
      className={cn(
        "border-border text-card-foreground shadow-card rounded-lg border",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "flex flex-col gap-1.5 px-5 pt-5 sm:px-6 sm:pt-6",
        className,
      )}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: ComponentProps<"h2">) {
  return (
    <h2
      data-slot="card-title"
      className={cn("text-card-title font-medium tracking-tight", className)}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-muted-foreground text-sm leading-6", className)}
      {...props}
    />
  );
}

export function CardContent({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="card-content"
      className={cn("px-5 py-5 sm:px-6 sm:py-6", className)}
      {...props}
    />
  );
}

export function CardFooter({ className, ...props }: ComponentProps<"footer">) {
  return (
    <footer
      data-slot="card-footer"
      className={cn(
        "border-border flex flex-wrap items-center gap-2 border-t px-5 py-4 sm:px-6",
        className,
      )}
      {...props}
    />
  );
}

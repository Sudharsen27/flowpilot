"use client";

import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import type { ReactElement, ReactNode } from "react";

import { cn } from "@/lib/utils";

const TooltipProvider = TooltipPrimitive.Provider;

type TooltipProps = {
  /** The hint text. It supplements the trigger's accessible name and never replaces it. */
  content: ReactNode;
  /** A single focusable element, such as a `Button`. */
  children: ReactElement;
  side?: TooltipPrimitive.Positioner.Props["side"];
  className?: string;
};

function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger render={children} />
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner
          side={side}
          sideOffset={6}
          className="z-50"
        >
          <TooltipPrimitive.Popup
            data-slot="tooltip"
            className={cn(
              "bg-foreground text-background shadow-overlay max-w-64 rounded-md px-2 py-1 text-xs leading-5",
              "origin-[var(--transform-origin)] transition-[transform,opacity] duration-100 ease-out",
              "data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[instant]:transition-none data-[starting-style]:scale-95 data-[starting-style]:opacity-0",
              className,
            )}
          >
            {content}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export { Tooltip, TooltipProvider };

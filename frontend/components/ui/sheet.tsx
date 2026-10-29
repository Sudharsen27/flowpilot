"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Side drawer built on the same Base UI dialog as `Dialog`: focus is trapped while
 * open, Escape and the backdrop close it, and focus returns to the trigger.
 */
const Sheet = DialogPrimitive.Root;
const SheetClose = DialogPrimitive.Close;

function SheetContent({ className, children, ...props }: DialogPrimitive.Popup.Props) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Backdrop className="bg-foreground/25 fixed inset-0 z-50" />
      <DialogPrimitive.Popup
        data-slot="sheet-content"
        className={cn(
          "border-border bg-surface-elevated text-foreground shadow-overlay fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col border-l outline-none",
          "motion-safe:transition-transform motion-safe:duration-200 data-[ending-style]:translate-x-full data-[starting-style]:translate-x-full",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          aria-label="Close panel"
          className="text-muted-foreground hover:bg-muted hover:text-foreground absolute top-3 right-3 flex size-8 items-center justify-center rounded-md outline-none focus-visible:ring-2"
        >
          <X className="size-4" aria-hidden="true" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Popup>
    </DialogPrimitive.Portal>
  );
}

function SheetHeader({ className, ...props }: ComponentProps<"header">) {
  return (
    <header
      data-slot="sheet-header"
      className={cn("border-border flex flex-col gap-1.5 border-b p-5 pr-12", className)}
      {...props}
    />
  );
}

function SheetBody({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="sheet-body" className={cn("flex-1 overflow-y-auto p-5", className)} {...props} />;
}

function SheetTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-base font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

function SheetDescription({ className, ...props }: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-muted-foreground text-sm", className)}
      {...props}
    />
  );
}

export { Sheet, SheetBody, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle };

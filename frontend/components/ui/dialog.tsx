"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import type { ComponentProps } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogClose = DialogPrimitive.Close;

function DialogContent({
  className,
  children,
  ...props
}: DialogPrimitive.Popup.Props) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Backdrop className="bg-foreground/30 fixed inset-0 z-50" />
      <DialogPrimitive.Viewport className="fixed inset-0 z-50 grid overflow-y-auto p-4 sm:place-items-center">
        <DialogPrimitive.Popup
          data-slot="dialog-content"
          className={cn(
            "border-border bg-surface-elevated text-foreground shadow-overlay relative my-auto w-full max-w-lg rounded-lg border p-5 outline-none sm:p-6",
            className,
          )}
          {...props}
        >
          {children}
          <DialogPrimitive.Close
            aria-label="Close dialog"
            className="text-muted-foreground hover:bg-muted hover:text-foreground absolute top-3 right-3 flex size-8 items-center justify-center rounded-md outline-none focus-visible:ring-2"
          >
            <X className="size-4" aria-hidden="true" />
          </DialogPrimitive.Close>
        </DialogPrimitive.Popup>
      </DialogPrimitive.Viewport>
    </DialogPrimitive.Portal>
  );
}

function DialogHeader({ className, ...props }: ComponentProps<"header">) {
  return (
    <header
      data-slot="dialog-header"
      className={cn("flex flex-col gap-1.5 pr-8", className)}
      {...props}
    />
  );
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-lg font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

function DialogDescription({
  className,
  ...props
}: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-muted-foreground text-sm leading-6", className)}
      {...props}
    />
  );
}

function DialogFooter({ className, ...props }: ComponentProps<"footer">) {
  return (
    <footer
      data-slot="dialog-footer"
      className={cn(
        "mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className,
      )}
      {...props}
    />
  );
}

function DialogCancel({ children = "Cancel" }: { children?: React.ReactNode }) {
  return (
    <DialogPrimitive.Close render={<Button variant="outline" />}>
      {children}
    </DialogPrimitive.Close>
  );
}

export {
  Dialog,
  DialogCancel,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
};

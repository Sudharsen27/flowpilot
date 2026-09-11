"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
  cancelLabel?: string;
  variant?: "default" | "destructive";
  confirmPending?: boolean;
  confirmDisabled?: boolean;
  children?: ReactNode;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  onConfirm,
  cancelLabel = "Cancel",
  variant = "default",
  confirmPending = false,
  confirmDisabled = false,
  children,
}: ConfirmDialogProps) {
  const confirmLocked = confirmPending || confirmDisabled;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
        <DialogFooter>
          <DialogCancel>{cancelLabel}</DialogCancel>
          <Button
            type="button"
            variant={variant === "destructive" ? "destructive" : "default"}
            disabled={confirmLocked}
            aria-busy={confirmPending || undefined}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { Toast as ToastPrimitive } from "@base-ui/react/toast";
import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { useMemo, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";

type ToastOptions = {
  title: string;
  description?: ReactNode;
  /** Milliseconds before auto-dismiss. `0` keeps the toast until it is closed. */
  timeout?: number;
};

const TONE_ICON = {
  success: CircleCheck,
  error: CircleAlert,
  info: Info,
} as const;

const TONE_ICON_CLASS: Record<ToastTone, string> = {
  success: "text-success-text",
  error: "text-danger-text",
  info: "text-info-text",
};

function isTone(value: string | undefined): value is ToastTone {
  return value === "success" || value === "error" || value === "info";
}

function ToastList() {
  const { toasts } = ToastPrimitive.useToastManager();
  return toasts.map((toast) => {
    const tone = isTone(toast.type) ? toast.type : "info";
    const Icon = TONE_ICON[tone];
    return (
      <ToastPrimitive.Root
        key={toast.id}
        toast={toast}
        data-slot="toast"
        className={cn(
          "border-border bg-popover text-popover-foreground shadow-overlay pointer-events-auto w-full rounded-lg border",
          "transition-[transform,opacity] duration-200 ease-out",
          "data-[ending-style]:opacity-0 data-[limited]:hidden data-[starting-style]:translate-y-2 data-[starting-style]:opacity-0",
        )}
      >
        <ToastPrimitive.Content className="flex items-start gap-3 p-3">
          <Icon
            className={cn("mt-0.5 size-4 shrink-0", TONE_ICON_CLASS[tone])}
            aria-hidden="true"
          />
          <div className="min-w-0 flex-1">
            <ToastPrimitive.Title className="text-sm font-medium" />
            <ToastPrimitive.Description className="text-muted-foreground mt-0.5 text-sm" />
          </div>
          <ToastPrimitive.Close
            aria-label="Dismiss notification"
            className="text-muted-foreground hover:text-foreground hover:bg-accent -m-1 rounded-sm p-1"
          >
            <X className="size-4" aria-hidden="true" />
          </ToastPrimitive.Close>
        </ToastPrimitive.Content>
      </ToastPrimitive.Root>
    );
  });
}

/** Mount once near the root. Use `useToast()` anywhere below it. */
function ToastProvider({ children }: { children: ReactNode }) {
  return (
    <ToastPrimitive.Provider limit={3}>
      {children}
      <ToastPrimitive.Portal>
        <ToastPrimitive.Viewport className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-[calc(100vw-2rem)] flex-col gap-2 sm:w-96">
          <ToastList />
        </ToastPrimitive.Viewport>
      </ToastPrimitive.Portal>
    </ToastPrimitive.Provider>
  );
}

function useToast() {
  const manager = ToastPrimitive.useToastManager();
  return useMemo(() => {
    const show = (type: ToastTone) => (options: ToastOptions) =>
      manager.add({
        ...options,
        type,
        priority: type === "error" ? "high" : "low",
      });
    return {
      success: show("success"),
      error: show("error"),
      info: show("info"),
      dismiss: (id: string) => manager.close(id),
    };
  }, [manager]);
}

export { ToastProvider, useToast };
export type { ToastOptions, ToastTone };

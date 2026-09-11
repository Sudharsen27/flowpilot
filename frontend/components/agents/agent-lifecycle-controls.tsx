"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { AgentStatus } from "@/types/api";

type AgentLifecycleControlsProps = {
  status: AgentStatus;
  canManage: boolean;
  isPending: boolean;
  onReady: () => void;
  onActivate: () => void;
  onPause: () => void;
};

const confirmCopy: Record<
  "activate" | "pause",
  { title: string; description: string; confirm: string }
> = {
  activate: {
    title: "Activate this agent?",
    description:
      "The agent will become ACTIVE and can be executed. You can pause it later.",
    confirm: "Activate",
  },
  pause: {
    title: "Pause this agent?",
    description:
      "The agent will become PAUSED and cannot be executed until it is activated again.",
    confirm: "Pause",
  },
};

export function AgentLifecycleControls({
  status,
  canManage,
  isPending,
  onReady,
  onActivate,
  onPause,
}: AgentLifecycleControlsProps) {
  const [confirming, setConfirming] = useState<"activate" | "pause" | null>(
    null,
  );
  const actionDisabled = !canManage || isPending;
  const copy = confirming ? confirmCopy[confirming] : null;

  function runConfirmed() {
    if (!confirming || isPending) return;
    if (confirming === "activate") onActivate();
    if (confirming === "pause") onPause();
    setConfirming(null);
  }

  return (
    <div className="grid gap-3">
      {status === "DRAFT" ? (
        <Button
          type="button"
          disabled={actionDisabled}
          onClick={onReady}
          className="w-full"
        >
          {isPending ? "Updating…" : "Mark Ready"}
        </Button>
      ) : null}
      {status === "READY" ? (
        <Button
          type="button"
          disabled={actionDisabled}
          onClick={() => setConfirming("activate")}
          className="w-full"
        >
          {isPending ? "Updating…" : "Activate"}
        </Button>
      ) : null}
      {status === "ACTIVE" ? (
        <Button
          type="button"
          variant="outline"
          disabled={actionDisabled}
          onClick={() => setConfirming("pause")}
          className="w-full"
        >
          {isPending ? "Updating…" : "Pause"}
        </Button>
      ) : null}
      {status === "PAUSED" ? (
        <Button
          type="button"
          disabled={actionDisabled}
          onClick={() => setConfirming("activate")}
          className="w-full"
        >
          {isPending ? "Updating…" : "Resume"}
        </Button>
      ) : null}
      {status === "NEEDS_ATTENTION" ? (
        <p className="text-muted-foreground text-xs leading-5">
          This agent needs attention and cannot change status from this screen.
        </p>
      ) : null}
      {!canManage && status !== "NEEDS_ATTENTION" ? (
        <p className="text-muted-foreground text-xs leading-5">
          Your role has read-only access to lifecycle controls.
        </p>
      ) : null}

      <ConfirmDialog
        open={copy !== null}
        onOpenChange={(open) => {
          if (!open) setConfirming(null);
        }}
        title={copy?.title ?? "Confirm"}
        description={copy?.description ?? ""}
        confirmLabel={copy?.confirm ?? "Confirm"}
        confirmPending={isPending}
        onConfirm={runConfirmed}
      />
    </div>
  );
}

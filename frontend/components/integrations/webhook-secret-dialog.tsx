"use client";

import { Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type WebhookSecretDialogProps = {
  secret: string | null;
  endpointName: string;
  onClose: () => void;
};

export function WebhookSecretDialog({
  secret,
  endpointName,
  onClose,
}: WebhookSecretDialogProps) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  async function copy() {
    if (!secret) return;
    try {
      await navigator.clipboard.writeText(secret);
      setCopied(true);
      setCopyError(false);
    } catch {
      setCopyError(true);
    }
  }

  return (
    <Dialog
      open={secret !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Copy your signing secret</DialogTitle>
          <DialogDescription>
            Use this secret to check that requests to “{endpointName}” really
            come from FlowPilot. It is shown only once. If you lose it, replace
            it with a new one.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-6 grid gap-3">
          <label htmlFor="webhook-secret" className="text-sm font-medium">
            Signing secret
          </label>
          <div className="flex gap-2">
            <input
              id="webhook-secret"
              readOnly
              value={secret ?? ""}
              className="border-input bg-muted w-full rounded-md border px-3 py-2 font-mono text-xs"
              onFocus={(event) => event.currentTarget.select()}
            />
            <Button type="button" variant="outline" onClick={() => void copy()}>
              <Copy aria-hidden="true" />
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          {copyError ? (
            <p className="text-danger-text text-xs" role="alert">
              Copy failed. Select the text and copy it manually.
            </p>
          ) : null}
          <p className="text-muted-foreground text-xs leading-5">
            Each request has a <code>FlowPilot-Signature</code> header like{" "}
            <code>t=1700000000,v1=…</code>. Compute HMAC-SHA256 of{" "}
            <code>{"{t}.{raw body}"}</code> with this secret and compare it to{" "}
            <code>v1</code>. Reject requests whose <code>t</code> is more than
            five minutes old.
          </p>
        </div>
        <DialogFooter>
          <Button type="button" onClick={onClose}>
            I have saved it
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

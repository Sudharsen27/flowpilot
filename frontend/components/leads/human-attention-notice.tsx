"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { resolveHumanAttention } from "@/lib/api/leads";
import type { Lead } from "@/types/api";

type HumanAttentionNoticeProps = {
  lead: Lead;
  onResolved: (lead: Lead) => void;
  onStale: () => Promise<void> | void;
};

export function HumanAttentionNotice({
  lead,
  onResolved,
  onStale,
}: HumanAttentionNoticeProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [staleMessage, setStaleMessage] = useState<string | null>(null);
  const inFlight = useRef(false);

  if (lead.human_attention_required !== true) {
    return null;
  }

  async function resolve() {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    setStaleMessage(null);
    try {
      const updated = await resolveHumanAttention(lead.id);
      onResolved(updated);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setStaleMessage(
          "Human attention changed. The latest lead state has been loaded.",
        );
        try {
          await onStale();
        } catch {
          setError(
            "The latest lead state could not be loaded. Refresh the page.",
          );
        }
      } else {
        setError("Human attention could not be resolved. Try again.");
      }
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  return (
    <section
      className="border-info/40 bg-info/5 rounded-lg border p-4 sm:p-5"
      aria-labelledby="human-attention-notice-title"
    >
      <h2 id="human-attention-notice-title" className="text-sm font-medium">
        Human attention
      </h2>
      <p className="text-muted-foreground mt-2 text-sm leading-6">
        This lead needs a person to review it. Resolving attention only clears
        that flag. It does not approve a draft, send an email, change lead
        status, or restart a Sales Run.
      </p>
      {staleMessage ? (
        <p className="text-info-text mt-3 text-sm" role="status">
          {staleMessage}
        </p>
      ) : null}
      {error ? (
        <p className="text-danger-text mt-3 text-sm" role="alert">
          {error}
        </p>
      ) : null}
      <Button
        type="button"
        className="mt-4"
        disabled={pending}
        aria-busy={pending}
        onClick={() => {
          void resolve();
        }}
      >
        {pending ? "Resolving…" : "Resolve human attention"}
      </Button>
    </section>
  );
}

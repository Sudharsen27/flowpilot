"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const stages = [
  "Reading the instruction",
  "Planning the allowed steps",
  "Running those steps",
  "Stopping if a person must approve",
] as const;

export function AgentRunTrace() {
  const [active, setActive] = useState(0);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!media || media.matches) return;
    const timer = window.setInterval(() => {
      setActive((current) => (current + 1) % stages.length);
    }, 1400);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div
      className="border-ai-border bg-ai/5 rounded-xl border p-5"
      role="status"
      aria-live="polite"
    >
      <p className="text-sm font-medium">Running your instruction…</p>
      <ol className="mt-4 grid gap-2">
        {stages.map((stage, index) => {
          const current = index === active;
          return (
            <li
              key={stage}
              aria-current={current ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 text-sm",
                current ? "text-foreground font-medium" : "text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  current ? "bg-ai-text" : "bg-border-strong",
                )}
                aria-hidden="true"
              />
              {stage}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

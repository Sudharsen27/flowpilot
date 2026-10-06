"use client";

import { useEffect, useState } from "react";

import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import { getRuntimeConfiguration } from "@/lib/api/runtime";
import type { RuntimeCheckStatus, RuntimeConfiguration } from "@/types/api";

function statusPresentation(status: RuntimeCheckStatus, label: string): {
  status: StatusValue;
  label: string;
} {
  if (status === "configured") {
    return { status: "success", label };
  }
  return { status: "draft", label: "Not configured" };
}

export default function AiSettingsPage() {
  const [configuration, setConfiguration] = useState<RuntimeConfiguration | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getRuntimeConfiguration()
      .then((response) => {
        if (cancelled) return;
        setConfiguration(response);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setConfiguration(null);
        if (cause instanceof ApiError && cause.status === 401) {
          setError("Your session has expired. Sign in again to view AI configuration.");
          return;
        }
        setError("AI configuration is unavailable. The status service could not be reached.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestKey]);

  const aiStatus = configuration
    ? statusPresentation(
        configuration.ai_status,
        configuration.ai_status === "configured" ? "AI configured" : "Not configured",
      )
    : null;
  const decisionStatus = configuration
    ? statusPresentation(
        configuration.human_decision_status,
        configuration.human_decision_status === "configured"
          ? "Configured"
          : "Not configured",
      )
    : null;
  const emailStatus = configuration
    ? statusPresentation(
        configuration.email_status,
        configuration.email_status === "configured" ? "Configured" : "Not configured",
      )
    : null;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="AI & Automation"
        description="Read-only deployment status for AI, human decisions, and email. These values come from the environment and are not edited for each organization."
        breadcrumbs={[{ label: "Settings", href: "/settings" }, { label: "AI & Automation" }]}
      />

      <section className="grid max-w-3xl gap-4" aria-labelledby="runtime-configuration-title">
        <SectionHeader
          id="runtime-configuration-title"
          title="Runtime configuration"
          description="Credentials stay on the server. This page shows whether each integration is configured."
        />
        {loading ? (
          <Card as="section" aria-busy="true">
            <CardContent className="grid gap-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-3/4" />
              <span className="sr-only">Loading AI configuration</span>
            </CardContent>
          </Card>
        ) : error ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="AI unavailable"
            description={error}
            action={
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setLoading(true);
                  setError(null);
                  setRequestKey((value) => value + 1);
                }}
              >
                Retry
              </Button>
            }
          />
        ) : configuration ? (
          <Card as="section">
            <CardContent>
              <dl className="grid gap-4">
                <DetailRow label="AI provider" value={configuration.ai_provider_label} />
                <DetailRow
                  label="Model"
                  value={configuration.ai_model ?? "Not configured"}
                  muted={configuration.ai_model === null}
                />
                <DetailRow
                  label="AI status"
                  value={
                    aiStatus ? (
                      <StatusBadge status={aiStatus.status} label={aiStatus.label} />
                    ) : null
                  }
                />
                <DetailRow
                  label="Human decision provider"
                  value={
                    decisionStatus ? (
                      <StatusBadge status={decisionStatus.status} label={decisionStatus.label} />
                    ) : null
                  }
                />
                <DetailRow
                  label="Email provider"
                  value={
                    <span className="inline-flex flex-wrap items-center gap-2">
                      <span>{configuration.email_provider_label}</span>
                      {emailStatus ? (
                        <StatusBadge status={emailStatus.status} label={emailStatus.label} />
                      ) : null}
                    </span>
                  }
                />
                <DetailRow
                  label="Sender identity"
                  value={configuration.sender_address ?? "Not configured"}
                  muted={configuration.sender_address === null}
                />
              </dl>
              <p className="text-muted-foreground mt-5 text-xs leading-5">
                Updating a provider, model, or sender requires a deployment change. This screen
                cannot approve mail, start an agent, or store an API key.
              </p>
            </CardContent>
          </Card>
        ) : null}
      </section>
    </div>
  );
}

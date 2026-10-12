"use client";

import {
  ChevronDown,
  ChevronUp,
  KeyRound,
  Pencil,
  Send,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { Switch } from "@/components/forms/switch";
import { WebhookDeliveryLog } from "@/components/integrations/webhook-delivery-log";
import { webhookEventLabels } from "@/components/integrations/webhook-labels";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import type { WebhookEndpoint } from "@/types/api";

type WebhookEndpointListProps = {
  endpoints: readonly WebhookEndpoint[];
  canManage: boolean;
  busyEndpointId: string | null;
  testResults: Record<string, { ok: boolean; message: string } | undefined>;
  logRefresh: Record<string, number | undefined>;
  onToggle: (endpoint: WebhookEndpoint) => void;
  onEdit: (endpoint: WebhookEndpoint) => void;
  onTest: (endpoint: WebhookEndpoint) => void;
  onRotate: (endpoint: WebhookEndpoint) => void;
  onDelete: (endpoint: WebhookEndpoint) => void;
};

export function WebhookEndpointList({
  endpoints,
  canManage,
  busyEndpointId,
  testResults,
  logRefresh,
  onToggle,
  onEdit,
  onTest,
  onRotate,
  onDelete,
}: WebhookEndpointListProps) {
  const [openLog, setOpenLog] = useState<string | null>(null);

  return (
    <ul className="grid gap-3" aria-label="Webhooks">
      {endpoints.map((endpoint) => {
        const busy = busyEndpointId === endpoint.id;
        const logOpen = openLog === endpoint.id;
        const counts = endpoint.delivery_counts;
        const test = testResults[endpoint.id];
        return (
          <li key={endpoint.id}>
            <Card as="article" aria-labelledby={`webhook-${endpoint.id}-name`}>
              <CardContent className="grid gap-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid min-w-0 gap-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge
                        status={endpoint.enabled ? "active" : "paused"}
                        label={endpoint.enabled ? "On" : "Off"}
                      />
                      {counts.failed > 0 ? (
                        <StatusBadge
                          status="failed"
                          label={`${counts.failed} failed`}
                        />
                      ) : null}
                    </div>
                    <h3
                      id={`webhook-${endpoint.id}-name`}
                      className="text-base font-medium tracking-tight break-words"
                    >
                      {endpoint.name}
                    </h3>
                    <p className="text-muted-foreground font-mono text-xs break-all">
                      {endpoint.url}
                    </p>
                    <p className="text-muted-foreground text-sm">
                      Sends:{" "}
                      {endpoint.events
                        .map((event) => webhookEventLabels[event])
                        .join(", ")}
                    </p>
                  </div>
                  {canManage ? (
                    <div className="flex items-center gap-2">
                      <label
                        htmlFor={`webhook-${endpoint.id}-enabled`}
                        className="text-sm"
                      >
                        {endpoint.enabled ? "On" : "Off"}
                      </label>
                      <Switch
                        id={`webhook-${endpoint.id}-enabled`}
                        checked={endpoint.enabled}
                        disabled={busy}
                        onCheckedChange={() => onToggle(endpoint)}
                        aria-label={`${endpoint.enabled ? "Turn off" : "Turn on"} ${endpoint.name}`}
                      />
                    </div>
                  ) : null}
                </div>
                <p className="text-muted-foreground text-xs">
                  {counts.delivered} delivered · {counts.pending} waiting ·{" "}
                  {counts.failed} failed · secret ends in{" "}
                  <code>{endpoint.secret_hint}</code>
                  {endpoint.last_delivery_at ? (
                    <>
                      {" "}
                      · last event{" "}
                      <RelativeTime value={endpoint.last_delivery_at} />
                    </>
                  ) : null}
                </p>
                {test ? (
                  <p
                    className={
                      test.ok
                        ? "text-success-text text-sm"
                        : "text-danger-text text-sm"
                    }
                    role="status"
                  >
                    {test.message}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-expanded={logOpen}
                    aria-controls={`webhook-${endpoint.id}-log`}
                    onClick={() => setOpenLog(logOpen ? null : endpoint.id)}
                  >
                    {logOpen ? (
                      <ChevronUp aria-hidden="true" />
                    ) : (
                      <ChevronDown aria-hidden="true" />
                    )}
                    {logOpen ? "Hide deliveries" : "Show deliveries"}
                  </Button>
                  {canManage ? (
                    <>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => onTest(endpoint)}
                        aria-label={`Send test event to ${endpoint.name}`}
                      >
                        <Send aria-hidden="true" />
                        Send test event
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => onEdit(endpoint)}
                        aria-label={`Edit ${endpoint.name}`}
                      >
                        <Pencil aria-hidden="true" />
                        Edit
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => onRotate(endpoint)}
                        aria-label={`Replace signing secret for ${endpoint.name}`}
                      >
                        <KeyRound aria-hidden="true" />
                        Replace secret
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() => onDelete(endpoint)}
                        aria-label={`Delete ${endpoint.name}`}
                      >
                        <Trash2 aria-hidden="true" />
                        Delete
                      </Button>
                    </>
                  ) : null}
                </div>
                {logOpen ? (
                  <div id={`webhook-${endpoint.id}-log`}>
                    <WebhookDeliveryLog
                      endpointId={endpoint.id}
                      endpointName={endpoint.name}
                      canManage={canManage}
                      refreshKey={logRefresh[endpoint.id] ?? 0}
                    />
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}

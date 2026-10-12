"use client";

import { useEffect, useState } from "react";

import {
  webhookDeliveryStatusBadge,
  webhookDeliveryStatusLabels,
  webhookEventLabels,
} from "@/components/integrations/webhook-labels";
import { Button } from "@/components/ui/button";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  listWebhookDeliveries,
  retryWebhookDelivery,
} from "@/lib/api/webhooks";
import type { WebhookDelivery, WebhookDeliveryListResponse } from "@/types/api";

type WebhookDeliveryLogProps = {
  endpointId: string;
  endpointName: string;
  canManage: boolean;
  refreshKey: number;
};

function outcome(delivery: WebhookDelivery) {
  if (delivery.status === "DELIVERED") {
    return delivery.last_status_code
      ? `HTTP ${delivery.last_status_code}`
      : null;
  }
  return delivery.last_error;
}

export function WebhookDeliveryLog({
  endpointId,
  endpointName,
  canManage,
  refreshKey,
}: WebhookDeliveryLogProps) {
  const [data, setData] = useState<WebhookDeliveryListResponse | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listWebhookDeliveries(endpointId)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(false);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [endpointId, reloadKey, refreshKey]);

  async function retry(delivery: WebhookDelivery) {
    setRetrying(delivery.id);
    setRetryError(null);
    try {
      await retryWebhookDelivery(endpointId, delivery.id);
      setReloadKey((value) => value + 1);
    } catch {
      setRetryError(
        "The delivery could not be queued again. Please try again.",
      );
    } finally {
      setRetrying(null);
    }
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <p className="text-danger-text" role="alert">
          The delivery log could not be loaded.
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setReloadKey((value) => value + 1)}
        >
          Retry
        </Button>
      </div>
    );
  }
  if (!data) {
    return (
      <div role="status">
        <Skeleton className="h-16 w-full" />
        <span className="sr-only">Loading delivery log</span>
      </div>
    );
  }
  if (data.items.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        Nothing sent yet. Use “Send test event” to check the connection.
      </p>
    );
  }
  return (
    <div className="grid gap-2">
      {retryError ? (
        <p className="text-danger-text text-sm" role="alert">
          {retryError}
        </p>
      ) : null}
      <ul
        className="divide-border grid divide-y text-sm"
        aria-label={`Recent deliveries to ${endpointName}`}
      >
        {data.items.map((delivery) => {
          const detail = outcome(delivery);
          return (
            <li
              key={delivery.id}
              className="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <StatusBadge
                  status={webhookDeliveryStatusBadge[delivery.status]}
                  label={webhookDeliveryStatusLabels[delivery.status]}
                />
                <span className="font-medium">
                  {webhookEventLabels[delivery.event_type]}
                </span>
                {detail ? (
                  <span className="text-muted-foreground">{detail}</span>
                ) : null}
                {delivery.status === "PENDING" && delivery.attempts > 0 ? (
                  <span className="text-muted-foreground text-xs">
                    Attempt {delivery.attempts} of 5. Will retry automatically.
                  </span>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground text-xs">
                  <RelativeTime
                    value={delivery.last_attempt_at ?? delivery.created_at}
                  />
                </span>
                {canManage &&
                delivery.status === "FAILED" &&
                delivery.event_type !== "webhook.test" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={retrying === delivery.id}
                    onClick={() => void retry(delivery)}
                    aria-label={`Retry ${webhookEventLabels[delivery.event_type]} delivery`}
                  >
                    Retry
                  </Button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

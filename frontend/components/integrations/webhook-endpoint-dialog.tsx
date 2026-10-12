"use client";

import { type FormEvent, useState } from "react";

import { Checkbox } from "@/components/forms/checkbox";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import {
  SUBSCRIBABLE_WEBHOOK_EVENTS,
  webhookEventHints,
  webhookEventLabels,
} from "@/components/integrations/webhook-labels";
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
import { ApiError } from "@/lib/api/client";
import { createWebhook, updateWebhook } from "@/lib/api/webhooks";
import type { WebhookEndpoint, WebhookEventType } from "@/types/api";

type WebhookEndpointDialogProps = {
  open: boolean;
  endpoint?: WebhookEndpoint | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (result: {
    endpoint: WebhookEndpoint;
    secret: string | null;
  }) => void;
};

function errorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.status === 409) {
      return "Someone else changed this webhook. Close this dialog, reload, and try again.";
    }
    if (cause.status === 403)
      return "Only owners and admins can change webhooks.";
    const detail = (cause.body as { detail?: unknown } | null)?.detail;
    if (cause.status === 400 && typeof detail === "string") return detail;
    if (cause.status === 422) return "Check the name, URL, and events.";
  }
  return "The webhook could not be saved. Please try again.";
}

export function WebhookEndpointDialog({
  open,
  endpoint,
  onOpenChange,
  onSaved,
}: WebhookEndpointDialogProps) {
  const [name, setName] = useState(endpoint?.name ?? "");
  const [url, setUrl] = useState(endpoint?.url ?? "");
  const [events, setEvents] = useState<WebhookEventType[]>(
    endpoint?.events ?? ["lead.created"],
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const httpsUrl = /^https:\/\/\S+$/i.test(url.trim());
  const valid = name.trim().length > 0 && httpsUrl && events.length > 0;

  function toggleEvent(event: WebhookEventType, checked: boolean) {
    setEvents((current) =>
      checked
        ? SUBSCRIBABLE_WEBHOOK_EVENTS.filter(
            (item) => item === event || current.includes(item),
          )
        : current.filter((item) => item !== event),
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !valid) return;
    setPending(true);
    setError(null);
    const input = { name: name.trim(), url: url.trim(), events };
    try {
      if (endpoint) {
        const saved = await updateWebhook(endpoint.id, {
          ...input,
          expected_revision: endpoint.revision,
        });
        onSaved({ endpoint: saved, secret: null });
      } else {
        const created = await createWebhook(input);
        onSaved({ endpoint: created.endpoint, secret: created.secret });
      }
      onOpenChange(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{endpoint ? "Edit webhook" : "Add webhook"}</DialogTitle>
          <DialogDescription>
            FlowPilot sends a signed HTTPS POST to this URL when the selected
            events happen. Only public HTTPS addresses are allowed.
          </DialogDescription>
        </DialogHeader>
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <FormField label="Name" htmlFor="webhook-name" required>
            <Input
              id="webhook-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              placeholder="For example: CRM sync"
              autoFocus
              required
            />
          </FormField>
          <FormField
            label="Endpoint URL"
            htmlFor="webhook-url"
            description={
              url && !httpsUrl
                ? "The URL must start with https://"
                : "Must start with https://"
            }
            required
          >
            <Input
              id="webhook-url"
              type="url"
              inputMode="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              maxLength={500}
              placeholder="https://example.com/webhooks/flowpilot"
              required
            />
          </FormField>
          <fieldset className="grid gap-2">
            <legend className="mb-1 text-sm font-medium">Events to send</legend>
            {SUBSCRIBABLE_WEBHOOK_EVENTS.map((event) => {
              const id = `webhook-event-${event.replace(".", "-")}`;
              return (
                <div key={event} className="flex items-start gap-3">
                  <Checkbox
                    id={id}
                    checked={events.includes(event)}
                    onChange={(change) =>
                      toggleEvent(event, change.target.checked)
                    }
                    aria-describedby={`${id}-hint`}
                    className="mt-0.5"
                  />
                  <div className="grid gap-0.5">
                    <label htmlFor={id} className="text-sm">
                      {webhookEventLabels[event]}{" "}
                      <code className="text-muted-foreground text-xs">
                        {event}
                      </code>
                    </label>
                    <p
                      id={`${id}-hint`}
                      className="text-muted-foreground text-xs"
                    >
                      {webhookEventHints[event]}
                    </p>
                  </div>
                </div>
              );
            })}
            {events.length === 0 ? (
              <p className="text-danger-text text-xs">
                Choose at least one event.
              </p>
            ) : null}
          </fieldset>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !valid}>
              {pending ? "Saving…" : endpoint ? "Save changes" : "Add webhook"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { Plus, Webhook } from "lucide-react";
import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { EmptyState } from "@/components/empty-state";
import { IntegrationCatalog } from "@/components/integrations/integration-catalog";
import { WebhookEndpointDialog } from "@/components/integrations/webhook-endpoint-dialog";
import { WebhookEndpointList } from "@/components/integrations/webhook-endpoint-list";
import { WebhookSecretDialog } from "@/components/integrations/webhook-secret-dialog";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import {
  deleteWebhook,
  listWebhooks,
  rotateWebhookSecret,
  sendWebhookTest,
  updateWebhook,
} from "@/lib/api/webhooks";
import type { WebhookEndpoint } from "@/types/api";

type TestResult = { ok: boolean; message: string };

export default function IntegrationsPage() {
  const { session } = useAuth();
  const role = session?.membership.role;
  const canManage = role === "OWNER" || role === "ADMIN";

  const [endpoints, setEndpoints] = useState<WebhookEndpoint[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogKey, setDialogKey] = useState(0);
  const [editing, setEditing] = useState<WebhookEndpoint | null>(null);
  const [deleting, setDeleting] = useState<WebhookEndpoint | null>(null);
  const [rotating, setRotating] = useState<WebhookEndpoint | null>(null);
  const [secret, setSecret] = useState<{ value: string; name: string } | null>(
    null,
  );
  const [busyEndpointId, setBusyEndpointId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, TestResult | undefined>
  >({});
  const [logRefresh, setLogRefresh] = useState<
    Record<string, number | undefined>
  >({});

  useEffect(() => {
    let cancelled = false;
    void listWebhooks()
      .then((result) => {
        if (cancelled) return;
        setEndpoints(result);
        setError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setEndpoints(null);
        setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function openDialog(endpoint: WebhookEndpoint | null) {
    setEditing(endpoint);
    setDialogKey((value) => value + 1);
    setDialogOpen(true);
  }

  function replace(saved: WebhookEndpoint) {
    setEndpoints(
      (current) =>
        current?.map((item) => (item.id === saved.id ? saved : item)) ?? null,
    );
  }

  async function toggle(endpoint: WebhookEndpoint) {
    setBusyEndpointId(endpoint.id);
    setActionError(null);
    try {
      replace(
        await updateWebhook(endpoint.id, {
          expected_revision: endpoint.revision,
          enabled: !endpoint.enabled,
        }),
      );
    } catch {
      setActionError(
        `“${endpoint.name}” could not be updated. Reload and try again.`,
      );
    } finally {
      setBusyEndpointId(null);
    }
  }

  async function sendTest(endpoint: WebhookEndpoint) {
    setBusyEndpointId(endpoint.id);
    setActionError(null);
    try {
      const delivery = await sendWebhookTest(endpoint.id);
      const result: TestResult =
        delivery.status === "DELIVERED"
          ? {
              ok: true,
              message: `Test event delivered${delivery.last_status_code ? ` (HTTP ${delivery.last_status_code})` : ""}.`,
            }
          : {
              ok: false,
              message: `Test event failed: ${delivery.last_error ?? "no response"}.`,
            };
      setTestResults((current) => ({ ...current, [endpoint.id]: result }));
      setLogRefresh((current) => ({
        ...current,
        [endpoint.id]: (current[endpoint.id] ?? 0) + 1,
      }));
      reload();
    } catch {
      setTestResults((current) => ({
        ...current,
        [endpoint.id]: {
          ok: false,
          message: "The test event could not be sent. Please try again.",
        },
      }));
    } finally {
      setBusyEndpointId(null);
    }
  }

  async function confirmRotate() {
    if (!rotating) return;
    const endpoint = rotating;
    setBusyEndpointId(endpoint.id);
    setActionError(null);
    try {
      const result = await rotateWebhookSecret(endpoint.id, endpoint.revision);
      replace(result.endpoint);
      setSecret({ value: result.secret, name: result.endpoint.name });
    } catch {
      setActionError(
        `The secret for “${endpoint.name}” could not be replaced. Reload and try again.`,
      );
    } finally {
      setRotating(null);
      setBusyEndpointId(null);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    const endpoint = deleting;
    setBusyEndpointId(endpoint.id);
    setActionError(null);
    try {
      await deleteWebhook(endpoint.id);
      setDeleting(null);
      reload();
    } catch {
      setActionError(
        `“${endpoint.name}” could not be deleted. Please try again.`,
      );
      setDeleting(null);
    } finally {
      setBusyEndpointId(null);
    }
  }

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Integrations"
        description="Send FlowPilot events to your other tools with signed webhooks. Connect a CRM, a spreadsheet, or an automation tool such as Zapier or Make."
        primaryAction={
          canManage ? (
            <Button type="button" onClick={() => openDialog(null)}>
              <Plus aria-hidden="true" />
              Add webhook
            </Button>
          ) : (
            <span className="text-muted-foreground text-xs">
              Only owners and admins can add or change integrations.
            </span>
          )
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Webhooks"
          description="Each event is sent as a signed HTTPS POST. Failed deliveries are retried up to 5 times over about 3 hours. Events are queued right away and sent by the background worker, so delivery starts once your team has turned it on. “Send test event” is sent immediately."
        />

        {actionError ? (
          <p className="text-danger-text text-sm" role="alert">
            {actionError}
          </p>
        ) : null}

        {loading && !endpoints ? (
          <div className="grid gap-3" role="status">
            <Skeleton className="h-32 w-full" />
            <span className="sr-only">Loading webhooks</span>
          </div>
        ) : error ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Webhooks could not be loaded"
            description="Check your connection and try again."
            action={
              <Button type="button" onClick={reload}>
                Retry
              </Button>
            }
          />
        ) : endpoints && endpoints.length > 0 ? (
          <WebhookEndpointList
            endpoints={endpoints}
            canManage={canManage}
            busyEndpointId={busyEndpointId}
            testResults={testResults}
            logRefresh={logRefresh}
            onToggle={(endpoint) => void toggle(endpoint)}
            onEdit={(endpoint) => openDialog(endpoint)}
            onTest={(endpoint) => void sendTest(endpoint)}
            onRotate={setRotating}
            onDelete={setDeleting}
          />
        ) : (
          <EmptyState
            headingLevel={3}
            icon={<Webhook />}
            title="No webhooks yet"
            description="Add the HTTPS URL of the tool that should hear about new leads, AI analyses, approved replies, or sent emails."
            action={
              canManage ? (
                <Button type="button" onClick={() => openDialog(null)}>
                  <Plus aria-hidden="true" />
                  Add webhook
                </Button>
              ) : undefined
            }
          />
        )}
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Other tools"
          description="Direct connections to these tools need provider setup first. They are listed so you can see what is planned."
        />
        <IntegrationCatalog />
      </section>

      <WebhookEndpointDialog
        key={`webhook-dialog-${dialogKey}`}
        open={dialogOpen}
        endpoint={editing}
        onOpenChange={setDialogOpen}
        onSaved={({ endpoint, secret: created }) => {
          if (created) setSecret({ value: created, name: endpoint.name });
          reload();
        }}
      />
      <WebhookSecretDialog
        secret={secret?.value ?? null}
        endpointName={secret?.name ?? ""}
        onClose={() => setSecret(null)}
      />
      <ConfirmDialog
        open={rotating !== null}
        onOpenChange={(open) => {
          if (!open) setRotating(null);
        }}
        title="Replace the signing secret?"
        description={`Requests to “${rotating?.name ?? ""}” will be signed with a new secret right away. Update the receiving tool, or it will reject them.`}
        confirmLabel="Replace secret"
        confirmPending={rotating !== null && busyEndpointId === rotating.id}
        onConfirm={() => void confirmRotate()}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this webhook?"
        description={`“${deleting?.name ?? ""}” and its delivery log will be removed, and waiting events will not be sent. To pause it instead, turn it off.`}
        confirmLabel="Delete webhook"
        variant="destructive"
        confirmPending={deleting !== null && busyEndpointId === deleting.id}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}

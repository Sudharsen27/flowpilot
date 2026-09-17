"use client";

import { useEffect, useMemo, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { FormField } from "@/components/forms/form-field";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { Switch } from "@/components/forms/switch";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgents } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import {
  getWebsiteCaptureSettings,
  updateWebsiteCaptureSettings,
} from "@/lib/api/website-capture";
import type { Agent, MembershipRole, WebsiteCaptureSettings } from "@/types/api";

type WebsiteEnquirySettingsProps = {
  slug: string;
  role: MembershipRole;
};

function captureUrl(slug: string) {
  if (typeof window === "undefined") {
    return `/capture/${slug}`;
  }
  return `${window.location.origin}/capture/${slug}`;
}

function isEligibleSalesAgent(agent: Agent) {
  return (
    agent.agent_type === "SALES" &&
    (agent.status === "READY" || agent.status === "ACTIVE")
  );
}

function settingsPayload(
  captureEnabled: boolean,
  autoStartEnabled: boolean,
  agentId: string,
): WebsiteCaptureSettings {
  const autoStart = captureEnabled && autoStartEnabled;
  return {
    website_capture_enabled: captureEnabled,
    sales_agent_auto_start_enabled: autoStart,
    default_sales_agent_id: autoStart && agentId ? agentId : null,
  };
}

export function WebsiteEnquirySettings({ slug, role }: WebsiteEnquirySettingsProps) {
  const canManage = role === "OWNER" || role === "ADMIN";
  const [settings, setSettings] = useState<WebsiteCaptureSettings | null>(null);
  const [autoStart, setAutoStart] = useState(false);
  const [agentId, setAgentId] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [agentRetryKey, setAgentRetryKey] = useState(0);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const eligible = useMemo(
    () => agents.filter(isEligibleSalesAgent),
    [agents],
  );

  useEffect(() => {
    let cancelled = false;
    void getWebsiteCaptureSettings()
      .then((next) => {
        if (cancelled) return;
        setSettings(next);
        setAutoStart(next.sales_agent_auto_start_enabled);
        setAgentId(next.default_sales_agent_id ?? "");
        setLoadError(false);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey]);

  useEffect(() => {
    let cancelled = false;
    void getAgents({ agentType: "SALES" })
      .then((data) => {
        if (cancelled) return;
        setAgents(data);
        setAgentsError(false);
      })
      .catch(() => {
        if (!cancelled) {
          setAgentsError(true);
          setAgents([]);
        }
      })
      .finally(() => {
        if (!cancelled) setAgentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentRetryKey]);

  const enabled = settings?.website_capture_enabled ?? false;
  const saved = settings;
  const autoStartChecked = enabled && autoStart;
  const selectedAgentEligible = eligible.some((agent) => agent.id === agentId);
  const dirty =
    saved !== null &&
    (autoStartChecked !== saved.sales_agent_auto_start_enabled ||
      (autoStartChecked ? agentId : "") !== (saved.default_sales_agent_id ?? "") ||
      (autoStartChecked &&
        !agentsLoading &&
        !agentsError &&
        eligible.length > 0 &&
        Boolean(agentId) &&
        !selectedAgentEligible));

  async function persist(next: WebsiteCaptureSettings) {
    setPending(true);
    setActionError(null);
    try {
      const result = await updateWebsiteCaptureSettings(next);
      setSettings(result);
      setAutoStart(result.sales_agent_auto_start_enabled);
      setAgentId(result.default_sales_agent_id ?? "");
      setConfirmOpen(false);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 403) {
        setActionError("Only owners and admins can change this.");
      } else if (cause instanceof ApiError && cause.status === 422) {
        setActionError(
          "Website capture settings could not be saved. Check capture, automatic start, and the Sales Agent.",
        );
      } else {
        setActionError("Website capture could not be updated. Please try again.");
      }
    } finally {
      setPending(false);
    }
  }

  async function setCapture(next: boolean) {
    if (next) {
      await persist(settingsPayload(true, false, ""));
      return;
    }
    await persist(settingsPayload(false, false, ""));
  }

  function onAutoStartChange(next: boolean) {
    if (!enabled || !canManage || pending) return;
    setActionError(null);
    if (next) {
      if (agentsError) {
        setActionError("Sales Agents could not be loaded. Try again.");
        return;
      }
      if (agentsLoading) {
        setActionError("Sales Agents are still loading. Try again in a moment.");
        return;
      }
      if (eligible.length === 0) {
        setActionError(
          "Create a READY or ACTIVE Sales Agent before enabling automatic start.",
        );
        return;
      }
      setAutoStart(true);
      return;
    }
    setAutoStart(false);
    setAgentId("");
    if (saved?.sales_agent_auto_start_enabled) {
      void persist(settingsPayload(true, false, ""));
    }
  }

  async function saveAutoStart() {
    if (!enabled || !autoStart) return;
    if (!agentId) {
      setActionError("Select a default Sales Agent before saving.");
      return;
    }
    if (!eligible.some((agent) => agent.id === agentId)) {
      setActionError("Select a READY or ACTIVE Sales Agent.");
      return;
    }
    await persist(settingsPayload(true, true, agentId));
  }

  async function copyUrl() {
    const url = captureUrl(slug);
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      setActionError("The URL could not be copied.");
      return;
    }
    setCopied(true);
  }

  const url = captureUrl(slug);
  const selectedAgent = eligible.find((agent) => agent.id === agentId);
  const showSelector = enabled && autoStartChecked;

  return (
    <>
      {loadError ? (
        <StatePanel
          kind="error"
          title="Website enquiries could not be loaded"
          description="Try again to retrieve website capture settings."
          action={
            <Button
              type="button"
              onClick={() => {
                setLoadError(false);
                setSettings(null);
                setRetryKey((value) => value + 1);
              }}
            >
              Try again
            </Button>
          }
        />
      ) : settings === null ? (
        <div role="status">
          <Skeleton className="h-56 max-w-2xl" />
          <span className="sr-only">Loading website enquiry settings</span>
        </div>
      ) : (
        <Card className="max-w-2xl" as="section">
          <CardHeader>
            <CardDescription>
              {autoStartChecked
                ? "Website visitors can submit an enquiry. New enquiries start the configured Sales Agent for qualification and a draft. Email is not sent until a person approves a response."
                : "Website visitors can submit an enquiry. The Sales Agent is not started automatically, and email is not sent until a person approves a response."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium">Website Capture Enabled</span>
              <StatusBadge
                status={enabled ? "active" : "draft"}
                label={enabled ? "On" : "Off"}
              />
            </div>
            {enabled ? (
              <p className="text-sm">
                Enquiry form URL:{" "}
                <span className="font-mono break-all">{url}</span>
              </p>
            ) : (
              <p className="text-muted-foreground text-sm">
                Website capture is off. Enquiries cannot be submitted.
              </p>
            )}
            <div className="flex items-start justify-between gap-4">
              <div>
                <Label htmlFor="sales-agent-auto-start">
                  Start Sales Agent automatically
                </Label>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  Automatically start the configured Sales Agent when a new
                  website enquiry is received.
                </p>
              </div>
              <Switch
                id="sales-agent-auto-start"
                checked={autoStartChecked}
                disabled={!canManage || !enabled || pending || agentsLoading}
                onCheckedChange={onAutoStartChange}
              />
            </div>
            {showSelector ? (
              agentsError ? (
                <StatePanel
                  kind="error"
                  title="Sales Agents could not be loaded"
                  description="Automatic start needs a READY or ACTIVE Sales Agent from this organization."
                  action={
                    canManage ? (
                      <Button
                        type="button"
                        onClick={() => {
                          setAgentsLoading(true);
                          setAgentsError(false);
                          setAgentRetryKey((value) => value + 1);
                        }}
                      >
                        Try again
                      </Button>
                    ) : undefined
                  }
                />
              ) : agentsLoading ? (
                <div role="status">
                  <Skeleton className="h-16" />
                  <span className="sr-only">Loading Sales Agents</span>
                </div>
              ) : eligible.length === 0 ? (
                <p className="text-danger-text text-sm" role="alert">
                  No READY or ACTIVE Sales Agent is available. Create one before
                  enabling automatic start.
                </p>
              ) : (
                <FormField
                  label="Default Sales Agent"
                  htmlFor="default-sales-agent"
                  required={canManage}
                  description="This agent will qualify the enquiry and prepare a response for review. Email is not sent until a person approves."
                  error={
                    canManage && dirty && !agentId
                      ? "Select a default Sales Agent."
                      : undefined
                  }
                >
                  {canManage ? (
                    <Select
                      id="default-sales-agent"
                      value={agentId}
                      disabled={pending}
                      aria-invalid={dirty && !agentId ? true : undefined}
                      onChange={(event) => {
                        setAgentId(event.target.value);
                        setActionError(null);
                      }}
                    >
                      <option value="">Select a Sales Agent</option>
                      {eligible.map((agent) => (
                        <option key={agent.id} value={agent.id}>
                          {agent.name}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <p id="default-sales-agent" className="text-sm">
                      {selectedAgent?.name ?? "No Sales Agent selected"}
                    </p>
                  )}
                </FormField>
              )
            ) : null}
            {!canManage ? (
              <p className="text-muted-foreground text-sm">
                Only owners and admins can change this.
              </p>
            ) : null}
            {actionError ? (
              <p className="text-danger-text text-sm" role="alert">
                {actionError}
              </p>
            ) : null}
          </CardContent>
          <CardFooter className="flex flex-wrap gap-2">
            {canManage && !enabled ? (
              <Button
                type="button"
                disabled={pending}
                onClick={() => void setCapture(true)}
              >
                {pending ? "Saving…" : "Enable website enquiries"}
              </Button>
            ) : null}
            {canManage && enabled ? (
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => setConfirmOpen(true)}
              >
                Disable website enquiries
              </Button>
            ) : null}
            {canManage && enabled && dirty && autoStartChecked ? (
              <Button
                type="button"
                disabled={pending || !agentId}
                onClick={() => void saveAutoStart()}
              >
                {pending ? "Saving…" : "Save Sales Agent settings"}
              </Button>
            ) : null}
            {enabled ? (
              <Button type="button" variant="outline" onClick={() => void copyUrl()}>
                {copied ? "Copied" : "Copy URL"}
              </Button>
            ) : null}
          </CardFooter>
        </Card>
      )}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Disable website enquiries?"
        description="The hosted form will stop accepting submissions. Automatic Sales Agent start will also stop. Existing leads are not changed."
        confirmLabel="Disable"
        variant="destructive"
        confirmPending={pending}
        onConfirm={() => {
          void setCapture(false);
        }}
      />
    </>
  );
}

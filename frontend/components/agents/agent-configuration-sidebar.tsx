import { FlaskConical, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { AgentLifecycleControls } from "@/components/agents/agent-lifecycle-controls";
import {
  AgentStatusBadge,
  type AgentStatus,
} from "@/components/agents/agent-status-badge";
import type { AgentStatus as ApiAgentStatus } from "@/types/api";

const activationLabel: Record<ApiAgentStatus, string> = {
  DRAFT: "Draft",
  READY: "Ready to activate",
  ACTIVE: "Active",
  PAUSED: "Paused",
  NEEDS_ATTENTION: "Needs attention",
};

export function AgentConfigurationSidebar({
  status,
  apiStatus,
  canEdit,
  isDirty,
  isSaving,
  isLifecyclePending,
  onSave,
  onReady,
  onActivate,
  onPause,
}: {
  status: AgentStatus;
  apiStatus: ApiAgentStatus;
  canEdit: boolean;
  isDirty: boolean;
  isSaving: boolean;
  isLifecyclePending: boolean;
  onSave: () => void;
  onReady: () => void;
  onActivate: () => void;
  onPause: () => void;
}) {
  return (
    <aside
      className="grid gap-4 xl:sticky xl:top-24"
      aria-label="Configuration status"
    >
      <Card as="section" aria-labelledby="configuration-status-title">
        <CardHeader>
          <CardTitle id="configuration-status-title">
            Configuration status
          </CardTitle>
          <CardDescription>
            {canEdit
              ? "Configuration changes are saved to the Agent API."
              : "Your role has read-only access to this configuration."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5">
          <AgentStatusBadge status={status} />
          <dl className="divide-border divide-y text-sm">
            <div className="flex justify-between gap-3 py-3 first:pt-0">
              <dt className="text-muted-foreground">Agent record</dt>
              <dd className="font-medium">Loaded</dd>
            </div>
            <div className="flex justify-between gap-3 py-3">
              <dt className="text-muted-foreground">Unsaved changes</dt>
              <dd className="font-medium">{isDirty ? "Yes" : "None"}</dd>
            </div>
            <div className="flex justify-between gap-3 py-3">
              <dt className="text-muted-foreground">Save state</dt>
              <dd className="font-medium">
                {canEdit ? (isSaving ? "Saving…" : "Ready") : "Read-only"}
              </dd>
            </div>
            <div className="flex justify-between gap-3 py-3 last:pb-0">
              <dt className="text-muted-foreground">Activation</dt>
              <dd className="font-medium">{activationLabel[apiStatus]}</dd>
            </div>
          </dl>
          <AgentLifecycleControls
            status={apiStatus}
            canManage={canEdit}
            isPending={isLifecyclePending || isSaving}
            onReady={onReady}
            onActivate={onActivate}
            onPause={onPause}
          />
          <Button
            type="button"
            disabled={!canEdit || !isDirty || isSaving || isLifecyclePending}
            onClick={onSave}
            className="w-full"
          >
            <Save aria-hidden="true" />
            {isSaving ? "Saving…" : "Save configuration"}
          </Button>
        </CardContent>
      </Card>

      <Card as="section" variant="subtle" aria-labelledby="test-agent-title">
        <CardHeader>
          <div
            className="bg-card text-muted-foreground border-border mb-2 flex size-8 items-center justify-center rounded-md border"
            aria-hidden="true"
          >
            <FlaskConical className="size-4" />
          </div>
          <CardTitle id="test-agent-title">Manual run</CardTitle>
          <CardDescription>
            Use Run agent to send a real request to the connected AI provider.
            Results stay on this page session only.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusBadge
            status={
              apiStatus === "READY" || apiStatus === "ACTIVE"
                ? "active"
                : "draft"
            }
            label={
              apiStatus === "READY" || apiStatus === "ACTIVE"
                ? "Eligible to run"
                : "Not executable"
            }
          />
        </CardContent>
      </Card>
    </aside>
  );
}

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
import {
  AgentStatusBadge,
  type AgentStatus,
} from "@/components/agents/agent-status-badge";

export function AgentConfigurationSidebar({
  status,
  canEdit,
  isDirty,
  isSaving,
  onSave,
}: {
  status: AgentStatus;
  canEdit: boolean;
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
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
              <dd className="font-medium">Not connected</dd>
            </div>
          </dl>
          <Button
            type="button"
            disabled={!canEdit || !isDirty || isSaving}
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
          <CardTitle id="test-agent-title">Test agent</CardTitle>
          <CardDescription>
            Preview and test behavior after an agent runtime is connected.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusBadge status="draft" label="Runtime unavailable" />
          <Button type="button" variant="outline" disabled className="w-full">
            Open test preview
          </Button>
        </CardContent>
      </Card>
    </aside>
  );
}

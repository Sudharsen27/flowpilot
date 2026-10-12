"use client";

import { Plus, Workflow } from "lucide-react";
import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkflowRuleDialog } from "@/components/workflows/workflow-rule-dialog";
import { WorkflowRuleList } from "@/components/workflows/workflow-rule-list";
import { useAuth } from "@/hooks/use-auth";
import {
  deleteWorkflow,
  listWorkflows,
  updateWorkflow,
} from "@/lib/api/workflows";
import type { WorkflowRule } from "@/types/api";

export default function WorkflowsPage() {
  const { session } = useAuth();
  const role = session?.membership.role;
  const canManage = role === "OWNER" || role === "ADMIN";

  const [rules, setRules] = useState<WorkflowRule[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogKey, setDialogKey] = useState(0);
  const [editing, setEditing] = useState<WorkflowRule | null>(null);
  const [deleting, setDeleting] = useState<WorkflowRule | null>(null);
  const [busyRuleId, setBusyRuleId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listWorkflows()
      .then((result) => {
        if (cancelled) return;
        setRules(result);
        setError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setRules(null);
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

  function openDialog(rule: WorkflowRule | null) {
    setEditing(rule);
    setDialogKey((value) => value + 1);
    setDialogOpen(true);
  }

  async function toggle(rule: WorkflowRule) {
    setBusyRuleId(rule.id);
    setActionError(null);
    try {
      const saved = await updateWorkflow(rule.id, {
        expected_revision: rule.revision,
        enabled: !rule.enabled,
      });
      setRules(
        (current) =>
          current?.map((item) => (item.id === saved.id ? saved : item)) ?? null,
      );
    } catch {
      setActionError(
        `“${rule.name}” could not be turned ${rule.enabled ? "off" : "on"}. Reload and try again.`,
      );
    } finally {
      setBusyRuleId(null);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    const rule = deleting;
    setBusyRuleId(rule.id);
    setActionError(null);
    try {
      await deleteWorkflow(rule.id);
      setDeleting(null);
      reload();
    } catch {
      setActionError(`“${rule.name}” could not be deleted. Please try again.`);
      setDeleting(null);
    } finally {
      setBusyRuleId(null);
    }
  }

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Workflows"
        description="Simple “when this happens, do that” rules that save your team routine work. Every AI reply still waits for a person to approve it."
        primaryAction={
          canManage ? (
            <Button type="button" onClick={() => openDialog(null)}>
              <Plus aria-hidden="true" />
              New workflow
            </Button>
          ) : (
            <span className="text-muted-foreground text-xs">
              Only owners and admins can create or change workflows.
            </span>
          )
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="How workflows run"
          description="When a trigger happens, each workflow that is on queues one run for that lead. The background worker carries out queued runs, so they wait until your team has started it. Workflows never send email. Drafts go to Approvals, and leads flagged for human attention only get a reminder."
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Your workflows"
          description={
            rules
              ? `${rules.length} ${rules.length === 1 ? "workflow" : "workflows"}, ${rules.filter((rule) => rule.enabled).length} on.`
              : "Turn workflows on or off, edit them, and see what they did."
          }
        />

        {actionError ? (
          <p className="text-danger-text text-sm" role="alert">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <div className="grid gap-3" role="status">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            <span className="sr-only">Loading workflows</span>
          </div>
        ) : error ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Workflows could not be loaded"
            description="Check your connection and try again."
            action={
              <Button type="button" onClick={reload}>
                Retry
              </Button>
            }
          />
        ) : rules && rules.length > 0 ? (
          <WorkflowRuleList
            rules={rules}
            canManage={canManage}
            busyRuleId={busyRuleId}
            onToggle={(rule) => void toggle(rule)}
            onEdit={(rule) => openDialog(rule)}
            onDelete={setDeleting}
          />
        ) : (
          <EmptyState
            headingLevel={3}
            icon={<Workflow />}
            title="Create your first workflow"
            description="For example: when a new website lead arrives, analyze it with AI. Or when a customer replies, schedule a follow-up reminder."
            action={
              canManage ? (
                <Button type="button" onClick={() => openDialog(null)}>
                  <Plus aria-hidden="true" />
                  New workflow
                </Button>
              ) : undefined
            }
          />
        )}
      </section>

      <WorkflowRuleDialog
        key={`workflow-dialog-${dialogKey}`}
        open={dialogOpen}
        rule={editing}
        onOpenChange={setDialogOpen}
        onSaved={() => reload()}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this workflow?"
        description={`“${deleting?.name ?? ""}” and its run history will be removed. Work it already did, such as analyses, drafts, and reminders, stays on the leads. To pause it instead, turn it off.`}
        confirmLabel="Delete workflow"
        variant="destructive"
        confirmPending={deleting !== null && busyRuleId === deleting.id}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}

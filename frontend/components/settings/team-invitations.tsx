"use client";

import { FormEvent, useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Button } from "@/components/ui/button";
import { apiErrorDetail } from "@/lib/api/error-detail";
import {
  createInvitation,
  listInvitationHistory,
  listInvitations,
  resendInvitation,
  revokeInvitation,
} from "@/lib/api/invitations";
import type {
  InvitationHistoryPublic,
  InvitationPublic,
  InvitationRole,
  MembershipRole,
} from "@/types/api";

const SENT_MESSAGE =
  "If this address can join the organization and the email can be delivered, the invitation appears in the pending list.";

function canManageInvitation(actor: MembershipRole, invitationRole: string) {
  if (actor === "OWNER") {
    return true;
  }
  return actor === "ADMIN" && invitationRole === "MEMBER";
}

const roleLabels: Record<string, string> = {
  ADMIN: "Admin",
  MEMBER: "Member",
};

const historyStatusLabels: Record<InvitationHistoryPublic["status"], string> = {
  accepted: "Accepted",
  revoked: "Revoked",
};

function formatWhen(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function TeamInvitations({ role }: { role: MembershipRole }) {
  const canInvite = role === "OWNER" || role === "ADMIN";
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<InvitationRole>("MEMBER");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [invitations, setInvitations] = useState<InvitationPublic[] | null>(null);
  const [history, setHistory] = useState<InvitationHistoryPublic[] | null>(null);
  const [listError, setListError] = useState(false);
  const [requestVersion, setRequestVersion] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    if (!canInvite) {
      return;
    }
    let cancelled = false;
    void Promise.all([listInvitations(), listInvitationHistory()])
      .then(([rows, historyRows]) => {
        if (!cancelled) {
          setInvitations(rows);
          setHistory(historyRows);
          setListError(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setListError(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [canInvite, requestVersion]);

  if (!canInvite) {
    return (
      <p className="text-muted-foreground text-sm">
        Only owners and admins can invite people to this organization.
      </p>
    );
  }

  function refreshLists() {
    setInvitations(null);
    setHistory(null);
    setListError(false);
    setRequestVersion((version) => version + 1);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const address = email.trim();
    if (!address || pending) {
      return;
    }
    setPending(true);
    setNotice(null);
    setFormError(null);
    const roleToStore: InvitationRole = role === "OWNER" ? inviteRole : "MEMBER";
    try {
      const response = await createInvitation(address, roleToStore);
      if (response.status !== "accepted") {
        setFormError("The invitation could not be sent. Try again.");
        return;
      }
      setEmail("");
      setInviteRole("MEMBER");
      setNotice(SENT_MESSAGE);
      refreshLists();
    } catch (cause) {
      setFormError(apiErrorDetail(cause, "The invitation could not be sent. Try again."));
    } finally {
      setPending(false);
    }
  }

  async function revoke(invitationId: string) {
    setBusyId(invitationId);
    setFormError(null);
    setNotice(null);
    try {
      await revokeInvitation(invitationId);
      setInvitations((current) => current?.filter((item) => item.id !== invitationId) ?? current);
      const historyRows = await listInvitationHistory();
      setHistory(historyRows);
    } catch (cause) {
      setFormError(apiErrorDetail(cause, "The invitation could not be revoked."));
    } finally {
      setBusyId(null);
    }
  }

  async function resend(invitationId: string) {
    setBusyId(invitationId);
    setFormError(null);
    setNotice(null);
    try {
      const updated = await resendInvitation(invitationId);
      setInvitations(
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)) ?? current,
      );
      setNotice("Invitation email resent.");
    } catch (cause) {
      setFormError(apiErrorDetail(cause, "The invitation could not be resent."));
      refreshLists();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="grid gap-5">
      <form className="grid max-w-xl gap-4" onSubmit={(event) => void handleSubmit(event)}>
        <FormField label="Email" htmlFor="invite-email" required>
          <Input
            id="invite-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </FormField>
        {role === "OWNER" ? (
          <FormField label="Role" htmlFor="invite-role" required>
            <Select
              id="invite-role"
              value={inviteRole}
              onChange={(event) => setInviteRole(event.target.value as InvitationRole)}
            >
              <option value="MEMBER">Member</option>
              <option value="ADMIN">Admin</option>
            </Select>
          </FormField>
        ) : (
          <p className="text-muted-foreground text-sm">
            Admins can invite members. The invitation role is member.
          </p>
        )}
        {formError ? (
          <p className="text-danger-text text-sm" role="alert">
            {formError}
          </p>
        ) : null}
        {notice ? (
          <p className="text-sm" role="status">
            {notice}
          </p>
        ) : null}
        <Button type="submit" className="w-fit" disabled={pending}>
          {pending ? "Sending…" : "Send invitation"}
        </Button>
      </form>
      {listError ? (
        <StatePanel
          kind="error"
          title="Invitations could not be loaded"
          description="Try again to retrieve pending invitations."
          action={<Button onClick={refreshLists}>Try again</Button>}
        />
      ) : invitations === null ? (
        <p className="text-muted-foreground text-sm" role="status">
          Loading invitations
        </p>
      ) : invitations.length === 0 ? (
        <p className="text-muted-foreground text-sm">No pending invitations.</p>
      ) : (
        <ul className="divide-border border-border divide-y rounded-lg border">
          {invitations.map((invitation) => (
            <li
              key={invitation.id}
              className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{invitation.email}</p>
                <p className="text-muted-foreground text-xs">
                  {roleLabels[invitation.role] ?? invitation.role} · Expires{" "}
                  {formatWhen(invitation.expires_at)}
                </p>
              </div>
              {canManageInvitation(role, invitation.role) ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busyId === invitation.id}
                    onClick={() => void resend(invitation.id)}
                  >
                    {busyId === invitation.id ? "Working…" : "Resend"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busyId === invitation.id}
                    onClick={() => void revoke(invitation.id)}
                  >
                    {busyId === invitation.id ? "Working…" : "Revoke"}
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-2">
        <h4 className="text-sm font-medium">Recent invitations</h4>
        {history === null && !listError ? (
          <p className="text-muted-foreground text-sm" role="status">
            Loading history
          </p>
        ) : history && history.length > 0 ? (
          <ul className="divide-border border-border divide-y rounded-lg border">
            {history.map((item) => (
              <li
                key={item.id}
                className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.email}</p>
                  <p className="text-muted-foreground text-xs">
                    {roleLabels[item.role] ?? item.role} ·{" "}
                    {historyStatusLabels[item.status]} · {formatWhen(item.resolved_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted-foreground text-sm">No recent accepted or revoked invitations.</p>
        )}
      </div>
    </div>
  );
}

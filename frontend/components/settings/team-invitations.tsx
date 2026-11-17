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
  listInvitations,
  revokeInvitation,
} from "@/lib/api/invitations";
import type { InvitationPublic, InvitationRole, MembershipRole } from "@/types/api";

const SENT_MESSAGE =
  "If this address can join the organization and the email can be delivered, the invitation appears in the pending list.";

function canRevokeInvitation(actor: MembershipRole, invitationRole: string) {
  if (actor === "OWNER") {
    return true;
  }
  return actor === "ADMIN" && invitationRole === "MEMBER";
}

const roleLabels: Record<string, string> = {
  ADMIN: "Admin",
  MEMBER: "Member",
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
  const [listError, setListError] = useState(false);
  const [requestVersion, setRequestVersion] = useState(0);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  useEffect(() => {
    if (!canInvite) {
      return;
    }
    let cancelled = false;
    void listInvitations()
      .then((rows) => {
        if (!cancelled) {
          setInvitations(rows);
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
      setInvitations(null);
      setListError(false);
      setRequestVersion((version) => version + 1);
    } catch (cause) {
      setFormError(apiErrorDetail(cause, "The invitation could not be sent. Try again."));
    } finally {
      setPending(false);
    }
  }

  async function revoke(invitationId: string) {
    setRevokingId(invitationId);
    setFormError(null);
    try {
      await revokeInvitation(invitationId);
      setInvitations((current) => current?.filter((item) => item.id !== invitationId) ?? current);
    } catch (cause) {
      setFormError(apiErrorDetail(cause, "The invitation could not be revoked."));
    } finally {
      setRevokingId(null);
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
          action={
            <Button
              onClick={() => {
                setInvitations(null);
                setListError(false);
                setRequestVersion((version) => version + 1);
              }}
            >
              Try again
            </Button>
          }
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
              {canRevokeInvitation(role, invitation.role) ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={revokingId === invitation.id}
                  onClick={() => void revoke(invitation.id)}
                >
                  {revokingId === invitation.id ? "Revoking…" : "Revoke"}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

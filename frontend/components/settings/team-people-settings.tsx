"use client";

import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { TeamInvitations } from "@/components/settings/team-invitations";
import {
  assignableRolesFor,
  canChangeMemberRole,
  canLeaveOrganization,
  canRemoveMember,
} from "@/components/settings/team-member-permissions";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/hooks/use-auth";
import { apiErrorDetail } from "@/lib/api/error-detail";
import {
  leaveOrganization,
  listMembers,
  removeMember,
  updateMemberRole,
} from "@/lib/api/members";
import type {
  AuthResponse,
  InvitationRole,
  MemberPublic,
  MembershipRole,
} from "@/types/api";

const roleLabels: Record<MembershipRole, string> = {
  OWNER: "Owner",
  ADMIN: "Admin",
  MEMBER: "Member",
};

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

type PendingAction =
  | { type: "remove"; member: MemberPublic }
  | { type: "leave" }
  | { type: "role"; member: MemberPublic; role: InvitationRole };

type TeamPeopleSettingsProps = {
  role: MembershipRole;
  currentUserId: string;
  currentMembershipId: string;
};

export function TeamPeopleSettings({
  role,
  currentUserId,
  currentMembershipId,
}: TeamPeopleSettingsProps) {
  const { completeAuth, signOut } = useAuth();
  const [members, setMembers] = useState<MemberPublic[] | null>(null);
  const [membersError, setMembersError] = useState(false);
  const [requestVersion, setRequestVersion] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void listMembers()
      .then((rows) => {
        if (!cancelled) {
          setMembers(rows);
          setMembersError(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMembersError(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [requestVersion]);

  function retryMembers() {
    setMembers(null);
    setMembersError(false);
    setRequestVersion((version) => version + 1);
  }

  async function runConfirmedAction() {
    if (!pending || confirmBusy) {
      return;
    }
    setConfirmBusy(true);
    setActionError(null);
    try {
      if (pending.type === "role") {
        const updated = await updateMemberRole(
          pending.member.membership_id,
          pending.role,
        );
        setMembers(
          (current) =>
            current?.map((row) =>
              row.membership_id === updated.membership_id ? updated : row,
            ) ?? current,
        );
      } else if (pending.type === "remove") {
        await removeMember(pending.member.membership_id);
        setMembers(
          (current) =>
            current?.filter(
              (row) => row.membership_id !== pending.member.membership_id,
            ) ?? current,
        );
      } else {
        const next = await leaveOrganization();
        if (next && typeof next === "object" && "access_token" in next) {
          completeAuth(next as AuthResponse);
          setMembers(null);
          setRequestVersion((version) => version + 1);
        } else {
          await signOut();
        }
      }
      setPending(null);
    } catch (cause) {
      setActionError(
        apiErrorDetail(cause, "The team change could not be completed."),
      );
    } finally {
      setConfirmBusy(false);
    }
  }

  const confirmOpen = pending !== null;
  const confirmTitle =
    pending?.type === "remove"
      ? `Remove ${pending.member.user.name}?`
      : pending?.type === "leave"
        ? "Leave this organization?"
        : pending?.type === "role"
          ? `Change role to ${roleLabels[pending.role]}?`
          : "";
  const confirmDescription =
    pending?.type === "remove"
      ? `${pending.member.user.name} will lose access to this organization immediately.`
      : pending?.type === "leave"
        ? "You will lose access to this organization. If you belong to another organization, you will switch to it."
        : pending?.type === "role"
          ? `${pending.member.user.name} will become ${roleLabels[pending.role]}.`
          : "";
  const confirmLabel =
    pending?.type === "remove"
      ? "Remove"
      : pending?.type === "leave"
        ? "Leave organization"
        : "Change role";
  const confirmVariant =
    pending?.type === "remove" || pending?.type === "leave"
      ? "destructive"
      : "default";

  return (
    <div className="grid gap-6">
      {actionError ? (
        <p className="text-danger-text text-sm" role="alert">
          {actionError}
        </p>
      ) : null}

      {membersError ? (
        <StatePanel
          kind="error"
          title="Members could not be loaded"
          description="Try again to retrieve the current organization members."
          action={<Button onClick={retryMembers}>Try again</Button>}
        />
      ) : members === null ? (
        <p className="text-muted-foreground text-sm" role="status">
          Loading people
        </p>
      ) : members.length === 0 ? (
        <StatePanel
          kind="unavailable"
          title="No organization members"
          description="No members were returned for the current organization."
        />
      ) : (
        <ul className="divide-border border-border divide-y rounded-lg border">
          {members.map((member) => {
            const isSelf =
              member.user.id === currentUserId ||
              member.membership_id === currentMembershipId;
            const targetRole = member.role;
            const showRoleChange = canChangeMemberRole(role, targetRole);
            const showRemove = canRemoveMember(role, targetRole, isSelf);
            const showLeave = isSelf && canLeaveOrganization(role);
            const hasActions = showRoleChange || showRemove || showLeave;
            const nextRoles = assignableRolesFor(role, targetRole).filter(
              (next) => next !== targetRole,
            );

            return (
              <li
                key={member.membership_id}
                className="flex items-center gap-3 px-4 py-3"
              >
                <span
                  className="bg-brand-subtle text-brand-text ring-brand-border flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1"
                  aria-hidden="true"
                >
                  {getInitials(member.user.name)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {member.user.name}
                    {isSelf ? (
                      <span className="text-muted-foreground font-normal">
                        {" "}
                        (you)
                      </span>
                    ) : null}
                  </p>
                  <p className="text-muted-foreground truncate text-xs">
                    {member.user.email}
                  </p>
                </div>
                <span className="bg-surface-subtle text-foreground inline-flex shrink-0 items-center rounded-md px-2 py-1 text-xs font-medium">
                  {roleLabels[targetRole]}
                </span>
                {hasActions ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      render={
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Actions for ${member.user.name}`}
                          className="shrink-0"
                        >
                          <MoreHorizontal className="size-4" aria-hidden="true" />
                        </Button>
                      }
                    />
                    <DropdownMenuContent>
                      {nextRoles.map((nextRole) => (
                        <DropdownMenuItem
                          key={nextRole}
                          onClick={() =>
                            setPending({
                              type: "role",
                              member,
                              role: nextRole,
                            })
                          }
                        >
                          Make {roleLabels[nextRole]}
                        </DropdownMenuItem>
                      ))}
                      {showRoleChange && (showRemove || showLeave) ? (
                        <DropdownMenuSeparator />
                      ) : null}
                      {showRemove ? (
                        <DropdownMenuItem
                          className="text-danger-text"
                          onClick={() => setPending({ type: "remove", member })}
                        >
                          Remove from organization
                        </DropdownMenuItem>
                      ) : null}
                      {showLeave ? (
                        <DropdownMenuItem
                          className="text-danger-text"
                          onClick={() => setPending({ type: "leave" })}
                        >
                          Leave organization
                        </DropdownMenuItem>
                      ) : null}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : (
                  <span className="size-9 shrink-0" aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="grid gap-3">
        <div>
          <h3 className="text-sm font-medium">Invitations</h3>
          <p className="text-muted-foreground text-xs">
            Invite people by email. Pending invitations stay here until accepted
            or revoked.
          </p>
        </div>
        <TeamInvitations role={role} />
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          if (!open && !confirmBusy) {
            setPending(null);
          }
        }}
        title={confirmTitle}
        description={confirmDescription}
        confirmLabel={confirmLabel}
        variant={confirmVariant}
        confirmPending={confirmBusy}
        onConfirm={() => {
          void runConfirmedAction();
        }}
      />
    </div>
  );
}

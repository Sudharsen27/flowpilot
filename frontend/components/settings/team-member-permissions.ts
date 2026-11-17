import type { InvitationRole, MembershipRole } from "@/types/api";

export function assignableRolesFor(
  actor: MembershipRole,
  targetRole: MembershipRole,
): InvitationRole[] {
  if (targetRole === "OWNER") {
    return [];
  }
  if (actor === "OWNER") {
    return ["ADMIN", "MEMBER"];
  }
  if (actor === "ADMIN" && targetRole === "MEMBER") {
    return ["MEMBER"];
  }
  return [];
}

export function canChangeMemberRole(
  actor: MembershipRole,
  targetRole: MembershipRole,
): boolean {
  const roles = assignableRolesFor(actor, targetRole);
  return roles.some((role) => role !== targetRole);
}

export function canRemoveMember(
  actor: MembershipRole,
  targetRole: MembershipRole,
  isSelf: boolean,
): boolean {
  if (isSelf || targetRole === "OWNER") {
    return false;
  }
  if (actor === "OWNER") {
    return targetRole === "ADMIN" || targetRole === "MEMBER";
  }
  if (actor === "ADMIN") {
    return targetRole === "MEMBER";
  }
  return false;
}

export function canLeaveOrganization(actor: MembershipRole): boolean {
  return actor !== "OWNER";
}

export function canTransferOwnership(
  actor: MembershipRole,
  targetRole: MembershipRole,
  isSelf: boolean,
): boolean {
  if (actor !== "OWNER" || isSelf || targetRole === "OWNER") {
    return false;
  }
  return targetRole === "ADMIN" || targetRole === "MEMBER";
}

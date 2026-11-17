import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type { AuthResponse, InvitationRole, MemberPublic } from "@/types/api";

export function listMembers() {
  return apiGet<MemberPublic[]>("/api/v1/organizations/current/members");
}

export function updateMemberRole(membershipId: string, role: InvitationRole) {
  return apiPatch<MemberPublic>(
    `/api/v1/organizations/current/members/${encodeURIComponent(membershipId)}`,
    { role },
  );
}

export function removeMember(membershipId: string) {
  return apiDelete(
    `/api/v1/organizations/current/members/${encodeURIComponent(membershipId)}`,
  );
}

export function leaveOrganization() {
  return apiPost<AuthResponse | undefined>("/api/v1/organizations/current/leave");
}

export function transferOwnership(membershipId: string) {
  return apiPost<MemberPublic>("/api/v1/organizations/current/transfer-ownership", {
    membership_id: membershipId,
  });
}

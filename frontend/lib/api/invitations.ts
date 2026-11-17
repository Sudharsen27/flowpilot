import { apiGet, apiPost } from "@/lib/api/client";
import type {
  InvitationAcceptResponse,
  InvitationHistoryPublic,
  InvitationPublic,
  InvitationRole,
  InvitationStatusResponse,
  UserOrganizationPublic,
} from "@/types/api";

export function listInvitations() {
  return apiGet<InvitationPublic[]>("/api/v1/organizations/current/invitations");
}

export function listInvitationHistory() {
  return apiGet<InvitationHistoryPublic[]>(
    "/api/v1/organizations/current/invitations/history",
  );
}

export function createInvitation(email: string, role: InvitationRole) {
  return apiPost<InvitationStatusResponse>("/api/v1/organizations/current/invitations", {
    email,
    role,
  });
}

export function resendInvitation(invitationId: string) {
  return apiPost<InvitationPublic>(
    `/api/v1/organizations/current/invitations/${encodeURIComponent(invitationId)}/resend`,
  );
}

export function revokeInvitation(invitationId: string) {
  return apiPost<void>(
    `/api/v1/organizations/current/invitations/${encodeURIComponent(invitationId)}/revoke`,
  );
}

export function acceptInvitation(input: { token: string; name?: string; password?: string }) {
  const body: { token: string; name?: string; password?: string } = { token: input.token };
  if (input.name !== undefined) {
    body.name = input.name;
  }
  if (input.password !== undefined) {
    body.password = input.password;
  }
  return apiPost<InvitationAcceptResponse>("/api/v1/invitations/accept", body);
}

export function listMyOrganizations() {
  return apiGet<UserOrganizationPublic[]>("/api/v1/users/me/organizations");
}

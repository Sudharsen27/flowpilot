import { apiGet } from "@/lib/api/client";
import type { MemberPublic, OrganizationPublic } from "@/types/api";

/** Fresh organization settings, e.g. the currency deals are recorded in. */
export function getCurrentOrganization() {
  return apiGet<OrganizationPublic>("/api/v1/organizations/current");
}

export function listOrganizationMembers() {
  return apiGet<MemberPublic[]>("/api/v1/organizations/current/members");
}

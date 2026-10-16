import { apiGet, apiPatch } from "@/lib/api/client";
import type {
  IdealCustomerProfile,
  IdealCustomerProfileUpdate,
} from "@/types/api";

const PROFILE_PATH = "/api/v1/organizations/current/ideal-customer-profile";

export function getIdealCustomerProfile() {
  return apiGet<IdealCustomerProfile>(PROFILE_PATH);
}

export function updateIdealCustomerProfile(input: IdealCustomerProfileUpdate) {
  return apiPatch<IdealCustomerProfile>(PROFILE_PATH, input);
}

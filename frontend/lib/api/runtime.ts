import { apiGet } from "@/lib/api/client";
import type { RuntimeConfiguration } from "@/types/api";

export function getRuntimeConfiguration() {
  return apiGet<RuntimeConfiguration>("/api/v1/runtime/configuration");
}

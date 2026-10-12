import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  WebhookDelivery,
  WebhookDeliveryListResponse,
  WebhookEndpoint,
  WebhookEndpointInput,
  WebhookEndpointWithSecret,
} from "@/types/api";

const BASE = "/api/v1/integrations/webhooks";

function path(endpointId: string) {
  return `${BASE}/${encodeURIComponent(endpointId)}`;
}

export function listWebhooks() {
  return apiGet<WebhookEndpoint[]>(BASE);
}

export function createWebhook(input: WebhookEndpointInput) {
  return apiPost<WebhookEndpointWithSecret>(BASE, input);
}

export function updateWebhook(
  endpointId: string,
  input: Partial<WebhookEndpointInput> & {
    expected_revision: number;
    enabled?: boolean;
  },
) {
  return apiPatch<WebhookEndpoint>(path(endpointId), input);
}

export function deleteWebhook(endpointId: string) {
  return apiDelete(path(endpointId));
}

export function rotateWebhookSecret(
  endpointId: string,
  expectedRevision: number,
) {
  return apiPost<WebhookEndpointWithSecret>(
    `${path(endpointId)}/rotate-secret`,
    {
      expected_revision: expectedRevision,
    },
  );
}

export function sendWebhookTest(endpointId: string) {
  return apiPost<WebhookDelivery>(`${path(endpointId)}/test`, {});
}

export function listWebhookDeliveries(
  endpointId: string,
  params: { limit?: number } = {},
) {
  return apiGet<WebhookDeliveryListResponse>(
    `${path(endpointId)}/deliveries?limit=${params.limit ?? 20}`,
  );
}

export function retryWebhookDelivery(endpointId: string, deliveryId: string) {
  return apiPost<WebhookDelivery>(
    `${path(endpointId)}/deliveries/${encodeURIComponent(deliveryId)}/retry`,
    {},
  );
}

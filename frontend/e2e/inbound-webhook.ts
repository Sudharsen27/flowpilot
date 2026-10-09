import { createHmac, randomUUID } from "node:crypto";

import { e2eWebhookSecret } from "./environment";

/** Test-only Svix secret. It is not a Resend credential. */
export const E2E_WEBHOOK_SECRET = e2eWebhookSecret;

export const E2E_INBOUND_DOMAIN = "inbound.e2e.test";

export const E2E_REPLY = "Can we see pricing and book a demo on Thursday?";

export function signInboundWebhook(payload: string): Record<string, string> {
  const messageId = `msg_${randomUUID()}`;
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const secret = Buffer.from(E2E_WEBHOOK_SECRET.replace(/^whsec_/, ""), "base64");
  const signed = Buffer.concat([
    Buffer.from(`${messageId}.${timestamp}.`),
    Buffer.from(payload),
  ]);
  const digest = createHmac("sha256", secret).update(signed).digest("base64");
  return {
    "svix-id": messageId,
    "svix-timestamp": timestamp,
    "svix-signature": `v1,${digest}`,
    "content-type": "application/json",
  };
}

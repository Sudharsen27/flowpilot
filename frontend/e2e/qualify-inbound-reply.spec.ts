import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

import {
  E2E_INBOUND_DOMAIN,
  E2E_REPLY,
  signInboundWebhook,
} from "./inbound-webhook";

const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";

test("qualifies a matched inbound reply from Inbox", async ({ page, request }) => {
  test.setTimeout(60_000);
  const stamp = randomUUID().slice(0, 8);
  const email = `e2e-${stamp}@example.com`;
  const password = "password12";
  const registered = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: {
      email,
      password,
      name: "E2E Owner",
      organization_name: `E2E ${stamp}`,
    },
  });
  expect(registered.ok()).toBeTruthy();
  const account = (await registered.json()) as {
    access_token: string;
    organization: { slug: string };
  };

  const createdLead = await request.post(`${API_URL}/api/v1/leads`, {
    headers: { Authorization: `Bearer ${account.access_token}` },
    data: {
      name: "Ada Prospect",
      email: `ada-${stamp}@customer.example`,
      enquiry: "Original website enquiry about onboarding.",
    },
  });
  expect(createdLead.ok()).toBeTruthy();
  const lead = (await createdLead.json()) as { id: string };

  const payload = JSON.stringify({
    type: "email.received",
    created_at: new Date().toISOString(),
    data: {
      email_id: `email_${stamp}`,
      created_at: new Date().toISOString(),
      from: `Ada Customer <ada-${stamp}@customer.example>`,
      to: [`${account.organization.slug}@${E2E_INBOUND_DOMAIN}`],
      cc: [],
      bcc: [],
      message_id: `<${stamp}@customer.example>`,
      subject: "Re: pricing",
      text: E2E_REPLY,
      html: "<p>hidden html</p>",
    },
  });
  const received = await request.post(`${API_URL}/api/v1/webhooks/resend/inbound`, {
    headers: signInboundWebhook(payload),
    data: payload,
  });
  expect(received.ok()).toBeTruthy();
  expect(await received.json()).toEqual({ status: "accepted" });

  await page.goto("/login");
  await page.getByRole("textbox", { name: "Email" }).fill(email);
  await page.getByRole("textbox", { name: "Password" }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/");

  await page.goto(`/inbox?lead=${lead.id}`);
  const timeline = page.getByRole("list", { name: "Conversation timeline" });
  await expect(timeline.getByText(E2E_REPLY)).toBeVisible();
  await expect(page.getByRole("button", { name: "Send reply" })).toBeDisabled();

  await page.getByRole("button", { name: "Qualify this reply" }).click();

  await expect(page.getByText("Needs more information · Demo request")).toBeVisible();
  await expect(page.getByText("request pricing")).toBeVisible();
  await expect(page.getByText("request demo")).toBeVisible();
  await expect(
    page.getByText("This reply has been qualified. No email was sent."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Qualify this reply" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Send reply" })).toBeDisabled();
});

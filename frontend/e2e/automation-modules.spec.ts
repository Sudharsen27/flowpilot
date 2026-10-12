import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8010";

test("an owner can use Analytics, Knowledge, Workflows and Integrations", async ({
  page,
  request,
}) => {
  test.setTimeout(90_000);
  const stamp = randomUUID().slice(0, 8);
  const email = `e2e-modules-${stamp}@example.com`;
  const password = "password12";
  const registered = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: {
      email,
      password,
      name: "E2E Owner",
      organization_name: `E2E Modules ${stamp}`,
    },
  });
  expect(registered.ok()).toBeTruthy();
  const account = (await registered.json()) as { access_token: string };
  const createdLead = await request.post(`${API_URL}/api/v1/leads`, {
    headers: { Authorization: `Bearer ${account.access_token}` },
    data: { name: "Ada Prospect", email: `ada-${stamp}@customer.example` },
  });
  expect(createdLead.ok()).toBeTruthy();

  await page.goto("/login");
  await page.getByRole("textbox", { name: "Email" }).fill(email);
  await page.getByRole("textbox", { name: "Password" }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/");

  const sidebar = page.getByRole("navigation").first();
  for (const label of ["Analytics", "Workflows", "Knowledge", "Integrations"]) {
    await expect(
      sidebar.getByRole("link", { name: label, exact: true }),
    ).toBeVisible();
  }
  await expect(page.getByText("Coming soon", { exact: true })).toHaveCount(0);

  await page.goto("/analytics");
  const leadsCard = page
    .getByRole("article")
    .filter({ hasText: "Leads created" });
  await expect(leadsCard).toContainText("1");

  await page.goto("/knowledge");
  await page.getByRole("button", { name: "Add entry" }).first().click();
  const knowledgeDialog = page.getByRole("dialog");
  await knowledgeDialog
    .getByLabel("Title")
    .fill("What does the Starter plan cost?");
  await knowledgeDialog
    .getByLabel("Content")
    .fill("Starter costs $49 per month, billed monthly.");
  await knowledgeDialog.getByRole("button", { name: "Add entry" }).click();
  await expect(
    page.getByRole("article", { name: "What does the Starter plan cost?" }),
  ).toBeVisible();

  await page.goto("/workflows");
  await page.getByRole("button", { name: "New workflow" }).first().click();
  const workflowDialog = page.getByRole("dialog");
  await workflowDialog.getByLabel("Name").fill("Remind me about new leads");
  await workflowDialog.getByLabel("Then").selectOption("CREATE_FOLLOW_UP");
  await workflowDialog.getByRole("button", { name: "Create workflow" }).click();
  const rule = page.getByRole("article", { name: "Remind me about new leads" });
  await expect(
    rule.getByRole("switch", { name: "Turn on Remind me about new leads" }),
  ).toBeVisible();
  await rule
    .getByRole("switch", { name: "Turn on Remind me about new leads" })
    .click();
  await expect(
    rule.getByRole("switch", { name: "Turn off Remind me about new leads" }),
  ).toBeVisible();

  await page.goto("/integrations");
  await page.getByRole("button", { name: "Add webhook" }).first().click();
  const webhookDialog = page.getByRole("dialog");
  await webhookDialog.getByLabel("Name").fill("Test receiver");
  await webhookDialog
    .getByLabel("Endpoint URL")
    .fill("https://receiver.e2e.invalid/hook");
  await webhookDialog.getByRole("button", { name: "Add webhook" }).click();
  const secretDialog = page.getByRole("dialog", {
    name: "Copy your signing secret",
  });
  await expect(secretDialog.getByLabel("Signing secret")).toHaveValue(
    /^whsec_[0-9a-f]{64}$/,
  );
  await secretDialog.getByRole("button", { name: "I have saved it" }).click();

  const hook = page.getByRole("article", { name: "Test receiver" });
  await hook
    .getByRole("button", { name: "Send test event to Test receiver" })
    .click();
  await expect(hook.getByText(/^Test event failed: /)).toBeVisible();
  await hook.getByRole("button", { name: "Show deliveries" }).click();
  await expect(
    page
      .getByRole("list", { name: "Recent deliveries to Test receiver" })
      .getByText("Failed"),
  ).toBeVisible();
});

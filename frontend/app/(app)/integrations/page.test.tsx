import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IntegrationsPage from "@/app/(app)/integrations/page";
import { IntegrationStatusBadge } from "@/components/integrations/integration-status-badge";
import {
  createWebhook,
  deleteWebhook,
  listWebhookDeliveries,
  listWebhooks,
  retryWebhookDelivery,
  rotateWebhookSecret,
  sendWebhookTest,
  updateWebhook,
} from "@/lib/api/webhooks";
import type {
  MembershipRole,
  WebhookDelivery,
  WebhookEndpoint,
} from "@/types/api";

const auth = vi.hoisted(() => ({ role: "OWNER" as MembershipRole }));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: { id: "user-1", email: "owner@example.com", name: "Owner" },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: {
        id: "membership-1",
        organization_id: "org-1",
        user_id: "user-1",
        role: auth.role,
      },
    },
  }),
}));

vi.mock("@/lib/api/webhooks", () => ({
  listWebhooks: vi.fn(),
  createWebhook: vi.fn(),
  updateWebhook: vi.fn(),
  deleteWebhook: vi.fn(),
  rotateWebhookSecret: vi.fn(),
  sendWebhookTest: vi.fn(),
  listWebhookDeliveries: vi.fn(),
  retryWebhookDelivery: vi.fn(),
}));

const listMock = vi.mocked(listWebhooks);
const createMock = vi.mocked(createWebhook);
const updateMock = vi.mocked(updateWebhook);
const deleteMock = vi.mocked(deleteWebhook);
const rotateMock = vi.mocked(rotateWebhookSecret);
const testMock = vi.mocked(sendWebhookTest);
const deliveriesMock = vi.mocked(listWebhookDeliveries);
const retryMock = vi.mocked(retryWebhookDelivery);

const endpoint: WebhookEndpoint = {
  id: "hook-1",
  name: "CRM sync",
  url: "https://hooks.example.com/flowpilot",
  events: ["lead.created", "email.sent"],
  enabled: true,
  secret_hint: "a1b2",
  revision: 2,
  created_at: "2026-10-10T10:00:00Z",
  updated_at: "2026-10-11T10:00:00Z",
  delivery_counts: { pending: 0, delivered: 3, failed: 1 },
  last_delivery_at: "2026-10-11T10:00:00Z",
};

function delivery(overrides: Partial<WebhookDelivery> = {}): WebhookDelivery {
  return {
    id: "delivery-1",
    endpoint_id: "hook-1",
    event_type: "lead.created",
    status: "DELIVERED",
    attempts: 1,
    last_status_code: 200,
    last_error: null,
    next_attempt_at: null,
    created_at: "2026-10-11T10:00:00Z",
    last_attempt_at: "2026-10-11T10:00:01Z",
    delivered_at: "2026-10-11T10:00:01Z",
    ...overrides,
  };
}

describe("Integrations page", () => {
  beforeEach(() => {
    auth.role = "OWNER";
    for (const mock of [
      listMock,
      createMock,
      updateMock,
      deleteMock,
      rotateMock,
      testMock,
      deliveriesMock,
      retryMock,
    ]) {
      mock.mockReset();
    }
    listMock.mockResolvedValue([endpoint]);
    deliveriesMock.mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
  });

  it("lists webhooks with visible controls for owners", async () => {
    render(<IntegrationsPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Integrations" }),
    ).toBeVisible();
    const card = await screen.findByRole("article", { name: "CRM sync" });
    expect(
      within(card).getByText("https://hooks.example.com/flowpilot"),
    ).toBeVisible();
    expect(
      within(card).getByText("Sends: Lead created, Email sent"),
    ).toBeVisible();
    expect(within(card).getByText("1 failed")).toBeVisible();
    for (const name of [
      "Send test event to CRM sync",
      "Edit CRM sync",
      "Replace signing secret for CRM sync",
      "Delete CRM sync",
      "Show deliveries",
    ]) {
      expect(within(card).getByRole("button", { name })).toBeVisible();
    }
    expect(
      within(card).getByRole("switch", { name: "Turn off CRM sync" }),
    ).toBeVisible();
  });

  it("creates a webhook and shows the secret once", async () => {
    listMock.mockResolvedValueOnce([]);
    createMock.mockResolvedValue({
      endpoint: { ...endpoint, id: "hook-2" },
      secret: "whsec_abc123",
    });
    render(<IntegrationsPage />);
    await screen.findByText("No webhooks yet");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Add webhook" })[0],
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Name/), "CRM sync");
    const url = within(dialog).getByLabelText(/Endpoint URL/);
    await userEvent.type(url, "http://insecure.example.com");
    expect(
      within(dialog).getByRole("button", { name: "Add webhook" }),
    ).toBeDisabled();
    await userEvent.clear(url);
    await userEvent.type(url, "https://hooks.example.com/flowpilot");
    await userEvent.click(
      within(dialog).getByRole("checkbox", { name: /Email sent/ }),
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add webhook" }),
    );
    expect(createMock).toHaveBeenCalledWith({
      name: "CRM sync",
      url: "https://hooks.example.com/flowpilot",
      events: ["lead.created", "email.sent"],
    });
    const secretDialog = await screen.findByRole("dialog", {
      name: "Copy your signing secret",
    });
    expect(within(secretDialog).getByLabelText("Signing secret")).toHaveValue(
      "whsec_abc123",
    );
    await userEvent.click(
      within(secretDialog).getByRole("button", { name: "I have saved it" }),
    );
    await waitFor(() =>
      expect(screen.queryByDisplayValue("whsec_abc123")).toBeNull(),
    );
  });

  it("reports the result of a test event", async () => {
    testMock.mockResolvedValueOnce(
      delivery({ event_type: "webhook.test", last_status_code: 204 }),
    );
    render(<IntegrationsPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Send test event to CRM sync",
      }),
    );
    expect(testMock).toHaveBeenCalledWith("hook-1");
    expect(
      await screen.findByText("Test event delivered (HTTP 204)."),
    ).toBeVisible();

    testMock.mockResolvedValueOnce(
      delivery({
        event_type: "webhook.test",
        status: "FAILED",
        last_status_code: null,
        last_error: "Could not connect to the endpoint",
      }),
    );
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Send test event to CRM sync",
      }),
    );
    expect(
      await screen.findByText(
        "Test event failed: Could not connect to the endpoint.",
      ),
    ).toBeVisible();
  });

  it("shows the delivery log and retries failed events", async () => {
    deliveriesMock.mockResolvedValue({
      items: [
        delivery({
          id: "delivery-2",
          status: "FAILED",
          attempts: 5,
          last_status_code: 500,
          last_error: "The endpoint responded with HTTP 500",
        }),
        delivery(),
      ],
      total: 2,
      limit: 20,
      offset: 0,
    });
    retryMock.mockResolvedValue(
      delivery({ id: "delivery-2", status: "PENDING", attempts: 0 }),
    );
    render(<IntegrationsPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Show deliveries" }),
    );
    const log = await screen.findByRole("list", {
      name: "Recent deliveries to CRM sync",
    });
    expect(
      within(log).getByText("The endpoint responded with HTTP 500"),
    ).toBeVisible();
    expect(within(log).getByText("HTTP 200")).toBeVisible();
    await userEvent.click(
      within(log).getByRole("button", { name: "Retry Lead created delivery" }),
    );
    expect(retryMock).toHaveBeenCalledWith("hook-1", "delivery-2");
  });

  it("replaces the secret only after confirmation", async () => {
    rotateMock.mockResolvedValue({
      endpoint: { ...endpoint, revision: 3 },
      secret: "whsec_new",
    });
    render(<IntegrationsPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Replace signing secret for CRM sync",
      }),
    );
    expect(rotateMock).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Replace secret" }),
    );
    expect(rotateMock).toHaveBeenCalledWith("hook-1", 2);
    expect(await screen.findByDisplayValue("whsec_new")).toBeVisible();
  });

  it("deletes only after confirmation and toggles with the revision", async () => {
    updateMock.mockResolvedValue({ ...endpoint, enabled: false, revision: 3 });
    deleteMock.mockResolvedValue(undefined);
    render(<IntegrationsPage />);
    await userEvent.click(
      await screen.findByRole("switch", { name: "Turn off CRM sync" }),
    );
    expect(updateMock).toHaveBeenCalledWith("hook-1", {
      expected_revision: 2,
      enabled: false,
    });
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete CRM sync" }),
    );
    expect(deleteMock).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete webhook" }),
    );
    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("hook-1"));
  });

  it("is read-only for members", async () => {
    auth.role = "MEMBER";
    render(<IntegrationsPage />);
    const card = await screen.findByRole("article", { name: "CRM sync" });
    expect(within(card).queryByRole("switch")).toBeNull();
    expect(
      within(card).queryByRole("button", { name: /Send test event/ }),
    ).toBeNull();
    expect(within(card).queryByRole("button", { name: /Delete/ })).toBeNull();
    expect(
      within(card).getByRole("button", { name: "Show deliveries" }),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Add webhook" })).toBeNull();
    expect(
      screen.getByText(
        "Only owners and admins can add or change integrations.",
      ),
    ).toBeVisible();
  });

  it("lists other tools honestly as needing provider setup", async () => {
    render(<IntegrationsPage />);
    await screen.findByRole("article", { name: "CRM sync" });
    const catalog = screen.getByRole("list", { name: "Integration catalog" });
    expect(within(catalog).getAllByRole("listitem")).toHaveLength(10);
    expect(
      within(catalog).queryByRole("heading", { name: "Webhooks" }),
    ).toBeNull();
    expect(within(catalog).getAllByText("Needs provider setup")).toHaveLength(
      10,
    );
    expect(within(catalog).queryByRole("button")).toBeNull();
    expect(
      within(catalog).getByText(/API keys for FlowPilot are not available yet/),
    ).toBeVisible();
  });

  it("filters the catalog locally", async () => {
    const user = userEvent.setup();
    render(<IntegrationsPage />);
    await screen.findByRole("article", { name: "CRM sync" });
    expect(screen.getByText("10 integrations")).toBeVisible();
    await user.type(
      screen.getByRole("searchbox", { name: "Search integrations" }),
      "HubSpot",
    );
    expect(screen.getByText("1 integration")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Integration category" }),
      "calendar",
    );
    expect(screen.getByText("2 integrations")).toBeVisible();
  });

  it("offers a retry when loading fails", async () => {
    listMock.mockRejectedValueOnce(new Error("offline"));
    render(<IntegrationsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("article", { name: "CRM sync" }),
    ).toBeVisible();
  });

  it("maps connection statuses to clear labels", () => {
    render(
      <>
        <IntegrationStatusBadge status="connected" />
        <IntegrationStatusBadge status="not-connected" />
        <IntegrationStatusBadge status="needs-attention" />
        <IntegrationStatusBadge status="needs-setup" />
      </>,
    );
    for (const label of [
      "Connected",
      "Not connected",
      "Needs attention",
      "Needs provider setup",
    ]) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });
});

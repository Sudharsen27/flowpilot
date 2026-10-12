import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WorkflowsPage from "@/app/(app)/workflows/page";
import {
  createWorkflow,
  deleteWorkflow,
  listWorkflowRuns,
  listWorkflows,
  updateWorkflow,
} from "@/lib/api/workflows";
import type { MembershipRole, WorkflowRule } from "@/types/api";

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

vi.mock("@/lib/api/workflows", () => ({
  listWorkflows: vi.fn(),
  createWorkflow: vi.fn(),
  updateWorkflow: vi.fn(),
  deleteWorkflow: vi.fn(),
  listWorkflowRuns: vi.fn(),
}));

const listMock = vi.mocked(listWorkflows);
const createMock = vi.mocked(createWorkflow);
const updateMock = vi.mocked(updateWorkflow);
const deleteMock = vi.mocked(deleteWorkflow);
const runsMock = vi.mocked(listWorkflowRuns);

const rule: WorkflowRule = {
  id: "rule-1",
  name: "Analyze website leads",
  trigger: "LEAD_CREATED",
  action: "ANALYZE_LEAD",
  source_filter: "WEBSITE",
  follow_up_delay_hours: null,
  enabled: false,
  revision: 3,
  created_at: "2026-10-10T10:00:00Z",
  updated_at: "2026-10-11T10:00:00Z",
  run_counts: { pending: 0, succeeded: 2, skipped: 1, failed: 1 },
  last_run_at: "2026-10-11T10:00:00Z",
};

describe("Workflows page", () => {
  beforeEach(() => {
    auth.role = "OWNER";
    for (const mock of [
      listMock,
      createMock,
      updateMock,
      deleteMock,
      runsMock,
    ]) {
      mock.mockReset();
    }
    listMock.mockResolvedValue([rule]);
    runsMock.mockResolvedValue({ items: [], total: 0, limit: 20, offset: 0 });
  });

  it("describes each rule in plain language with visible controls", async () => {
    render(<WorkflowsPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Workflows" }),
    ).toBeVisible();
    const card = await screen.findByRole("article", {
      name: "Analyze website leads",
    });
    expect(card).toHaveTextContent(
      "When a new lead is added from Website, then analyze the lead with ai.",
    );
    expect(within(card).getByText("1 failed")).toBeVisible();
    expect(
      within(card).getByRole("switch", {
        name: "Turn on Analyze website leads",
      }),
    ).toBeVisible();
    expect(
      within(card).getByRole("button", { name: "Edit Analyze website leads" }),
    ).toBeVisible();
    expect(
      within(card).getByRole("button", {
        name: "Delete Analyze website leads",
      }),
    ).toBeVisible();
    expect(screen.getByText(/Workflows never send email/)).toBeVisible();
  });

  it("turns a rule on with its current revision", async () => {
    updateMock.mockResolvedValue({ ...rule, enabled: true, revision: 4 });
    render(<WorkflowsPage />);
    await userEvent.click(
      await screen.findByRole("switch", {
        name: "Turn on Analyze website leads",
      }),
    );
    expect(updateMock).toHaveBeenCalledWith("rule-1", {
      expected_revision: 3,
      enabled: true,
    });
    expect(
      await screen.findByRole("switch", {
        name: "Turn off Analyze website leads",
      }),
    ).toBeVisible();
  });

  it("creates a follow-up workflow and limits actions for human attention", async () => {
    listMock.mockResolvedValueOnce([]);
    createMock.mockResolvedValue({ ...rule, id: "rule-2" });
    render(<WorkflowsPage />);
    await screen.findByText("Create your first workflow");
    await userEvent.click(
      screen.getAllByRole("button", { name: "New workflow" })[0],
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(
      within(dialog).getByLabelText(/Name/),
      "Remind on escalation",
    );
    await userEvent.selectOptions(
      within(dialog).getByLabelText(/When/),
      "HUMAN_ATTENTION_REQUIRED",
    );
    const action = within(dialog).getByLabelText(/Then/);
    expect(
      within(action)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["Schedule a follow-up reminder"]);
    expect(within(dialog).queryByLabelText(/Only for leads from/)).toBeNull();
    await userEvent.selectOptions(
      within(dialog).getByLabelText(/Reminder due after/),
      "4",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Create workflow" }),
    );
    expect(createMock).toHaveBeenCalledWith({
      name: "Remind on escalation",
      trigger: "HUMAN_ATTENTION_REQUIRED",
      action: "CREATE_FOLLOW_UP",
      source_filter: null,
      follow_up_delay_hours: 4,
    });
  });

  it("warns about overlap with Sales Agent auto-start", async () => {
    listMock.mockResolvedValueOnce([]);
    render(<WorkflowsPage />);
    await screen.findByText("Create your first workflow");
    await userEvent.click(
      screen.getAllByRole("button", { name: "New workflow" })[0],
    );
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("note")).toHaveTextContent(
      /Sales Agent auto-start/,
    );
  });

  it("shows run history on request", async () => {
    runsMock.mockResolvedValue({
      items: [
        {
          id: "run-1",
          rule_id: "rule-1",
          lead_id: "lead-1",
          lead_name: "Ada Prospect",
          status: "SKIPPED",
          detail: "The lead has no enquiry to analyze.",
          result_entity_id: null,
          created_at: "2026-10-11T10:00:00Z",
          started_at: "2026-10-11T10:00:01Z",
          completed_at: "2026-10-11T10:00:02Z",
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });
    render(<WorkflowsPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Show runs" }),
    );
    const runs = await screen.findByRole("list", {
      name: "Recent runs of Analyze website leads",
    });
    expect(
      within(runs).getByRole("link", { name: "Ada Prospect" }),
    ).toHaveAttribute("href", "/leads/lead-1");
    expect(within(runs).getByText("Skipped")).toBeVisible();
    expect(runsMock).toHaveBeenCalledWith("rule-1");
  });

  it("deletes only after confirmation", async () => {
    deleteMock.mockResolvedValue(undefined);
    render(<WorkflowsPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Delete Analyze website leads",
      }),
    );
    expect(deleteMock).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Delete workflow" }),
    );
    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("rule-1"));
  });

  it("is read-only for members", async () => {
    auth.role = "MEMBER";
    render(<WorkflowsPage />);
    const card = await screen.findByRole("article", {
      name: "Analyze website leads",
    });
    expect(within(card).queryByRole("switch")).toBeNull();
    expect(within(card).queryByRole("button", { name: /Edit/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "New workflow" })).toBeNull();
    expect(
      screen.getByText(
        "Only owners and admins can create or change workflows.",
      ),
    ).toBeVisible();
    expect(
      within(card).getByRole("button", { name: "Show runs" }),
    ).toBeVisible();
  });

  it("offers a retry when loading fails", async () => {
    listMock.mockRejectedValueOnce(new Error("offline"));
    render(<WorkflowsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("article", { name: "Analyze website leads" }),
    ).toBeVisible();
  });
});

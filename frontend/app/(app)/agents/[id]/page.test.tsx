import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentDetailPage from "@/app/(app)/agents/[id]/page";
import { ApiError } from "@/lib/api/client";
import { getAgent, updateAgent } from "@/lib/api/agents";
import type { Agent } from "@/types/api";

const authMock = vi.hoisted(() => ({
  role: "OWNER" as "OWNER" | "ADMIN" | "MEMBER",
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "agent-real-1" }),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: { membership: { role: authMock.role } },
    isLoading: false,
  }),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgent: vi.fn(),
  updateAgent: vi.fn(),
}));

const agent: Agent = {
  id: "agent-real-1",
  name: "Inbound qualifier",
  description: "Qualifies new inbound leads.",
  agent_type: "SALES",
  system_instructions: "Ask concise qualification questions.",
  status: "READY",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-09T10:00:00Z",
};

const getAgentMock = vi.mocked(getAgent);
const updateAgentMock = vi.mocked(updateAgent);

describe("Agent Detail page", () => {
  beforeEach(() => {
    getAgentMock.mockReset();
    updateAgentMock.mockReset();
    authMock.role = "OWNER";
  });

  it("shows loading while requesting the agent id", () => {
    getAgentMock.mockReturnValue(new Promise(() => undefined));
    render(<AgentDetailPage />);
    expect(screen.getByText("Loading agent details")).toBeVisible();
    expect(getAgentMock).toHaveBeenCalledWith("agent-real-1");
  });

  it("renders real identity, status, and system instructions", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inbound qualifier",
      }),
    ).toBeVisible();
    expect(screen.getByText("Qualifies new inbound leads.")).toBeVisible();
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
    expect(screen.getByRole("textbox", { name: "Agent name" })).toHaveValue(
      "Inbound qualifier",
    );
    expect(screen.getByRole("combobox", { name: "Agent type" })).toHaveValue(
      "SALES",
    );
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toHaveValue("Ask concise qualification questions.");
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toBeEnabled();
    screen
      .getAllByRole("button", { name: "Save configuration" })
      .forEach((button) => expect(button).toBeDisabled());
  });

  it("shows a not-found state with back navigation", async () => {
    getAgentMock.mockRejectedValue(new ApiError("Request failed: 404", 404));
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Agent not found" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Back to AI Agents" }),
    ).toHaveAttribute("href", "/agents");
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows a retryable API error and retries", async () => {
    const user = userEvent.setup();
    getAgentMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", {
        name: "Agent could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inbound qualifier",
      }),
    ).toBeVisible();
    expect(getAgentMock).toHaveBeenCalledTimes(2);
  });

  it("keeps the existing back breadcrumb", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("link", { name: "AI Agents" }),
    ).toHaveAttribute("href", "/agents");
  });

  it.each(["OWNER", "ADMIN"] as const)(
    "allows %s to edit and sends only changed fields",
    async (role) => {
      const user = userEvent.setup();
      authMock.role = role;
      getAgentMock.mockResolvedValue(agent);
      updateAgentMock.mockResolvedValue({
        ...agent,
        name: "Updated qualifier",
      });
      render(<AgentDetailPage />);
      const name = await screen.findByRole("textbox", { name: "Agent name" });
      expect(
        screen.getAllByRole("button", { name: "Save configuration" })[0],
      ).toBeDisabled();
      await user.clear(name);
      await user.type(name, "Updated qualifier");
      const saveButtons = screen.getAllByRole("button", {
        name: "Save configuration",
      });
      expect(saveButtons[0]).toBeEnabled();
      await user.click(saveButtons[0]);
      expect(updateAgentMock).toHaveBeenCalledWith("agent-real-1", {
        name: "Updated qualifier",
      });
      expect(await screen.findByRole("status")).toHaveTextContent(
        "Configuration saved.",
      );
      expect(
        screen.getByRole("textbox", { name: "Agent name" }),
      ).toHaveValue("Updated qualifier");
      expect(
        screen.getAllByRole("button", { name: "Save configuration" })[0],
      ).toBeDisabled();
    },
  );

  it("shows a save error and preserves changes", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    updateAgentMock.mockRejectedValue(new Error("network"));
    render(<AgentDetailPage />);
    const description = await screen.findByRole("textbox", {
      name: "Description",
    });
    await user.clear(description);
    await user.type(description, "Changed description");
    await user.click(
      screen.getAllByRole("button", { name: "Save configuration" })[0],
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The configuration could not be saved",
    );
    expect(description).toHaveValue("Changed description");
  });

  it("shows members a read-only configuration", async () => {
    authMock.role = "MEMBER";
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { name: "Read-only configuration" }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Agent name" })).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toBeDisabled();
    screen
      .getAllByRole("button", { name: "Save configuration" })
      .forEach((button) => expect(button).toBeDisabled());
  });
});

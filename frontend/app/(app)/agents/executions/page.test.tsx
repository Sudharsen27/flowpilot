import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentExecutionsPage from "@/app/(app)/agents/executions/page";
import { useAuth } from "@/hooks/use-auth";
import {
  getAgentExecution,
  getAgents,
  listOrganizationExecutions,
  listToolInvocations,
} from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import type {
  Agent,
  AgentExecutionDetail,
  OrganizationExecutionListItem,
  OrganizationExecutionListResponse,
} from "@/types/api";

const mockReplace = vi.fn();
let currentSearch = "";
const searchListeners = new Set<() => void>();

function notifySearchListeners() {
  for (const listener of searchListeners) listener();
}

vi.mock("next/navigation", async () => {
  const React = await import("react");
  return {
    useRouter: () => ({
      replace: (href: string, options?: { scroll?: boolean }) => {
        mockReplace(href, options);
        currentSearch = href.includes("?") ? (href.split("?")[1] ?? "") : "";
        notifySearchListeners();
      },
      push: vi.fn(),
    }),
    usePathname: () => "/agents/executions",
    useSearchParams: () => {
      React.useSyncExternalStore(
        (onStoreChange) => {
          searchListeners.add(onStoreChange);
          return () => {
            searchListeners.delete(onStoreChange);
          };
        },
        () => currentSearch,
        () => currentSearch,
      );
      return new URLSearchParams(currentSearch);
    },
  };
});

vi.mock("@/hooks/use-auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
  listOrganizationExecutions: vi.fn(),
  getAgentExecution: vi.fn(),
  listToolInvocations: vi.fn(),
}));

const useAuthMock = vi.mocked(useAuth);
const getAgentsMock = vi.mocked(getAgents);
const listMock = vi.mocked(listOrganizationExecutions);
const getAgentExecutionMock = vi.mocked(getAgentExecution);
const listToolInvocationsMock = vi.mocked(listToolInvocations);

const agents: Agent[] = [
  {
    id: "agent-1",
    name: "Sales Agent",
    description: "",
    agent_type: "SALES",
    system_instructions: "",
    status: "ACTIVE",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
  {
    id: "agent-2",
    name: "Support Agent",
    description: "",
    agent_type: "SUPPORT",
    system_instructions: "",
    status: "READY",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  },
];

function row(overrides: Partial<OrganizationExecutionListItem> = {}): OrganizationExecutionListItem {
  return {
    id: "exec-1",
    status: "COMPLETED",
    provider: "anthropic",
    model: "claude",
    started_at: "2026-10-28T10:00:00Z",
    completed_at: "2026-10-28T10:00:02Z",
    created_at: "2026-10-28T10:00:00Z",
    input_preview: "Qualify Acme Corp",
    error_preview: null,
    duration_ms: 2000,
    failure_category: null,
    agent_id: "agent-1",
    agent_name: "Sales Agent",
    lead_id: "lead-1",
    lead_name: "Acme Corp",
    initiated_by_user_id: "user-1",
    is_stale: false,
    ...overrides,
  };
}

const counts = { QUEUED: 1, RUNNING: 2, COMPLETED: 30, FAILED: 4, CANCELLED: 0 };

function listPage(
  items: OrganizationExecutionListItem[],
  overrides: Partial<OrganizationExecutionListResponse> = {},
): OrganizationExecutionListResponse {
  return {
    items,
    limit: 20,
    offset: 0,
    total: items.length,
    status_counts: counts,
    ...overrides,
  };
}

function lastListParams() {
  return listMock.mock.calls.at(-1)?.[0];
}

function setRole(role: "OWNER" | "ADMIN" | "MEMBER") {
  useAuthMock.mockReturnValue({
    session: { membership: { role } },
  } as unknown as ReturnType<typeof useAuth>);
}

describe("Agent runs page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    searchListeners.clear();
    setRole("MEMBER");
    getAgentsMock.mockResolvedValue(agents);
    listMock.mockResolvedValue(listPage([row()]));
  });

  it("announces loading, then renders rows with agent and lead links", async () => {
    let resolve: (value: OrganizationExecutionListResponse) => void = () => {};
    listMock.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    render(<AgentExecutionsPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Agent runs" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Loading records")).toBeInTheDocument();

    resolve(listPage([row()]));

    const agentLinks = await screen.findAllByRole("link", { name: "Sales Agent" });
    expect(agentLinks[0]).toHaveAttribute("href", "/agents/agent-1");
    expect(screen.getAllByRole("link", { name: "Acme Corp" })[0]).toHaveAttribute(
      "href",
      "/leads/lead-1",
    );
    expect(screen.getAllByText("Qualify Acme Corp").length).toBeGreaterThan(0);
    expect(screen.getAllByText("2s").length).toBeGreaterThan(0);
    expect(screen.getByText("Showing 1–1 of 1")).toBeInTheDocument();
    expect(lastListParams()).toEqual({
      status: undefined,
      agentId: undefined,
      leadId: undefined,
      limit: 20,
      offset: 0,
    });
  });

  it("shows organization-wide status counts that filter the list", async () => {
    const user = userEvent.setup();
    render(<AgentExecutionsPage />);
    const overview = await screen.findByRole("list", {
      name: "Executions by status across your organization",
    });
    const failed = await within(overview).findByRole("button", {
      name: "Failed: 4 across organization",
    });
    expect(
      within(overview).getByRole("button", { name: "Completed: 30 across organization" }),
    ).toBeInTheDocument();

    await user.click(failed);

    expect(mockReplace).toHaveBeenLastCalledWith(
      "/agents/executions?status=FAILED",
      { scroll: false },
    );
    await waitFor(() => expect(lastListParams()?.status).toBe("FAILED"));
    expect(
      await within(overview).findByRole("button", {
        name: "Failed: 4 across organization, filter applied",
      }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("filters by status and agent and resets the page offset", async () => {
    const user = userEvent.setup();
    currentSearch = "offset=20";
    listMock.mockResolvedValue(listPage([row()], { offset: 20, total: 21 }));
    render(<AgentExecutionsPage />);
    await screen.findByText("Showing 21–21 of 21");

    await user.selectOptions(screen.getByRole("combobox", { name: "Execution status" }), "RUNNING");
    expect(mockReplace).toHaveBeenLastCalledWith(
      "/agents/executions?status=RUNNING",
      { scroll: false },
    );

    await screen.findByRole("option", { name: "Support Agent" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Agent" }), "agent-2");
    expect(mockReplace).toHaveBeenLastCalledWith(
      "/agents/executions?status=RUNNING&agent_id=agent-2",
      { scroll: false },
    );
    await waitFor(() =>
      expect(lastListParams()).toMatchObject({
        status: "RUNNING",
        agentId: "agent-2",
        offset: 0,
      }),
    );
  });

  it("applies a lead filter from the URL and lets the user remove it", async () => {
    const user = userEvent.setup();
    currentSearch = "lead_id=lead-1";
    render(<AgentExecutionsPage />);
    expect(await screen.findByText("Lead: Acme Corp")).toBeInTheDocument();
    expect(lastListParams()?.leadId).toBe("lead-1");

    await user.click(screen.getByRole("button", { name: "Remove lead filter" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions", {
      scroll: false,
    });
  });

  it("ignores invalid URL values instead of sending them to the API", async () => {
    currentSearch = `status=STALE&agent_id=${"x".repeat(37)}&offset=-5&limit=999`;
    render(<AgentExecutionsPage />);
    await screen.findAllByRole("link", { name: "Sales Agent" });
    expect(lastListParams()).toEqual({
      status: undefined,
      agentId: undefined,
      leadId: undefined,
      limit: 50,
      offset: 0,
    });
  });

  it("marks stale running executions clearly", async () => {
    listMock.mockResolvedValue(
      listPage([
        row({
          id: "exec-stale",
          status: "RUNNING",
          completed_at: null,
          duration_ms: null,
          is_stale: true,
        }),
        row({ id: "exec-live", status: "RUNNING", completed_at: null, duration_ms: null }),
      ]),
    );
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByText("1 running execution on this page looks stale.", {
        exact: false,
      }),
    ).toBeInTheDocument();
    // DataTable renders a desktop and a mobile layout; one stale row → two badges.
    expect(screen.getAllByText("Stale")).toHaveLength(2);
    expect(screen.getAllByText("In progress").length).toBeGreaterThan(0);
  });

  it("shows failure information and plain text for missing names", async () => {
    listMock.mockResolvedValue(
      listPage([
        row({
          id: "exec-failed",
          status: "FAILED",
          failure_category: "PROVIDER_ERROR",
          error_preview: "Provider timed out",
          agent_name: null,
          lead_name: null,
        }),
        row({ id: "exec-no-lead", lead_id: null, lead_name: null }),
      ]),
    );
    render(<AgentExecutionsPage />);
    expect((await screen.findAllByText("Provider error")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Provider timed out").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unknown agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lead unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Unknown agent" })).not.toBeInTheDocument();
    expect(screen.getAllByText("No lead").length).toBeGreaterThan(0);
  });

  it("paginates with limit and offset", async () => {
    const user = userEvent.setup();
    listMock.mockImplementation(async (params) =>
      listPage([row({ id: `exec-${params?.offset ?? 0}` })], {
        offset: params?.offset ?? 0,
        total: 45,
      }),
    );
    render(<AgentExecutionsPage />);
    await screen.findByText("Showing 1–1 of 45");
    expect(screen.getByRole("button", { name: "Previous executions page" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next executions page" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions?offset=20", {
      scroll: false,
    });
    await screen.findByText("Showing 21–21 of 45");
    expect(lastListParams()?.offset).toBe(20);
    expect(screen.getByRole("button", { name: "Previous executions page" })).toBeEnabled();
  });

  it("offers a way back when the offset is past the last page", async () => {
    const user = userEvent.setup();
    currentSearch = "offset=200";
    listMock.mockImplementation(async (params) =>
      params?.offset
        ? listPage([], { offset: params.offset, total: 3 })
        : listPage([row()], { total: 3 }),
    );
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByRole("heading", { level: 3, name: "No executions on this page" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Go to first page" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions", {
      scroll: false,
    });
  });

  it("shows an empty state when the organization has no runs", async () => {
    listMock.mockResolvedValue(
      listPage([], {
        status_counts: { QUEUED: 0, RUNNING: 0, COMPLETED: 0, FAILED: 0, CANCELLED: 0 },
      }),
    );
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByRole("heading", { level: 3, name: "No agent executions yet" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open AI Agents" })).toHaveAttribute(
      "href",
      "/agents",
    );
  });

  it("shows a filtered empty state with clear filters", async () => {
    const user = userEvent.setup();
    currentSearch = "status=CANCELLED";
    listMock.mockResolvedValue(listPage([]));
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByRole("heading", {
        level: 3,
        name: "No executions match these filters",
      }),
    ).toBeInTheDocument();
    const clearButtons = screen.getAllByRole("button", { name: "Clear filters" });
    await user.click(clearButtons.at(-1)!);
    expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions", {
      scroll: false,
    });
  });

  it("shows an error with retry and recovers", async () => {
    const user = userEvent.setup();
    listMock.mockRejectedValueOnce(new Error("network"));
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByText("Agent executions could not be loaded. Please try again."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 3, name: "Agent executions could not be loaded" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect((await screen.findAllByRole("link", { name: "Sales Agent" })).length).toBeGreaterThan(0);
    expect(listMock).toHaveBeenCalledTimes(2);
  });

  it("explains expired sessions and missing permission", async () => {
    listMock.mockRejectedValueOnce(new ApiError("Request failed: 401", 401));
    const { unmount } = render(<AgentExecutionsPage />);
    expect(
      await screen.findByText("Your session has expired. Sign in again to view this history."),
    ).toBeInTheDocument();
    unmount();

    listMock.mockRejectedValueOnce(new ApiError("Request failed: 403", 403));
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByText("You do not have permission to view this history."),
    ).toBeInTheDocument();
  });

  it("keeps the list usable when agents cannot be loaded", async () => {
    getAgentsMock.mockRejectedValue(new Error("network"));
    render(<AgentExecutionsPage />);
    expect(
      await screen.findByText("Agents could not be loaded, so the agent filter is unavailable."),
    ).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Agent" })).toBeDisabled();
    expect(screen.getAllByRole("link", { name: "Sales Agent" }).length).toBeGreaterThan(0);
  });

  it("refreshes without polling", async () => {
    const user = userEvent.setup();
    render(<AgentExecutionsPage />);
    await screen.findAllByRole("link", { name: "Sales Agent" });
    expect(listMock).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
  });

  it("opens the existing execution detail panel for the row's agent", async () => {
    const user = userEvent.setup();
    const detail: AgentExecutionDetail = {
      id: "exec-1",
      agent_id: "agent-1",
      status: "COMPLETED",
      input: "Qualify Acme Corp",
      output: "Qualified.",
      provider: "anthropic",
      model: "claude",
      usage: null,
      error: null,
      started_at: "2026-10-28T10:00:00Z",
      completed_at: "2026-10-28T10:00:02Z",
      created_at: "2026-10-28T10:00:00Z",
      initiated_by_user_id: "user-1",
      duration_ms: 2000,
      failure_category: null,
    };
    getAgentExecutionMock.mockResolvedValue(detail);
    listToolInvocationsMock.mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 });
    render(<AgentExecutionsPage />);
    const viewButtons = await screen.findAllByRole("button", { name: "View execution exec-1" });
    await user.click(viewButtons[0]!);

    expect(
      await screen.findByRole("heading", { name: "Execution detail" }),
    ).toBeInTheDocument();
    expect(getAgentExecutionMock).toHaveBeenCalledWith("agent-1", "exec-1");

    await user.click(screen.getByRole("button", { name: "Back to history" }));
    expect(screen.queryByRole("heading", { name: "Execution detail" })).not.toBeInTheDocument();

    // Any URL change, including browser back/forward, closes the panel.
    await user.click(viewButtons[0]!);
    expect(
      await screen.findByRole("heading", { name: "Execution detail" }),
    ).toBeInTheDocument();
    act(() => {
      currentSearch = "status=COMPLETED";
      notifySearchListeners();
    });
    expect(screen.queryByRole("heading", { name: "Execution detail" })).not.toBeInTheDocument();
    await waitFor(() => expect(lastListParams()?.status).toBe("COMPLETED"));
  });

  describe("execution deep links", () => {
    const detail: AgentExecutionDetail = {
      id: "exec-9",
      agent_id: "agent-2",
      status: "FAILED",
      input: "Qualify Beta",
      output: null,
      provider: "groq",
      model: "openai/gpt-oss-20b",
      usage: null,
      error: "Provider timed out",
      started_at: "2026-10-28T10:00:00Z",
      completed_at: "2026-10-28T10:00:05Z",
      created_at: "2026-10-28T10:00:00Z",
      initiated_by_user_id: null,
      duration_ms: 5000,
      failure_category: "PROVIDER_ERROR",
    };

    beforeEach(() => {
      getAgentExecutionMock.mockResolvedValue(detail);
      listToolInvocationsMock.mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 });
    });

    it("opens the linked execution with the agent from the URL", async () => {
      currentSearch = "agent_id=agent-2&execution=exec-9";
      render(<AgentExecutionsPage />);
      expect(
        await screen.findByRole("heading", { name: "Execution detail" }),
      ).toBeInTheDocument();
      expect(getAgentExecutionMock).toHaveBeenCalledWith("agent-2", "exec-9");
      expect(listMock).toHaveBeenCalledTimes(1);
      expect(lastListParams()).toMatchObject({ agentId: "agent-2", offset: 0 });
      expect(lastListParams()).not.toHaveProperty("execution");
    });

    it("keeps the list request unchanged when a panel opens or closes", async () => {
      const user = userEvent.setup();
      getAgentExecutionMock.mockResolvedValue({ ...detail, id: "exec-1", agent_id: "agent-1" });
      render(<AgentExecutionsPage />);
      const viewButtons = await screen.findAllByRole("button", {
        name: "View execution exec-1",
      });
      await user.click(viewButtons[0]!);
      expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions?execution=exec-1", {
        scroll: false,
      });
      expect(
        await screen.findByRole("heading", { name: "Execution detail" }),
      ).toBeInTheDocument();
      expect(getAgentExecutionMock).toHaveBeenCalledWith("agent-1", "exec-1");

      await user.click(screen.getByRole("button", { name: "Back to history" }));
      expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions", { scroll: false });
      expect(listMock).toHaveBeenCalledTimes(1);
    });

    it("drops the open execution when filters change", async () => {
      const user = userEvent.setup();
      currentSearch = "agent_id=agent-2&execution=exec-9";
      render(<AgentExecutionsPage />);
      await screen.findByRole("heading", { name: "Execution detail" });
      await user.selectOptions(
        screen.getByRole("combobox", { name: "Execution status" }),
        "FAILED",
      );
      expect(mockReplace).toHaveBeenLastCalledWith(
        "/agents/executions?status=FAILED&agent_id=agent-2",
        { scroll: false },
      );
      expect(screen.queryByRole("heading", { name: "Execution detail" })).not.toBeInTheDocument();
    });

    it("shows the existing not-found state for a missing or inaccessible execution", async () => {
      getAgentExecutionMock.mockRejectedValue(new ApiError("Request failed: 404", 404));
      currentSearch = "agent_id=agent-2&execution=exec-missing";
      render(<AgentExecutionsPage />);
      expect(
        await screen.findByText("This execution could not be found."),
      ).toBeInTheDocument();
      expect(screen.getAllByRole("link", { name: "Sales Agent" }).length).toBeGreaterThan(0);
    });

    it("explains when a linked execution has no agent to load it with", async () => {
      const user = userEvent.setup();
      currentSearch = "execution=exec-unknown";
      render(<AgentExecutionsPage />);
      expect(
        await screen.findByRole("heading", {
          level: 3,
          name: "This execution could not be opened",
        }),
      ).toBeInTheDocument();
      expect(getAgentExecutionMock).not.toHaveBeenCalled();
      await user.click(screen.getByRole("button", { name: "Close" }));
      expect(mockReplace).toHaveBeenLastCalledWith("/agents/executions", { scroll: false });
    });
  });

  it.each(["OWNER", "ADMIN", "MEMBER"] as const)(
    "gives %s the same read-only view",
    async (role) => {
      setRole(role);
      render(<AgentExecutionsPage />);
      await screen.findAllByRole("link", { name: "Sales Agent" });
      for (const name of [
        /^run agent$/i,
        /^start/i,
        /^cancel( execution| run)?$/i,
        /^retry execution$/i,
        /^delete/i,
        /^recover/i,
      ]) {
        expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
      }
      expect(
        screen.getAllByRole("button", { name: "View execution exec-1" }).length,
      ).toBeGreaterThan(0);
    },
  );
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ActivityPage from "@/app/(app)/activity/page";
import { getActivity, listActivity } from "@/lib/api/activity";
import type { ActivityEvent, ActivityListResponse } from "@/types/api";

vi.mock("@/lib/api/activity", () => ({
  listActivity: vi.fn(),
  getActivity: vi.fn(),
}));

const listActivityMock = vi.mocked(listActivity);
const getActivityMock = vi.mocked(getActivity);

const event: ActivityEvent = {
  id: "event-1",
  type: "AI_ACTION",
  title: "Lead qualified",
  summary: "AI completed enquiry qualification for this lead.",
  occurred_at: "2026-09-17T10:00:00Z",
  actor_type: "AGENT",
  actor_user_id: null,
  agent_id: "agent-1",
  entity_type: "LEAD_QUALIFICATION",
  entity_id: "qual-1",
  lead_id: "lead-1",
  status: "COMPLETED",
  sales_run_id: null,
  execution_id: null,
  email_send_id: null,
  follow_up_id: null,
  follow_up_execution_id: null,
  draft_id: null,
  qualification_id: "qual-1",
};

function pageOf(items: ActivityEvent[], total = items.length): ActivityListResponse {
  return {
    items,
    limit: 20,
    offset: 0,
    total,
    type_counts: {
      AI_ACTION: items.filter((item) => item.type === "AI_ACTION").length,
      APPROVAL: 0,
      HUMAN_ACTION: 0,
      SYSTEM_EVENT: 0,
    },
  };
}

describe("Activity page", () => {
  beforeEach(() => {
    listActivityMock.mockReset();
    getActivityMock.mockReset();
    listActivityMock.mockResolvedValue(pageOf([]));
    getActivityMock.mockResolvedValue(event);
  });

  it("renders loading then empty state without fabricated events", async () => {
    render(<ActivityPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Activity" })).toBeVisible();
    expect(await screen.findByRole("heading", { name: "No activity yet" })).toBeVisible();
    expect(screen.queryByText("Example event")).not.toBeInTheDocument();
    expect(listActivityMock).toHaveBeenCalled();
  });

  it("shows error and retry", async () => {
    listActivityMock.mockRejectedValueOnce(new Error("network"));
    render(<ActivityPage />);
    expect(
      await screen.findByRole("heading", { name: "Activity could not be loaded" }),
    ).toBeVisible();
    listActivityMock.mockResolvedValueOnce(pageOf([]));
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: "No activity yet" })).toBeVisible();
  });

  it("renders populated activity and loads detail on select", async () => {
    listActivityMock.mockResolvedValue(pageOf([event]));
    render(<ActivityPage />);
    expect(await screen.findByText("Lead qualified")).toBeVisible();
    expect(screen.getByText("AI actions")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: /Lead qualified/ }));
    await waitFor(() => expect(getActivityMock).toHaveBeenCalledWith("event-1"));
    expect(await screen.findByText(event.summary!)).toBeVisible();
    expect(screen.getByRole("link", { name: "Open lead" })).toHaveAttribute(
      "href",
      "/leads/lead-1",
    );
  });

  it("sends search, type, and entity filters to the API", async () => {
    const user = userEvent.setup();
    render(<ActivityPage />);
    await screen.findByRole("heading", { name: "No activity yet" });
    await user.type(screen.getByRole("searchbox", { name: "Search activity" }), "qualified");
    await user.selectOptions(screen.getByRole("combobox", { name: "Event type" }), "AI_ACTION");
    await user.selectOptions(screen.getByRole("combobox", { name: "Entity type" }), "LEAD");
    await waitFor(() => {
      expect(listActivityMock).toHaveBeenCalledWith(
        expect.objectContaining({
          q: "qualified",
          type: "AI_ACTION",
          entity_type: "LEAD",
        }),
      );
    });
  });

  it("paginates with next", async () => {
    listActivityMock.mockResolvedValue({
      ...pageOf([event], 21),
      total: 21,
    });
    render(<ActivityPage />);
    expect(await screen.findByText("Showing 1–20 of 21")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(listActivityMock).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 20, limit: 20 }),
      );
    });
  });

  it("keeps mobile timeline and detail navigation", async () => {
    const user = userEvent.setup();
    render(<ActivityPage />);
    await screen.findByRole("heading", { name: "No activity yet" });
    const timelineButton = screen.getByRole("button", { name: "Timeline" });
    const detailButton = screen.getByRole("button", { name: "Event detail" });
    expect(timelineButton).toHaveAttribute("aria-pressed", "true");
    await user.click(detailButton);
    expect(detailButton).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Back to activity timeline" }));
    expect(timelineButton).toHaveAttribute("aria-pressed", "true");
  });
});

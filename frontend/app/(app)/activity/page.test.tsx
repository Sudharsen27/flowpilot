import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ActivityPage from "@/app/(app)/activity/page";
import { ActivityDetail } from "@/components/activity/activity-detail";
import {
  ActivityTimeline,
  type ActivityEventItem,
} from "@/components/activity/activity-timeline";

describe("Activity page", () => {
  it("renders the page hierarchy and honest unavailable summary", () => {
    render(<ActivityPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Activity" }),
    ).toBeVisible();
    for (const section of [
      "Activity summary",
      "Activity workspace",
      "Event and audit context",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Events",
      "AI actions",
      "Workflow events",
      "Human actions",
    ];
    expect(metricCards).toHaveLength(metricLabels.length);
    metricLabels.forEach((label, index) => {
      expect(
        within(metricCards[index]).getByRole("heading", {
          level: 3,
          name: label,
        }),
      ).toBeVisible();
    });
    expect(screen.getAllByText("—")).toHaveLength(4);
  });

  it("provides accessible, locally resettable activity filters", async () => {
    const user = userEvent.setup();
    render(<ActivityPage />);

    const search = screen.getByRole("searchbox", { name: "Search activity" });
    const eventType = screen.getByRole("combobox", { name: "Event type" });
    const actor = screen.getByRole("combobox", { name: "Actor or source" });
    const status = screen.getByRole("combobox", { name: "Event status" });

    await user.type(search, "Example");
    await user.selectOptions(eventType, "workflow");
    await user.selectOptions(actor, "person");
    await user.selectOptions(status, "completed");
    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(search).toHaveValue("");
    expect(eventType).toHaveValue("all");
    expect(actor).toHaveValue("all");
    expect(status).toHaveValue("all");
    expect(
      screen.getByText(
        /Filters are ready for use when an activity event source is connected/,
      ),
    ).toBeVisible();
  });

  it("shows an honest empty timeline without fabricated events", () => {
    render(<ActivityPage />);

    expect(
      screen.getByRole("heading", { name: "No activity recorded" }),
    ).toBeVisible();
    expect(screen.getByText(/begin performing real work/)).toBeVisible();
    expect(
      screen.queryByRole("list", { name: "Activity timeline" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Example event")).not.toBeInTheDocument();
  });

  it("renders an honest empty event detail foundation", () => {
    render(<ActivityPage />);

    const detail = screen
      .getByRole("heading", { name: "Event detail" })
      .closest("section");
    expect(detail).not.toBeNull();
    expect(
      within(detail!).getByRole("heading", { name: "No event selected" }),
    ).toBeVisible();
    for (const field of [
      "Event type",
      "Actor",
      "Description",
      "Related object",
      "Timestamp",
      "Status",
      "Details and context",
    ]) {
      expect(within(detail!).getByText(field)).toBeVisible();
    }
    expect(within(detail!).getAllByText("No event selected.")).toHaveLength(7);
  });

  it("renders all event-type concepts and audit questions", () => {
    render(<ActivityPage />);

    const concepts = screen.getByRole("list", {
      name: "Activity event type concepts",
    });
    for (const eventType of [
      "AI action",
      "Workflow",
      "Approval",
      "Integration",
      "Human action",
      "System event",
    ]) {
      expect(within(concepts).getByText(eventType)).toBeVisible();
    }
    for (const question of [
      "What happened",
      "When it happened",
      "Which agent or person initiated it",
      "Which system or workflow was involved",
    ]) {
      expect(screen.getByText(question)).toBeVisible();
    }
    expect(
      screen.getByText(
        /No audit-log persistence, event ingestion, or compliance guarantee/,
      ),
    ).toBeVisible();
  });

  it("provides clear mobile detail and back navigation", async () => {
    const user = userEvent.setup();
    render(<ActivityPage />);

    const timelineButton = screen.getByRole("button", { name: "Timeline" });
    const detailButton = screen.getByRole("button", { name: "Event detail" });
    const timelinePane = document.querySelector("#activity-timeline-pane");
    const detailPane = document.querySelector("#activity-detail-pane");

    expect(timelineButton).toHaveAttribute("aria-pressed", "true");
    expect(timelinePane).toHaveClass("block");
    expect(detailPane).toHaveClass("hidden");

    await user.click(detailButton);
    expect(detailButton).toHaveAttribute("aria-pressed", "true");
    expect(timelinePane).toHaveClass("hidden");
    expect(detailPane).toHaveClass("block");

    await user.click(
      screen.getByRole("button", { name: "Back to activity timeline" }),
    );
    expect(timelineButton).toHaveAttribute("aria-pressed", "true");
    expect(timelinePane).toHaveClass("block");
    expect(detailPane).toHaveClass("hidden");
  });

  it("renders keyboard-accessible timeline rows for real events", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const event: ActivityEventItem = {
      id: "event-1",
      type: "workflow",
      actor: "Test actor",
      description: "Test event description",
      relatedObject: "Test workflow",
      status: "completed",
      timestamp: "Test timestamp",
      details: "Test event details",
    };

    render(
      <ActivityTimeline
        events={[event]}
        selectedId={event.id}
        onSelect={onSelect}
      />,
    );

    const row = screen.getByRole("button", {
      name: /Test event description/,
    });
    expect(
      screen.getByRole("list", { name: "Activity timeline" }),
    ).toBeVisible();
    expect(row).toHaveAttribute("aria-pressed", "true");
    expect(within(row).getByText("Workflow")).toBeVisible();
    expect(within(row).getByText("Completed")).toBeVisible();

    await user.click(row);
    expect(onSelect).toHaveBeenCalledWith(event);
  });

  it("renders supplied event detail without adding actions", () => {
    const event: ActivityEventItem = {
      id: "event-1",
      type: "human-action",
      actor: "Test actor",
      description: "Test event description",
      relatedObject: "Test object",
      status: "information",
      timestamp: "Test timestamp",
      details: "Test details",
    };

    render(<ActivityDetail event={event} />);

    expect(screen.getByText("Human action")).toBeVisible();
    expect(screen.getByText("Test actor")).toBeVisible();
    expect(screen.getByText("Test timestamp")).toBeVisible();
    expect(screen.getByText("Test details")).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

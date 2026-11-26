import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EntityActivityTimeline } from "@/components/activity/entity-activity-timeline";
import { getActivity, listActivity } from "@/lib/api/activity";
import type {
  ActivityEntityType,
  ActivityEvent,
  ActivityListParams,
  ActivityListResponse,
} from "@/types/api";

vi.mock("@/lib/api/activity", () => ({
  getActivity: vi.fn(),
  listActivity: vi.fn(),
}));

const getActivityMock = vi.mocked(getActivity);
const listActivityMock = vi.mocked(listActivity);

function activityEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: "event-1",
    type: "HUMAN_ACTION",
    title: "Contact created",
    summary: null,
    occurred_at: "2026-10-28T10:00:00Z",
    actor_type: "USER",
    actor_user_id: "user-1",
    agent_id: null,
    entity_type: "CONTACT",
    entity_id: "contact-1",
    lead_id: null,
    status: "CREATED",
    sales_run_id: null,
    execution_id: null,
    email_send_id: null,
    follow_up_id: null,
    follow_up_execution_id: null,
    draft_id: null,
    qualification_id: null,
    ...overrides,
  };
}

function activityPage(
  items: ActivityEvent[],
  total = items.length,
  offset = 0,
): ActivityListResponse {
  return {
    items,
    limit: 20,
    offset,
    total,
    type_counts: {
      AI_ACTION: 0,
      APPROVAL: 0,
      HUMAN_ACTION: items.filter((item) => item.type === "HUMAN_ACTION").length,
      SYSTEM_EVENT: 0,
    },
  };
}

function renderTimeline(
  entityType: Extract<ActivityEntityType, "CONTACT" | "COMPANY"> = "CONTACT",
  entityId = "contact-1",
) {
  return render(
    <EntityActivityTimeline entityType={entityType} entityId={entityId} />,
  );
}

describe("EntityActivityTimeline", () => {
  beforeEach(() => {
    listActivityMock.mockReset();
    getActivityMock.mockReset();
    listActivityMock.mockResolvedValue(activityPage([]));
    getActivityMock.mockResolvedValue(
      activityEvent({ summary: "Complete activity detail." }),
    );
  });

  it("shows loading before the initial event page resolves", async () => {
    let resolvePage!: (page: ActivityListResponse) => void;
    listActivityMock.mockImplementationOnce(
      () =>
        new Promise<ActivityListResponse>((resolve) => {
          resolvePage = resolve;
        }),
    );

    renderTimeline();

    expect(screen.getByText("Loading activity")).toBeVisible();
    await act(async () => resolvePage(activityPage([activityEvent()])));

    expect(
      await screen.findByRole("button", { name: /Contact created/ }),
    ).toBeVisible();
  });

  it("filters requests by Contact type and ID", async () => {
    listActivityMock.mockResolvedValueOnce(activityPage([activityEvent()]));

    renderTimeline("CONTACT", "contact-7");

    expect(
      await screen.findByRole("button", { name: /Contact created/ }),
    ).toBeVisible();
    expect(listActivityMock).toHaveBeenCalledWith(
      {
        entity_type: "CONTACT",
        entity_id: "contact-7",
        limit: 20,
        offset: 0,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("filters requests by Company type and ID", async () => {
    listActivityMock.mockResolvedValueOnce(
      activityPage([
        activityEvent({
          id: "event-company",
          title: "Company updated",
          entity_type: "COMPANY",
          entity_id: "company-4",
          status: "UPDATED",
        }),
      ]),
    );

    renderTimeline("COMPANY", "company-4");

    expect(
      await screen.findByRole("button", { name: /Company updated/ }),
    ).toBeVisible();
    expect(listActivityMock).toHaveBeenCalledWith(
      {
        entity_type: "COMPANY",
        entity_id: "company-4",
        limit: 20,
        offset: 0,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("renders populated events through the shared Activity timeline", async () => {
    listActivityMock.mockResolvedValueOnce(activityPage([activityEvent()]));

    renderTimeline();

    const timeline = await screen.findByRole("list", {
      name: "Activity timeline",
    });
    expect(within(timeline).getByText("Contact created")).toBeVisible();
    expect(within(timeline).getByText("Team member")).toBeVisible();
    expect(within(timeline).getByText("Contact")).toBeVisible();
  });

  it("shows the shared empty state when no matching events exist", async () => {
    renderTimeline();

    expect(
      await screen.findByRole("heading", { name: "No activity yet" }),
    ).toBeVisible();
  });

  it("shows a list error and retries the current page", async () => {
    const user = userEvent.setup();
    listActivityMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(activityPage([activityEvent()]));

    renderTimeline();

    expect(
      await screen.findByRole("heading", {
        name: "Activity could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("button", { name: /Contact created/ }),
    ).toBeVisible();
    expect(listActivityMock).toHaveBeenCalledTimes(2);
  });

  it("paginates by 20 without repeating or skipping the boundary event", async () => {
    const user = userEvent.setup();
    const firstPageEvents = Array.from({ length: 20 }, (_, index) =>
      activityEvent({
        id: `event-${index + 1}`,
        title: `Event ${index + 1}`,
      }),
    );
    const twentyFirstEvent = activityEvent({
      id: "event-21",
      title: "Event 21",
    });
    listActivityMock.mockImplementation(
      async (params: ActivityListParams = {}) =>
        params.offset === 20
          ? activityPage([twentyFirstEvent], 21, 20)
          : activityPage(firstPageEvents, 21, 0),
    );

    renderTimeline();

    let timeline = await screen.findByRole("list", {
      name: "Activity timeline",
    });
    expect(within(timeline).getAllByRole("button")).toHaveLength(20);
    expect(screen.getByText("Showing 1–20 of 21")).toBeVisible();
    expect(listActivityMock).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ limit: 20, offset: 0 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(
      await screen.findByRole("button", { name: /Event 21/ }),
    ).toBeVisible();
    timeline = screen.getByRole("list", { name: "Activity timeline" });
    expect(within(timeline).getAllByRole("button")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /Event 1/ })).toBeNull();
    expect(screen.getByText("Showing 21–21 of 21")).toBeVisible();
    expect(listActivityMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 20, offset: 20 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    await user.click(screen.getByRole("button", { name: "Previous" }));
    timeline = await screen.findByRole("list", {
      name: "Activity timeline",
    });
    expect(within(timeline).getAllByRole("button")).toHaveLength(20);
    expect(screen.queryByRole("button", { name: /Event 21/ })).toBeNull();
    expect(listActivityMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 20, offset: 0 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("fetches selected event detail and displays it after the detail loading state", async () => {
    const user = userEvent.setup();
    let resolveDetail!: (event: ActivityEvent) => void;
    listActivityMock.mockResolvedValueOnce(activityPage([activityEvent()]));
    getActivityMock.mockImplementationOnce(
      () =>
        new Promise<ActivityEvent>((resolve) => {
          resolveDetail = resolve;
        }),
    );

    renderTimeline();
    await user.click(
      await screen.findByRole("button", { name: /Contact created/ }),
    );

    expect(screen.getByText("Loading event detail")).toBeVisible();
    expect(getActivityMock).toHaveBeenCalledWith(
      "event-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    await act(async () =>
      resolveDetail(activityEvent({ summary: "Full selected event summary." })),
    );

    expect(
      await screen.findByText("Full selected event summary."),
    ).toBeVisible();
  });

  it("shows detail errors and retries the selected event", async () => {
    const user = userEvent.setup();
    getActivityMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(
        activityEvent({ summary: "Detail loaded after retry." }),
      );
    listActivityMock.mockResolvedValueOnce(activityPage([activityEvent()]));

    renderTimeline();
    await user.click(
      await screen.findByRole("button", { name: /Contact created/ }),
    );

    expect(
      await screen.findByText("Event details could not be loaded"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry detail" }));

    expect(await screen.findByText("Detail loaded after retry.")).toBeVisible();
    expect(getActivityMock).toHaveBeenCalledTimes(2);
  });

  it("aborts a pending list request when unmounted", async () => {
    let signal: AbortSignal | undefined;
    listActivityMock.mockImplementationOnce(
      (_params, options) =>
        new Promise<ActivityListResponse>(() => {
          signal = options?.signal;
        }),
    );

    const view = renderTimeline();
    await waitFor(() => expect(signal).toBeDefined());

    view.unmount();
    expect(signal?.aborted).toBe(true);
  });

  it("aborts a pending detail request when unmounted", async () => {
    const user = userEvent.setup();
    let signal: AbortSignal | undefined;
    listActivityMock.mockResolvedValueOnce(activityPage([activityEvent()]));
    getActivityMock.mockImplementationOnce(
      (_eventId, options) =>
        new Promise<ActivityEvent>(() => {
          signal = options?.signal;
        }),
    );

    const view = renderTimeline();
    await user.click(
      await screen.findByRole("button", { name: /Contact created/ }),
    );
    await waitFor(() => expect(signal).toBeDefined());

    view.unmount();
    expect(signal?.aborted).toBe(true);
  });

  it("aborts and ignores a stale list response after changing entity ID", async () => {
    let resolveOldPage!: (page: ActivityListResponse) => void;
    let oldSignal: AbortSignal | undefined;
    listActivityMock.mockImplementation(
      (params: ActivityListParams = {}, options) => {
        if (params.entity_id === "contact-1") {
          oldSignal = options?.signal;
          return new Promise<ActivityListResponse>((resolve) => {
            resolveOldPage = resolve;
          });
        }
        return Promise.resolve(
          activityPage([
            activityEvent({
              id: "current-event",
              entity_id: "contact-2",
              title: "Current entity event",
            }),
          ]),
        );
      },
    );

    const view = renderTimeline("CONTACT", "contact-1");
    await waitFor(() => expect(oldSignal).toBeDefined());
    view.rerender(
      <EntityActivityTimeline entityType="CONTACT" entityId="contact-2" />,
    );

    expect(
      await screen.findByRole("button", { name: /Current entity event/ }),
    ).toBeVisible();
    expect(oldSignal?.aborted).toBe(true);
    await act(async () =>
      resolveOldPage(
        activityPage([
          activityEvent({ id: "stale-event", title: "Stale entity event" }),
        ]),
      ),
    );
    expect(
      screen.queryByRole("button", { name: /Stale entity event/ }),
    ).toBeNull();
  });

  it("aborts and ignores stale event detail after changing entity ID", async () => {
    const user = userEvent.setup();
    let resolveOldDetail!: (event: ActivityEvent) => void;
    let detailSignal: AbortSignal | undefined;
    listActivityMock.mockImplementation(
      async (params: ActivityListParams = {}) =>
        activityPage([
          activityEvent({
            id: `${params.entity_id}-event`,
            entity_type: params.entity_type,
            entity_id: params.entity_id,
            title:
              params.entity_id === "contact-1"
                ? "Old entity row"
                : "New entity row",
          }),
        ]),
    );
    getActivityMock.mockImplementationOnce((_eventId, options) => {
      detailSignal = options?.signal;
      return new Promise<ActivityEvent>((resolve) => {
        resolveOldDetail = resolve;
      });
    });

    const view = renderTimeline("CONTACT", "contact-1");
    await user.click(
      await screen.findByRole("button", { name: /Old entity row/ }),
    );
    await waitFor(() => expect(detailSignal).toBeDefined());

    view.rerender(
      <EntityActivityTimeline entityType="COMPANY" entityId="company-2" />,
    );
    expect(
      await screen.findByRole("button", { name: /New entity row/ }),
    ).toBeVisible();
    expect(detailSignal?.aborted).toBe(true);

    await act(async () =>
      resolveOldDetail(
        activityEvent({
          title: "Stale event detail",
          summary: "Stale detail summary.",
        }),
      ),
    );
    expect(screen.queryByText("Stale detail summary.")).toBeNull();
    expect(
      screen.getByRole("heading", { name: "No event selected" }),
    ).toBeVisible();
  });

  it("resets pagination and selected detail when the entity scope changes", async () => {
    const user = userEvent.setup();
    listActivityMock.mockImplementation(
      async (params: ActivityListParams = {}) => {
        if (params.entity_id === "contact-1" && params.offset === 20) {
          return activityPage(
            [
              activityEvent({
                id: "second-page-event",
                title: "Second page event",
              }),
            ],
            21,
            20,
          );
        }
        if (params.entity_id === "company-2") {
          return activityPage([
            activityEvent({
              id: "company-event",
              title: "Company scope event",
              entity_type: "COMPANY",
              entity_id: "company-2",
            }),
          ]);
        }
        return activityPage(
          [activityEvent({ title: "First page event" })],
          21,
          0,
        );
      },
    );
    getActivityMock.mockImplementation(async (eventId) =>
      activityEvent({
        id: eventId,
        title: "Second page event",
        summary: "Selected second page detail.",
      }),
    );

    const view = renderTimeline();
    await user.click(await screen.findByRole("button", { name: "Next" }));
    await user.click(
      await screen.findByRole("button", { name: /Second page event/ }),
    );
    expect(
      await screen.findByText("Selected second page detail."),
    ).toBeVisible();

    view.rerender(
      <EntityActivityTimeline entityType="COMPANY" entityId="company-2" />,
    );
    expect(
      await screen.findByRole("button", { name: /Company scope event/ }),
    ).toBeVisible();
    expect(listActivityMock).toHaveBeenLastCalledWith(
      {
        entity_type: "COMPANY",
        entity_id: "company-2",
        limit: 20,
        offset: 0,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.queryByText("Selected second page detail.")).toBeNull();
    expect(
      screen.getByRole("heading", { name: "No event selected" }),
    ).toBeVisible();
  });
});

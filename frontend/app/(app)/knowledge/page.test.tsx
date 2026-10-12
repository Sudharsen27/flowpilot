import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import KnowledgePage from "@/app/(app)/knowledge/page";
import {
  createKnowledgeEntry,
  deleteKnowledgeEntry,
  listKnowledge,
  updateKnowledgeEntry,
} from "@/lib/api/knowledge";
import type {
  KnowledgeEntry,
  KnowledgeListResponse,
  MembershipRole,
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

vi.mock("@/lib/api/knowledge", () => ({
  listKnowledge: vi.fn(),
  createKnowledgeEntry: vi.fn(),
  updateKnowledgeEntry: vi.fn(),
  deleteKnowledgeEntry: vi.fn(),
}));

const listMock = vi.mocked(listKnowledge);
const createMock = vi.mocked(createKnowledgeEntry);
const updateMock = vi.mocked(updateKnowledgeEntry);
const deleteMock = vi.mocked(deleteKnowledgeEntry);

const entry: KnowledgeEntry = {
  id: "entry-1",
  category: "PRODUCT",
  title: "Pricing plans",
  content: "Starter costs $49 per month.",
  use_in_ai: true,
  status: "ACTIVE",
  revision: 2,
  created_at: "2026-10-10T10:00:00Z",
  updated_at: "2026-10-11T10:00:00Z",
};

function listOf(items: KnowledgeEntry[]): KnowledgeListResponse {
  return {
    items,
    total: items.length,
    category_counts: {
      FAQ: 0,
      PRODUCT: items.length,
      POLICY: 0,
      COMPANY: 0,
      OTHER: 0,
    },
  };
}

describe("Knowledge page", () => {
  beforeEach(() => {
    auth.role = "OWNER";
    listMock.mockReset();
    createMock.mockReset();
    updateMock.mockReset();
    deleteMock.mockReset();
    listMock.mockResolvedValue(listOf([entry]));
  });

  it("lists active entries with visible actions for owners", async () => {
    render(<KnowledgePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Knowledge" }),
    ).toBeVisible();
    const card = await screen.findByRole("article", { name: "Pricing plans" });
    expect(within(card).getByText("Product information")).toBeVisible();
    expect(
      within(card).getByRole("button", { name: "Edit Pricing plans" }),
    ).toBeVisible();
    expect(
      within(card).getByRole("button", { name: "Archive Pricing plans" }),
    ).toBeVisible();
    expect(
      within(card).getByRole("button", { name: "Delete Pricing plans" }),
    ).toBeVisible();
    expect(listMock).toHaveBeenCalledWith({
      category: null,
      status: "ACTIVE",
      q: "",
    });
  });

  it("guides an empty workspace to add the first entry", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue(listOf([]));
    createMock.mockResolvedValue({ ...entry, id: "entry-2", title: "Refunds" });
    render(<KnowledgePage />);

    const empty = await screen.findByRole("heading", {
      name: "Add your first knowledge entry",
    });
    expect(empty).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Add entry" })[0]!);

    const dialog = await screen.findByRole("dialog", {
      name: "Add knowledge entry",
    });
    const save = within(dialog).getByRole("button", { name: "Add entry" });
    expect(save).toBeDisabled();
    await user.selectOptions(
      within(dialog).getByLabelText(/Category/),
      "POLICY",
    );
    await user.type(within(dialog).getByLabelText(/Title/), "Refunds");
    await user.type(
      within(dialog).getByLabelText(/Content/),
      "Within 30 days.",
    );
    await user.click(
      within(dialog).getByRole("switch", { name: "Use in AI replies" }),
    );
    await user.click(save);

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith({
        category: "POLICY",
        title: "Refunds",
        content: "Within 30 days.",
        use_in_ai: false,
      }),
    );
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
  });

  it("edits with the current revision and explains conflicts", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api/client");
    updateMock.mockRejectedValue(new ApiError("conflict", 409));
    render(<KnowledgePage />);

    await user.click(
      await screen.findByRole("button", { name: "Edit Pricing plans" }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Edit knowledge entry",
    });
    const title = within(dialog).getByLabelText(/Title/);
    await user.clear(title);
    await user.type(title, "Plans");
    await user.click(
      within(dialog).getByRole("button", { name: "Save changes" }),
    );

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith(
        "entry-1",
        expect.objectContaining({ expected_revision: 2, title: "Plans" }),
      ),
    );
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      /Someone else changed/,
    );
  });

  it("archives and deletes only after confirmation", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue({ ...entry, status: "ARCHIVED", revision: 3 });
    deleteMock.mockResolvedValue(undefined);
    render(<KnowledgePage />);

    await user.click(
      await screen.findByRole("button", { name: "Archive Pricing plans" }),
    );
    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("entry-1", {
        expected_revision: 2,
        status: "ARCHIVED",
      }),
    );

    await user.click(
      await screen.findByRole("button", { name: "Delete Pricing plans" }),
    );
    expect(deleteMock).not.toHaveBeenCalled();
    const confirm = await screen.findByRole("dialog", {
      name: "Delete this entry?",
    });
    await user.click(
      within(confirm).getByRole("button", { name: "Delete entry" }),
    );
    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("entry-1"));
  });

  it("searches and filters through the API", async () => {
    const user = userEvent.setup();
    render(<KnowledgePage />);
    await screen.findByRole("article", { name: "Pricing plans" });

    await user.type(
      screen.getByRole("searchbox", { name: "Search knowledge" }),
      "refund",
    );
    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith({
        category: null,
        status: "ACTIVE",
        q: "refund",
      }),
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Status" }),
      "ARCHIVED",
    );
    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith({
        category: null,
        status: "ARCHIVED",
        q: "refund",
      }),
    );
  });

  it("shows members the entries without management actions", async () => {
    auth.role = "MEMBER";
    render(<KnowledgePage />);

    await screen.findByRole("article", { name: "Pricing plans" });
    expect(
      screen.getByText("Only owners and admins can add or change knowledge."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /Add entry|Edit|Archive|Delete/ }),
    ).toBeNull();
  });

  it("offers a retry when loading fails", async () => {
    const user = userEvent.setup();
    listMock.mockRejectedValueOnce(new Error("offline"));
    render(<KnowledgePage />);

    expect(
      await screen.findByText("Knowledge could not be loaded"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("article", { name: "Pricing plans" }),
    ).toBeVisible();
  });
});

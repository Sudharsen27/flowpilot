import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CompanyProspectsPage from "@/app/(app)/company-prospects/page";
import {
  createCompanyProspect,
  getCompanyProspects,
} from "@/lib/api/company-prospects";
import type {
  CompanyProspect,
  CompanyProspectListResponse,
  MembershipRole,
} from "@/types/api";

const auth = vi.hoisted(() => ({ role: "OWNER" as MembershipRole }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

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

vi.mock("@/lib/api/company-prospects", () => ({
  getCompanyProspects: vi.fn(),
  createCompanyProspect: vi.fn(),
}));

const listMock = vi.mocked(getCompanyProspects);
const createMock = vi.mocked(createCompanyProspect);

const prospect: CompanyProspect = {
  id: "company-1",
  name: "Acme Systems",
  website_domain: "acme.example",
  name_evidence_quality: "SOURCE_REPORTED",
  website_domain_evidence_quality: "ESTIMATED",
  status: "IDENTIFIED",
  created_at: "2026-01-01T12:00:00Z",
  updated_at: "2026-01-02T12:00:00Z",
};

function page(
  items: CompanyProspect[] = [prospect],
  total = items.length,
): CompanyProspectListResponse {
  return { items, total, limit: 20, offset: 0 };
}

describe("CompanyProspectsPage", () => {
  beforeEach(() => {
    auth.role = "OWNER";
    listMock.mockReset();
    createMock.mockReset();
    listMock.mockResolvedValue(page());
    createMock.mockResolvedValue(prospect);
  });

  it("lists tenant-scoped prospects and shows management controls for owners/admins", async () => {
    render(<CompanyProspectsPage />);

    expect(
      await screen.findByRole("heading", { name: "Company Prospects" }),
    ).toBeVisible();
    expect(
      (await screen.findAllByRole("link", { name: "Acme Systems" }))[0],
    ).toHaveAttribute("href", "/company-prospects/company-1");
    expect(screen.getAllByText("acme.example")[0]).toBeVisible();
    expect(screen.getAllByText("Source reported")[0]).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Add company prospect" }),
    ).toBeVisible();
  });

  it("hides management controls for members", async () => {
    auth.role = "MEMBER";
    render(<CompanyProspectsPage />);

    expect(
      await screen.findByRole("heading", { name: "Company Prospects" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Add company prospect" }),
    ).toBeNull();
  });

  it("sends search and status filters to the API and resets pagination", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue(page([prospect], 41));
    render(<CompanyProspectsPage />);

    await screen.findByText("Showing 1–20 of 41");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith({
        q: undefined,
        status: undefined,
        limit: 20,
        offset: 20,
      }),
    );

    await user.type(
      screen.getByRole("searchbox", { name: "Search company prospects" }),
      "  acme  ",
    );
    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith({
        q: "acme",
        status: undefined,
        limit: 20,
        offset: 0,
      }),
    );

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Lifecycle status" }),
      "REVIEWED",
    );
    await waitFor(() =>
      expect(listMock).toHaveBeenLastCalledWith({
        q: "acme",
        status: "REVIEWED",
        limit: 20,
        offset: 0,
      }),
    );
  });

  it("renders an empty state and retries a failed list request", async () => {
    const user = userEvent.setup();
    listMock
      .mockResolvedValueOnce(page([]))
      .mockRejectedValueOnce(new Error("offline"));
    render(<CompanyProspectsPage />);

    expect(
      await screen.findByRole("heading", { name: "No company prospects found" }),
    ).toBeVisible();
    await user.type(
      screen.getByRole("searchbox", { name: "Search company prospects" }),
      "x",
    );
    expect(
      await screen.findByText("Company prospects could not be loaded"),
    ).toBeVisible();

    listMock.mockResolvedValueOnce(page());
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect((await screen.findAllByText("Acme Systems"))[0]).toBeVisible();
  });
});

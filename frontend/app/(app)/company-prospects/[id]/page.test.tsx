import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CompanyProspectDetailPage from "@/app/(app)/company-prospects/[id]/page";
import { ApiError } from "@/lib/api/client";
import { getCompanyProspect } from "@/lib/api/company-prospects";
import type { CompanyProspect, MembershipRole } from "@/types/api";

const route = vi.hoisted(() => ({ id: "company-1" }));
const auth = vi.hoisted(() => ({ role: "OWNER" as MembershipRole }));

vi.mock("next/navigation", () => ({
  useParams: () => route,
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
  getCompanyProspect: vi.fn(),
  updateCompanyProspectLifecycle: vi.fn(),
}));

const getMock = vi.mocked(getCompanyProspect);

const prospect: CompanyProspect = {
  id: "company-1",
  name: "Acme Systems",
  website_domain: "acme.example",
  name_evidence_quality: "SOURCE_REPORTED",
  website_domain_evidence_quality: "INFERRED",
  status: "REVIEWED",
  created_at: "2026-01-01T12:00:00Z",
  updated_at: "2026-01-02T12:00:00Z",
};

describe("CompanyProspectDetailPage", () => {
  beforeEach(() => {
    auth.role = "OWNER";
    route.id = "company-1";
    getMock.mockReset();
    getMock.mockResolvedValue(prospect);
  });

  it("shows persisted company information, evidence labels, and management actions", async () => {
    render(<CompanyProspectDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Acme Systems" }),
    ).toBeVisible();
    expect(screen.getByText("acme.example")).toBeVisible();
    expect(screen.getByText("Source reported")).toBeVisible();
    expect(screen.getByText("Inferred")).toBeVisible();
    expect(screen.getByText("Reviewed")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Mark identified" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Archive" })).toBeVisible();
    expect(getMock).toHaveBeenCalledWith("company-1");
  });

  it("shows read-only notice for members instead of action buttons", async () => {
    auth.role = "MEMBER";
    render(<CompanyProspectDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Acme Systems" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Management actions \(review, archive, restore\) require Owner or Admin permissions\./,
      ),
    ).toBeVisible();
  });

  it("renders a not-found state for tenant-scoped 404 responses", async () => {
    getMock.mockRejectedValue(new ApiError("missing", 404));
    render(<CompanyProspectDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Company prospect not found" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Back to Company Prospects" }),
    ).toHaveAttribute("href", "/company-prospects");
  });

  it("shows loading and retryable generic error states", async () => {
    let resolve: ((value: CompanyProspect) => void) | undefined;
    getMock.mockImplementationOnce(
      () =>
        new Promise<CompanyProspect>((result) => {
          resolve = result;
        }),
    );
    render(<CompanyProspectDetailPage />);

    expect(
      screen.getByRole("heading", { name: "Loading company prospect" }),
    ).toBeVisible();
    resolve?.(prospect);
    expect(
      await screen.findByRole("heading", { name: "Acme Systems" }),
    ).toBeVisible();
  });

  it("retries a generic load error", async () => {
    const user = userEvent.setup();
    getMock
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(prospect);
    render(<CompanyProspectDetailPage />);

    expect(
      await screen.findByRole("heading", {
        name: "Company prospect unavailable",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("heading", { name: "Acme Systems" }),
    ).toBeVisible();
  });
});

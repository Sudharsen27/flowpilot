import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CompanyProspectDetailPage from "@/app/(app)/company-prospects/[id]/page";
import { ApiError } from "@/lib/api/client";
import {
  getCompanyProspect,
  getCompanyProspectDuplicateAssessment,
} from "@/lib/api/company-prospects";
import type {
  CompanyDuplicateAssessmentItem,
  CompanyDuplicateAssessmentResponse,
  CompanyProspect,
  MembershipRole,
} from "@/types/api";

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
  getCompanyProspectDuplicateAssessment: vi.fn(),
  updateCompanyProspectLifecycle: vi.fn(),
}));

const getMock = vi.mocked(getCompanyProspect);
const assessMock = vi.mocked(getCompanyProspectDuplicateAssessment);

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

const matchedProspect: CompanyProspect = {
  ...prospect,
  id: "company-2",
  name: "Acme Systems Limited",
  website_domain: "acme-systems.example",
};

function assessmentResponse(
  item: Partial<CompanyDuplicateAssessmentItem> = {},
): CompanyDuplicateAssessmentResponse {
  return {
    assessments: [
      {
        reference_id: "company-1",
        outcome: "NEW",
        reason_code: "NO_MATCHING_RECORDS",
        explanation: "No matching record was found using the supported evidence.",
        matching_fields: [],
        existing_match_references: [],
        in_batch_match_reference: null,
        ...item,
      },
    ],
    total_evaluated: 1,
    persisted_cin_available: false,
  };
}

const possibleDuplicate = assessmentResponse({
  outcome: "POSSIBLE_DUPLICATE",
  reason_code: "PERSISTED_NAME_SIMILARITY",
  explanation: "Company name closely matches an existing prospect.",
  matching_fields: ["company_name"],
  existing_match_references: ["company-2"],
});

describe("CompanyProspectDetailPage", () => {
  beforeEach(() => {
    auth.role = "OWNER";
    route.id = "company-1";
    getMock.mockReset();
    getMock.mockImplementation(async (id: string) =>
      id === matchedProspect.id ? matchedProspect : prospect,
    );
    assessMock.mockReset();
    assessMock.mockResolvedValue(assessmentResponse());
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

  describe("duplicate review", () => {
    it("shows a loading state while the assessment is pending", async () => {
      assessMock.mockImplementationOnce(() => new Promise(() => {}));
      render(<CompanyProspectDetailPage />);

      expect(
        await screen.findByText("Checking for duplicate company prospects…"),
      ).toBeVisible();
      expect(screen.getByRole("heading", { name: "Duplicate review" })).toBeVisible();
    });

    it("shows the no-match state for a NEW outcome", async () => {
      render(<CompanyProspectDetailPage />);

      expect(await screen.findByText("No match found")).toBeVisible();
      expect(
        screen.getByText("No matching record was found using the supported evidence."),
      ).toBeVisible();
      expect(
        screen.getByText(
          "No other company prospects in your organization match this record.",
        ),
      ).toBeVisible();
      expect(screen.queryByText(/Matched fields:/)).toBeNull();
      expect(assessMock).toHaveBeenCalledWith("company-1");
    });

    it("shows a possible duplicate with matched fields and a named link", async () => {
      assessMock.mockResolvedValue(possibleDuplicate);
      render(<CompanyProspectDetailPage />);

      expect(await screen.findByText("Possible duplicate")).toBeVisible();
      expect(
        screen.getByText("Company name closely matches an existing prospect."),
      ).toBeVisible();
      expect(screen.getByText("Matched fields: Company name")).toBeVisible();
      expect(
        screen.getByRole("link", { name: "Acme Systems Limited" }),
      ).toHaveAttribute("href", "/company-prospects/company-2");
      expect(getMock).toHaveBeenCalledWith("company-2");
    });

    it("never links the prospect to itself", async () => {
      assessMock.mockResolvedValue(
        assessmentResponse({
          outcome: "POSSIBLE_DUPLICATE",
          matching_fields: ["company_name"],
          existing_match_references: ["company-1", "company-2"],
        }),
      );
      render(<CompanyProspectDetailPage />);

      expect(
        await screen.findByRole("link", { name: "Acme Systems Limited" }),
      ).toBeVisible();
      const hrefs = screen
        .getAllByRole("link")
        .map((link) => link.getAttribute("href"));
      expect(hrefs).not.toContain("/company-prospects/company-1");
      const matchedList = screen.getByRole("list", {
        name: "Matched company prospects",
      });
      expect(within(matchedList).getAllByRole("listitem")).toHaveLength(1);
    });

    it("falls back to a generic label when a matched prospect cannot be loaded", async () => {
      assessMock.mockResolvedValue(possibleDuplicate);
      getMock.mockImplementation(async (id: string) => {
        if (id === matchedProspect.id) throw new ApiError("missing", 404);
        return prospect;
      });
      render(<CompanyProspectDetailPage />);

      expect(
        await screen.findByRole("link", { name: "Matched prospect" }),
      ).toHaveAttribute("href", "/company-prospects/company-2");
    });

    it.each([
      ["EXACT_MATCH", "Exact duplicate found"],
      ["INSUFFICIENT_DATA", "Insufficient data"],
    ] as const)("renders the %s outcome badge", async (outcome, label) => {
      assessMock.mockResolvedValue(assessmentResponse({ outcome }));
      render(<CompanyProspectDetailPage />);

      expect(await screen.findByText(label)).toBeVisible();
    });

    it("keeps company details visible and retries only the assessment on failure", async () => {
      const user = userEvent.setup();
      assessMock
        .mockRejectedValueOnce(new Error("offline"))
        .mockResolvedValueOnce(possibleDuplicate);
      render(<CompanyProspectDetailPage />);

      expect(
        await screen.findByRole("heading", { name: "Duplicate review unavailable" }),
      ).toBeVisible();
      expect(screen.getByRole("heading", { name: "Acme Systems" })).toBeVisible();
      expect(screen.getByText("acme.example")).toBeVisible();

      await user.click(screen.getByRole("button", { name: "Retry duplicate review" }));

      expect(await screen.findByText("Possible duplicate")).toBeVisible();
      expect(assessMock).toHaveBeenCalledTimes(2);
      expect(getMock.mock.calls.filter(([id]) => id === "company-1")).toHaveLength(1);
    });

    it("does not request an assessment when the prospect is not found", async () => {
      getMock.mockRejectedValue(new ApiError("missing", 404));
      render(<CompanyProspectDetailPage />);

      expect(
        await screen.findByRole("heading", { name: "Company prospect not found" }),
      ).toBeVisible();
      expect(assessMock).not.toHaveBeenCalled();
    });

    it("is visible to members alongside the read-only lifecycle notice", async () => {
      auth.role = "MEMBER";
      assessMock.mockResolvedValue(possibleDuplicate);
      render(<CompanyProspectDetailPage />);

      expect(await screen.findByText("Possible duplicate")).toBeVisible();
      expect(
        screen.getByRole("link", { name: "Acme Systems Limited" }),
      ).toBeVisible();
      expect(
        screen.getByText(/require Owner or Admin permissions\./),
      ).toBeVisible();
      expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
    });
  });
});

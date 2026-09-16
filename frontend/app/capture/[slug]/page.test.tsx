import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CaptureEnquiryForm } from "@/app/capture/[slug]/capture-form";
import { ApiError } from "@/lib/api/client";
import {
  getPublicEnquiryForm,
  submitPublicEnquiry,
} from "@/lib/api/website-capture";

vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "acme" }),
}));

vi.mock("@/lib/api/website-capture", () => ({
  getPublicEnquiryForm: vi.fn(),
  submitPublicEnquiry: vi.fn(),
}));

const getFormMock = vi.mocked(getPublicEnquiryForm);
const submitMock = vi.mocked(submitPublicEnquiry);

describe("hosted website enquiry capture", () => {
  beforeEach(() => {
    getFormMock.mockReset();
    submitMock.mockReset();
    getFormMock.mockResolvedValue({ organization_name: "Acme" });
    submitMock.mockResolvedValue(undefined);
  });

  it("shows a loading state then the enquiry form", async () => {
    getFormMock.mockReturnValue(new Promise(() => undefined));
    render(<CaptureEnquiryForm />);
    expect(screen.getByText("Loading enquiry form")).toBeInTheDocument();
  });

  it("shows unavailable copy when the form cannot be loaded", async () => {
    getFormMock.mockRejectedValue(
      new ApiError("missing", 404, { detail: "This enquiry form is not available." }),
    );
    render(<CaptureEnquiryForm />);
    expect(
      await screen.findByText("This enquiry form is not available."),
    ).toBeVisible();
    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
    expect(screen.queryByText(/inbox/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/activity/i)).not.toBeInTheDocument();
  });

  it("validates required fields before submit", async () => {
    const user = userEvent.setup();
    render(<CaptureEnquiryForm />);
    expect(await screen.findByRole("heading", { name: "Contact us" })).toBeVisible();
    expect(screen.getByText("Acme")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(screen.getByText("Name is required.")).toBeVisible();
    expect(screen.getByText("Email is required.")).toBeVisible();
    expect(screen.getByText("Enquiry is required.")).toBeVisible();
    expect(submitMock).not.toHaveBeenCalled();
  });

  it("submits and shows a success state", async () => {
    const user = userEvent.setup();
    render(<CaptureEnquiryForm />);
    await screen.findByRole("heading", { name: "Contact us" });
    await user.type(screen.getByLabelText(/Name/), "Ada Prospect");
    await user.type(screen.getByLabelText(/Email/), "ada@example.com");
    await user.type(screen.getByLabelText(/Company/), "Northstar");
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo next week");
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() =>
      expect(submitMock).toHaveBeenCalledWith("acme", {
        name: "Ada Prospect",
        email: "ada@example.com",
        company: "Northstar",
        enquiry: "Need a demo next week",
        website: null,
      }),
    );
    expect(screen.getByText("Thank you. We received your enquiry.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
  });

  it("disables the form while submitting", async () => {
    const user = userEvent.setup();
    let resolveSubmit: () => void = () => undefined;
    submitMock.mockReturnValue(
      new Promise((resolve) => {
        resolveSubmit = () => resolve(undefined);
      }),
    );
    render(<CaptureEnquiryForm />);
    await screen.findByRole("heading", { name: "Contact us" });
    await user.type(screen.getByLabelText(/Name/), "Ada Prospect");
    await user.type(screen.getByLabelText(/Email/), "ada@example.com");
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo");
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(screen.getByRole("button", { name: "Submitting…" })).toBeDisabled();
    resolveSubmit();
    expect(await screen.findByText("Thank you. We received your enquiry.")).toBeVisible();
  });

  it("shows a rate-limit alert", async () => {
    const user = userEvent.setup();
    submitMock.mockRejectedValue(
      new ApiError("limited", 429, {
        detail: "Please wait before sending another enquiry.",
      }),
    );
    render(<CaptureEnquiryForm />);
    await screen.findByRole("heading", { name: "Contact us" });
    await user.type(screen.getByLabelText(/Name/), "Ada Prospect");
    await user.type(screen.getByLabelText(/Email/), "ada@example.com");
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo");
    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(
      await screen.findByText("Please wait before sending another enquiry."),
    ).toBeVisible();
    expect(screen.getByRole("alert")).toBeVisible();
  });

  it("keeps fields labelled and avoids AI chrome", async () => {
    render(<CaptureEnquiryForm />);
    expect(await screen.findByLabelText(/Name/)).toBeVisible();
    expect(screen.getByLabelText(/Email/)).toHaveAttribute("autocomplete", "email");
    expect(screen.getByLabelText(/Company/)).toBeVisible();
    expect(screen.getByLabelText(/Enquiry/)).toBeVisible();
    expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/typing/i)).not.toBeInTheDocument();
  });
});

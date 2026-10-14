import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ContactPage, { metadata } from "@/app/(marketing)/contact/page";
import { MarketingHeader } from "@/components/marketing/marketing-header";

const fetchMock = vi.fn();

describe("contact page", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("renders the form, related pages, and metadata", () => {
    render(<ContactPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Request a demo or contact the team.",
      }),
    ).toBeVisible();
    expect(screen.getByLabelText(/Full name/i)).toBeVisible();
    expect(screen.getByLabelText(/Work email/i)).toBeVisible();
    expect(screen.getByLabelText(/Company name/i)).toBeVisible();
    expect(screen.getByLabelText(/Job title/i)).toBeVisible();
    expect(screen.getByLabelText(/Reason for contacting us/i)).toBeVisible();
    expect(screen.getByLabelText(/Message/i)).toBeVisible();
    expect(screen.getAllByRole("link", { name: "Product" }).length).toBeGreaterThan(0);
    screen.getAllByRole("link", { name: "Product" }).forEach((link) => {
      expect(link).toHaveAttribute("href", "/product");
    });
    expect(screen.getAllByRole("link", { name: "How it works" }).length).toBeGreaterThan(0);
    screen.getAllByRole("link", { name: "How it works" }).forEach((link) => {
      expect(link).toHaveAttribute("href", "/how-it-works");
    });
    expect(screen.getAllByRole("link", { name: "Use cases" }).length).toBeGreaterThan(0);
    screen.getAllByRole("link", { name: "Use cases" }).forEach((link) => {
      expect(link).toHaveAttribute("href", "/use-cases");
    });
    expect(metadata.title).toBe("Contact");
    expect(metadata.description).toMatch(/demo/i);
    expect(metadata.alternates).toBeUndefined();
  });

  it("blocks invalid values before calling the API", async () => {
    const user = userEvent.setup();
    render(<ContactPage />);

    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Enter your full name.")).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/Full name/i), "Ada Lovelace");
    await user.type(screen.getByLabelText(/Work email/i), "not-an-email");
    await user.type(screen.getByLabelText(/Company name/i), "Analytical Engines");
    await user.selectOptions(screen.getByLabelText(/Reason for contacting us/i), "demo");
    await user.type(screen.getByLabelText(/Message/i), "Please show the approval step.");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("Enter a valid email address.")).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows success after one submission and ignores a second click", async () => {
    const user = userEvent.setup();
    let release: (() => void) | undefined;
    fetchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () =>
            resolve({
              ok: true,
              status: 200,
              text: async () =>
                JSON.stringify({ accepted: true, confirmation_sent: true }),
              json: async () => ({ accepted: true, confirmation_sent: true }),
            });
        }),
    );
    render(<ContactPage />);
    await fillValid(user);
    const form = screen.getByRole("button", { name: "Send message" }).closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);
    fireEvent.submit(form!);
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    release?.();
    expect(await screen.findByRole("heading", { name: "Message sent" })).toBeVisible();
    expect(screen.getByText(/short confirmation is on its way/i)).toBeVisible();
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/public/contact");
    expect(request.method).toBe("POST");
    expect(JSON.parse(String(request.body))).toMatchObject({
      name: "Ada Lovelace",
      email: "ada@example.com",
      company: "Analytical Engines",
      reason: "demo",
    });
    const headers = new Headers(request.headers);
    expect(headers.get("Authorization")).toBeNull();
  });

  it("shows a safe message when delivery fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({ detail: "provider secret and visitor message" }),
      text: async () => "",
    });
    render(<ContactPage />);
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(
      await screen.findByText("We could not send your message. Please try again later."),
    ).toBeVisible();
    expect(screen.queryByText(/provider secret/i)).not.toBeInTheDocument();
  });
});

describe("marketing navigation includes contact", () => {
  it("keeps existing routes and adds contact", () => {
    render(<MarketingHeader />);
    expect(screen.getAllByRole("link", { name: "Contact" })[0]).toHaveAttribute(
      "href",
      "/contact",
    );
    expect(screen.getAllByRole("link", { name: "Product" })[0]).toHaveAttribute(
      "href",
      "/product",
    );
    expect(screen.getAllByRole("link", { name: "Sign in" })[0]).toHaveAttribute("href", "/login");
    expect(screen.getAllByRole("link", { name: "Get started" })[0]).toHaveAttribute(
      "href",
      "/register",
    );
  });
});

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Full name/i), "Ada Lovelace");
  await user.type(screen.getByLabelText(/Work email/i), "ada@example.com");
  await user.type(screen.getByLabelText(/Company name/i), "Analytical Engines");
  await user.selectOptions(screen.getByLabelText(/Reason for contacting us/i), "demo");
  await user.type(screen.getByLabelText(/Message/i), "Please show the approval step.");
}

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import MarketingHomePage, { metadata } from "@/app/(marketing)/page";
import { MarketingHeader } from "@/components/marketing/marketing-header";

describe("public marketing homepage", () => {
  it("explains the product with a complete, truthful workflow", () => {
    render(<MarketingHomePage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Turn new enquiries into your next customers.",
      }),
    ).toBeVisible();

    for (const step of [
      "Enquiry captured",
      "Lead qualified",
      "Response drafted",
      "Human reviewed",
      "Explicitly sent",
      "Follow-up tracked",
    ]) {
      expect(screen.getByRole("heading", { name: step })).toBeVisible();
    }

    expect(
      screen.getAllByText(/Approval does not send the email/i),
    ).not.toHaveLength(0);
    expect(
      screen.getByText(
        /Illustrative product walkthrough using representative workspace data/i,
      ),
    ).toBeVisible();
  });

  it("uses only real authentication destinations for primary access links", () => {
    render(<MarketingHomePage />);

    const registerLinks = screen.getAllByRole("link", { name: "Get started" });
    expect(registerLinks.length).toBeGreaterThanOrEqual(3);
    registerLinks.forEach((link) =>
      expect(link).toHaveAttribute("href", "/register"),
    );

    screen
      .getAllByRole("link", { name: "Sign in" })
      .forEach((link) => expect(link).toHaveAttribute("href", "/login"));
    expect(
      screen.getByRole("link", { name: "Command Center" }),
    ).toHaveAttribute("href", "/dashboard");
  });

  it("labels pricing as a preview without claiming billing exists", () => {
    render(<MarketingHomePage />);

    expect(
      screen.getByRole("heading", {
        name: /Commercial plans are still being shaped/i,
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/does not currently include in-product billing/i),
    ).toBeVisible();
    expect(screen.getByText("Pricing not yet published")).toBeVisible();
    expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument();
  });

  it("publishes marketing metadata without inventing a production canonical URL", () => {
    expect(metadata.title).toBe("AI Sales Operations Platform");
    expect(metadata.description).toMatch(/qualify enquiries with AI/i);
    expect(metadata.openGraph).toMatchObject({
      title: "FlowPilot — AI Sales Operations Platform",
      type: "website",
    });
    expect(metadata.alternates).toBeUndefined();
  });
});

describe("marketing navigation", () => {
  it("opens and closes the accessible mobile navigation", async () => {
    const user = userEvent.setup();
    render(<MarketingHeader />);

    const trigger = screen.getByRole("button", { name: "Open navigation" });
    const menu = document.getElementById("marketing-mobile-menu");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveClass("hidden");

    await user.click(trigger);
    expect(
      screen.getByRole("button", { name: "Close navigation" }),
    ).toHaveAttribute("aria-expanded", "true");
    expect(menu).toHaveClass("grid");

    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("button", { name: "Open navigation" }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveClass("hidden");
  });
});

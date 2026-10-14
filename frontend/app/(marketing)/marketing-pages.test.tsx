import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HowItWorksPage, {
  metadata as howMetadata,
} from "@/app/(marketing)/how-it-works/page";
import ProductPage, { metadata as productMetadata } from "@/app/(marketing)/product/page";
import UseCasesPage, {
  metadata as useCasesMetadata,
} from "@/app/(marketing)/use-cases/page";
import { MarketingHeader } from "@/components/marketing/marketing-header";

describe("marketing navigation routes", () => {
  it("links the public pages and keeps sign-in and registration", () => {
    render(<MarketingHeader />);

    expect(screen.getAllByRole("link", { name: "Product" })[0]).toHaveAttribute(
      "href",
      "/product",
    );
    expect(screen.getAllByRole("link", { name: "How it works" })[0]).toHaveAttribute(
      "href",
      "/how-it-works",
    );
    expect(screen.getAllByRole("link", { name: "Use cases" })[0]).toHaveAttribute(
      "href",
      "/use-cases",
    );
    expect(screen.getAllByRole("link", { name: "Contact" })[0]).toHaveAttribute(
      "href",
      "/contact",
    );
    expect(screen.getAllByRole("link", { name: "Pricing" })[0]).toHaveAttribute(
      "href",
      "/#pricing",
    );
    expect(screen.getAllByRole("link", { name: "Trust" })[0]).toHaveAttribute(
      "href",
      "/#trust",
    );
    expect(screen.getAllByRole("link", { name: "Get started" }).length).toBeGreaterThan(0);
    screen
      .getAllByRole("link", { name: "Get started" })
      .forEach((link) => expect(link).toHaveAttribute("href", "/register"));
    screen
      .getAllByRole("link", { name: "Sign in" })
      .forEach((link) => expect(link).toHaveAttribute("href", "/login"));
  });
});

describe("product marketing page", () => {
  it("explains current capabilities and keeps sending separate from approval", () => {
    render(<ProductPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "One lead record for preparation, review, and follow-up.",
      }),
    ).toBeVisible();
    for (const name of [
      "Lead and customer context",
      "AI lead qualification",
      "Lead-bound Sales Copilot",
      "Response drafting and human approval",
      "Explicit email sending",
      "Sales Runs and follow-up operations",
      "Activity and execution visibility",
    ]) {
      expect(screen.getByRole("heading", { name })).toBeVisible();
    }
    expect(screen.getByText(/Approving a draft records that decision/i)).toBeVisible();
    expect(screen.getByText(/Illustrative summary of the current product/i)).toBeVisible();
    expect(
      screen.getAllByRole("link", { name: "How it works" }).length,
    ).toBeGreaterThan(0);
    screen.getAllByRole("link", { name: "How it works" }).forEach((link) => {
      expect(link).toHaveAttribute("href", "/how-it-works");
    });
  });

  it("publishes unique metadata without a canonical URL when no site origin is configured", () => {
    expect(productMetadata.title).toBe("Product");
    expect(productMetadata.description).toMatch(/explicit email sending/i);
    expect(productMetadata.openGraph).toMatchObject({
      title: "FlowPilot — Product",
      type: "website",
    });
    expect(productMetadata.alternates).toBeUndefined();
  });
});

describe("how it works page", () => {
  it("lists the supported sequence and says approval does not send", () => {
    render(<HowItWorksPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Preparation can be automatic. Sending is not.",
      }),
    ).toBeVisible();
    for (const name of [
      "Capture or select a lead",
      "Review the original enquiry and context",
      "Qualify the lead using AI",
      "Prepare a response draft",
      "Have a human review and approve it",
      "Send only through the supported explicit action",
      "Track follow-ups and activity",
    ]) {
      expect(screen.getByRole("heading", { name })).toBeVisible();
    }
    expect(screen.getAllByText(/Approval does not send the email/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/not every workflow runs automatically/i)).toBeVisible();
  });

  it("uses its own title and description", () => {
    expect(howMetadata.title).toBe("How it works");
    expect(howMetadata.description).toMatch(/approve with a person/i);
    expect(howMetadata.title).not.toBe(productMetadata.title);
  });
});

describe("use cases page", () => {
  it("labels realistic workflows as examples", () => {
    render(<UseCasesPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Example workflows for inbound sales work.",
      }),
    ).toBeVisible();
    expect(screen.getAllByText("Example").length).toBeGreaterThanOrEqual(5);
    expect(screen.getByText(/not customer case studies/i)).toBeVisible();
    expect(screen.queryByText(/\$\d/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /book a demo/i })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Get started" })[0]).toHaveAttribute(
      "href",
      "/register",
    );
  });

  it("uses its own title and description", () => {
    expect(useCasesMetadata.title).toBe("Use cases");
    expect(useCasesMetadata.description).toMatch(/Practical FlowPilot examples/i);
    expect(useCasesMetadata.alternates).toBeUndefined();
  });
});

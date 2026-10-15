import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DEMO_RESPONSE } from "@/components/marketing/demo-fixtures";
import { InteractiveProductDemo } from "@/components/marketing/interactive-product-demo";

describe("interactive product demo", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("runs the fictional workflow locally and restart clears every step", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
    const tokenRead = vi.spyOn(Storage.prototype, "getItem");
    const fetchRequest = vi.spyOn(globalThis, "fetch");

    render(<InteractiveProductDemo />);
    await user.click(screen.getByRole("button", { name: "Play Product Demo" }));

    expect(
      screen.getByRole("dialog", { name: "Interactive product demo" }),
    ).toBeVisible();
    expect(screen.getByText("Alex Morgan")).toBeVisible();
    expect(screen.getByText("Northstar Analytics")).toBeVisible();
    expect(screen.getByText("Operations Director")).toBeVisible();
    expect(screen.getByText("New", { selector: "dd" })).toBeVisible();
    expect(
      screen.getByText(
        (_text, element) =>
          element?.tagName === "BLOCKQUOTE" &&
          element.textContent?.includes(
            "We are evaluating a sales operations platform for a 20-person team.",
          ) === true,
      ),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "View lead context" }));
    expect(screen.getByText("Sample activity history")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Continue to qualification" }),
    );
    expect(
      screen.queryByText("Evaluating a sales operations platform"),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Run Sample Qualification" }),
    );
    expect(screen.getByText("Simulated AI results")).toBeVisible();
    expect(
      screen.getByText("Evaluating a sales operations platform"),
    ).toBeVisible();
    expect(screen.getByText("86% illustrative sample score")).toBeVisible();
    expect(screen.getByText("Team size identified")).toBeVisible();
    expect(screen.getByText("Decision process")).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Continue to sample draft" }),
    );
    expect(
      screen.queryByRole("textbox", { name: "Sample response draft" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Generate Sample Draft" }),
    );
    const draft = screen.getByRole("textbox", {
      name: "Sample response draft",
    });
    expect(draft).toHaveValue(DEMO_RESPONSE);
    await user.clear(draft);
    await user.type(draft, "Hi Alex, this is an edited sample.");

    await user.click(
      screen.getByRole("button", { name: "Continue to review" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Review sample response" }),
    ).toHaveValue("Hi Alex, this is an edited sample.");
    await user.click(
      screen.getByRole("button", { name: "Approve Sample Draft" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("Approved in demo");
    await user.click(
      screen.getByRole("button", { name: "Continue to sending boundary" }),
    );
    expect(screen.getByText("Ready for a real sending workflow")).toBeVisible();
    expect(screen.getByText(/This demo never sends email/i)).toBeVisible();
    expect(screen.queryByText(/Email sent|SENT/)).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "View workflow summary" }),
    );
    expect(screen.getByText("Sample workflow complete")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Request a real demo" }),
    ).toHaveAttribute("href", "/contact");
    await user.click(screen.getByRole("button", { name: "Restart Demo" }));
    expect(screen.getByText("Step 1 of 7")).toBeVisible();
    expect(screen.queryByText("Simulated AI results")).not.toBeInTheDocument();
    expect(screen.queryByText("Approved in demo")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "Sample response draft" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "View lead context" }));
    await user.click(
      screen.getByRole("button", { name: "Continue to qualification" }),
    );
    expect(
      screen.getByRole("button", { name: "Run Sample Qualification" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Run Sample Qualification" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Continue to sample draft" }),
    );
    expect(
      screen.getByRole("button", { name: "Generate Sample Draft" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Generate Sample Draft" }),
    );
    expect(
      screen.getByRole("textbox", { name: "Sample response draft" }),
    ).toHaveValue(DEMO_RESPONSE);
    expect(fetchRequest).not.toHaveBeenCalled();
    expect(tokenRead).not.toHaveBeenCalledWith("flowpilot.access_token");
  });

  it("dismisses with Escape and the explicit close action", async () => {
    const user = userEvent.setup();
    render(<InteractiveProductDemo />);
    const trigger = screen.getByRole("button", { name: "Play Product Demo" });

    await user.click(trigger);
    expect(
      screen.getByRole("dialog", { name: "Interactive product demo" }),
    ).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );

    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "Close demo" }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("keeps the dialog scrollable and width-constrained at mobile viewport sizes", async () => {
    const user = userEvent.setup();
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 375,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 667,
    });
    render(<InteractiveProductDemo />);
    await user.click(screen.getByRole("button", { name: "Play Product Demo" }));

    const dialog = screen.getByRole("dialog", {
      name: "Interactive product demo",
    });
    expect(dialog).toHaveClass("max-h-[calc(100dvh-2rem)]", "overflow-y-auto");
    expect(dialog).toHaveClass("w-full");
  });
});

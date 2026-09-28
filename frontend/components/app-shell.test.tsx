import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: vi.fn() }),
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
        role: "OWNER",
      },
    },
    signOut: vi.fn(),
  }),
}));

describe("mobile application navigation", () => {
  it("connects aria-controls, focuses the drawer, closes on Escape, and restores focus", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <div>Page content</div>
      </AppShell>,
    );

    const openButton = screen.getByRole("button", { name: "Open menu" });
    expect(openButton).toHaveAttribute("aria-controls", "mobile-navigation");

    await user.click(openButton);

    const drawer = screen.getByRole("dialog", { name: "Primary navigation" });
    expect(drawer).toHaveAttribute("id", "mobile-navigation");
    expect(document.body.style.overflow).toBe("hidden");
    const appContent = document.querySelector('[data-slot="app-content"]');
    expect(appContent).toHaveAttribute("aria-hidden", "true");
    expect(appContent).toHaveAttribute("inert");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Close menu" })).toHaveFocus(),
    );

    await user.keyboard("{Escape}");

    expect(
      screen.queryByRole("dialog", { name: "Primary navigation" }),
    ).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe("");
    expect(appContent).not.toHaveAttribute("aria-hidden");
    expect(appContent).not.toHaveAttribute("inert");
    await waitFor(() => expect(openButton).toHaveFocus());
  });
});

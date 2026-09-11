import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";

describe("ConfirmDialog", () => {
  it("renders title, description, cancel, and confirm actions", async () => {
    const onOpenChange = vi.fn();
    const onConfirm = vi.fn();
    const user = userEvent.setup();

    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Cancel this follow-up?"
        description="The record will be kept as cancelled."
        cancelLabel="Keep follow-up"
        confirmLabel="Cancel follow-up"
        onConfirm={onConfirm}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Cancel this follow-up?" }),
    ).toBeVisible();
    expect(screen.getByText("The record will be kept as cancelled.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Keep follow-up" }));
    expect(onOpenChange.mock.calls[0]?.[0]).toBe(false);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("confirms from the primary action", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();

    render(
      <ConfirmDialog
        open
        onOpenChange={() => undefined}
        title="Approve this response?"
        description="Nothing will be sent now."
        confirmLabel="Approve"
        onConfirm={onConfirm}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("supports a destructive confirm variant", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={() => undefined}
        title="Cancel this follow-up?"
        description="The record will be kept as cancelled."
        confirmLabel="Cancel follow-up"
        variant="destructive"
        onConfirm={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "Cancel follow-up" })).toHaveClass(
      "bg-destructive/10",
    );
  });

  it("disables confirm while pending", () => {
    render(
      <ConfirmDialog
        open
        onOpenChange={() => undefined}
        title="Send this email?"
        description="This is an external action."
        confirmLabel="Sending…"
        confirmPending
        onConfirm={() => undefined}
      />,
    );

    const confirm = screen.getByRole("button", { name: "Sending…" });
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute("aria-busy", "true");
  });

  it("closes on Escape and restores no confirm action", async () => {
    const onOpenChange = vi.fn();
    const onConfirm = vi.fn();
    const user = userEvent.setup();

    render(
      <ConfirmDialog
        open
        onOpenChange={onOpenChange}
        title="Pause this agent?"
        description="The agent will become PAUSED."
        confirmLabel="Pause"
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByRole("dialog", { name: "Pause this agent?" })).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(onOpenChange.mock.calls[0]?.[0]).toBe(false);
    });
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

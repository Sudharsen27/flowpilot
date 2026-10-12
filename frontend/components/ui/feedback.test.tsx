import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";
import { ToastProvider, useToast } from "@/components/ui/toast";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";

function ToastTrigger() {
  const toast = useToast();
  return (
    <>
      <Button
        onClick={() =>
          toast.success({ title: "Lead saved", description: "Ada was added." })
        }
      >
        Save
      </Button>
      <Button
        onClick={() => toast.error({ title: "Email not sent", timeout: 0 })}
      >
        Send
      </Button>
    </>
  );
}

describe("tooltip", () => {
  it("keeps the trigger's accessible name and shows the hint on focus", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider delay={0}>
        <Tooltip content="Switch to dark theme">
          <Button aria-label="Switch to dark theme" size="icon">
            ☾
          </Button>
        </Tooltip>
      </TooltipProvider>,
    );

    const trigger = screen.getByRole("button", {
      name: "Switch to dark theme",
    });
    await user.tab();
    expect(trigger).toHaveFocus();
    await waitFor(() =>
      expect(document.querySelector('[data-slot="tooltip"]')).toHaveTextContent(
        "Switch to dark theme",
      ),
    );
  });
});

describe("toast", () => {
  it("shows a titled success toast with a description", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Lead saved")).toBeVisible();
    expect(screen.getByText("Ada was added.")).toBeVisible();
  });

  it("can be dismissed with its close button", async () => {
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(document.querySelector('[data-slot="toast"]')).toHaveTextContent(
        "Email not sent",
      ),
    );

    await user.click(screen.getByLabelText("Dismiss notification"));
    await waitFor(() =>
      expect(document.querySelector('[data-slot="toast"]')).toBeNull(),
    );
  });
});

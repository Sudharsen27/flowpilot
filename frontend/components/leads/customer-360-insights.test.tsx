import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Customer360Insights } from "@/components/leads/customer-360-insights";
import type { Lead } from "@/types/api";

const lead: Lead = {
  id: "lead-1",
  name: "Jordan Lee",
  email: "jordan@example.com",
  phone: null,
  company: "Acme",
  source: "MANUAL",
  status: "NEW",
  notes: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-01T10:00:00Z",
};

describe("Customer360Insights", () => {
  it("uses the shared button primitive for retry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(
      <Customer360Insights
        lead={lead}
        error="The insight request failed."
        onRetry={onRetry}
      />,
    );

    const retry = screen.getByRole("button", { name: "Retry" });
    expect(retry).toHaveAttribute("data-slot", "button");
    await user.click(retry);
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
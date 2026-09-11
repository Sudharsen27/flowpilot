import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AiBadge, AI_BADGE_LABELS } from "@/components/ai/ai-badge";

describe("AiBadge", () => {
  it.each(AI_BADGE_LABELS)("renders the %s label with accessible AI text", (label) => {
    render(<AiBadge label={label} />);

    const badge = screen.getByLabelText(`AI ${label}`);
    expect(badge).toBeVisible();
    expect(badge).toHaveAttribute("data-slot", "ai-badge");
    expect(badge).toHaveAttribute("data-ai-label", label);
    expect(screen.getByText(label)).toBeVisible();
    expect(badge.className).toContain("border-ai-border");
    expect(badge.className).not.toMatch(/shadow|gradient|animate|glow/i);
  });

  it("marks processing as busy without implying certainty", () => {
    render(<AiBadge label="Processing" />);

    const badge = screen.getByLabelText("AI Processing");
    expect(badge).toHaveAttribute("aria-busy", "true");
    expect(badge).not.toHaveTextContent(/certain|confidence|guaranteed/i);
  });
});

import { Mail } from "lucide-react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DetailRow } from "@/components/data-display/detail-row";

describe("DetailRow", () => {
  it("renders a label and value", () => {
    render(
      <dl>
        <DetailRow label="Recipient" value="ada@example.com" />
      </dl>,
    );

    expect(screen.getByText("Recipient")).toBeVisible();
    expect(screen.getByText("ada@example.com")).toBeVisible();
  });

  it("supports a muted value and optional icon", () => {
    render(
      <dl>
        <DetailRow
          label="Provider"
          value="Not recorded"
          muted
          icon={<Mail data-testid="detail-icon" />}
        />
      </dl>,
    );

    expect(screen.getByTestId("detail-icon")).toBeVisible();
    expect(screen.getByText("Not recorded")).toHaveClass("text-muted-foreground");
  });
});

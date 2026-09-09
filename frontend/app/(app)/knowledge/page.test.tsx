import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import KnowledgePage from "@/app/(app)/knowledge/page";
import {
  KnowledgeSourceList,
  type KnowledgeSourceListItem,
} from "@/components/knowledge/knowledge-source-list";

describe("Knowledge page", () => {
  it("renders the page hierarchy and honest unavailable overview", () => {
    render(<KnowledgePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Knowledge" }),
    ).toBeVisible();
    for (const section of [
      "Knowledge overview",
      "Knowledge sources",
      "Knowledge setup",
      "AI agent connection",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article").slice(0, 4);
    const metricLabels = [
      "Knowledge sources",
      "Documents",
      "Indexed",
      "Needs attention",
    ];
    expect(metricCards).toHaveLength(metricLabels.length);
    metricLabels.forEach((label, index) => {
      expect(
        within(metricCards[index]).getByRole("heading", {
          level: 3,
          name: label,
        }),
      ).toBeVisible();
    });
    expect(screen.getAllByText("—")).toHaveLength(4);
  });

  it("keeps adding knowledge sources honestly unavailable", () => {
    render(<KnowledgePage />);

    const addButton = screen.getByRole("button", { name: "Add source" });
    expect(addButton).toBeDisabled();
    expect(addButton).toHaveAccessibleDescription(
      "Adding knowledge sources is not available yet.",
    );
  });

  it("provides an accessible local-only search field", async () => {
    const user = userEvent.setup();
    render(<KnowledgePage />);

    const search = screen.getByRole("searchbox", {
      name: "Search knowledge sources",
    });
    expect(screen.getByText(/Search is UI-only/)).toBeVisible();

    await user.type(search, "Example");
    expect(search).toHaveValue("Example");
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(search).toHaveValue("");
  });

  it("shows an honest setup state without fabricated sources", () => {
    render(<KnowledgePage />);

    expect(
      screen.getByRole("heading", {
        name: "Give your agents the context they need",
      }),
    ).toBeVisible();
    expect(screen.getByText(/after ingestion is implemented/)).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("example.pdf")).not.toBeInTheDocument();
  });

  it("renders all planned source types as explicit concepts", () => {
    render(<KnowledgePage />);

    const concepts = screen.getByRole("list", {
      name: "Knowledge source concepts",
    });
    for (const sourceType of [
      "Documents",
      "FAQs",
      "Website",
      "Product information",
      "Policies",
      "Company information",
    ]) {
      expect(
        within(concepts).getByRole("heading", { name: sourceType }),
      ).toBeVisible();
    }
    expect(within(concepts).getAllByText("Source concept")).toHaveLength(6);
  });

  it("presents conceptual indexing states and AI-agent connection", () => {
    render(<KnowledgePage />);

    const connection = screen.getByRole("list", {
      name: "Conceptual knowledge connection",
    });
    expect(within(connection).getAllByRole("listitem")).toHaveLength(4);
    for (const step of [
      "Business knowledge",
      "Knowledge retrieval",
      "AI agent",
      "Customer response / business action",
    ]) {
      expect(within(connection).getByText(step)).toBeVisible();
    }

    const statuses = screen.getByLabelText("Indexing status concepts");
    for (const status of [
      "Ready",
      "Processing",
      "Needs attention",
      "Not indexed",
    ]) {
      expect(within(statuses).getByText(status)).toBeVisible();
    }
    expect(screen.getByText("Retrieval unavailable")).toBeVisible();
  });

  it("supports desktop table and mobile list representations for real sources", () => {
    const source: KnowledgeSourceListItem = {
      id: "source-1",
      name: "Test source",
      type: "document",
      status: "setup",
      indexingStatus: "not-indexed",
    };

    render(<KnowledgeSourceList sources={[source]} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByText("Test source")).toHaveLength(2);
    expect(screen.getAllByText("Document")).toHaveLength(2);
    expect(screen.getAllByText("Not indexed")).toHaveLength(2);
  });
});

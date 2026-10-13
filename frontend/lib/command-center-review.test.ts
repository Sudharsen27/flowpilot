import { describe, expect, it } from "vitest";

import { dedupeReviewItemsByDraftId } from "@/lib/command-center-review";

describe("dedupeReviewItemsByDraftId", () => {
  it("keeps the first item for each draft_id", () => {
    const items = [
      { draft_id: "draft-1", label: "first" },
      { draft_id: "draft-2", label: "other" },
      { draft_id: "draft-1", label: "duplicate" },
    ];

    expect(dedupeReviewItemsByDraftId(items)).toEqual([
      { draft_id: "draft-1", label: "first" },
      { draft_id: "draft-2", label: "other" },
    ]);
  });
});

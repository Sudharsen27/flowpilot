export function dedupeReviewItemsByDraftId<T extends { draft_id: string }>(
  items: T[],
): T[] {
  const seen = new Set<string>();
  const unique: T[] = [];
  for (const item of items) {
    if (seen.has(item.draft_id)) continue;
    seen.add(item.draft_id);
    unique.push(item);
  }
  return unique;
}

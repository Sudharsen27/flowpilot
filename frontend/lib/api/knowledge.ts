import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  KnowledgeCategory,
  KnowledgeEntry,
  KnowledgeEntryInput,
  KnowledgeEntryStatus,
  KnowledgeListResponse,
} from "@/types/api";

export function listKnowledge(
  params: {
    category?: KnowledgeCategory | null;
    status?: KnowledgeEntryStatus;
    q?: string;
  } = {},
) {
  const query = new URLSearchParams();
  if (params.category) query.set("category", params.category);
  if (params.status) query.set("status", params.status);
  if (params.q?.trim()) query.set("q", params.q.trim());
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiGet<KnowledgeListResponse>(`/api/v1/knowledge${suffix}`);
}

export function createKnowledgeEntry(input: KnowledgeEntryInput) {
  return apiPost<KnowledgeEntry>("/api/v1/knowledge", input);
}

export function updateKnowledgeEntry(
  entryId: string,
  input: Partial<KnowledgeEntryInput> & {
    expected_revision: number;
    status?: KnowledgeEntryStatus;
  },
) {
  return apiPatch<KnowledgeEntry>(
    `/api/v1/knowledge/${encodeURIComponent(entryId)}`,
    input,
  );
}

export function deleteKnowledgeEntry(entryId: string) {
  return apiDelete(`/api/v1/knowledge/${encodeURIComponent(entryId)}`);
}

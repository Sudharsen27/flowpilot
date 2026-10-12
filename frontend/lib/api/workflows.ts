import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  WorkflowRule,
  WorkflowRuleInput,
  WorkflowRunListResponse,
} from "@/types/api";

export function listWorkflows() {
  return apiGet<WorkflowRule[]>("/api/v1/workflows");
}

export function createWorkflow(input: WorkflowRuleInput) {
  return apiPost<WorkflowRule>("/api/v1/workflows", input);
}

export function updateWorkflow(
  ruleId: string,
  input: Partial<WorkflowRuleInput> & { expected_revision: number },
) {
  return apiPatch<WorkflowRule>(
    `/api/v1/workflows/${encodeURIComponent(ruleId)}`,
    input,
  );
}

export function deleteWorkflow(ruleId: string) {
  return apiDelete(`/api/v1/workflows/${encodeURIComponent(ruleId)}`);
}

export function listWorkflowRuns(
  ruleId: string,
  params: { limit?: number } = {},
) {
  const limit = params.limit ?? 20;
  return apiGet<WorkflowRunListResponse>(
    `/api/v1/workflows/${encodeURIComponent(ruleId)}/runs?limit=${limit}`,
  );
}

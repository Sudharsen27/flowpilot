export type UserPublic = {
  id: string;
  email: string;
  name: string;
};

export type OrganizationPublic = {
  id: string;
  name: string;
  slug: string;
};

export type MembershipRole = "OWNER" | "ADMIN" | "MEMBER";

export type MembershipPublic = {
  id: string;
  role: MembershipRole;
  organization_id: string;
  user_id: string;
};

export type MemberPublic = {
  membership_id: string;
  role: MembershipRole;
  user: UserPublic;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: UserPublic;
  organization: OrganizationPublic;
  membership: MembershipPublic;
};

export type MeResponse = {
  user: UserPublic;
  organization: OrganizationPublic;
  membership: MembershipPublic;
};

export type HealthResponse = {
  status: string;
  service: string;
};

export type AgentType =
  | "SALES"
  | "SUPPORT"
  | "OPERATIONS"
  | "COMMUNICATION";

export type AgentStatus =
  | "DRAFT"
  | "READY"
  | "ACTIVE"
  | "PAUSED"
  | "NEEDS_ATTENTION";

export type Agent = {
  id: string;
  name: string;
  description: string;
  agent_type: AgentType;
  system_instructions: string;
  status: AgentStatus;
  created_at: string;
  updated_at: string;
};

export type AgentListResponse = Agent[];

export type AgentCreateRequest = {
  name: string;
  description?: string;
  agent_type: AgentType;
  system_instructions?: string;
};

export type AgentUpdateRequest = Partial<AgentCreateRequest>;

export type AgentExecutionStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type AgentExecutionRequest = {
  input: string;
};

export type AgentExecutionCreated = {
  execution_id: string;
  status: AgentExecutionStatus;
  started_at: string | null;
};

export type AgentTokenUsage = {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
};

export type ExecutionFailureCategory =
  | "PROVIDER_ERROR"
  | "TOOL_ERROR"
  | "POLICY_ERROR"
  | "VALIDATION_ERROR"
  | "EXECUTION_ERROR"
  | "CONFIGURATION_ERROR";

export type AgentExecutionResult = {
  execution_id: string;
  status: AgentExecutionStatus;
  output: string | null;
  provider: string | null;
  model: string | null;
  usage: AgentTokenUsage | null;
  error: string | null;
  duration_ms?: number | null;
  failure_category?: ExecutionFailureCategory | null;
};

export type AgentExecutionListItem = {
  id: string;
  status: AgentExecutionStatus;
  provider: string | null;
  model: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  input_preview: string | null;
  error_preview: string | null;
  duration_ms: number | null;
  failure_category: ExecutionFailureCategory | null;
};

export type AgentExecutionListResponse = {
  items: AgentExecutionListItem[];
  limit: number;
  offset: number;
  total: number;
};

export type AgentExecutionDetail = {
  id: string;
  agent_id: string;
  status: AgentExecutionStatus;
  input: string | null;
  output: string | null;
  provider: string | null;
  model: string | null;
  usage: AgentTokenUsage | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  initiated_by_user_id: string | null;
  duration_ms: number | null;
  failure_category: ExecutionFailureCategory | null;
};

export type ToolRiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type ToolPolicyDecision = "ALLOW" | "REQUIRE_APPROVAL" | "DENY";

export type ToolInvocationStatus =
  | "SUCCESS"
  | "FAILED"
  | "REJECTED"
  | "AWAITING_APPROVAL";

export type ToolInvocationListItem = {
  id: string;
  execution_id: string;
  agent_id: string;
  call_id: string;
  tool_name: string;
  risk_level: ToolRiskLevel | null;
  decision: ToolPolicyDecision | null;
  status: ToolInvocationStatus;
  argument_keys: string[] | null;
  error: string | null;
  started_at: string;
  completed_at: string;
  created_at: string;
  duration_ms: number | null;
};

export type ToolInvocationListResponse = {
  items: ToolInvocationListItem[];
  limit: number;
  offset: number;
  total: number;
};

export type LeadStatus =
  | "NEW"
  | "CONTACTED"
  | "QUALIFIED"
  | "UNQUALIFIED"
  | "CONVERTED";

export type LeadSource =
  | "MANUAL"
  | "WEBSITE"
  | "EMAIL"
  | "CHAT"
  | "API"
  | "IMPORT";

export type Lead = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  source: LeadSource;
  status: LeadStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
  latest_qualification?: LeadQualificationSummary | null;
  latest_response_draft?: LeadResponseDraftSummary | null;
};

export type LeadAiQualification =
  | "QUALIFIED"
  | "UNQUALIFIED"
  | "NEEDS_MORE_INFORMATION";

export type LeadIntent =
  | "REQUEST_DEMO"
  | "REQUEST_PRICING"
  | "GENERAL_ENQUIRY"
  | "SUPPORT_REQUEST"
  | "OTHER";

export type LeadQualificationSummary = {
  id: string;
  status: "COMPLETED" | "FAILED";
  qualification: LeadAiQualification | null;
  confidence: number | null;
  created_at: string;
  error: string | null;
};

export type LeadQualificationAnalysis = {
  summary: string;
  intent: LeadIntent;
  qualification: LeadAiQualification;
  qualification_reasons: string[];
  confidence: number;
  extracted_contact: {
    name: string | null;
    email: string | null;
    phone: string | null;
  };
  extracted_company: {
    name: string | null;
  };
  buying_signals: string[];
  missing_information: string[];
};

export type LeadQualificationResult = {
  id: string;
  lead_id: string;
  status: "COMPLETED" | "FAILED";
  enquiry: string;
  analysis: LeadQualificationAnalysis | null;
  error: string | null;
  failure_category: ExecutionFailureCategory | null;
  provider: string | null;
  model: string | null;
  usage: AgentTokenUsage | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  duration_ms: number | null;
};

export type LeadQualifyRequest = {
  enquiry: string;
};

export type LeadResponseDraftSummary = {
  id: string;
  status: "COMPLETED" | "FAILED";
  review_status?: LeadResponseReviewStatus | null;
  created_at: string;
};

export type LeadResponseReviewStatus =
  | "GENERATED"
  | "EDITED"
  | "APPROVED"
  | "REJECTED";

export type LeadEmailSendStatus = "PENDING" | "SENT" | "FAILED";

export type LeadEmailSendResult = {
  id: string;
  lead_id: string;
  response_draft_id: string;
  status: LeadEmailSendStatus;
  recipient_email: string;
  sender_email: string;
  subject: string;
  body_text: string;
  draft_revision: number;
  provider: string | null;
  provider_message_id: string | null;
  error: string | null;
  failure_category: ExecutionFailureCategory | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  duration_ms: number | null;
};

export type LeadResponseDraftResult = {
  id: string;
  lead_id: string;
  status: "COMPLETED" | "FAILED";
  enquiry: string;
  original_response?: string | null;
  response: string | null;
  human_edited?: boolean;
  review_status?: LeadResponseReviewStatus | null;
  reviewed_by_user_id?: string | null;
  reviewed_at?: string | null;
  rejection_reason?: string | null;
  revision: number;
  error: string | null;
  failure_category: ExecutionFailureCategory | null;
  provider: string | null;
  model: string | null;
  usage: AgentTokenUsage | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at?: string;
  duration_ms: number | null;
  latest_email_send?: LeadEmailSendResult | null;
};

export type LeadRespondRequest = {
  enquiry: string;
};

export type LeadResponseDraftUpdateRequest = {
  response: string;
  expected_revision: number;
};

export type LeadResponseDraftApproveRequest = {
  expected_revision: number;
};

export type LeadResponseDraftRejectRequest = {
  expected_revision: number;
  reason?: string | null;
};

export type LeadFollowUpStatus = "PENDING" | "COMPLETED" | "CANCELLED";

export type LeadFollowUpType = "EMAIL_FOLLOW_UP" | "MANUAL_FOLLOW_UP";

export type LeadFollowUp = {
  id: string;
  lead_id: string;
  email_send_id?: string | null;
  type: LeadFollowUpType;
  status: LeadFollowUpStatus;
  due_at: string;
  notes?: string | null;
  body_text?: string | null;
  revision: number;
  is_overdue: boolean;
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LeadFollowUpListResponse = {
  items: LeadFollowUp[];
  limit: number;
  offset: number;
  total: number;
};

export type LeadFollowUpCreateRequest = {
  due_at: string;
  type: LeadFollowUpType;
  notes?: string | null;
  body_text?: string | null;
  email_send_id?: string | null;
};

export type LeadFollowUpUpdateRequest = {
  expected_revision: number;
  due_at?: string;
  type?: LeadFollowUpType;
  notes?: string | null;
  body_text?: string | null;
};

export type LeadFollowUpLifecycleRequest = {
  expected_revision: number;
};

export type LeadFollowUpExecutionStatus =
  | "PENDING"
  | "RUNNING"
  | "SENT"
  | "FAILED";

/**
 * Safe execution fields only. The API never returns provider payloads,
 * authorization headers or secrets.
 */
export type FollowUpExecutionSummary = {
  id: string;
  status: LeadFollowUpExecutionStatus;
  attempt: number;
  recipient_email: string;
  provider: string | null;
  provider_message_id: string | null;
  failure_category: ExecutionFailureCategory | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
};

export type FollowUpLeadSummary = {
  id: string;
  name: string;
  email: string | null;
};

/**
 * One attempt at sending a follow-up. `body_text` is the human-authored body
 * snapshotted at claim time, never AI-generated content.
 */
export type LeadFollowUpExecution = {
  id: string;
  lead_id: string;
  follow_up_id: string;
  status: LeadFollowUpExecutionStatus;
  attempt: number;
  recipient_email: string;
  sender_email: string;
  subject: string;
  body_text: string;
  provider: string | null;
  provider_message_id: string | null;
  failure_category: ExecutionFailureCategory | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  duration_ms: number | null;
  provider_idempotency_key: string;
};

export type LeadFollowUpExecutionListResponse = {
  items: LeadFollowUpExecution[];
  limit: number;
  offset: number;
  total: number;
};

export type FollowUpOperationsItem = {
  follow_up: LeadFollowUp;
  lead: FollowUpLeadSummary;
  latest_execution: FollowUpExecutionSummary | null;
};

export type FollowUpOperationsSummary = {
  overdue: number;
  due_today: number;
  upcoming: number;
  completed: number;
  cancelled: number;
};

export type FollowUpOperationsResponse = {
  items: FollowUpOperationsItem[];
  summary: FollowUpOperationsSummary;
  limit: number;
  offset: number;
  total: number;
};

export type FollowUpOperationsParams = {
  status?: LeadFollowUpStatus;
  overdue?: boolean;
  limit?: number;
  offset?: number;
};

export type LeadListResponse = {
  items: Lead[];
  limit: number;
  offset: number;
  total: number;
  status_counts: Record<LeadStatus, number>;
};

export type LeadCreateRequest = {
  name: string;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  source?: LeadSource;
  status?: LeadStatus;
  notes?: string | null;
};

export type LeadUpdateRequest = Partial<LeadCreateRequest>;

export type SalesRunStatus =
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "FAILED"
  | "CANCELLED";

export type SalesRunStage =
  | "MATCH_LEAD"
  | "QUALIFY"
  | "DRAFT"
  | "AWAIT_APPROVAL";

export type SalesRunLeadSummary = {
  id: string;
  name: string;
  email: string | null;
  status: LeadStatus;
};

export type SalesRunQualificationSummary = {
  id: string;
  status: string;
};

export type SalesRunDraftSummary = {
  id: string;
  status: string;
  review_status: LeadResponseReviewStatus | null;
};

export type SalesRun = {
  id: string;
  agent_id: string;
  lead_id: string;
  status: SalesRunStatus;
  stage: SalesRunStage;
  qualification_id: string | null;
  response_draft_id: string | null;
  failure_category: ExecutionFailureCategory | null;
  error: string | null;
  initiated_by_user_id: string | null;
  revision: number;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  enquiry?: string | null;
  lead?: SalesRunLeadSummary | null;
  qualification?: SalesRunQualificationSummary | null;
  response_draft?: SalesRunDraftSummary | null;
};

export type SalesRunListResponse = {
  items: SalesRun[];
  limit: number;
  offset: number;
  total: number;
  status_counts?: Record<string, number> | null;
};

export type SalesRunStartRequest = {
  enquiry: string;
  lead_id?: string | null;
  name?: string | null;
  email?: string | null;
};

export type SalesRunCancelRequest = {
  expected_revision: number;
};

export type SalesRunListParams = {
  status?: SalesRunStatus;
  limit?: number;
  offset?: number;
};

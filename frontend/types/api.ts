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
  created_at: string;
};

export type LeadResponseDraftResult = {
  id: string;
  lead_id: string;
  status: "COMPLETED" | "FAILED";
  enquiry: string;
  response: string | null;
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

export type LeadRespondRequest = {
  enquiry: string;
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

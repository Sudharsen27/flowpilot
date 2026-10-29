export type UserPublic = {
  id: string;
  email: string;
  name: string;
};

export type OrganizationPublic = {
  id: string;
  name: string;
  slug: string;
  website_capture_enabled?: boolean;
  /** ISO 4217 code for every deal and target. Absent in sessions saved before deals existed. */
  default_currency?: string;
};

export type MembershipRole = "OWNER" | "ADMIN" | "MEMBER";

export type RuntimeCheckStatus = "configured" | "not_configured";

export type RuntimeConfiguration = {
  source: "environment";
  ai_provider: "openai" | "groq";
  ai_provider_label: "OpenAI" | "Groq";
  ai_model: string | null;
  ai_status: RuntimeCheckStatus;
  human_decision_provider: "typesafe";
  human_decision_status: RuntimeCheckStatus;
  email_provider_label: "Resend" | "Not configured";
  email_status: RuntimeCheckStatus;
  sender_address: string | null;
  sender_status: RuntimeCheckStatus;
  government_company_discovery_available: boolean;
  government_company_discovery_max_page_size: number;
  government_company_discovery_max_offset: number;
};

export type GovernmentCompanyDiscoveryRequest = {
  state_code: string;
  offset: number;
  page_size: number;
};

export type CompanyDataAttribution = {
  provider: string;
  dataset: string;
  resource_uuid: string;
  endpoint: string;
  attribution: string;
  licensing_status: string;
};

export type NormalizedCompanyRecord = {
  cin: string | null;
  company_name: string | null;
  company_status: string | number | boolean | null;
  company_class: string | number | boolean | null;
  company_category: string | number | boolean | null;
  company_sub_category: string | number | boolean | null;
  authorized_capital: string | number | boolean | null;
  paid_up_capital: string | number | boolean | null;
  number_of_members: string | number | boolean | null;
  date_of_incorporation: string | null;
  registered_address: string | number | boolean | null;
  company_state_code: string | number | boolean | null;
  registrar_of_companies: string | number | boolean | null;
  principal_business_activity: string | number | boolean | null;
  industrial_classification_code: string | number | boolean | null;
  attribution: CompanyDataAttribution;
  retrieved_at: string;
};

export type GovernmentCompanyDiscoveryResponse = {
  source: "GOVERNMENT";
  items: Record<string, string | number | boolean | null>[];
  normalized_items?: NormalizedCompanyRecord[];
  total: number | null;
  offset: number;
  page_size: number;
  has_more: boolean;
  next_offset: number | null;
  attribution: CompanyDataAttribution;
};

export type DuplicateAssessmentOutcome =
  | "NEW"
  | "EXACT_MATCH"
  | "POSSIBLE_DUPLICATE"
  | "INSUFFICIENT_DATA";

export type CompanyDuplicateCandidateInput = {
  reference_id: string;
  company_name?: string | null;
  website_domain?: string | null;
  cin?: string | null;
};

export type CompanyDuplicateAssessmentRequest = {
  candidates: CompanyDuplicateCandidateInput[];
};

export type CompanyDuplicateAssessmentItem = {
  reference_id: string;
  outcome: DuplicateAssessmentOutcome;
  reason_code: string;
  explanation: string;
  matching_fields: string[];
  existing_match_references: string[];
  in_batch_match_reference?: string | null;
};

export type CompanyDuplicateAssessmentResponse = {
  assessments: CompanyDuplicateAssessmentItem[];
  total_evaluated: number;
  persisted_cin_available: boolean;
};

export type CompanyProspectStatus = "IDENTIFIED" | "REVIEWED" | "ARCHIVED";

export type EvidenceQuality =
  | "SOURCE_REPORTED"
  | "ESTIMATED"
  | "INFERRED"
  | "UNKNOWN";

export type CompanyProspect = {
  id: string;
  name: string;
  website_domain: string | null;
  name_evidence_quality: EvidenceQuality;
  website_domain_evidence_quality: EvidenceQuality;
  status: CompanyProspectStatus;
  created_at: string;
  updated_at: string;
};

export type CompanyProspectListResponse = {
  items: CompanyProspect[];
  limit: number;
  offset: number;
  total: number;
};

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

export type AgentOrchestrateRequest = {
  instruction: string;
  lead_id?: string;
};

export type OrchestrationOutcome =
  | "SUCCESS"
  | "PLANNING_FAILED"
  | "PLAN_VALIDATION_FAILED"
  | "TOOL_DENIED"
  | "APPROVAL_REQUIRED"
  | "TOOL_FAILED"
  | "EXECUTION_FAILED";

export type ToolOutcome =
  | "SUCCESS"
  | "FAILURE"
  | "VALIDATION_FAILURE"
  | "PERMISSION_DENIED"
  | "APPROVAL_REQUIRED";

export type ToolSideEffectLevel =
  | "READ"
  | "WRITE"
  | "SENSITIVE_WRITE"
  | "APPROVAL_REQUIRED";

export type ToolResult = {
  call_id: string;
  tool_name: string;
  success: boolean;
  outcome: ToolOutcome;
  decision: ToolPolicyDecision | null;
  risk_level: ToolRiskLevel | null;
  side_effect_level: ToolSideEffectLevel | null;
  output: Record<string, unknown> | null;
  error: string | null;
  executed: boolean;
  failure_category: ExecutionFailureCategory | null;
};

export type PlanStepResult = {
  step_id: string;
  sequence: number;
  tool_name: string;
  result: ToolResult | null;
};

export type OrchestrationResult = {
  execution_id: string | null;
  outcome: OrchestrationOutcome;
  execution_status: AgentExecutionStatus | null;
  plan_id: string | null;
  approval_required: boolean;
  completed_step_count: number;
  total_step_count: number;
  stopped_at_step_id: string | null;
  step_results: PlanStepResult[];
  failure_category: ExecutionFailureCategory | null;
  error: string | null;
  provider: string | null;
  model: string | null;
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

/** Organization-wide row: safe list fields plus the agent and lead it belongs to. */
export type OrganizationExecutionListItem = AgentExecutionListItem & {
  agent_id: string;
  agent_name: string | null;
  lead_id: string | null;
  lead_name: string | null;
  initiated_by_user_id: string | null;
  is_stale: boolean;
};

export type OrganizationExecutionListResponse = {
  items: OrganizationExecutionListItem[];
  limit: number;
  offset: number;
  total: number;
  /** Organization-wide counts per status; never narrowed by list filters. */
  status_counts: Partial<Record<AgentExecutionStatus, number>>;
};

export type OrganizationExecutionListParams = {
  status?: AgentExecutionStatus;
  agentId?: string;
  leadId?: string;
  limit?: number;
  offset?: number;
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

export type AnalyticsRangeDays = 7 | 30 | 90;

export type AnalyticsTotals = {
  leads_created: number;
  leads_qualified: number;
  ai_analyses: number;
  ai_drafts: number;
  drafts_approved: number;
  emails_sent: number;
  customer_replies: number;
  human_handoffs: number;
  follow_ups_completed: number;
};

export type AnalyticsDailyPoint = {
  date: string;
  leads_created: number;
  ai_analyses: number;
  emails_sent: number;
};

export type AnalyticsSummary = {
  range_days: AnalyticsRangeDays;
  source: LeadSource | null;
  start: string;
  end: string;
  totals: AnalyticsTotals;
  daily: AnalyticsDailyPoint[];
  leads_by_source: { source: LeadSource; count: number }[];
  qualification_outcomes: {
    qualified: number;
    unqualified: number;
    needs_more_information: number;
  };
};

export type Lead = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  source: LeadSource;
  status: LeadStatus;
  human_attention_required?: boolean;
  notes: string | null;
  enquiry?: string | null;
  created_at: string;
  updated_at: string;
  latest_qualification?: LeadQualificationSummary | null;
  latest_response_draft?: LeadResponseDraftSummary | null;
  latest_sales_run?: LeadLatestSalesRunSummary | null;
  fit_score?: LeadFitScore | null;
};

export type IdealCustomerCriterion = {
  terms: string[];
  weight: number;
};

export type IdealCustomerCompanySizeCriterion = {
  minimum_employees: number | null;
  maximum_employees: number | null;
  weight: number;
};

export type IdealCustomerGeographicTarget = {
  country: string;
  region: string | null;
};

export type IdealCustomerGeographyCriterion = {
  targets: IdealCustomerGeographicTarget[];
  weight: number;
};

export type IdealCustomerProfileUpdate = {
  company: IdealCustomerCriterion;
  enquiry: IdealCustomerCriterion;
  industry: IdealCustomerCriterion;
  company_size: IdealCustomerCompanySizeCriterion;
  geography: IdealCustomerGeographyCriterion;
};

export type IdealCustomerProfile = IdealCustomerProfileUpdate & {
  available_criteria: (
    | "company"
    | "enquiry"
    | "industry"
    | "company_size"
    | "geography"
  )[];
  unavailable_criteria: Record<string, string>;
  configuration_valid: boolean;
};

export type LeadFitComponent = {
  criterion:
    | "company"
    | "enquiry"
    | "industry"
    | "company_size"
    | "geography";
  status: "MATCHED" | "UNMATCHED" | "UNKNOWN" | "UNCONFIGURED";
  weight: number;
  matched_terms: string[];
  explanation: string;
};

export type LeadFitScore = {
  score: number | null;
  confidence: number;
  fit: "STRONG" | "MODERATE" | "WEAK" | "UNKNOWN";
  components: LeadFitComponent[];
  unavailable_criteria: Record<string, string>;
  configuration_valid: boolean;
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

export type LeadQualifyRequest =
  | { enquiry: string }
  | { inbound_email_id: string };

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

export type ProspectPreviewColumn = {
  index: number;
  label: string;
  field: string | null;
};

export type ProspectDiscoverySearchRequest = {
  industry?: string;
  country?: string;
  region?: string;
  minimum_employees?: number;
  maximum_employees?: number;
  page_size: number;
  cursor?: string;
};

export type ProspectDiscoveryBusinessResult = {
  name: string;
  industry: string;
  country: string;
  region: string;
  employee_count: number;
  description: string;
  synthetic: true;
  verification_status: "SYNTHETIC_UNVERIFIED";
  match_explanations: string[];
};

export type ProspectDiscoverySearchResponse = {
  source: "SYNTHETIC";
  items: ProspectDiscoveryBusinessResult[];
  page_size: number;
  has_more: boolean;
  next_cursor: string | null;
};

export type ProspectPreviewIssue = {
  code: string;
  message: string;
  row_number: number | null;
  field: string | null;
  severity: "error" | "warning";
};

export type ProspectPreviewRow = {
  row_number: number;
  cells: string[];
  valid: boolean;
  errors: ProspectPreviewIssue[];
  duplicate_reasons: string[];
  duplicate_of_row: number | null;
};

export type ProspectPreviewResponse = {
  columns: ProspectPreviewColumn[];
  issues: ProspectPreviewIssue[];
  rows: ProspectPreviewRow[];
  summary: {
    total_rows: number;
    valid_rows: number;
    invalid_rows: number;
    duplicate_rows: number;
  };
};

export type ProspectImportRowResult = {
  row_number: number;
  status: "IMPORTED" | "SKIPPED" | "FAILED";
  reason_code: string | null;
  message: string | null;
  duplicate_of_row: number | null;
};

export type ProspectImportResponse = {
  total_rows: number;
  imported_count: number;
  skipped_count: number;
  failed_count: number;
  rows: ProspectImportRowResult[];
};

export type LeadCreateRequest = {
  name: string;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  source?: LeadSource;
  status?: LeadStatus;
  notes?: string | null;
  enquiry?: string | null;
};

export type LeadUpdateRequest = Partial<LeadCreateRequest>;

export type SalesRunStatus =
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type SalesRunStage =
  | "MATCH_LEAD"
  | "QUALIFY"
  | "DRAFT"
  | "AWAIT_APPROVAL"
  | "SEND"
  | "DONE";

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

export type SalesRunEmailSendSummary = {
  id: string;
  status: string;
  recipient_email: string;
  provider: string | null;
  provider_message_id: string | null;
  draft_revision: number;
  failure_category: ExecutionFailureCategory | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
};

export type SalesRunFollowUpSummary = {
  id: string;
  type: LeadFollowUpType;
  status: LeadFollowUpStatus;
  due_at: string;
  is_overdue: boolean;
};

export type LeadLatestSalesRunEmailSummary = {
  status: string;
  completed_at: string | null;
};

export type LeadLatestSalesRunFollowUpSummary = {
  status: LeadFollowUpStatus;
  due_at: string;
  is_overdue: boolean;
};

export type LeadLatestSalesRunSummary = {
  id: string;
  agent_id: string;
  status: SalesRunStatus;
  stage: SalesRunStage;
  email_send: LeadLatestSalesRunEmailSummary | null;
  follow_up: LeadLatestSalesRunFollowUpSummary | null;
};

export type SalesRun = {
  id: string;
  agent_id: string;
  lead_id: string;
  status: SalesRunStatus;
  stage: SalesRunStage;
  qualification_id: string | null;
  response_draft_id: string | null;
  email_send_id: string | null;
  follow_up_id: string | null;
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
  email_send?: SalesRunEmailSendSummary | null;
  follow_up?: SalesRunFollowUpSummary | null;
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

export type LeadSalesRunStartRequest = {
  enquiry: string;
  agent_id: string;
};

export type SalesRunCancelRequest = {
  expected_revision: number;
};

export type SalesRunSendRequest = {
  expected_revision: number;
};

export type SalesRunScheduleFollowUpRequest = {
  expected_revision: number;
  due_at: string;
  type: LeadFollowUpType;
  notes?: string | null;
  body_text?: string | null;
};

export type SalesRunListParams = {
  status?: SalesRunStatus;
  stage?: SalesRunStage;
  limit?: number;
  offset?: number;
};

export type WebsiteCaptureSettings = {
  website_capture_enabled: boolean;
  sales_agent_auto_start_enabled: boolean;
  default_sales_agent_id: string | null;
};

export type WebsiteCaptureSettingsUpdate = {
  website_capture_enabled: boolean;
  sales_agent_auto_start_enabled: boolean;
  default_sales_agent_id: string | null;
};

export type PublicEnquiryForm = {
  organization_name: string;
};

export type PublicEnquiryCreateRequest = {
  name: string;
  email: string;
  company?: string | null;
  enquiry: string;
  website?: string | null;
};

export type ActivityEventType =
  | "AI_ACTION"
  | "APPROVAL"
  | "HUMAN_ACTION"
  | "SYSTEM_EVENT";

export type ActivityActorType =
  | "USER"
  | "AGENT"
  | "SYSTEM"
  | "PUBLIC_VISITOR";

export type ActivityEntityType =
  | "LEAD"
  | "SALES_RUN"
  | "LEAD_EMAIL_SEND"
  | "AGENT_EXECUTION"
  | "LEAD_FOLLOW_UP"
  | "LEAD_FOLLOW_UP_EXECUTION"
  | "LEAD_RESPONSE_DRAFT"
  | "LEAD_QUALIFICATION"
  | "KNOWLEDGE_ENTRY"
  | "WORKFLOW_RULE"
  | "WEBHOOK_ENDPOINT"
  | "COMPANY_PROSPECT";

export type WebhookEventType =
  | "lead.created"
  | "lead.qualified"
  | "draft.approved"
  | "email.sent"
  | "webhook.test";

export type WebhookDeliveryStatus = "PENDING" | "SENDING" | "DELIVERED" | "FAILED";

export type WebhookEndpoint = {
  id: string;
  name: string;
  url: string;
  events: WebhookEventType[];
  enabled: boolean;
  secret_hint: string;
  revision: number;
  created_at: string;
  updated_at: string;
  delivery_counts: { pending: number; delivered: number; failed: number };
  last_delivery_at: string | null;
};

export type WebhookEndpointWithSecret = {
  endpoint: WebhookEndpoint;
  secret: string;
};

export type WebhookEndpointInput = {
  name: string;
  url: string;
  events: WebhookEventType[];
};

export type WebhookDelivery = {
  id: string;
  endpoint_id: string;
  event_type: WebhookEventType;
  status: WebhookDeliveryStatus;
  attempts: number;
  last_status_code: number | null;
  last_error: string | null;
  next_attempt_at: string | null;
  created_at: string;
  last_attempt_at: string | null;
  delivered_at: string | null;
};

export type WebhookDeliveryListResponse = {
  items: WebhookDelivery[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowTrigger =
  | "LEAD_CREATED"
  | "INBOUND_REPLY_RECEIVED"
  | "HUMAN_ATTENTION_REQUIRED";

export type WorkflowAction = "ANALYZE_LEAD" | "DRAFT_RESPONSE" | "CREATE_FOLLOW_UP";

export type WorkflowRunStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "SKIPPED" | "FAILED";

export type WorkflowRule = {
  id: string;
  name: string;
  trigger: WorkflowTrigger;
  action: WorkflowAction;
  source_filter: LeadSource | null;
  follow_up_delay_hours: number | null;
  enabled: boolean;
  revision: number;
  created_at: string;
  updated_at: string;
  run_counts: { pending: number; succeeded: number; skipped: number; failed: number };
  last_run_at: string | null;
};

export type WorkflowRuleInput = {
  name: string;
  trigger: WorkflowTrigger;
  action: WorkflowAction;
  source_filter: LeadSource | null;
  follow_up_delay_hours: number | null;
  enabled?: boolean;
};

export type WorkflowRun = {
  id: string;
  rule_id: string;
  lead_id: string;
  lead_name: string | null;
  status: WorkflowRunStatus;
  detail: string | null;
  result_entity_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type WorkflowRunListResponse = {
  items: WorkflowRun[];
  total: number;
  limit: number;
  offset: number;
};

export type KnowledgeCategory = "FAQ" | "PRODUCT" | "POLICY" | "COMPANY" | "OTHER";

export type KnowledgeEntryStatus = "ACTIVE" | "ARCHIVED";

export type KnowledgeEntry = {
  id: string;
  category: KnowledgeCategory;
  title: string;
  content: string;
  use_in_ai: boolean;
  status: KnowledgeEntryStatus;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type KnowledgeListResponse = {
  items: KnowledgeEntry[];
  total: number;
  category_counts: Record<KnowledgeCategory, number>;
};

export type KnowledgeEntryInput = {
  category: KnowledgeCategory;
  title: string;
  content: string;
  use_in_ai: boolean;
};

export type ActivityEvent = {
  id: string;
  type: ActivityEventType;
  title: string;
  summary: string | null;
  occurred_at: string;
  actor_type: ActivityActorType;
  actor_user_id: string | null;
  /** Display name of the acting user; null for agent, system and public actors. */
  actor_name?: string | null;
  agent_id: string | null;
  entity_type: ActivityEntityType;
  entity_id: string;
  lead_id: string | null;
  status: string | null;
  sales_run_id: string | null;
  execution_id: string | null;
  email_send_id: string | null;
  follow_up_id: string | null;
  follow_up_execution_id: string | null;
  draft_id: string | null;
  /**
   * Approval queue that lists the draft now; null when the draft is missing,
   * failed or outside the organization. Absent from older API responses.
   */
  draft_approval_status?: ApprovalQueueStatus | null;
  qualification_id: string | null;
};

export type ActivityListResponse = {
  items: ActivityEvent[];
  limit: number;
  offset: number;
  total: number;
  type_counts: Record<ActivityEventType, number>;
};

export type ActivityListParams = {
  type?: ActivityEventType;
  entity_type?: ActivityEntityType;
  entity_id?: string;
  lead_id?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

export type InboxConversationState = "OPEN" | "NEEDS_APPROVAL" | "CLOSED";

export type InboxTimelineKind =
  | "LEAD_CREATED"
  | "WEBSITE_ENQUIRY"
  | "CUSTOMER_REPLY"
  | "LEAD_STATUS_CHANGED"
  | "QUALIFICATION_COMPLETED"
  | "DRAFT_GENERATED"
  | "DRAFT_EDITED"
  | "DRAFT_APPROVED"
  | "DRAFT_REJECTED"
  | "EMAIL_SENT"
  | "EMAIL_FAILED"
  | "FOLLOW_UP_SCHEDULED"
  | "FOLLOW_UP_RESCHEDULED"
  | "FOLLOW_UP_COMPLETED"
  | "FOLLOW_UP_CANCELLED"
  | "FOLLOW_UP_EXECUTION_SENT"
  | "FOLLOW_UP_EXECUTION_FAILED"
  | "SALES_RUN_STARTED"
  | "SALES_RUN_WAITING_APPROVAL"
  | "SALES_RUN_COMPLETED"
  | "SALES_RUN_CANCELLED"
  | "SALES_RUN_FAILED"
  | "HUMAN_ATTENTION_REQUIRED"
  | "HUMAN_ATTENTION_RESOLVED"
  | "AGENT_EXECUTION_COMPLETED"
  | "AGENT_EXECUTION_FAILED"
  | "SALES_AGENT_AUTO_START_SKIPPED"
  | "SALES_AGENT_AUTO_START_FAILED";

export type InboxDirection = "inbound" | "outbound" | "internal";

export type InboxItem = {
  lead_id: string;
  name: string;
  email: string | null;
  company: string | null;
  source: LeadSource;
  lead_status: LeadStatus;
  human_attention_required?: boolean;
  conversation_state: InboxConversationState;
  needs_approval: boolean;
  last_activity_at: string;
  last_activity_type: ActivityEventType | null;
  last_activity_title: string | null;
  preview: string | null;
  latest_draft: LeadResponseDraftSummary | null;
  latest_email_status: LeadEmailSendStatus | null;
  latest_sales_run: LeadLatestSalesRunSummary | null;
  latest_follow_up_status: LeadFollowUpStatus | null;
  latest_follow_up_overdue: boolean | null;
};

export type InboxListResponse = {
  items: InboxItem[];
  limit: number;
  offset: number;
  total: number;
  state_counts: Record<InboxConversationState, number>;
  needs_approval_count: number;
  human_attention_count?: number;
};

export type InboxListParams = {
  q?: string;
  lead_status?: LeadStatus;
  needs_approval?: boolean;
  human_attention_required?: boolean;
  conversation_state?: InboxConversationState;
  email_status?: LeadEmailSendStatus;
  sales_run_status?: SalesRunStatus;
  follow_up_status?: LeadFollowUpStatus;
  source?: LeadSource;
  limit?: number;
  offset?: number;
};

export type InboxLeadContext = {
  lead_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  source: LeadSource;
  lead_status: LeadStatus;
  human_attention_required?: boolean;
  enquiry: string | null;
  conversation_state: InboxConversationState;
  needs_approval: boolean;
  latest_draft: LeadResponseDraftSummary | null;
  latest_sales_run: LeadLatestSalesRunSummary | null;
};

export type InboxTimelineItem = {
  id: string;
  kind: InboxTimelineKind;
  direction: InboxDirection;
  occurred_at: string;
  title: string;
  summary: string | null;
  body: string | null;
  status: string | null;
  actor_type: ActivityActorType | null;
  actor_user_id: string | null;
  agent_id: string | null;
  source_entity_type: ActivityEntityType;
  source_entity_id: string;
  activity_id: string | null;
  is_draft: boolean;
  is_sent_message: boolean;
  draft_id?: string | null;
  email_send_id?: string | null;
  follow_up_id?: string | null;
  follow_up_execution_id?: string | null;
  sales_run_id?: string | null;
  qualification_id?: string | null;
  inbound_email_id?: string | null;
  qualification_intent?: string | null;
  qualification_outcome?: LeadAiQualification | null;
  buying_signals?: string[];
};

export type InboxConversationResponse = {
  lead: InboxLeadContext;
  items: InboxTimelineItem[];
  total_items: number;
};

export type ApprovalQueueStatus = "pending" | "approved" | "rejected";

export type ApprovalLead = {
  name: string;
  email: string | null;
  company: string | null;
  status: LeadStatus;
  source: LeadSource;
};

export type ApprovalDraft = {
  response: string | null;
  review_status: LeadResponseReviewStatus | null;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type ApprovalSalesRun = {
  id: string;
  status: SalesRunStatus;
  stage: SalesRunStage;
  agent_id: string;
  agent_name: string | null;
};

export type ApprovalEmail = {
  status: string;
  sent_at: string | null;
};

export type ApprovalQueueItem = {
  draft_id: string;
  lead_id: string;
  lead: ApprovalLead;
  enquiry: string;
  draft: ApprovalDraft;
  sales_run: ApprovalSalesRun | null;
  email: ApprovalEmail | null;
  needs_approval: boolean;
  can_approve: boolean;
  can_reject: boolean;
  can_edit: boolean;
  can_send: boolean;
  created_at: string;
  updated_at: string;
};

export type ApprovalListResponse = {
  items: ApprovalQueueItem[];
  limit: number;
  offset: number;
  total: number;
};

export type ApprovalListParams = {
  q?: string;
  status?: ApprovalQueueStatus;
  limit?: number;
  offset?: number;
};

/** Decimal amount as sent by the API, e.g. "125000.50". Never converted to a float. */
export type MoneyString = string;

export type DealStage =
  | "QUALIFICATION"
  | "DISCOVERY"
  | "PROPOSAL"
  | "NEGOTIATION"
  | "CLOSED_WON"
  | "CLOSED_LOST";

export type DealProbabilitySource = "STAGE_DEFAULT" | "OVERRIDE";

export type Deal = {
  id: string;
  name: string;
  description: string | null;
  amount: MoneyString;
  currency: string;
  stage: DealStage;
  /** Override for open stages; null means the stage default applies. */
  probability: number | null;
  effective_probability: number;
  probability_source: DealProbabilitySource;
  expected_close_date: string;
  closed_at: string | null;
  owner_user_id: string | null;
  owner_name: string | null;
  lead_id: string | null;
  lead_name: string | null;
  lost_reason: string | null;
  revision: number;
  stage_entered_at: string;
  created_at: string;
  updated_at: string;
};

export type DealListResponse = {
  items: Deal[];
  limit: number;
  offset: number;
  total: number;
};

export type DealCreateRequest = {
  name: string;
  description?: string | null;
  amount: MoneyString;
  currency?: string;
  stage?: DealStage;
  probability?: number | null;
  expected_close_date: string;
  /** Omit to own the deal yourself; null leaves it unassigned. */
  owner_user_id?: string | null;
  lead_id?: string | null;
  lost_reason?: string | null;
};

export type DealUpdateRequest = {
  expected_revision: number;
  name?: string;
  description?: string | null;
  amount?: MoneyString;
  expected_close_date?: string;
  probability?: number | null;
  owner_user_id?: string | null;
  lost_reason?: string | null;
  change_reason?: string | null;
};

export type DealStageChangeRequest = {
  stage: DealStage;
  expected_revision: number;
  probability?: number | null;
  lost_reason?: string | null;
  change_reason?: string | null;
};

export type DealHistoryChange =
  | "CREATED"
  | "STAGE"
  | "AMOUNT"
  | "EXPECTED_CLOSE_DATE"
  | "PROBABILITY";

export type DealHistoryEvent = {
  id: string;
  deal_id: string;
  changes: DealHistoryChange[];
  previous_stage: DealStage | null;
  new_stage: DealStage;
  previous_amount: MoneyString | null;
  new_amount: MoneyString;
  previous_expected_close_date: string | null;
  new_expected_close_date: string;
  /**
   * Probability override before/after the event; null means the stage default.
   * Rows recorded before probability history existed have null (or omit) both.
   */
  previous_probability?: number | null;
  new_probability?: number | null;
  /** A manager's audited amount correction on a won deal. */
  is_correction?: boolean;
  changed_by_user_id: string | null;
  changed_by_name: string | null;
  change_reason: string | null;
  created_at: string;
};

export type DealAmountCorrectionRequest = {
  expected_revision: number;
  amount: MoneyString;
  /** Required; kept in the deal history. */
  reason: string;
};

export type DealHistoryResponse = {
  items: DealHistoryEvent[];
  limit: number;
  offset: number;
  total: number;
};

export type SalesTarget = {
  id: string;
  owner_user_id: string | null;
  owner_name: string | null;
  period_start: string;
  period_end: string;
  amount: MoneyString;
  currency: string;
  created_by_user_id: string | null;
  updated_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type SalesTargetListResponse = {
  items: SalesTarget[];
  limit: number;
  offset: number;
  total: number;
};

export type SalesTargetUpsertRequest = {
  /** First day of a calendar month (YYYY-MM-01). */
  period_start: string;
  /** Omit for an organization-wide target. */
  owner_user_id?: string | null;
  amount: MoneyString;
  currency?: string;
};

export type PipelineTotals = {
  count: number;
  total_amount: MoneyString;
};

export type PipelineSummary = {
  currency: string;
  generated_at: string;
  open: PipelineTotals & { weighted_amount: MoneyString };
  won: PipelineTotals;
  lost: PipelineTotals;
  overdue_open: PipelineTotals;
  by_stage: (PipelineTotals & {
    stage: DealStage;
    weighted_amount: MoneyString;
    default_probability: number;
  })[];
  won_by_month: (PipelineTotals & { month: string })[];
  excluded_other_currency_count: number;
};

export type ForecastGranularity = "month" | "quarter";

export type ForecastAssumptionCode =
  | "STAGE_PROBABILITY_WEIGHTING"
  | "PROBABILITY_OVERRIDES"
  | "NO_HISTORICAL_WIN_RATES"
  | "EXPECTED_CLOSE_DATE_PERIODS"
  | "PAST_DUE_SEPARATED"
  | "UTC_PERIODS"
  | "SINGLE_CURRENCY"
  | "OTHER_CURRENCY_EXCLUDED"
  | "WON_AMOUNT_CURRENT_VALUE";

/** Open deals in a bucket; override_count use a manual probability override. */
export type ForecastOpenTotals = PipelineTotals & {
  weighted_amount: MoneyString;
  override_count: number;
};

export type ForecastPeriod = {
  /** "2026-Q4" or "2026-11". */
  label: string;
  period_start: string;
  /** Inclusive. */
  period_end: string;
  /** Actual revenue: deals won inside the period. */
  won: PipelineTotals;
  /** Open deals expected to close in the period. */
  open: ForecastOpenTotals;
  /** won + weighted open, computed by the API. An estimate, not committed revenue. */
  projected_amount: MoneyString;
};

/** Stage-probability-weighted forecast computed by the API from stored deals. */
export type PipelineForecast = {
  currency: string;
  as_of: string;
  granularity: ForecastGranularity;
  method: "STAGE_PROBABILITY_WEIGHTED";
  rounding: "PER_DEAL_HALF_UP_CENTS";
  horizon_start: string;
  /** Inclusive. */
  horizon_end: string;
  periods: ForecastPeriod[];
  /** Open deals whose expected close date has passed; not forecast into any period. */
  past_due: ForecastOpenTotals & { oldest_expected_close_date: string | null };
  /** Open deals expected to close after horizon_end. */
  beyond_horizon: ForecastOpenTotals;
  /** All open deals: past due + every period + beyond horizon. */
  open_pipeline: ForecastOpenTotals;
  won_in_horizon: PipelineTotals;
  projected_in_horizon_amount: MoneyString;
  stage_probabilities: { stage: DealStage; default_probability: number }[];
  assumptions: { code: ForecastAssumptionCode; detail: string }[];
  excluded_other_currency_count: number;
};

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
  | "FAILED";

export type AgentExecutionRequest = {
  input: string;
};

export type AgentTokenUsage = {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
};

export type AgentExecutionResult = {
  execution_id: string;
  status: AgentExecutionStatus;
  output: string | null;
  provider: string | null;
  model: string | null;
  usage: AgentTokenUsage | null;
  error: string | null;
};

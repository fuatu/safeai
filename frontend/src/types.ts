export type ExplainerMode = 'plain' | 'technical' | 'off';

export interface PendingApprovalEvent {
  type: string;
  actionId: string;
  sessionId: string;
  toolName: string;
  riskScore: number;
  riskFactors: string[];
  plainExplanation: string;
  activeLanguage: string;
  rawPayload: Record<string, any>;
  timeoutSeconds: number;
  receivedAt: number;
}

export interface SafeAISettings {
  approval_threshold: number;
  active_language: string;
  explainer_mode: ExplainerMode;
  dlp_enabled: boolean;
  approval_timeout_seconds: number;
}

export interface SessionRecord {
  id: string;
  client_name: string;
  title?: string | null;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  total_actions: number;
  blocked_actions: number;
}

export interface ActionLog {
  id: string;
  session_id: string;
  timestamp: string;
  tool_name: string;
  raw_payload: string;
  plain_language_explanation: string;
  language_code: string;
  risk_score: number;
  risk_factors: string[];
  status: 'AUTO_APPROVED' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'TIMED_OUT';
  user_decision_by: string | null;
  decision_notes: string | null;
  execution_duration_ms: number | null;
  execution_result: string | null;
}

export interface PolicyRule {
  id: string;
  rule_type: 'DENY_PATH' | 'ALLOW_PATH' | 'DENY_COMMAND' | 'DENY_DOMAIN';
  pattern: string;
  description: string | null;
  is_active: boolean;
}

export interface ToolSetting {
  id?: number;
  tool_name: string;
  custom_threshold: number | null;
  downstream_url: string | null;
  bypass_approval: boolean;
  timeout_ms: number;
  is_enabled: boolean;
  description: string | null;
}

export interface ClientConfigItem {
  id: string;
  name: string;
  filename: string;
  description: string;
  target_paths?: Record<string, string>;
  config: Record<string, any>;
  command_hint?: string;
  mcp_url?: string;
  openai_url?: string;
}

export type ClientConfigsMap = Record<string, ClientConfigItem>;



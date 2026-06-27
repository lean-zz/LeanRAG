export type Role = "user" | "assistant";

export type FeedbackValue = "like" | "dislike" | null;

export type MessageStatus = "streaming" | "done" | "cancelled" | "error";

export interface User {
  userId: string;
  username?: string;
  role: string;
  token: string;
  avatar?: string;
}

export type CurrentUser = Omit<User, "token">;

export interface Session {
  id: string;
  title: string;
  lastTime?: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  thinking?: string;
  thinkingDuration?: number;
  isDeepThinking?: boolean;
  isThinking?: boolean;
  createdAt?: string;
  feedback?: FeedbackValue;
  status?: MessageStatus;
}

export interface StreamMetaPayload {
  conversationId: string;
  taskId: string;
}

export interface MessageDeltaPayload {
  type: string;
  delta: string;
}

export interface CompletionPayload {
  messageId?: string | null;
  title?: string | null;
}

export interface EvidenceItem {
  id: string;
  kind: "document" | "tool" | string;
  sourceId?: string | null;
  title?: string | null;
  locator?: string | null;
  snippet?: string | null;
  score?: number | null;
  channel?: string | null;
  producedByNode?: string | null;
  sensitivityLevel?: string | null;
  messageId?: string | null;
}

export interface GuardrailResult {
  action: "allow" | "redact" | "block" | "escalate" | string;
  reason?: string | null;
  sanitizedText?: string | null;
  summary?: string | null;
}

export interface ReliabilityDecision {
  type: "answer" | "clarify" | "refuse" | "escalate" | "fallback" | string;
  reasons?: string[];
  confidence?: number | null;
  guardrailSummary?: string | null;
  messageId?: string | null;
}

export interface ExperimentAssignment {
  id: string;
  experimentId: string;
  userId: string;
  conversationId?: string | null;
  variant: string;
  bucket: number;
  config?: Record<string, unknown>;
  assignedAt?: string;
}

export interface EvalCaseResult {
  id: string;
  caseId?: string | null;
  category?: string | null;
  passed: boolean;
  guardrailAction?: string | null;
  expectedGuardrailAction?: string | null;
  decisionType?: string | null;
  requiredEvidence?: string[];
  forbiddenClaims?: string[];
  citationCoverage?: number | null;
}

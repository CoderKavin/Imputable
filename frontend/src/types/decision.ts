/**
 * Imputable TypeScript Types
 * Mirrors the backend Pydantic schemas
 */

// =============================================================================
// ENUMS
// =============================================================================

export type DecisionStatus =
  | "draft"
  | "pending_review"
  | "approved"
  | "deprecated"
  | "superseded";

export type ImpactLevel = "low" | "medium" | "high" | "critical";

export type RelationshipType =
  | "supersedes"
  | "blocked_by"
  | "related_to"
  | "implements"
  | "conflicts_with";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "abstained";

// =============================================================================
// USER & TEAM
// =============================================================================

export interface UserRef {
  id: string;
  name: string;
  email?: string;
  avatar_url?: string;
}

export interface TeamRef {
  id: string;
  slug: string;
  name: string;
}

// =============================================================================
// DECISION CONTENT
// =============================================================================

export interface Alternative {
  name: string;
  rejected_reason: string;
}

export interface DecisionContent {
  context: string;
  choice: string;
  rationale: string;
  alternatives: Alternative[];
  consequences?: string;
  review_date?: string;
}

// =============================================================================
// DECISION VERSION
// =============================================================================

export interface DecisionVersion {
  id: string;
  version_number: number;
  title: string;
  impact_level: ImpactLevel;
  content: DecisionContent;
  tags: string[];
  content_hash?: string;
  created_by: UserRef;
  created_at: string;
  change_summary?: string;
  is_current: boolean;
}

export interface VersionHistoryItem {
  id: string;
  version_number: number;
  title: string;
  impact_level: ImpactLevel;
  content_hash: string;
  created_by: UserRef;
  created_at: string;
  change_summary?: string;
}

// =============================================================================
// DECISION
// =============================================================================

export interface Decision {
  id: string;
  organization_id: string;
  decision_number: number;
  status: DecisionStatus;
  created_by: UserRef;
  created_at: string;
  version: DecisionVersion;
  version_count: number;
  requested_version?: number;
}

export interface DecisionSummary {
  id: string;
  decision_number: number;
  title: string;
  status: DecisionStatus;
  impact_level: ImpactLevel;
  tags: string[];
  owner_team?: TeamRef;
  created_by: UserRef;
  created_at: string;
  version_count: number;
}

// =============================================================================
// RELATIONSHIPS
// =============================================================================

export interface DecisionRef {
  id: string;
  decision_number: number;
  title: string;
  status: DecisionStatus;
}

export interface DecisionRelationship {
  id: string;
  source_decision: DecisionRef;
  target_decision: DecisionRef;
  relationship_type: RelationshipType;
  description?: string;
  created_by: UserRef;
  created_at: string;
}

export interface DecisionLineage {
  current_decision: DecisionRef;
  predecessors: DecisionRef[];
  successors: DecisionRef[];
}

// =============================================================================
// API REQUESTS
// =============================================================================

export interface CreateDecisionRequest {
  title: string;
  content: DecisionContent;
  impact_level?: ImpactLevel;
  tags?: string[];
  owner_team_id?: string;
  reviewer_ids?: string[];
}

export interface AmendDecisionRequest {
  title: string;
  content: DecisionContent;
  impact_level: ImpactLevel;
  tags?: string[];
  change_summary: string;
  expected_version?: number;
}

export interface SupersedeRequest {
  new_decision_id: string;
  reason?: string;
}

// =============================================================================
// API RESPONSES
// =============================================================================

export interface SupersedeResponse {
  old_decision_id: string;
  old_decision_number: number;
  new_decision_id: string;
  new_decision_number: number;
  relationship_id: string;
  message: string;
}

export interface VersionCompareResponse {
  version_a: {
    number: number;
    title: string;
    content: DecisionContent;
    tags: string[];
    created_at: string;
  };
  version_b: {
    number: number;
    title: string;
    content: DecisionContent;
    tags: string[];
    created_at: string;
  };
  changes: {
    title_changed: boolean;
    content_changed: boolean;
    tags_changed: boolean;
  };
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// =============================================================================
// UI STATE
// =============================================================================

export interface VersionViewState {
  decision: Decision;
  selectedVersion: number;
  compareMode: boolean;
  compareVersion?: number;
}

export type DiffMode = "unified" | "split" | "inline";

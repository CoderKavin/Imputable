/**
 * React Query Hooks for Risk Dashboard
 * Provides data fetching for tech debt tracking and executive views
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";

// =============================================================================
// TYPES
// =============================================================================

export interface RiskStats {
  total_expired: number;
  total_at_risk: number;
  expiring_this_week: number;
  expiring_this_month: number;
  by_team: Record<string, number>;
  by_impact: Record<string, number>;
}

export interface ExpiringDecision {
  decision_id: string;
  decision_number: number;
  title: string;
  owner_team_name: string | null;
  creator_name: string;
  review_by_date: string;
  days_until_expiry: number;
  status: "expired" | "at_risk" | "approved";
  is_temporary: boolean;
  last_reminder_sent: string | null;
}

export interface ExpiringDecisionsList {
  decisions: ExpiringDecision[];
  total_count: number;
  has_more: boolean;
}

export interface CalendarDay {
  date: string;
  decisions: Array<{
    id: string;
    decision_number: number;
    title: string;
    status: string;
    impact_level: string;
    team_name: string | null;
    is_temporary: boolean;
  }>;
}

export interface CalendarData {
  start_date: string;
  end_date: string;
  days: CalendarDay[];
}

export interface HeatmapDataPoint {
  week: string;
  count: number;
}

export interface HeatmapData {
  data: HeatmapDataPoint[];
  max_count: number;
  total_decisions: number;
}

export interface TeamHeatmapItem {
  team_name: string;
  team_id: string | null;
  expired_count: number;
  at_risk_count: number;
  healthy_count: number;
  total_count: number;
  health_score: number;
  color: "red" | "yellow" | "green";
}

export interface TeamHeatmapData {
  teams: TeamHeatmapItem[];
}

export interface TagHeatmapItem {
  tag: string;
  expired_count: number;
  at_risk_count: number;
  total_count: number;
  health_score: number;
  color: "red" | "yellow" | "green";
}

export interface TagHeatmapData {
  tags: TagHeatmapItem[];
}

export interface SnoozeRequest {
  days: number;
  reason?: string;
}

export interface SnoozeResponse {
  decision_id: string;
  old_review_date: string;
  new_review_date: string;
  days_extended: number;
  message: string;
}

export interface RequestUpdateRequest {
  message?: string;
  urgency?: "low" | "normal" | "high" | "critical";
}

export interface RequestUpdateResponse {
  request_id: string;
  decision_id: string;
  message: string;
}

export interface ResolveRequest {
  resolution_note: string;
  new_review_date?: string;
}

export interface ResolveResponse {
  decision_id: string;
  decision_number: number;
  new_status: string;
  message: string;
}

export interface UpdateRequest {
  id: string;
  decision_id: string;
  decision_number: number | null;
  decision_title: string | null;
  requested_by_name: string;
  message: string | null;
  urgency: string;
  created_at: string;
}

// =============================================================================
// API CLIENT
// =============================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    credentials: "include",
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

const riskApi = {
  getStats: () => fetchApi<RiskStats>("/risk-dashboard/stats"),

  getExpiringDecisions: (params?: {
    status_filter?: string;
    team_id?: string;
    limit?: number;
    offset?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params?.status_filter)
      searchParams.set("status_filter", params.status_filter);
    if (params?.team_id) searchParams.set("team_id", params.team_id);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));

    const query = searchParams.toString();
    return fetchApi<ExpiringDecisionsList>(
      `/risk-dashboard/expiring${query ? `?${query}` : ""}`,
    );
  },

  getCalendar: (startDate?: string, endDate?: string) => {
    const searchParams = new URLSearchParams();
    if (startDate) searchParams.set("start_date", startDate);
    if (endDate) searchParams.set("end_date", endDate);

    const query = searchParams.toString();
    return fetchApi<CalendarData>(
      `/risk-dashboard/calendar${query ? `?${query}` : ""}`,
    );
  },

  getHeatmap: (months = 12) =>
    fetchApi<HeatmapData>(`/risk-dashboard/heatmap?months=${months}`),

  getTeamHeatmap: () =>
    fetchApi<TeamHeatmapData>("/risk-dashboard/heatmap/teams"),

  getTagHeatmap: () => fetchApi<TagHeatmapData>("/risk-dashboard/heatmap/tags"),

  snoozeDecision: (decisionId: string, data: SnoozeRequest) =>
    fetchApi<SnoozeResponse>(`/risk-dashboard/decisions/${decisionId}/snooze`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  requestUpdate: (decisionId: string, data: RequestUpdateRequest) =>
    fetchApi<RequestUpdateResponse>(
      `/risk-dashboard/decisions/${decisionId}/request-update`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  resolveDecision: (decisionId: string, data: ResolveRequest) =>
    fetchApi<ResolveResponse>(
      `/risk-dashboard/decisions/${decisionId}/resolve`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    ),

  getUpdateRequests: (myDecisionsOnly = false) =>
    fetchApi<UpdateRequest[]>(
      `/risk-dashboard/update-requests?my_decisions_only=${myDecisionsOnly}`,
    ),
};

// =============================================================================
// QUERY KEYS
// =============================================================================

export const riskDashboardKeys = {
  all: ["risk-dashboard"] as const,
  stats: () => [...riskDashboardKeys.all, "stats"] as const,
  expiring: (filters?: object) =>
    [...riskDashboardKeys.all, "expiring", filters] as const,
  calendar: (startDate?: string, endDate?: string) =>
    [...riskDashboardKeys.all, "calendar", startDate, endDate] as const,
  heatmap: (months: number) =>
    [...riskDashboardKeys.all, "heatmap", months] as const,
  teamHeatmap: () => [...riskDashboardKeys.all, "heatmap", "teams"] as const,
  tagHeatmap: () => [...riskDashboardKeys.all, "heatmap", "tags"] as const,
  updateRequests: (myDecisionsOnly: boolean) =>
    [...riskDashboardKeys.all, "update-requests", myDecisionsOnly] as const,
};

// =============================================================================
// QUERY HOOKS
// =============================================================================

/**
 * Fetch risk dashboard overview statistics
 */
export function useRiskStats(
  options?: Omit<UseQueryOptions<RiskStats>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: riskDashboardKeys.stats(),
    queryFn: riskApi.getStats,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Refresh every minute
    ...options,
  });
}

/**
 * Fetch list of expiring decisions with optional filters
 */
export function useExpiringDecisions(
  filters?: {
    status_filter?: string;
    team_id?: string;
    limit?: number;
    offset?: number;
  },
  options?: Omit<
    UseQueryOptions<ExpiringDecisionsList>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: riskDashboardKeys.expiring(filters),
    queryFn: () => riskApi.getExpiringDecisions(filters),
    staleTime: 30 * 1000,
    ...options,
  });
}

/**
 * Fetch calendar data for debt wall view
 */
export function useCalendarData(
  startDate?: string,
  endDate?: string,
  options?: Omit<UseQueryOptions<CalendarData>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: riskDashboardKeys.calendar(startDate, endDate),
    queryFn: () => riskApi.getCalendar(startDate, endDate),
    staleTime: 60 * 1000,
    ...options,
  });
}

/**
 * Fetch heatmap data for visualization
 */
export function useHeatmapData(
  months = 12,
  options?: Omit<UseQueryOptions<HeatmapData>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: riskDashboardKeys.heatmap(months),
    queryFn: () => riskApi.getHeatmap(months),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Fetch team-based heatmap data
 */
export function useTeamHeatmap(
  options?: Omit<UseQueryOptions<TeamHeatmapData>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: riskDashboardKeys.teamHeatmap(),
    queryFn: riskApi.getTeamHeatmap,
    staleTime: 60 * 1000, // 1 minute
    ...options,
  });
}

/**
 * Fetch tag-based heatmap data
 */
export function useTagHeatmap(
  options?: Omit<UseQueryOptions<TagHeatmapData>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: riskDashboardKeys.tagHeatmap(),
    queryFn: riskApi.getTagHeatmap,
    staleTime: 60 * 1000, // 1 minute
    ...options,
  });
}

/**
 * Fetch pending update requests
 */
export function useUpdateRequests(
  myDecisionsOnly = false,
  options?: Omit<UseQueryOptions<UpdateRequest[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: riskDashboardKeys.updateRequests(myDecisionsOnly),
    queryFn: () => riskApi.getUpdateRequests(myDecisionsOnly),
    staleTime: 30 * 1000,
    ...options,
  });
}

// =============================================================================
// MUTATION HOOKS
// =============================================================================

/**
 * Snooze a decision (extend review date)
 */
export function useSnoozeDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      decisionId,
      data,
    }: {
      decisionId: string;
      data: SnoozeRequest;
    }) => riskApi.snoozeDecision(decisionId, data),
    onSuccess: () => {
      // Invalidate all risk dashboard data
      queryClient.invalidateQueries({ queryKey: riskDashboardKeys.all });
    },
  });
}

/**
 * Request an update from decision owner
 */
export function useRequestUpdate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      decisionId,
      data,
    }: {
      decisionId: string;
      data: RequestUpdateRequest;
    }) => riskApi.requestUpdate(decisionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: riskDashboardKeys.updateRequests(false),
      });
      queryClient.invalidateQueries({
        queryKey: riskDashboardKeys.updateRequests(true),
      });
    },
  });
}

/**
 * Resolve tech debt for a decision
 */
export function useResolveDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      decisionId,
      data,
    }: {
      decisionId: string;
      data: ResolveRequest;
    }) => riskApi.resolveDecision(decisionId, data),
    onSuccess: () => {
      // Invalidate all risk dashboard data
      queryClient.invalidateQueries({ queryKey: riskDashboardKeys.all });
    },
  });
}

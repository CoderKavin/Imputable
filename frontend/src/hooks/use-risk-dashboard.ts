/**
 * React Query Hooks for Risk Dashboard
 * Provides data fetching for tech debt tracking and executive views
 *
 * Uses Firebase authentication via useApiClient hook.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { useApiClient } from "./use-api";
import { useCallback } from "react";

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
// AUTHENTICATED API HOOK
// =============================================================================

/**
 * Hook for risk dashboard API calls with Firebase auth
 */
export function useRiskDashboardApi() {
  const client = useApiClient();

  const getStats = useCallback(async (): Promise<RiskStats> => {
    const response = await client.get<RiskStats>("/risk-dashboard/stats");
    return response.data;
  }, [client]);

  const getExpiringDecisions = useCallback(
    async (params?: {
      status_filter?: string;
      team_id?: string;
      limit?: number;
      offset?: number;
    }): Promise<ExpiringDecisionsList> => {
      const response = await client.get<ExpiringDecisionsList>(
        "/risk-dashboard/expiring",
        { params },
      );
      return response.data;
    },
    [client],
  );

  const getCalendar = useCallback(
    async (startDate?: string, endDate?: string): Promise<CalendarData> => {
      const response = await client.get<CalendarData>(
        "/risk-dashboard/calendar",
        {
          params: { start_date: startDate, end_date: endDate },
        },
      );
      return response.data;
    },
    [client],
  );

  const getHeatmap = useCallback(
    async (months = 12): Promise<HeatmapData> => {
      const response = await client.get<HeatmapData>(
        "/risk-dashboard/heatmap",
        {
          params: { months },
        },
      );
      return response.data;
    },
    [client],
  );

  const getTeamHeatmap = useCallback(async (): Promise<TeamHeatmapData> => {
    const response = await client.get<TeamHeatmapData>(
      "/risk-dashboard/heatmap/teams",
    );
    return response.data;
  }, [client]);

  const getTagHeatmap = useCallback(async (): Promise<TagHeatmapData> => {
    const response = await client.get<TagHeatmapData>(
      "/risk-dashboard/heatmap/tags",
    );
    return response.data;
  }, [client]);

  const snoozeDecision = useCallback(
    async (
      decisionId: string,
      data: SnoozeRequest,
    ): Promise<SnoozeResponse> => {
      const response = await client.post<SnoozeResponse>(
        `/risk-dashboard/decisions/${decisionId}/snooze`,
        data,
      );
      return response.data;
    },
    [client],
  );

  const requestUpdate = useCallback(
    async (
      decisionId: string,
      data: RequestUpdateRequest,
    ): Promise<RequestUpdateResponse> => {
      const response = await client.post<RequestUpdateResponse>(
        `/risk-dashboard/decisions/${decisionId}/request-update`,
        data,
      );
      return response.data;
    },
    [client],
  );

  const resolveDecision = useCallback(
    async (
      decisionId: string,
      data: ResolveRequest,
    ): Promise<ResolveResponse> => {
      const response = await client.post<ResolveResponse>(
        `/risk-dashboard/decisions/${decisionId}/resolve`,
        data,
      );
      return response.data;
    },
    [client],
  );

  const getUpdateRequests = useCallback(
    async (myDecisionsOnly = false): Promise<UpdateRequest[]> => {
      const response = await client.get<UpdateRequest[]>(
        "/risk-dashboard/update-requests",
        { params: { my_decisions_only: myDecisionsOnly } },
      );
      return response.data;
    },
    [client],
  );

  return {
    getStats,
    getExpiringDecisions,
    getCalendar,
    getHeatmap,
    getTeamHeatmap,
    getTagHeatmap,
    snoozeDecision,
    requestUpdate,
    resolveDecision,
    getUpdateRequests,
  };
}

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
  const { getStats } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [...riskDashboardKeys.stats(), currentOrganization?.id],
    queryFn: getStats,
    staleTime: 5 * 60 * 1000, // 5 minutes - stats don't change frequently
    // Removed auto-refetch - was causing unnecessary API calls every minute
    enabled: !!user && !!currentOrganization?.id,
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
  const { getExpiringDecisions } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [...riskDashboardKeys.expiring(filters), currentOrganization?.id],
    queryFn: () => getExpiringDecisions(filters),
    staleTime: 30 * 1000,
    enabled: !!user && !!currentOrganization?.id,
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
  const { getCalendar } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [
      ...riskDashboardKeys.calendar(startDate, endDate),
      currentOrganization?.id,
    ],
    queryFn: () => getCalendar(startDate, endDate),
    staleTime: 60 * 1000,
    enabled: !!user && !!currentOrganization?.id,
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
  const { getHeatmap } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [...riskDashboardKeys.heatmap(months), currentOrganization?.id],
    queryFn: () => getHeatmap(months),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!user && !!currentOrganization?.id,
    ...options,
  });
}

/**
 * Fetch team-based heatmap data
 */
export function useTeamHeatmap(
  options?: Omit<UseQueryOptions<TeamHeatmapData>, "queryKey" | "queryFn">,
) {
  const { getTeamHeatmap } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [...riskDashboardKeys.teamHeatmap(), currentOrganization?.id],
    queryFn: getTeamHeatmap,
    staleTime: 60 * 1000, // 1 minute
    enabled: !!user && !!currentOrganization?.id,
    ...options,
  });
}

/**
 * Fetch tag-based heatmap data
 */
export function useTagHeatmap(
  options?: Omit<UseQueryOptions<TagHeatmapData>, "queryKey" | "queryFn">,
) {
  const { getTagHeatmap } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [...riskDashboardKeys.tagHeatmap(), currentOrganization?.id],
    queryFn: getTagHeatmap,
    staleTime: 60 * 1000, // 1 minute
    enabled: !!user && !!currentOrganization?.id,
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
  const { getUpdateRequests } = useRiskDashboardApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [
      ...riskDashboardKeys.updateRequests(myDecisionsOnly),
      currentOrganization?.id,
    ],
    queryFn: () => getUpdateRequests(myDecisionsOnly),
    staleTime: 30 * 1000,
    enabled: !!user && !!currentOrganization?.id,
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
  const { snoozeDecision } = useRiskDashboardApi();

  return useMutation({
    mutationFn: ({
      decisionId,
      data,
    }: {
      decisionId: string;
      data: SnoozeRequest;
    }) => snoozeDecision(decisionId, data),
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
  const { requestUpdate } = useRiskDashboardApi();

  return useMutation({
    mutationFn: ({
      decisionId,
      data,
    }: {
      decisionId: string;
      data: RequestUpdateRequest;
    }) => requestUpdate(decisionId, data),
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
  const { resolveDecision } = useRiskDashboardApi();

  return useMutation({
    mutationFn: ({
      decisionId,
      data,
    }: {
      decisionId: string;
      data: ResolveRequest;
    }) => resolveDecision(decisionId, data),
    onSuccess: () => {
      // Invalidate all risk dashboard data
      queryClient.invalidateQueries({ queryKey: riskDashboardKeys.all });
    },
  });
}

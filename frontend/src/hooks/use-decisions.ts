/**
 * React Query Hooks for Imputable
 * Provides efficient data fetching with caching for version switching
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";
import { api, decisionKeys } from "@/lib/api-client";
import type {
  Decision,
  DecisionSummary,
  VersionHistoryItem,
  VersionCompareResponse,
  CreateDecisionRequest,
  AmendDecisionRequest,
  SupersedeRequest,
  SupersedeResponse,
  PaginatedResponse,
  DecisionLineage,
} from "@/types/decision";

// =============================================================================
// DECISION QUERIES
// =============================================================================

/**
 * Fetch a decision, optionally at a specific version
 * Caches each version separately for instant switching
 */
export function useDecision(
  id: string,
  version?: number,
  options?: Omit<UseQueryOptions<Decision>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: version
      ? decisionKeys.version(id, version)
      : decisionKeys.detail(id),
    queryFn: () => api.getDecision(id, version),
    staleTime: 5 * 60 * 1000, // 5 minutes - versions are immutable!
    gcTime: 30 * 60 * 1000, // Keep in cache for 30 minutes
    ...options,
  });
}

/**
 * Prefetch a specific version (for hover/anticipation)
 */
export function usePrefetchVersion() {
  const queryClient = useQueryClient();

  return (id: string, version: number) => {
    queryClient.prefetchQuery({
      queryKey: decisionKeys.version(id, version),
      queryFn: () => api.getDecision(id, version),
      staleTime: 5 * 60 * 1000,
    });
  };
}

/**
 * Fetch version history for a decision
 */
export function useVersionHistory(
  decisionId: string,
  options?: Omit<UseQueryOptions<VersionHistoryItem[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: decisionKeys.versions(decisionId),
    queryFn: () => api.getVersionHistory(decisionId),
    staleTime: 60 * 1000, // 1 minute
    ...options,
  });
}

/**
 * Compare two versions - useful for diff view
 */
export function useVersionComparison(
  decisionId: string,
  versionA: number,
  versionB: number,
  options?: Omit<
    UseQueryOptions<VersionCompareResponse>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery({
    queryKey: decisionKeys.compare(decisionId, versionA, versionB),
    queryFn: () => api.compareVersions(decisionId, versionA, versionB),
    staleTime: Infinity, // Comparisons are immutable
    enabled: versionA > 0 && versionB > 0 && versionA !== versionB,
    ...options,
  });
}

/**
 * Fetch decision list with pagination
 */
export function useDecisionList(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: decisionKeys.list(page, pageSize),
    queryFn: () => api.listDecisions(page, pageSize),
    staleTime: 30 * 1000, // 30 seconds
  });
}

/**
 * Fetch decision lineage (supersession chain)
 */
export function useDecisionLineage(
  decisionId: string,
  options?: Omit<UseQueryOptions<DecisionLineage>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: decisionKeys.lineage(decisionId),
    queryFn: () => api.getLineage(decisionId),
    staleTime: 60 * 1000,
    ...options,
  });
}

// =============================================================================
// DECISION MUTATIONS
// =============================================================================

/**
 * Create a new decision
 */
export function useCreateDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateDecisionRequest) => api.createDecision(data),
    onSuccess: (newDecision) => {
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: decisionKeys.lists() });
      // Add the new decision to cache
      queryClient.setQueryData(
        decisionKeys.detail(newDecision.id),
        newDecision,
      );
    },
  });
}

/**
 * Amend a decision (creates new version)
 * This is the core "no overwrite" mutation
 */
export function useAmendDecision(decisionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AmendDecisionRequest) =>
      api.amendDecision(decisionId, data),
    onSuccess: (updatedDecision) => {
      // Update the main decision cache
      queryClient.setQueryData(
        decisionKeys.detail(decisionId),
        updatedDecision,
      );

      // Cache the new version
      queryClient.setQueryData(
        decisionKeys.version(
          decisionId,
          updatedDecision.version.version_number,
        ),
        updatedDecision,
      );

      // Invalidate version history (new version added)
      queryClient.invalidateQueries({
        queryKey: decisionKeys.versions(decisionId),
      });

      // Invalidate list (status might have changed)
      queryClient.invalidateQueries({ queryKey: decisionKeys.lists() });
    },
  });
}

/**
 * Supersede a decision
 */
export function useSupersedeDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      oldDecisionId,
      data,
    }: {
      oldDecisionId: string;
      data: SupersedeRequest;
    }) => api.supersedeDecision(oldDecisionId, data),
    onSuccess: (response) => {
      // Invalidate both decisions
      queryClient.invalidateQueries({
        queryKey: decisionKeys.detail(response.old_decision_id),
      });
      queryClient.invalidateQueries({
        queryKey: decisionKeys.detail(response.new_decision_id),
      });
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: decisionKeys.lists() });
    },
  });
}

// =============================================================================
// OPTIMISTIC VERSION SWITCHING
// =============================================================================

/**
 * Hook for managing version selection with optimistic updates
 */
export function useVersionSwitcher(decisionId: string) {
  const queryClient = useQueryClient();
  const prefetchVersion = usePrefetchVersion();

  // Preload adjacent versions when hovering
  const preloadVersion = (version: number) => {
    prefetchVersion(decisionId, version);
  };

  // Get a cached version instantly if available
  const getCachedVersion = (version: number): Decision | undefined => {
    return queryClient.getQueryData(decisionKeys.version(decisionId, version));
  };

  // Check if a version is cached
  const isVersionCached = (version: number): boolean => {
    return !!getCachedVersion(version);
  };

  return {
    preloadVersion,
    getCachedVersion,
    isVersionCached,
  };
}

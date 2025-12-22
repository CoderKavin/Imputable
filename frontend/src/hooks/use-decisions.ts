/**
 * React Query Hooks for Imputable
 * Provides efficient data fetching with caching for version switching
 *
 * These hooks now use Firebase authentication via useDecisionApi hook.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
} from "@tanstack/react-query";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { decisionKeys } from "@/lib/api-client";
import { useDecisionApi } from "./use-api";
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
  const { getDecision } = useDecisionApi();

  return useQuery({
    queryKey: version
      ? decisionKeys.version(id, version)
      : decisionKeys.detail(id),
    queryFn: () => getDecision(id, version),
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
  const { getDecision } = useDecisionApi();

  return (id: string, version: number) => {
    queryClient.prefetchQuery({
      queryKey: decisionKeys.version(id, version),
      queryFn: () => getDecision(id, version),
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
  const { getVersionHistory } = useDecisionApi();

  return useQuery({
    queryKey: decisionKeys.versions(decisionId),
    queryFn: () => getVersionHistory(decisionId),
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
  const { compareVersions } = useDecisionApi();

  return useQuery({
    queryKey: decisionKeys.compare(decisionId, versionA, versionB),
    queryFn: () => compareVersions(decisionId, versionA, versionB),
    staleTime: Infinity, // Comparisons are immutable
    enabled: versionA > 0 && versionB > 0 && versionA !== versionB,
    ...options,
  });
}

// Alias for DiffViewer component
export const useVersionCompare = useVersionComparison;

/**
 * Fetch decision list with pagination
 */
export function useDecisionList(page = 1, pageSize = 20) {
  const { listDecisions } = useDecisionApi();
  const { user } = useAuth();
  const { currentOrganization } = useOrganization();

  return useQuery({
    queryKey: [...decisionKeys.list(page, pageSize), currentOrganization?.id],
    queryFn: () => listDecisions(page, pageSize),
    staleTime: 30 * 1000, // 30 seconds
    enabled: !!user && !!currentOrganization?.id, // Only fetch when signed in with org
  });
}

/**
 * Fetch decision lineage (supersession chain)
 * TODO: Add getLineage to useDecisionApi when backend supports it
 */
export function useDecisionLineage(
  decisionId: string,
  options?: Omit<UseQueryOptions<DecisionLineage>, "queryKey" | "queryFn">,
) {
  // Placeholder - lineage endpoint not yet implemented in useDecisionApi
  return useQuery({
    queryKey: decisionKeys.lineage(decisionId),
    queryFn: async (): Promise<DecisionLineage> => {
      // Return empty lineage for now
      return {
        current_decision: {
          id: decisionId,
          decision_number: 0,
          title: "",
          status: "draft" as const,
        },
        predecessors: [],
        successors: [],
      };
    },
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
  const { createDecision } = useDecisionApi();

  return useMutation({
    mutationFn: (data: CreateDecisionRequest) => createDecision(data),
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
  const { amendDecision } = useDecisionApi();

  return useMutation({
    mutationFn: (data: AmendDecisionRequest) => amendDecision(decisionId, data),
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
 * TODO: Add supersedeDecision to useDecisionApi when backend supports it
 */
export function useSupersedeDecision() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      oldDecisionId,
      data,
    }: {
      oldDecisionId: string;
      data: SupersedeRequest;
    }): Promise<SupersedeResponse> => {
      // Placeholder - supersede endpoint not yet implemented in useDecisionApi
      throw new Error("Supersede not yet implemented");
    },
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

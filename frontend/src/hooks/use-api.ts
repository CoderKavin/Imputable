/**
 * API Hook with Firebase Authentication
 *
 * This hook provides authenticated API access using Firebase ID tokens.
 * Use this instead of the raw api-client for all authenticated requests.
 */

import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { useCallback, useMemo } from "react";
import axios from "axios";
import type {
  Decision,
  DecisionSummary,
  PaginatedResponse,
  VersionHistoryItem,
  VersionCompareResponse,
  CreateDecisionRequest,
  AmendDecisionRequest,
  ApproveDecisionRequest,
  ApprovalProgress,
} from "@/types/decision";

// Use same-origin for Vercel Python functions
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

/**
 * Hook that provides an authenticated API client
 */
export function useApiClient() {
  const { getToken } = useAuth();
  const { currentOrganization } = useOrganization();

  const client = useMemo(() => {
    const instance = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Request interceptor to add auth headers
    instance.interceptors.request.use(async (config) => {
      try {
        const token = await getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        if (currentOrganization?.id) {
          config.headers["X-Organization-ID"] = currentOrganization.id;
        }
      } catch (error) {
        console.error("Failed to get auth token:", error);
      }
      return config;
    });

    return instance;
  }, [getToken, currentOrganization?.id]);

  return client;
}

/**
 * Hook for decision-related API calls with Firebase auth
 */
export function useDecisionApi() {
  const client = useApiClient();

  const listDecisions = useCallback(
    async (
      page = 1,
      pageSize = 20,
    ): Promise<PaginatedResponse<DecisionSummary>> => {
      const response = await client.get<PaginatedResponse<DecisionSummary>>(
        "/decisions",
        { params: { page, page_size: pageSize } },
      );
      return response.data;
    },
    [client],
  );

  const getDecision = useCallback(
    async (id: string, version?: number): Promise<Decision> => {
      const params = version ? { version } : {};
      const response = await client.get<Decision>(`/decisions/${id}`, {
        params,
      });
      return response.data;
    },
    [client],
  );

  const createDecision = useCallback(
    async (data: CreateDecisionRequest): Promise<Decision> => {
      const response = await client.post<Decision>("/decisions", data);
      return response.data;
    },
    [client],
  );

  const amendDecision = useCallback(
    async (id: string, data: AmendDecisionRequest): Promise<Decision> => {
      const response = await client.put<Decision>(`/decisions/${id}`, data);
      return response.data;
    },
    [client],
  );

  const getVersionHistory = useCallback(
    async (decisionId: string): Promise<VersionHistoryItem[]> => {
      const response = await client.get<VersionHistoryItem[]>(
        `/decisions/${decisionId}/versions`,
      );
      return response.data;
    },
    [client],
  );

  const compareVersions = useCallback(
    async (
      decisionId: string,
      versionA: number,
      versionB: number,
    ): Promise<VersionCompareResponse> => {
      const response = await client.get<VersionCompareResponse>(
        `/decisions/${decisionId}/compare`,
        { params: { version_a: versionA, version_b: versionB } },
      );
      return response.data;
    },
    [client],
  );

  const approveDecision = useCallback(
    async (
      decisionId: string,
      data: ApproveDecisionRequest,
    ): Promise<{
      success: boolean;
      approval_progress: ApprovalProgress;
      decision_status: string;
    }> => {
      const response = await client.post(
        `/decisions/${decisionId}/approve`,
        data,
      );
      return response.data;
    },
    [client],
  );

  return {
    listDecisions,
    getDecision,
    createDecision,
    amendDecision,
    getVersionHistory,
    compareVersions,
    approveDecision,
  };
}

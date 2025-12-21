/**
 * API Client for Imputable
 * Handles all communication with the backend
 *
 * Note: This client now integrates with Clerk for authentication.
 * The token is fetched from Clerk's session.
 */

import axios, { AxiosInstance, AxiosError } from "axios";
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
// CONFIGURATION
// =============================================================================

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// =============================================================================
// AUTH TYPES
// =============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface DevLoginRequest {
  email: string;
  organization_id?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  user_name: string;
  user_email: string;
  organization_id?: string;
  organization_name?: string;
}

export interface DevUser {
  id: string;
  name: string;
  email: string;
  organizations: Array<{
    id: string;
    name: string;
    slug: string;
  }>;
}

// =============================================================================
// ERROR HANDLING
// =============================================================================

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function handleApiError(error: AxiosError): never {
  if (error.response) {
    const data = error.response.data as Record<string, unknown>;
    throw new ApiError(
      (data.message as string) ||
        (data.detail as string) ||
        "An error occurred",
      error.response.status,
      data.code as string,
      data.details as Record<string, unknown>,
    );
  }
  throw new ApiError("Network error", 0);
}

// =============================================================================
// API CLIENT CLASS
// =============================================================================

class ImputableApi {
  private client: AxiosInstance;
  private organizationId: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Request interceptor to add auth and org headers
    this.client.interceptors.request.use((config) => {
      const token = this.getToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      if (this.organizationId) {
        config.headers["X-Organization-ID"] = this.organizationId;
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => handleApiError(error),
    );
  }

  // Auth helpers
  private getToken(): string | null {
    if (typeof window !== "undefined") {
      return localStorage.getItem("auth_token");
    }
    return null;
  }

  setToken(token: string): void {
    if (typeof window !== "undefined") {
      localStorage.setItem("auth_token", token);
    }
  }

  clearToken(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("user_info");
    }
    this.organizationId = null;
  }

  setOrganization(orgId: string): void {
    this.organizationId = orgId;
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  // =========================================================================
  // AUTHENTICATION
  // =========================================================================

  /**
   * Login with email and password
   */
  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>("/auth/login", data);
    const tokenData = response.data;

    // Store token and org
    this.setToken(tokenData.access_token);
    if (tokenData.organization_id) {
      this.setOrganization(tokenData.organization_id);
    }

    // Store user info
    if (typeof window !== "undefined") {
      localStorage.setItem(
        "user_info",
        JSON.stringify({
          id: tokenData.user_id,
          name: tokenData.user_name,
          email: tokenData.user_email,
          organization_id: tokenData.organization_id,
          organization_name: tokenData.organization_name,
        }),
      );
    }

    return tokenData;
  }

  /**
   * Dev login (no password required)
   */
  async devLogin(data: DevLoginRequest): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>(
      "/auth/dev-login",
      data,
    );
    const tokenData = response.data;

    // Store token and org
    this.setToken(tokenData.access_token);
    if (tokenData.organization_id) {
      this.setOrganization(tokenData.organization_id);
    }

    // Store user info
    if (typeof window !== "undefined") {
      localStorage.setItem(
        "user_info",
        JSON.stringify({
          id: tokenData.user_id,
          name: tokenData.user_name,
          email: tokenData.user_email,
          organization_id: tokenData.organization_id,
          organization_name: tokenData.organization_name,
        }),
      );
    }

    return tokenData;
  }

  /**
   * Get available users for dev login
   */
  async getDevUsers(): Promise<DevUser[]> {
    const response = await this.client.get<DevUser[]>("/auth/users");
    return response.data;
  }

  /**
   * Logout - clear stored credentials
   */
  logout(): void {
    this.clearToken();
  }

  // =========================================================================
  // DECISIONS - CRUD
  // =========================================================================

  /**
   * Create a new decision
   */
  async createDecision(data: CreateDecisionRequest): Promise<Decision> {
    const response = await this.client.post<Decision>("/decisions", data);
    return response.data;
  }

  /**
   * Get a decision by ID, optionally at a specific version (time travel)
   */
  async getDecision(id: string, version?: number): Promise<Decision> {
    const params = version ? { version } : {};
    const response = await this.client.get<Decision>(`/decisions/${id}`, {
      params,
    });
    return response.data;
  }

  /**
   * Amend a decision (creates new version)
   */
  async amendDecision(
    id: string,
    data: AmendDecisionRequest,
  ): Promise<Decision> {
    const response = await this.client.put<Decision>(`/decisions/${id}`, data);
    return response.data;
  }

  /**
   * List decisions with pagination
   */
  async listDecisions(
    page = 1,
    pageSize = 20,
  ): Promise<PaginatedResponse<DecisionSummary>> {
    const response = await this.client.get<PaginatedResponse<DecisionSummary>>(
      "/decisions",
      { params: { page, page_size: pageSize } },
    );
    return response.data;
  }

  // =========================================================================
  // VERSION HISTORY
  // =========================================================================

  /**
   * Get all versions of a decision
   */
  async getVersionHistory(decisionId: string): Promise<VersionHistoryItem[]> {
    const response = await this.client.get<VersionHistoryItem[]>(
      `/decisions/${decisionId}/versions`,
    );
    return response.data;
  }

  /**
   * Compare two versions of a decision
   */
  async compareVersions(
    decisionId: string,
    versionA: number,
    versionB: number,
  ): Promise<VersionCompareResponse> {
    const response = await this.client.get<VersionCompareResponse>(
      `/decisions/${decisionId}/compare`,
      { params: { version_a: versionA, version_b: versionB } },
    );
    return response.data;
  }

  // =========================================================================
  // SUPERSESSION
  // =========================================================================

  /**
   * Supersede a decision with another
   */
  async supersedeDecision(
    oldDecisionId: string,
    data: SupersedeRequest,
  ): Promise<SupersedeResponse> {
    const response = await this.client.post<SupersedeResponse>(
      `/decisions/${oldDecisionId}/supersede`,
      data,
    );
    return response.data;
  }

  /**
   * Get the supersession lineage of a decision
   */
  async getLineage(decisionId: string): Promise<DecisionLineage> {
    const response = await this.client.get<DecisionLineage>(
      `/decisions/${decisionId}/lineage`,
    );
    return response.data;
  }

  /**
   * Get the current (non-superseded) version of a decision chain
   */
  async getCurrentDecision(decisionId: string): Promise<Decision> {
    const response = await this.client.get<Decision>(
      `/decisions/${decisionId}/current`,
    );
    return response.data;
  }
}

// Singleton instance
export const api = new ImputableApi();

// =============================================================================
// REACT QUERY KEY FACTORIES
// =============================================================================

export const decisionKeys = {
  all: ["decisions"] as const,
  lists: () => [...decisionKeys.all, "list"] as const,
  list: (page: number, pageSize: number) =>
    [...decisionKeys.lists(), { page, pageSize }] as const,
  details: () => [...decisionKeys.all, "detail"] as const,
  detail: (id: string) => [...decisionKeys.details(), id] as const,
  version: (id: string, version: number) =>
    [...decisionKeys.detail(id), "version", version] as const,
  versions: (id: string) => [...decisionKeys.detail(id), "versions"] as const,
  compare: (id: string, versionA: number, versionB: number) =>
    [...decisionKeys.detail(id), "compare", versionA, versionB] as const,
  lineage: (id: string) => [...decisionKeys.detail(id), "lineage"] as const,
};

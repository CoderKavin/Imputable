import { auth, currentUser } from "@clerk/nextjs/server";

/**
 * Auth Helper Functions for Server Components
 *
 * These functions provide easy access to the current user's
 * authentication context in Server Components and Server Actions.
 */

/**
 * Get the current authentication context
 * Returns userId, orgId, and other auth properties
 *
 * Usage in Server Components:
 * ```tsx
 * import { getAuthContext } from "@/lib/auth";
 *
 * export default async function MyServerComponent() {
 *   const { userId, orgId } = await getAuthContext();
 *
 *   if (!userId) {
 *     return <div>Not authenticated</div>;
 *   }
 *
 *   // Use userId and orgId to fetch data
 *   const decisions = await fetchDecisions(orgId);
 *   return <DecisionList decisions={decisions} />;
 * }
 * ```
 */
export async function getAuthContext() {
  const authResult = await auth();

  return {
    userId: authResult.userId,
    orgId: authResult.orgId,
    orgRole: authResult.orgRole,
    orgSlug: authResult.orgSlug,
    sessionId: authResult.sessionId,
    sessionClaims: authResult.sessionClaims,
    // Helper to check if user has selected an organization
    hasOrganization: !!authResult.orgId,
    // Helper to check if user is authenticated
    isAuthenticated: !!authResult.userId,
  };
}

/**
 * Get the current user's full profile
 * Includes email, name, and other user details
 *
 * Usage:
 * ```tsx
 * const user = await getCurrentUser();
 * console.log(user?.emailAddresses[0]?.emailAddress);
 * ```
 */
export async function getCurrentUser() {
  return await currentUser();
}

/**
 * Require authentication - throws redirect if not authenticated
 * Use this at the top of protected Server Components
 *
 * Usage:
 * ```tsx
 * export default async function ProtectedPage() {
 *   const { userId, orgId } = await requireAuth();
 *   // Safe to use userId and orgId here - they're guaranteed to exist
 * }
 * ```
 */
export async function requireAuth() {
  const authResult = await auth();

  if (!authResult.userId) {
    throw new Error("Unauthorized: User must be signed in");
  }

  return {
    userId: authResult.userId,
    orgId: authResult.orgId,
    orgRole: authResult.orgRole,
    orgSlug: authResult.orgSlug,
  };
}

/**
 * Require organization context - throws if no org selected
 * Use this for pages that require an organization to be selected
 *
 * Usage:
 * ```tsx
 * export default async function OrgPage() {
 *   const { userId, orgId } = await requireOrganization();
 *   // Safe to use orgId here - it's guaranteed to exist
 * }
 * ```
 */
export async function requireOrganization() {
  const authResult = await auth();

  if (!authResult.userId) {
    throw new Error("Unauthorized: User must be signed in");
  }

  if (!authResult.orgId) {
    throw new Error("Organization required: Please select an organization");
  }

  return {
    userId: authResult.userId,
    orgId: authResult.orgId,
    orgRole: authResult.orgRole!,
    orgSlug: authResult.orgSlug!,
  };
}

/**
 * Check if current user has admin role in the organization
 */
export async function isOrgAdmin() {
  const authResult = await auth();
  return authResult.orgRole === "org:admin";
}

/**
 * Get auth headers for API requests from Server Components
 * Use this when making requests to your backend API
 *
 * Usage:
 * ```tsx
 * const headers = await getAuthHeaders();
 * const response = await fetch('/api/decisions', { headers });
 * ```
 */
export async function getAuthHeaders(): Promise<HeadersInit> {
  const authResult = await auth();
  const token = await authResult.getToken();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (authResult.orgId) {
    headers["X-Organization-ID"] = authResult.orgId;
  }

  return headers;
}

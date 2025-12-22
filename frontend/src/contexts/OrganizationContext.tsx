"use client";

/**
 * Organization Context
 *
 * Manages organization state and switching for multi-tenant functionality.
 * Organizations are stored in the database and fetched via API.
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { useAuth } from "./AuthContext";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role?: string;
}

interface OrganizationContextType {
  organizations: Organization[];
  currentOrganization: Organization | null;
  loading: boolean;
  error: string | null;
  switchOrganization: (orgId: string) => void;
  refreshOrganizations: () => Promise<void>;
  createOrganization: (name: string, slug: string) => Promise<Organization>;
}

const OrganizationContext = createContext<OrganizationContextType | undefined>(
  undefined,
);

const CURRENT_ORG_KEY = "imputable_current_org";

export function OrganizationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading: authLoading, getToken } = useAuth();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [currentOrganization, setCurrentOrganization] =
    useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrganizations = useCallback(async () => {
    if (!user) {
      setOrganizations([]);
      setCurrentOrganization(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const token = await getToken();
      if (!token) {
        setLoading(false);
        return;
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/me/organizations`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!response.ok) {
        throw new Error("Failed to fetch organizations");
      }

      const data = await response.json();
      const orgs: Organization[] = data.organizations || data || [];
      setOrganizations(orgs);

      // Restore previously selected org from localStorage
      const savedOrgId = localStorage.getItem(CURRENT_ORG_KEY);
      const savedOrg = orgs.find((o) => o.id === savedOrgId);

      if (savedOrg) {
        setCurrentOrganization(savedOrg);
      } else if (orgs.length > 0) {
        // Default to first organization
        setCurrentOrganization(orgs[0]);
        localStorage.setItem(CURRENT_ORG_KEY, orgs[0].id);
      }
    } catch (err) {
      console.error("Error fetching organizations:", err);
      setError(
        err instanceof Error ? err.message : "Failed to fetch organizations",
      );
    } finally {
      setLoading(false);
    }
  }, [user, getToken]);

  // Fetch organizations when user changes
  useEffect(() => {
    if (!authLoading) {
      fetchOrganizations();
    }
  }, [user, authLoading, fetchOrganizations]);

  const switchOrganization = useCallback(
    (orgId: string) => {
      const org = organizations.find((o) => o.id === orgId);
      if (org) {
        setCurrentOrganization(org);
        localStorage.setItem(CURRENT_ORG_KEY, orgId);
      }
    },
    [organizations],
  );

  const refreshOrganizations = useCallback(async () => {
    await fetchOrganizations();
  }, [fetchOrganizations]);

  const createOrganization = useCallback(
    async (name: string, slug: string): Promise<Organization> => {
      const token = await getToken();
      if (!token) {
        throw new Error("Not authenticated");
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/me/organizations`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ name, slug }),
        },
      );

      if (!response.ok) {
        const errorText = await response.text();
        let errorDetail = `Failed to create organization (${response.status})`;
        try {
          const errorData = JSON.parse(errorText);
          errorDetail = errorData.detail || errorDetail;
        } catch {
          // Response wasn't JSON
          if (errorText) {
            errorDetail = errorText.substring(0, 100);
          }
        }
        console.error("Create org error:", response.status, errorDetail);
        throw new Error(errorDetail);
      }

      const newOrg = await response.json();

      // Refresh org list and switch to the new org
      await fetchOrganizations();
      setCurrentOrganization(newOrg);
      localStorage.setItem(CURRENT_ORG_KEY, newOrg.id);

      return newOrg;
    },
    [getToken, fetchOrganizations],
  );

  const value: OrganizationContextType = {
    organizations,
    currentOrganization,
    loading: loading || authLoading,
    error,
    switchOrganization,
    refreshOrganizations,
    createOrganization,
  };

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization() {
  const context = useContext(OrganizationContext);
  if (context === undefined) {
    throw new Error(
      "useOrganization must be used within an OrganizationProvider",
    );
  }
  return context;
}

// Convenience hook to get just the current org
export function useCurrentOrganization() {
  const { currentOrganization, loading } = useOrganization();
  return { organization: currentOrganization, loading };
}

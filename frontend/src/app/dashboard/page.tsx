"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { AppLayout } from "@/components/app";
import { DashboardContent } from "./dashboard-content";

/**
 * Dashboard Page
 *
 * Main landing page after sign-in.
 * Shows overview stats and quick actions.
 * Requires authentication.
 */
export default function DashboardPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { currentOrganization, loading: orgLoading } = useOrganization();

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/sign-in");
    }
  }, [user, authLoading, router]);

  // Loading state
  if (authLoading || orgLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-8 h-8 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin" />
      </div>
    );
  }

  // Not signed in - will redirect
  if (!user) {
    return null;
  }

  return (
    <AppLayout
      title="Dashboard"
      subtitle="Welcome back! Here's what's happening."
    >
      <DashboardContent hasOrg={!!currentOrganization} />
    </AppLayout>
  );
}

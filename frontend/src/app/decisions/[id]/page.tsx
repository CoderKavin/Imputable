"use client";

/**
 * Decision View Page
 *
 * Route: /decisions/[id]
 * Optional query params:
 * - version: specific version to view (time travel)
 */

import { useState, useCallback, useEffect } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { DecisionView } from "@/components/decision/DecisionView";
import { ProposeChangeModal } from "@/components/decision/ProposeChangeModal";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";

export default function DecisionPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const decisionId = params.id as string;
  const initialVersion = searchParams.get("version")
    ? parseInt(searchParams.get("version")!, 10)
    : undefined;

  const [showProposeChange, setShowProposeChange] = useState(false);

  // All hooks must be called before any conditional returns
  const handleProposeChange = useCallback(() => {
    setShowProposeChange(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setShowProposeChange(false);
  }, []);

  const handleSuccess = useCallback(() => {
    router.refresh();
  }, [router]);

  const handleBack = useCallback(() => {
    router.push("/decisions");
  }, [router]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      const returnUrl = encodeURIComponent(
        window.location.pathname + window.location.search,
      );
      router.push(`/login?returnUrl=${returnUrl}`);
    }
  }, [authLoading, user, router]);

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50/50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Don't render if not authenticated (will redirect)
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50/50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
          <p className="text-sm text-gray-500">Redirecting to login...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <DecisionView
        decisionId={decisionId}
        initialVersion={initialVersion}
        onProposeChange={handleProposeChange}
        onBack={handleBack}
      />

      {showProposeChange && (
        <ProposeChangeModal
          decisionId={decisionId}
          onClose={handleCloseModal}
          onSuccess={handleSuccess}
        />
      )}
    </>
  );
}

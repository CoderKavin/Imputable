"use client";

/**
 * Decision View Page
 *
 * Route: /decisions/[id]
 * Optional query params:
 * - version: specific version to view (time travel)
 */

import { useState, useCallback } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { DecisionView } from "@/components/decision/DecisionView";
import { ProposeChangeModal } from "@/components/decision/ProposeChangeModal";

export default function DecisionPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();

  const decisionId = params.id as string;
  const initialVersion = searchParams.get("version")
    ? parseInt(searchParams.get("version")!, 10)
    : undefined;

  const [showProposeChange, setShowProposeChange] = useState(false);

  const handleProposeChange = useCallback(() => {
    setShowProposeChange(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setShowProposeChange(false);
  }, []);

  const handleSuccess = useCallback(() => {
    // Refresh the page to show new version
    router.refresh();
  }, [router]);

  const handleBack = useCallback(() => {
    router.push("/decisions");
  }, [router]);

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

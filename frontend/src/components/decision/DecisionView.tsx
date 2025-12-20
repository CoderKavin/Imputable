"use client";

/**
 * Decision View Page Component
 *
 * Main layout combining:
 * - Decision content (main column)
 * - History sidebar (right rail)
 * - Action buttons (Propose Change, etc.)
 */

import React, { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useDecision, useVersionSwitcher } from "@/hooks/use-decisions";
import { DecisionHistorySidebar } from "./DecisionHistorySidebar";
import { DecisionContent } from "./DecisionContent";
import { DiffViewer } from "./DiffViewer";
import { Button } from "@/components/ui/button";
import {
  FileEdit,
  GitCompare,
  ExternalLink,
  Share2,
  MoreHorizontal,
  Loader2,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";

interface DecisionViewProps {
  decisionId: string;
  initialVersion?: number;
  onProposeChange?: () => void;
  onBack?: () => void;
}

export function DecisionView({
  decisionId,
  initialVersion,
  onProposeChange,
  onBack,
}: DecisionViewProps) {
  // Version selection state
  const [selectedVersion, setSelectedVersion] = useState<number | undefined>(
    initialVersion
  );
  const [showDiff, setShowDiff] = useState(false);
  const [compareVersion, setCompareVersion] = useState<number | undefined>();

  // Fetch decision data
  const {
    data: decision,
    isLoading,
    error,
  } = useDecision(decisionId, selectedVersion);

  const { getCachedVersion } = useVersionSwitcher(decisionId);

  // Handle version selection
  const handleVersionSelect = useCallback((version: number) => {
    setSelectedVersion(version);
    setShowDiff(false);
  }, []);

  // Toggle diff view
  const handleToggleDiff = useCallback(() => {
    if (!decision) return;

    if (!showDiff) {
      // Enable diff: compare selected with previous version
      const currentV = selectedVersion || decision.version.version_number;
      if (currentV > 1) {
        setCompareVersion(currentV - 1);
        setShowDiff(true);
      }
    } else {
      setShowDiff(false);
      setCompareVersion(undefined);
    }
  }, [decision, selectedVersion, showDiff]);

  // Loading state
  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading decision...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !decision) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3 text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-destructive" />
          <h2 className="text-xl font-semibold">Decision Not Found</h2>
          <p className="text-sm text-muted-foreground">
            The decision you're looking for doesn't exist or you don't have
            permission to view it.
          </p>
          {onBack && (
            <Button variant="outline" onClick={onBack} className="mt-4">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Go Back
            </Button>
          )}
        </div>
      </div>
    );
  }

  const currentVersionNumber = decision.version_count;
  const viewingVersion = selectedVersion || decision.version.version_number;
  const isViewingHistory = viewingVersion !== currentVersionNumber;
  const canShowDiff = viewingVersion > 1;

  return (
    <div className="h-screen flex flex-col bg-background">
      {/* Top Action Bar */}
      <header className="border-b bg-background px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-4">
          {onBack && (
            <Button variant="ghost" size="sm" onClick={onBack}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
          )}
          <div>
            <span className="font-mono text-sm text-muted-foreground">
              DEC-{decision.decision_number}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Diff Toggle */}
          {canShowDiff && (
            <Button
              variant={showDiff ? "secondary" : "outline"}
              size="sm"
              onClick={handleToggleDiff}
            >
              <GitCompare className="h-4 w-4 mr-2" />
              {showDiff ? "Hide Changes" : "Show Changes"}
            </Button>
          )}

          {/* Propose Change - Only show for non-superseded decisions */}
          {decision.status !== "superseded" && onProposeChange && (
            <Button size="sm" onClick={onProposeChange}>
              <FileEdit className="h-4 w-4 mr-2" />
              Propose Change
            </Button>
          )}

          {/* More actions */}
          <Button variant="ghost" size="icon">
            <Share2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon">
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main Content Column */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-6 py-8">
            {showDiff && compareVersion ? (
              <DiffViewer
                decisionId={decisionId}
                versionA={compareVersion}
                versionB={viewingVersion}
                onClose={() => setShowDiff(false)}
              />
            ) : (
              <DecisionContent
                decision={decision}
                version={decision.version}
                isViewingHistory={isViewingHistory}
              />
            )}
          </div>
        </main>

        {/* History Sidebar */}
        <DecisionHistorySidebar
          decisionId={decisionId}
          currentVersionNumber={currentVersionNumber}
          selectedVersion={viewingVersion}
          onVersionSelect={handleVersionSelect}
          decisionStatus={decision.status}
          className="flex-shrink-0 hidden lg:flex"
        />
      </div>
    </div>
  );
}

export default DecisionView;

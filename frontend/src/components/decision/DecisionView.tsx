"use client";

/**
 * Decision View Page Component
 *
 * Notion-like document view with:
 * - Centered content area (max-w-3xl)
 * - Floating meta rail on the right
 * - Clean typography
 */

import React, { useState, useCallback } from "react";
import { cn, formatDateTime, formatStatus } from "@/lib/utils";
import { useDecision, useVersionSwitcher } from "@/hooks/use-decisions";
import { DecisionHistorySidebar } from "./DecisionHistorySidebar";
import { DiffViewer } from "./DiffViewer";
import { Button } from "@/components/ui/button";
import { StatusPill, ImpactPill } from "@/components/app";
import {
  FileEdit,
  GitCompare,
  Share2,
  MoreHorizontal,
  Loader2,
  AlertCircle,
  ArrowLeft,
  User,
  Calendar,
  History,
  Tag,
  AlertTriangle,
  FileText,
  CheckCircle2,
  Brain,
  XCircle,
} from "lucide-react";
import type { Decision, DecisionVersion } from "@/types/decision";

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
    initialVersion,
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
      <div className="min-h-screen flex items-center justify-center bg-gray-50/50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
          <p className="text-sm text-gray-500">Loading decision...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !decision) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50/50">
        <div className="flex flex-col items-center gap-4 text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">
            Decision Not Found
          </h2>
          <p className="text-gray-500">
            The decision you're looking for doesn't exist or you don't have
            permission to view it.
          </p>
          {onBack && (
            <Button
              variant="outline"
              onClick={onBack}
              className="mt-2 rounded-xl"
            >
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
    <div className="min-h-screen bg-gray-50/50">
      {/* Top Action Bar */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-xl border-b border-gray-200/50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {onBack && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="rounded-xl"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            )}
            <span className="font-mono text-sm text-gray-500">
              DEC-{decision.decision_number}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {canShowDiff && (
              <Button
                variant={showDiff ? "secondary" : "outline"}
                size="sm"
                onClick={handleToggleDiff}
                className="rounded-xl"
              >
                <GitCompare className="h-4 w-4 mr-2" />
                {showDiff ? "Hide Changes" : "Show Changes"}
              </Button>
            )}

            {decision.status !== "superseded" && onProposeChange && (
              <Button
                size="sm"
                onClick={onProposeChange}
                className="rounded-xl"
              >
                <FileEdit className="h-4 w-4 mr-2" />
                Propose Change
              </Button>
            )}

            <Button variant="ghost" size="icon" className="rounded-xl">
              <Share2 className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" className="rounded-xl">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex">
        {/* Main Document */}
        <main className="flex-1 py-8 px-6">
          <div className="max-w-3xl mx-auto">
            {showDiff && compareVersion ? (
              <DiffViewer
                decisionId={decisionId}
                versionA={compareVersion}
                versionB={viewingVersion}
                onClose={() => setShowDiff(false)}
              />
            ) : (
              <DocumentContent
                decision={decision}
                version={decision.version}
                isViewingHistory={isViewingHistory}
              />
            )}
          </div>
        </main>

        {/* Right Meta Rail */}
        <aside className="hidden xl:block w-80 flex-shrink-0 border-l border-gray-200/50 bg-white/50">
          <div className="sticky top-16 p-6 space-y-6">
            {/* Meta Card */}
            <MetaRail decision={decision} version={decision.version} />

            {/* History Sidebar */}
            <DecisionHistorySidebar
              decisionId={decisionId}
              currentVersionNumber={currentVersionNumber}
              selectedVersion={viewingVersion}
              onVersionSelect={handleVersionSelect}
              decisionStatus={decision.status}
              className="bg-white rounded-2xl border border-gray-100 p-4"
            />
          </div>
        </aside>
      </div>
    </div>
  );
}

// =============================================================================
// DOCUMENT CONTENT
// =============================================================================

function DocumentContent({
  decision,
  version,
  isViewingHistory,
}: {
  decision: Decision;
  version: DecisionVersion;
  isViewingHistory: boolean;
}) {
  const content = version.content;

  return (
    <div className="space-y-8">
      {/* Warnings */}
      {isViewingHistory && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-start gap-3">
          <History className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-amber-800">
              Viewing Historical Version {version.version_number}
            </p>
            <p className="text-sm text-amber-700 mt-1">
              This is not the current version. Created on{" "}
              {formatDateTime(version.created_at)}.
            </p>
          </div>
        </div>
      )}

      {decision.status === "superseded" && (
        <div className="p-4 rounded-2xl bg-red-50 border border-red-200 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-red-800">
              This Decision Has Been Superseded
            </p>
            <p className="text-sm text-red-700 mt-1">
              A newer decision has replaced this one.
            </p>
          </div>
        </div>
      )}

      {/* Title */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <StatusPill status={decision.status} />
          <ImpactPill level={version.impact_level} />
        </div>
        <h1 className="text-4xl font-bold text-gray-900 leading-tight">
          {version.title}
        </h1>
      </div>

      {/* Tags */}
      {version.tags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {version.tags.map((tag) => (
            <span
              key={tag}
              className="px-3 py-1 bg-gray-100 text-gray-600 text-sm rounded-full"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Content Sections */}
      <div className="space-y-8 pt-4">
        <ContentSection icon={FileText} title="Context">
          {content.context.split("\n").map((p, i) => (
            <p key={i} className="text-gray-700 leading-relaxed mb-4 last:mb-0">
              {p}
            </p>
          ))}
        </ContentSection>

        <ContentSection icon={CheckCircle2} title="Decision" highlight>
          {content.choice.split("\n").map((p, i) => (
            <p key={i} className="text-gray-700 leading-relaxed mb-4 last:mb-0">
              {p}
            </p>
          ))}
        </ContentSection>

        <ContentSection icon={Brain} title="Rationale">
          {content.rationale.split("\n").map((p, i) => (
            <p key={i} className="text-gray-700 leading-relaxed mb-4 last:mb-0">
              {p}
            </p>
          ))}
        </ContentSection>

        {content.alternatives.length > 0 && (
          <ContentSection icon={XCircle} title="Alternatives Considered">
            <div className="space-y-3">
              {content.alternatives.map((alt, index) => (
                <div
                  key={index}
                  className="p-4 rounded-xl bg-gray-50 border border-gray-100"
                >
                  <p className="font-medium text-gray-900">{alt.name}</p>
                  <p className="text-sm text-gray-600 mt-1">
                    <span className="text-red-600 font-medium">Rejected:</span>{" "}
                    {alt.rejected_reason}
                  </p>
                </div>
              ))}
            </div>
          </ContentSection>
        )}

        {content.consequences && (
          <ContentSection icon={AlertTriangle} title="Consequences">
            {content.consequences.split("\n").map((p, i) => (
              <p
                key={i}
                className="text-gray-700 leading-relaxed mb-4 last:mb-0"
              >
                {p}
              </p>
            ))}
          </ContentSection>
        )}

        {content.review_date && (
          <div className="flex items-center gap-3 p-4 rounded-2xl bg-blue-50 border border-blue-200">
            <Calendar className="h-5 w-5 text-blue-600" />
            <span className="text-sm text-blue-800">
              Scheduled for review on{" "}
              <strong>{formatDateTime(content.review_date)}</strong>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// CONTENT SECTION
// =============================================================================

function ContentSection({
  icon: Icon,
  title,
  highlight,
  children,
}: {
  icon: React.ElementType;
  title: string;
  highlight?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-2xl border p-6",
        highlight
          ? "bg-indigo-50/50 border-indigo-200"
          : "bg-white border-gray-100",
      )}
    >
      <div className="flex items-center gap-2 mb-4">
        <Icon
          className={cn(
            "h-5 w-5",
            highlight ? "text-indigo-600" : "text-gray-400",
          )}
        />
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      <div>{children}</div>
    </section>
  );
}

// =============================================================================
// META RAIL
// =============================================================================

function MetaRail({
  decision,
  version,
}: {
  decision: Decision;
  version: DecisionVersion;
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-gray-900">Details</h3>

      <div className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-gray-500 flex items-center gap-2">
            <User className="w-4 h-4" />
            Owner
          </span>
          <span className="font-medium text-gray-900">
            {version.created_by.name}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-500 flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Created
          </span>
          <span className="font-medium text-gray-900">
            {formatDateTime(version.created_at)}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-500 flex items-center gap-2">
            <History className="w-4 h-4" />
            Version
          </span>
          <span className="font-medium text-gray-900">
            {version.version_number} of {decision.version_count}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-gray-500 flex items-center gap-2">
            <Tag className="w-4 h-4" />
            Status
          </span>
          <StatusPill status={decision.status} />
        </div>
      </div>
    </div>
  );
}

export default DecisionView;

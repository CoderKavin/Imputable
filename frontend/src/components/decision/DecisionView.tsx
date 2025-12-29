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
import {
  useDecision,
  useVersionSwitcher,
  useApproveDecision,
} from "@/hooks/use-decisions";
import { DecisionHistorySidebar } from "./DecisionHistorySidebar";
import { DiffViewer } from "./DiffViewer";
import { Button } from "@/components/ui/button";
import { StatusPill, ImpactPill } from "@/components/app";
import {
  FileEdit,
  GitCompare,
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
  Users,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
  Check,
  X,
  ExternalLink,
} from "lucide-react";
import type {
  Decision,
  DecisionVersion,
  ReviewerInfo,
  ApprovalStatus,
} from "@/types/decision";

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
            The decision you&apos;re looking for doesn&apos;t exist or you
            don&apos;t have permission to view it.
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
      <header className="sticky top-0 z-[102] bg-white border-b border-gray-200">
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
              DECISION-{decision.decision_number}
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
            {/* Approval Actions - Show if user is a reviewer */}
            {decision.is_reviewer && decision.status === "pending_review" && (
              <ApprovalActions
                decisionId={decisionId}
                currentApproval={decision.current_user_approval}
              />
            )}

            {/* Reviewers Section */}
            {decision.reviewers && decision.reviewers.length > 0 && (
              <ReviewersSection
                reviewers={decision.reviewers}
                approvalProgress={decision.approval_progress}
              />
            )}

            {/* Poll Results - Show if there are poll votes */}
            {decision.poll_votes &&
              (decision.poll_votes.agree > 0 ||
                decision.poll_votes.concern > 0 ||
                decision.poll_votes.block > 0) && (
                <PollResults votes={decision.poll_votes} />
              )}

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

      <div className="space-y-4 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-gray-500 flex items-center gap-2">
            <User className="w-4 h-4" />
            Owner
          </span>
          <span className="font-medium text-gray-900 text-right">
            {version.created_by.name}
          </span>
        </div>

        <div className="flex items-start justify-between">
          <span className="text-gray-500 flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Created
          </span>
          <span className="font-medium text-gray-900 text-right">
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

        {/* View in Slack link - only shown for Slack-created decisions */}
        {decision.slack_link && (
          <div className="pt-2 border-t border-gray-100">
            <a
              href={decision.slack_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-700 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" />
              </svg>
              View in Slack
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}

        {/* View in Teams link - only shown for Teams-created decisions */}
        {decision.teams_link && (
          <div
            className={cn(
              "pt-2",
              !decision.slack_link && "border-t border-gray-100",
            )}
          >
            <a
              href={decision.teams_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-700 transition-colors"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M20.625 8.073h-7.448c-.19 0-.375.077-.51.213a.715.715 0 00-.21.516v7.448c0 .19.077.375.213.51.136.137.32.214.511.214h7.447a.718.718 0 00.723-.724V8.803a.718.718 0 00-.726-.73zm-1.531 6.677h-4.39v-1.35h4.39v1.35zm0-2.396h-4.39v-1.35h4.39v1.35zm-2.569-5.281a2.573 2.573 0 100-5.146 2.573 2.573 0 000 5.146zm-6.49 1.854a3.073 3.073 0 100-6.146 3.073 3.073 0 000 6.146zm4.182 8.854H2.594a.72.72 0 01-.719-.72v-5.813a.72.72 0 01.72-.719h2.697V8.802a.72.72 0 01.719-.719h5.49a4.37 4.37 0 00-.563 2.156v.292H5.729v5.823h8.854V13.26c.26.03.524.046.79.046h.844v4.756a.72.72 0 01-.72.72z" />
              </svg>
              View in Teams
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// APPROVAL ACTIONS
// =============================================================================

function ApprovalActions({
  decisionId,
  currentApproval,
}: {
  decisionId: string;
  currentApproval?: ApprovalStatus;
}) {
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { mutate: approve, isPending } = useApproveDecision(decisionId);

  const handleApprove = (status: "approved" | "rejected" | "abstained") => {
    setError(null);
    approve(
      { status, comment: comment.trim() || undefined },
      {
        onSuccess: () => {
          setComment("");
          setShowComment(false);
        },
        onError: (err) => {
          setError(
            err instanceof Error ? err.message : "Failed to submit approval",
          );
        },
      },
    );
  };

  // Already voted
  if (currentApproval && currentApproval !== "pending") {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Your Vote</h3>
        <div className="flex items-center gap-2">
          {currentApproval === "approved" && (
            <>
              <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                <Check className="w-4 h-4 text-green-600" />
              </div>
              <span className="text-sm font-medium text-green-700">
                You approved this decision
              </span>
            </>
          )}
          {currentApproval === "rejected" && (
            <>
              <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
                <X className="w-4 h-4 text-red-600" />
              </div>
              <span className="text-sm font-medium text-red-700">
                You rejected this decision
              </span>
            </>
          )}
          {currentApproval === "abstained" && (
            <>
              <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                <MinusCircle className="w-4 h-4 text-gray-600" />
              </div>
              <span className="text-sm font-medium text-gray-700">
                You abstained from voting
              </span>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-indigo-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">
        Your Review Required
      </h3>
      <p className="text-xs text-gray-500 mb-4">
        You&apos;ve been asked to review this decision.
      </p>

      {error && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
          {error}
        </div>
      )}

      {showComment && (
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Add a comment (optional)..."
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-xl mb-3 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          rows={2}
        />
      )}

      {!showComment && (
        <button
          onClick={() => setShowComment(true)}
          className="text-xs text-indigo-600 hover:text-indigo-700 mb-3 block"
        >
          + Add comment
        </button>
      )}

      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => handleApprove("approved")}
          disabled={isPending}
          className="flex-1 rounded-xl bg-green-600 hover:bg-green-700 text-white"
        >
          {isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <ThumbsUp className="w-4 h-4 mr-1" />
              Approve
            </>
          )}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => handleApprove("rejected")}
          disabled={isPending}
          className="flex-1 rounded-xl border-red-200 text-red-600 hover:bg-red-50"
        >
          <ThumbsDown className="w-4 h-4 mr-1" />
          Reject
        </Button>
      </div>

      <button
        onClick={() => handleApprove("abstained")}
        disabled={isPending}
        className="w-full mt-2 text-xs text-gray-500 hover:text-gray-700 py-1"
      >
        Abstain from voting
      </button>
    </div>
  );
}

// =============================================================================
// REVIEWERS SECTION
// =============================================================================

function ReviewersSection({
  reviewers,
  approvalProgress,
}: {
  reviewers: ReviewerInfo[];
  approvalProgress?: { required: number; approved: number; rejected: number };
}) {
  const getStatusIcon = (status: ApprovalStatus) => {
    switch (status) {
      case "approved":
        return <Check className="w-3 h-3 text-green-600" />;
      case "rejected":
        return <X className="w-3 h-3 text-red-600" />;
      case "abstained":
        return <MinusCircle className="w-3 h-3 text-gray-400" />;
      default:
        return null;
    }
  };

  const getStatusBorder = (status: ApprovalStatus) => {
    switch (status) {
      case "approved":
        return "ring-2 ring-green-500";
      case "rejected":
        return "ring-2 ring-red-500";
      case "abstained":
        return "ring-2 ring-gray-300";
      default:
        return "ring-1 ring-gray-200";
    }
  };

  // Generate avatar background color from name
  const getAvatarColor = (name: string) => {
    const colors = [
      "bg-indigo-500",
      "bg-purple-500",
      "bg-pink-500",
      "bg-blue-500",
      "bg-cyan-500",
      "bg-teal-500",
      "bg-green-500",
      "bg-orange-500",
    ];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
  };

  const getInitials = (name: string) => {
    if (!name) return "??";
    return (
      name
        .split(" ")
        .filter((n) => n.length > 0)
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2) || "??"
    );
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <Users className="w-4 h-4 text-gray-400" />
          Reviewers
        </h3>
        {approvalProgress && (
          <span className="text-xs text-gray-500">
            {approvalProgress.approved}/{approvalProgress.required} approved
          </span>
        )}
      </div>

      {/* Progress bar */}
      {approvalProgress && approvalProgress.required > 0 && (
        <div className="h-1.5 bg-gray-100 rounded-full mb-4 overflow-hidden">
          <div className="h-full flex">
            <div
              className="bg-green-500 transition-all"
              style={{
                width: `${(approvalProgress.approved / approvalProgress.required) * 100}%`,
              }}
            />
            <div
              className="bg-red-500 transition-all"
              style={{
                width: `${(approvalProgress.rejected / approvalProgress.required) * 100}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Reviewer list */}
      <div className="space-y-2">
        {reviewers.map((reviewer) => (
          <div key={reviewer.id} className="flex items-center gap-3 py-1.5">
            <div
              className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-medium",
                getAvatarColor(reviewer.name),
                getStatusBorder(reviewer.status),
              )}
            >
              {getInitials(reviewer.name)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">
                {reviewer.name}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {getStatusIcon(reviewer.status)}
              <span
                className={cn(
                  "text-xs capitalize",
                  reviewer.status === "approved" && "text-green-600",
                  reviewer.status === "rejected" && "text-red-600",
                  reviewer.status === "abstained" && "text-gray-400",
                  reviewer.status === "pending" && "text-gray-400",
                )}
              >
                {reviewer.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// POLL RESULTS
// =============================================================================

function PollResults({
  votes,
}: {
  votes: { agree: number; concern: number; block: number };
}) {
  const total = votes.agree + votes.concern + votes.block;

  if (total === 0) return null;

  const agreePercent = Math.round((votes.agree / total) * 100);
  const concernPercent = Math.round((votes.concern / total) * 100);
  const blockPercent = Math.round((votes.block / total) * 100);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">
        Consensus Poll
      </h3>

      <div className="space-y-3">
        {/* Agree */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="flex items-center gap-1.5 text-green-700">
              <ThumbsUp className="w-3 h-3" />
              Agree
            </span>
            <span className="text-gray-500">
              {votes.agree} ({agreePercent}%)
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all"
              style={{ width: `${agreePercent}%` }}
            />
          </div>
        </div>

        {/* Concern */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="flex items-center gap-1.5 text-amber-700">
              <AlertTriangle className="w-3 h-3" />
              Concern
            </span>
            <span className="text-gray-500">
              {votes.concern} ({concernPercent}%)
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-full transition-all"
              style={{ width: `${concernPercent}%` }}
            />
          </div>
        </div>

        {/* Block */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="flex items-center gap-1.5 text-red-700">
              <XCircle className="w-3 h-3" />
              Block
            </span>
            <span className="text-gray-500">
              {votes.block} ({blockPercent}%)
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-red-500 rounded-full transition-all"
              style={{ width: `${blockPercent}%` }}
            />
          </div>
        </div>
      </div>

      <p className="text-xs text-gray-400 mt-3 text-center">
        {total} vote{total !== 1 ? "s" : ""} from Slack/Teams
      </p>
    </div>
  );
}

export default DecisionView;

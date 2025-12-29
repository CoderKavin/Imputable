"use client";

/**
 * Decision Content Display
 *
 * Renders the full content of a decision version:
 * - Title and metadata
 * - Context, Choice, Rationale sections
 * - Alternatives considered
 * - Tags and impact level
 * - AI confidence score and verification badge (for AI-generated decisions)
 */

import React from "react";
import { cn, formatDateTime, formatStatus } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type {
  Decision,
  DecisionVersion,
  DecisionStatus,
  ImpactLevel,
} from "@/types/decision";
import {
  FileText,
  CheckCircle2,
  Brain,
  XCircle,
  AlertTriangle,
  Calendar,
  Tag,
  User,
  Clock,
  History,
  Sparkles,
  ShieldCheck,
} from "lucide-react";

interface DecisionContentProps {
  decision: Decision;
  version: DecisionVersion;
  isViewingHistory: boolean;
  className?: string;
}

// AI Confidence Badge Component
function AIConfidenceBadge({
  confidence,
  verified,
}: {
  confidence: number;
  verified: boolean;
}) {
  const confidencePct = Math.round(confidence * 100);

  let confidenceColor: string;
  let confidenceText: string;

  if (confidencePct >= 80) {
    confidenceColor = "bg-green-100 text-green-800 border-green-200";
    confidenceText = "High confidence";
  } else if (confidencePct >= 50) {
    confidenceColor = "bg-yellow-100 text-yellow-800 border-yellow-200";
    confidenceText = "Medium confidence";
  } else {
    confidenceColor = "bg-orange-100 text-orange-800 border-orange-200";
    confidenceText = "Low confidence";
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Badge
        variant="outline"
        className={cn("flex items-center gap-1.5", confidenceColor)}
      >
        <Sparkles className="h-3 w-3" />
        AI Generated ({confidencePct}%)
      </Badge>
      {verified && (
        <Badge
          variant="outline"
          className="flex items-center gap-1.5 bg-blue-100 text-blue-800 border-blue-200"
        >
          <ShieldCheck className="h-3 w-3" />
          Verified by User
        </Badge>
      )}
      <span className="text-xs text-muted-foreground">{confidenceText}</span>
    </div>
  );
}

export function DecisionContent({
  decision,
  version,
  isViewingHistory,
  className,
}: DecisionContentProps) {
  const content = version.content;
  const aiMetadata = version.ai_metadata;

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header with Status Banners */}
      <div className="space-y-4">
        {/* AI-Generated Banner */}
        {aiMetadata?.ai_generated && (
          <div className="p-4 rounded-xl bg-indigo-50 border border-indigo-200 flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-indigo-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <p className="font-medium text-indigo-800">
                  AI-Analyzed Decision
                </p>
                <AIConfidenceBadge
                  confidence={aiMetadata.ai_confidence_score}
                  verified={aiMetadata.verified_by_user}
                />
              </div>
              <p className="text-sm text-indigo-700 mt-1">
                This decision was automatically extracted from a conversation
                thread using AI.
                {aiMetadata.verified_by_user
                  ? " A team member has reviewed and verified the content."
                  : " Please review for accuracy."}
              </p>
            </div>
          </div>
        )}

        {/* Historical Version Warning */}
        {isViewingHistory && (
          <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3">
            <History className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-amber-800">
                Viewing Historical Version {version.version_number}
              </p>
              <p className="text-sm text-amber-700 mt-1">
                This is not the current version. Created on{" "}
                {formatDateTime(version.created_at)}.
                {version.change_summary && (
                  <span className="block mt-1 italic">
                    Changes: &quot;{version.change_summary}&quot;
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Superseded Warning */}
        {decision.status === "superseded" && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-medium text-red-800">
                This Decision Has Been Superseded
              </p>
              <p className="text-sm text-red-700 mt-1">
                A newer decision has replaced this one. This version is kept for
                historical reference only.
              </p>
            </div>
          </div>
        )}

        {/* Title and Meta */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-sm font-mono text-muted-foreground">
                DECISION-{decision.decision_number}
              </span>
              <Badge variant={decision.status as DecisionStatus}>
                {formatStatus(decision.status)}
              </Badge>
              <Badge variant={version.impact_level as ImpactLevel}>
                {version.impact_level.toUpperCase()} Impact
              </Badge>
            </div>
            <h1 className="text-2xl font-bold text-foreground">
              {version.title}
            </h1>
          </div>
        </div>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <User className="h-4 w-4" />
            {version.created_by.name}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock className="h-4 w-4" />
            {formatDateTime(version.created_at)}
          </span>
          <span className="flex items-center gap-1.5">
            <History className="h-4 w-4" />
            Version {version.version_number} of {decision.version_count}
          </span>
        </div>

        {/* Tags */}
        {version.tags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <Tag className="h-4 w-4 text-muted-foreground" />
            {version.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Content Sections */}
      <div className="space-y-6">
        {/* Context */}
        {content?.context && (
          <ContentSection
            icon={FileText}
            title="Context"
            description="The background and problem being addressed"
          >
            <div className="prose prose-sm max-w-none text-foreground">
              {(content.context || "").split("\n").map((paragraph, i) => (
                <p key={`context-${i}`}>{paragraph}</p>
              ))}
            </div>
          </ContentSection>
        )}

        {/* Decision */}
        {content?.choice && (
          <ContentSection
            icon={CheckCircle2}
            title="Decision"
            description="What we decided"
            highlight
          >
            <div className="prose prose-sm max-w-none text-foreground">
              {(content.choice || "").split("\n").map((paragraph, i) => (
                <p key={`choice-${i}`}>{paragraph}</p>
              ))}
            </div>
          </ContentSection>
        )}

        {/* Rationale */}
        {content?.rationale && (
          <ContentSection
            icon={Brain}
            title="Rationale"
            description="Why we made this choice"
          >
            <div className="prose prose-sm max-w-none text-foreground">
              {(content.rationale || "").split("\n").map((paragraph, i) => (
                <p key={`rationale-${i}`}>{paragraph}</p>
              ))}
            </div>
          </ContentSection>
        )}

        {/* Alternatives Considered */}
        {content?.alternatives && content.alternatives.length > 0 && (
          <ContentSection
            icon={XCircle}
            title="Alternatives Considered"
            description="Options we evaluated but rejected"
          >
            <div className="space-y-3">
              {content.alternatives.map((alt, index) => (
                <div
                  key={alt.name || `alt-${index}`}
                  className="p-3 rounded-xl bg-muted/50 border border-border"
                >
                  <p className="font-medium text-foreground">{alt.name}</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    <span className="text-red-600 font-medium">Rejected:</span>{" "}
                    {alt.rejected_reason}
                  </p>
                </div>
              ))}
            </div>
          </ContentSection>
        )}

        {/* Consequences */}
        {content?.consequences && (
          <ContentSection
            icon={AlertTriangle}
            title="Consequences"
            description="Expected outcomes and implications"
          >
            <div className="prose prose-sm max-w-none text-foreground">
              {(content.consequences || "").split("\n").map((paragraph, i) => (
                <p key={`consequence-${i}`}>{paragraph}</p>
              ))}
            </div>
          </ContentSection>
        )}

        {/* Review Date */}
        {content.review_date && (
          <div className="flex items-center gap-2 p-3 rounded-xl bg-blue-50 border border-blue-200">
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
// CONTENT SECTION COMPONENT
// =============================================================================

interface ContentSectionProps {
  icon: React.ElementType;
  title: string;
  description: string;
  highlight?: boolean;
  children: React.ReactNode;
}

function ContentSection({
  icon: Icon,
  title,
  description,
  highlight,
  children,
}: ContentSectionProps) {
  return (
    <Card className={cn(highlight && "border-primary/30 bg-primary/5")}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Icon
            className={cn(
              "h-5 w-5",
              highlight ? "text-primary" : "text-muted-foreground",
            )}
          />
          <div>
            <h3 className="font-semibold text-foreground">{title}</h3>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default DecisionContent;

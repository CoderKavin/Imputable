"use client";

/**
 * Diff Viewer Component (The Money Feature)
 *
 * Visualizes changes between two versions with:
 * - Green highlighting for additions
 * - Red highlighting for deletions
 * - Side-by-side or unified view
 * - Section-by-section comparison
 */

import React, { useMemo, useState } from "react";
import DiffMatchPatch from "diff-match-patch";
import { cn, formatDateTime } from "@/lib/utils";
import { useVersionComparison, useDecision } from "@/hooks/use-decisions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { DecisionContent, DiffMode } from "@/types/decision";
import {
  X,
  ArrowRight,
  Columns,
  Rows,
  FileText,
  CheckCircle2,
  Brain,
  Loader2,
  Plus,
  Minus,
  Equal,
} from "lucide-react";

interface DiffViewerProps {
  decisionId: string;
  versionA: number; // Older version
  versionB: number; // Newer version
  onClose?: () => void;
}

export function DiffViewer({
  decisionId,
  versionA,
  versionB,
  onClose,
}: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<DiffMode>("unified");

  // Fetch both versions
  const { data: comparison, isLoading, error } = useVersionComparison(
    decisionId,
    versionA,
    versionB
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">Loading comparison...</span>
      </div>
    );
  }

  if (error || !comparison) {
    return (
      <div className="text-center py-12 text-destructive">
        Failed to load version comparison
      </div>
    );
  }

  const { version_a: oldVersion, version_b: newVersion, changes } = comparison;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="outline" className="font-mono">
              v{versionA}
            </Badge>
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
            <Badge variant="default" className="font-mono">
              v{versionB}
            </Badge>
          </div>
          <span className="text-sm text-muted-foreground">
            Comparing changes
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex items-center border rounded-lg p-1">
            <Button
              variant={viewMode === "unified" ? "secondary" : "ghost"}
              size="sm"
              className="h-7 px-2"
              onClick={() => setViewMode("unified")}
            >
              <Rows className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === "split" ? "secondary" : "ghost"}
              size="sm"
              className="h-7 px-2"
              onClick={() => setViewMode("split")}
            >
              <Columns className="h-4 w-4" />
            </Button>
          </div>

          {onClose && (
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Change Summary */}
      <div className="flex items-center gap-4 p-4 rounded-lg bg-muted/50 border">
        <DiffStat
          icon={Plus}
          label="Additions"
          color="text-emerald-600"
          hasChanges={changes.content_changed || changes.title_changed}
        />
        <DiffStat
          icon={Minus}
          label="Removals"
          color="text-red-600"
          hasChanges={changes.content_changed || changes.title_changed}
        />
        <DiffStat
          icon={Equal}
          label="Unchanged"
          color="text-muted-foreground"
          hasChanges={!changes.content_changed && !changes.title_changed}
        />
      </div>

      {/* Title Diff */}
      {changes.title_changed && (
        <DiffSection
          title="Title"
          icon={FileText}
          oldValue={oldVersion.title}
          newValue={newVersion.title}
          viewMode={viewMode}
        />
      )}

      {/* Content Diffs */}
      {changes.content_changed && (
        <>
          <DiffSection
            title="Context"
            icon={FileText}
            oldValue={oldVersion.content.context}
            newValue={newVersion.content.context}
            viewMode={viewMode}
          />
          <DiffSection
            title="Decision"
            icon={CheckCircle2}
            oldValue={oldVersion.content.choice}
            newValue={newVersion.content.choice}
            viewMode={viewMode}
            highlight
          />
          <DiffSection
            title="Rationale"
            icon={Brain}
            oldValue={oldVersion.content.rationale}
            newValue={newVersion.content.rationale}
            viewMode={viewMode}
          />
        </>
      )}

      {/* Tags Diff */}
      {changes.tags_changed && (
        <Card>
          <CardHeader className="pb-3">
            <h3 className="font-semibold flex items-center gap-2">
              Tags Changed
            </h3>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <p className="text-xs text-muted-foreground mb-2">Before</p>
                <div className="flex flex-wrap gap-1">
                  {oldVersion.tags.map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className={cn(
                        !newVersion.tags.includes(tag) &&
                          "bg-red-50 border-red-200 text-red-700 line-through"
                      )}
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <div className="flex-1">
                <p className="text-xs text-muted-foreground mb-2">After</p>
                <div className="flex flex-wrap gap-1">
                  {newVersion.tags.map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className={cn(
                        !oldVersion.tags.includes(tag) &&
                          "bg-emerald-50 border-emerald-200 text-emerald-700"
                      )}
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* No changes */}
      {!changes.title_changed && !changes.content_changed && !changes.tags_changed && (
        <div className="text-center py-12 text-muted-foreground">
          <Equal className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No differences found between these versions</p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// DIFF SECTION COMPONENT
// =============================================================================

interface DiffSectionProps {
  title: string;
  icon: React.ElementType;
  oldValue: string;
  newValue: string;
  viewMode: DiffMode;
  highlight?: boolean;
}

function DiffSection({
  title,
  icon: Icon,
  oldValue,
  newValue,
  viewMode,
  highlight,
}: DiffSectionProps) {
  const diffs = useMemo(() => {
    const dmp = new DiffMatchPatch();
    const diff = dmp.diff_main(oldValue, newValue);
    dmp.diff_cleanupSemantic(diff);
    return diff;
  }, [oldValue, newValue]);

  // Check if there are actual changes
  const hasChanges = diffs.some(([op]) => op !== 0);

  if (!hasChanges) {
    return null;
  }

  return (
    <Card className={cn(highlight && "border-primary/30")}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Icon className={cn(
            "h-5 w-5",
            highlight ? "text-primary" : "text-muted-foreground"
          )} />
          <h3 className="font-semibold">{title}</h3>
        </div>
      </CardHeader>
      <CardContent>
        {viewMode === "unified" ? (
          <UnifiedDiffView diffs={diffs} />
        ) : (
          <SplitDiffView oldValue={oldValue} newValue={newValue} diffs={diffs} />
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// UNIFIED DIFF VIEW
// =============================================================================

interface UnifiedDiffViewProps {
  diffs: [number, string][];
}

function UnifiedDiffView({ diffs }: UnifiedDiffViewProps) {
  return (
    <div className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
      {diffs.map(([operation, text], index) => {
        if (operation === -1) {
          // Deletion
          return (
            <span
              key={index}
              className="bg-red-100 text-red-800 px-0.5 rounded"
              style={{ textDecoration: "line-through" }}
            >
              {text}
            </span>
          );
        }
        if (operation === 1) {
          // Addition
          return (
            <span
              key={index}
              className="bg-emerald-100 text-emerald-800 px-0.5 rounded"
            >
              {text}
            </span>
          );
        }
        // Unchanged
        return <span key={index}>{text}</span>;
      })}
    </div>
  );
}

// =============================================================================
// SPLIT DIFF VIEW
// =============================================================================

interface SplitDiffViewProps {
  oldValue: string;
  newValue: string;
  diffs: [number, string][];
}

function SplitDiffView({ oldValue, newValue, diffs }: SplitDiffViewProps) {
  // Build left and right sides
  const leftParts: React.ReactNode[] = [];
  const rightParts: React.ReactNode[] = [];

  diffs.forEach(([operation, text], index) => {
    if (operation === -1) {
      // Deletion - only on left
      leftParts.push(
        <span
          key={`l-${index}`}
          className="bg-red-100 text-red-800 px-0.5 rounded"
        >
          {text}
        </span>
      );
    } else if (operation === 1) {
      // Addition - only on right
      rightParts.push(
        <span
          key={`r-${index}`}
          className="bg-emerald-100 text-emerald-800 px-0.5 rounded"
        >
          {text}
        </span>
      );
    } else {
      // Unchanged - both sides
      leftParts.push(<span key={`l-${index}`}>{text}</span>);
      rightParts.push(<span key={`r-${index}`}>{text}</span>);
    }
  });

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="p-3 rounded-lg bg-red-50/50 border border-red-100">
        <div className="text-xs font-medium text-red-600 mb-2 flex items-center gap-1">
          <Minus className="h-3 w-3" />
          Before
        </div>
        <div className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
          {leftParts}
        </div>
      </div>
      <div className="p-3 rounded-lg bg-emerald-50/50 border border-emerald-100">
        <div className="text-xs font-medium text-emerald-600 mb-2 flex items-center gap-1">
          <Plus className="h-3 w-3" />
          After
        </div>
        <div className="font-mono text-sm leading-relaxed whitespace-pre-wrap">
          {rightParts}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// DIFF STAT COMPONENT
// =============================================================================

interface DiffStatProps {
  icon: React.ElementType;
  label: string;
  color: string;
  hasChanges: boolean;
}

function DiffStat({ icon: Icon, label, color, hasChanges }: DiffStatProps) {
  return (
    <div className={cn(
      "flex items-center gap-2 text-sm",
      !hasChanges && "opacity-50"
    )}>
      <Icon className={cn("h-4 w-4", color)} />
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}

export default DiffViewer;

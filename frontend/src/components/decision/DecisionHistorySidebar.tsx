"use client";

/**
 * Decision History Sidebar (The History Rail)
 *
 * Displays a timeline of all versions with:
 * - Version number and title
 * - Author and timestamp
 * - Change summary
 * - Visual indicator for current version
 * - Hover prefetching for instant switching
 */

import React from "react";
import { formatRelativeTime, formatDateTime, cn } from "@/lib/utils";
import { useVersionHistory, useVersionSwitcher } from "@/hooks/use-decisions";
import { Badge } from "@/components/ui/badge";
import type { VersionHistoryItem, DecisionStatus } from "@/types/decision";
import {
  Clock,
  User,
  GitCommit,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  FileEdit,
  Loader2,
} from "lucide-react";

interface DecisionHistorySidebarProps {
  decisionId: string;
  currentVersionNumber: number;
  selectedVersion: number;
  onVersionSelect: (version: number) => void;
  decisionStatus: DecisionStatus;
  className?: string;
}

export function DecisionHistorySidebar({
  decisionId,
  currentVersionNumber,
  selectedVersion,
  onVersionSelect,
  decisionStatus,
  className,
}: DecisionHistorySidebarProps) {
  const { data: versions, isLoading, error } = useVersionHistory(decisionId);
  const { preloadVersion, isVersionCached } = useVersionSwitcher(decisionId);

  if (isLoading) {
    return (
      <div className={cn("w-80 border-l bg-muted/30", className)}>
        <div className="p-4 border-b">
          <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
            Version History
          </h3>
        </div>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("w-80 border-l bg-muted/30", className)}>
        <div className="p-4 border-b">
          <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
            Version History
          </h3>
        </div>
        <div className="p-4 text-sm text-destructive">
          Failed to load version history
        </div>
      </div>
    );
  }

  return (
    <aside className={cn("w-80 border-l bg-muted/30 flex flex-col", className)}>
      {/* Header */}
      <div className="p-4 border-b bg-background">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
            Version History
          </h3>
          <Badge variant="outline" className="text-xs">
            {versions?.length || 0} versions
          </Badge>
        </div>

        {/* Status warning for superseded/deprecated */}
        {(decisionStatus === "superseded" || decisionStatus === "deprecated") && (
          <div className="mt-3 p-2 rounded-md bg-amber-50 border border-amber-200 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-amber-800">
              This decision has been {decisionStatus}.
              {decisionStatus === "superseded" && " View the successor for the current policy."}
            </p>
          </div>
        )}
      </div>

      {/* Version Timeline */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-2">
          {versions?.map((version, index) => (
            <VersionItem
              key={version.id}
              version={version}
              isSelected={version.version_number === selectedVersion}
              isCurrent={version.version_number === currentVersionNumber}
              isFirst={index === 0}
              isLast={index === versions.length - 1}
              isCached={isVersionCached(version.version_number)}
              onClick={() => onVersionSelect(version.version_number)}
              onMouseEnter={() => preloadVersion(version.version_number)}
            />
          ))}
        </div>
      </div>

      {/* Footer hint */}
      <div className="p-3 border-t bg-background">
        <p className="text-xs text-muted-foreground text-center">
          Click any version to view its content
        </p>
      </div>
    </aside>
  );
}

// =============================================================================
// VERSION ITEM COMPONENT
// =============================================================================

interface VersionItemProps {
  version: VersionHistoryItem;
  isSelected: boolean;
  isCurrent: boolean;
  isFirst: boolean;
  isLast: boolean;
  isCached: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
}

function VersionItem({
  version,
  isSelected,
  isCurrent,
  isFirst,
  isLast,
  isCached,
  onClick,
  onMouseEnter,
}: VersionItemProps) {
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={cn(
        "w-full text-left p-3 rounded-lg transition-all duration-150 relative",
        "hover:bg-accent/50 focus:outline-none focus:ring-2 focus:ring-primary/20",
        isSelected && "bg-accent ring-1 ring-primary/20",
        !isSelected && "hover:translate-x-1"
      )}
    >
      {/* Timeline connector */}
      <div className="absolute left-6 top-0 bottom-0 flex flex-col items-center">
        {!isFirst && (
          <div className="w-px h-3 bg-border" />
        )}
        <div
          className={cn(
            "w-3 h-3 rounded-full border-2 flex-shrink-0 z-10",
            isSelected
              ? "bg-primary border-primary"
              : isCurrent
              ? "bg-emerald-500 border-emerald-500"
              : "bg-background border-muted-foreground/30"
          )}
        />
        {!isLast && (
          <div className="w-px flex-1 bg-border" />
        )}
      </div>

      {/* Content */}
      <div className="ml-8">
        {/* Version header */}
        <div className="flex items-center gap-2 mb-1">
          <span className={cn(
            "font-semibold text-sm",
            isSelected ? "text-primary" : "text-foreground"
          )}>
            v{version.version_number}
          </span>

          {isCurrent && (
            <Badge variant="approved" className="text-[10px] px-1.5 py-0">
              <CheckCircle className="h-3 w-3 mr-1" />
              Current
            </Badge>
          )}

          {isCached && !isSelected && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Cached" />
          )}
        </div>

        {/* Title (truncated) */}
        <p className={cn(
          "text-sm truncate mb-2",
          isSelected ? "text-foreground" : "text-muted-foreground"
        )}>
          {version.title}
        </p>

        {/* Change summary */}
        {version.change_summary && (
          <div className="flex items-start gap-1.5 mb-2">
            <FileEdit className="h-3 w-3 text-muted-foreground mt-0.5 flex-shrink-0" />
            <p className="text-xs text-muted-foreground line-clamp-2">
              {version.change_summary}
            </p>
          </div>
        )}

        {/* Meta info */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <User className="h-3 w-3" />
            {version.created_by.name.split(" ")[0]}
          </span>
          <span className="flex items-center gap-1" title={formatDateTime(version.created_at)}>
            <Clock className="h-3 w-3" />
            {formatRelativeTime(version.created_at)}
          </span>
        </div>
      </div>

      {/* Selection indicator */}
      {isSelected && (
        <ChevronRight className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-primary" />
      )}
    </button>
  );
}

export default DecisionHistorySidebar;

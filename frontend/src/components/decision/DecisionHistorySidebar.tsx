"use client";

/**
 * Decision History Sidebar (The History Rail)
 *
 * Displays a timeline of all versions with modern design.
 */

import React from "react";
import { formatRelativeTime, formatDateTime, cn } from "@/lib/utils";
import { useVersionHistory, useVersionSwitcher } from "@/hooks/use-decisions";
import type { VersionHistoryItem, DecisionStatus } from "@/types/decision";
import {
  Clock,
  User,
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
      <div className={cn("", className)}>
        <div className="pb-4 border-b border-gray-100">
          <h3 className="font-semibold text-sm text-gray-900">
            Version History
          </h3>
        </div>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn("", className)}>
        <div className="pb-4 border-b border-gray-100">
          <h3 className="font-semibold text-sm text-gray-900">
            Version History
          </h3>
        </div>
        <div className="p-4 text-sm text-red-600">
          Failed to load version history
        </div>
      </div>
    );
  }

  return (
    <div className={cn("", className)}>
      {/* Header */}
      <div className="pb-4 border-b border-gray-100 mb-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm text-gray-900">
            Version History
          </h3>
          <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
            {versions?.length || 0} versions
          </span>
        </div>

        {/* Status warning */}
        {(decisionStatus === "superseded" ||
          decisionStatus === "deprecated") && (
          <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-amber-800">
              This decision has been {decisionStatus}.
            </p>
          </div>
        )}
      </div>

      {/* Version Timeline */}
      <div className="space-y-2 max-h-80 overflow-y-auto">
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

      {/* Footer hint */}
      <div className="pt-4 mt-4 border-t border-gray-100">
        <p className="text-xs text-gray-400 text-center">
          Click any version to view
        </p>
      </div>
    </div>
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
  isCached,
  onClick,
  onMouseEnter,
}: VersionItemProps) {
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={cn(
        "w-full text-left p-3 rounded-xl transition-all duration-200 relative group",
        isSelected ? "bg-gray-900 text-white" : "hover:bg-gray-50",
      )}
    >
      {/* Content */}
      <div>
        {/* Version header */}
        <div className="flex items-center gap-2 mb-1">
          <span
            className={cn(
              "font-semibold text-sm",
              isSelected ? "text-white" : "text-gray-900",
            )}
          >
            v{version.version_number}
          </span>

          {isCurrent && (
            <span
              className={cn(
                "inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full",
                isSelected
                  ? "bg-white/20 text-white"
                  : "bg-emerald-50 text-emerald-700",
              )}
            >
              <CheckCircle className="h-3 w-3" />
              Current
            </span>
          )}

          {isCached && !isSelected && (
            <span
              className="w-1.5 h-1.5 rounded-full bg-emerald-400"
              title="Cached"
            />
          )}
        </div>

        {/* Title (truncated) */}
        <p
          className={cn(
            "text-sm truncate mb-2",
            isSelected ? "text-white/80" : "text-gray-600",
          )}
        >
          {version.title}
        </p>

        {/* Change summary */}
        {version.change_summary && (
          <div className="flex items-start gap-1.5 mb-2">
            <FileEdit
              className={cn(
                "h-3 w-3 mt-0.5 flex-shrink-0",
                isSelected ? "text-white/60" : "text-gray-400",
              )}
            />
            <p
              className={cn(
                "text-xs line-clamp-2",
                isSelected ? "text-white/60" : "text-gray-500",
              )}
            >
              {version.change_summary}
            </p>
          </div>
        )}

        {/* Meta info */}
        <div
          className={cn(
            "flex items-center gap-3 text-xs",
            isSelected ? "text-white/50" : "text-gray-400",
          )}
        >
          <span className="flex items-center gap-1">
            <User className="h-3 w-3" />
            {version.created_by.name.split(" ")[0]}
          </span>
          <span
            className="flex items-center gap-1"
            title={formatDateTime(version.created_at)}
          >
            <Clock className="h-3 w-3" />
            {formatRelativeTime(version.created_at)}
          </span>
        </div>
      </div>

      {/* Selection indicator */}
      {isSelected && (
        <ChevronRight className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-white/60" />
      )}
    </button>
  );
}

export default DecisionHistorySidebar;

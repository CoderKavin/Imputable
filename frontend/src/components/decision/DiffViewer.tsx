"use client";

/**
 * DiffViewer Component
 *
 * Shows a side-by-side comparison of two decision versions.
 * Highlights changes in content, metadata, and structure.
 */

import React from "react";
import { useVersionCompare } from "@/hooks/use-decisions";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  X,
  Loader2,
  AlertCircle,
  ArrowRight,
  Plus,
  Minus,
  FileText,
} from "lucide-react";

interface DiffViewerProps {
  decisionId: string;
  versionA: number;
  versionB: number;
  onClose?: () => void;
}

export function DiffViewer({
  decisionId,
  versionA,
  versionB,
  onClose,
}: DiffViewerProps) {
  const { data, isLoading, error } = useVersionCompare(
    decisionId,
    versionA,
    versionB,
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
          <p className="text-sm text-gray-500">Loading comparison...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="w-12 h-12 rounded-xl bg-red-50 flex items-center justify-center">
            <AlertCircle className="h-6 w-6 text-red-500" />
          </div>
          <p className="text-gray-500">Failed to load comparison</p>
          {onClose && (
            <Button variant="outline" onClick={onClose} className="rounded-xl">
              Close
            </Button>
          )}
        </div>
      </div>
    );
  }

  const { version_a, version_b, changes } = data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="px-3 py-1 rounded-full bg-red-100 text-red-700 font-medium">
              v{versionA}
            </span>
            <ArrowRight className="w-4 h-4 text-gray-400" />
            <span className="px-3 py-1 rounded-full bg-green-100 text-green-700 font-medium">
              v{versionB}
            </span>
          </div>
          <div className="text-sm text-gray-500">
            Comparing version {versionA} to version {versionB}
          </div>
        </div>
        {onClose && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="rounded-xl"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Change Summary */}
      <div className="flex items-center gap-4 p-4 rounded-2xl bg-gray-50 border border-gray-100">
        <FileText className="w-5 h-5 text-gray-400" />
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-900">Changes detected:</p>
          <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
            {changes.title_changed && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Title changed
              </span>
            )}
            {changes.content_changed && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-indigo-500" />
                Content changed
              </span>
            )}
            {changes.tags_changed && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-purple-500" />
                Tags changed
              </span>
            )}
            {!changes.title_changed &&
              !changes.content_changed &&
              !changes.tags_changed && (
                <span className="text-gray-400">No significant changes</span>
              )}
          </div>
        </div>
      </div>

      {/* Title Diff */}
      {changes.title_changed && (
        <DiffSection title="Title">
          <div className="grid grid-cols-2 gap-4">
            <DiffBlock type="removed" content={version_a.title} />
            <DiffBlock type="added" content={version_b.title} />
          </div>
        </DiffSection>
      )}

      {/* Content Diff */}
      {changes.content_changed && (
        <>
          {/* Context */}
          {version_a.content?.context !== version_b.content?.context && (
            <DiffSection title="Context">
              <div className="grid grid-cols-2 gap-4">
                <DiffBlock
                  type="removed"
                  content={version_a.content?.context || ""}
                />
                <DiffBlock
                  type="added"
                  content={version_b.content?.context || ""}
                />
              </div>
            </DiffSection>
          )}

          {/* Decision */}
          {version_a.content?.choice !== version_b.content?.choice && (
            <DiffSection title="Decision">
              <div className="grid grid-cols-2 gap-4">
                <DiffBlock
                  type="removed"
                  content={version_a.content?.choice || ""}
                />
                <DiffBlock
                  type="added"
                  content={version_b.content?.choice || ""}
                />
              </div>
            </DiffSection>
          )}

          {/* Rationale */}
          {version_a.content?.rationale !== version_b.content?.rationale && (
            <DiffSection title="Rationale">
              <div className="grid grid-cols-2 gap-4">
                <DiffBlock
                  type="removed"
                  content={version_a.content?.rationale || ""}
                />
                <DiffBlock
                  type="added"
                  content={version_b.content?.rationale || ""}
                />
              </div>
            </DiffSection>
          )}

          {/* Consequences */}
          {version_a.content?.consequences !==
            version_b.content?.consequences && (
            <DiffSection title="Consequences">
              <div className="grid grid-cols-2 gap-4">
                <DiffBlock
                  type="removed"
                  content={version_a.content?.consequences || ""}
                />
                <DiffBlock
                  type="added"
                  content={version_b.content?.consequences || ""}
                />
              </div>
            </DiffSection>
          )}
        </>
      )}

      {/* Tags Diff */}
      {changes.tags_changed && (
        <DiffSection title="Tags">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <p className="text-xs font-medium text-red-600 uppercase tracking-wide">
                Version {versionA}
              </p>
              <div className="flex flex-wrap gap-2">
                {(version_a.tags || []).map((tag: string) => (
                  <span
                    key={tag}
                    className={cn(
                      "px-3 py-1 rounded-full text-sm",
                      !(version_b.tags || []).includes(tag)
                        ? "bg-red-100 text-red-700 line-through"
                        : "bg-gray-100 text-gray-600",
                    )}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium text-green-600 uppercase tracking-wide">
                Version {versionB}
              </p>
              <div className="flex flex-wrap gap-2">
                {(version_b.tags || []).map((tag: string) => (
                  <span
                    key={tag}
                    className={cn(
                      "px-3 py-1 rounded-full text-sm",
                      !(version_a.tags || []).includes(tag)
                        ? "bg-green-100 text-green-700 font-medium"
                        : "bg-gray-100 text-gray-600",
                    )}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </DiffSection>
      )}

      {/* Metadata */}
      <DiffSection title="Metadata">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-2 p-4 rounded-xl bg-gray-50">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Version {versionA}
            </p>
            <p className="text-gray-900">
              Created: {new Date(version_a.created_at).toLocaleString()}
            </p>
          </div>
          <div className="space-y-2 p-4 rounded-xl bg-gray-50">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Version {versionB}
            </p>
            <p className="text-gray-900">
              Created: {new Date(version_b.created_at).toLocaleString()}
            </p>
          </div>
        </div>
      </DiffSection>
    </div>
  );
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function DiffSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      {children}
    </div>
  );
}

function DiffBlock({
  type,
  content,
}: {
  type: "added" | "removed";
  content: string;
}) {
  const isAdded = type === "added";

  return (
    <div
      className={cn(
        "p-4 rounded-xl border text-sm whitespace-pre-wrap",
        isAdded
          ? "bg-green-50 border-green-200 text-green-900"
          : "bg-red-50 border-red-200 text-red-900",
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        {isAdded ? (
          <Plus className="w-4 h-4 text-green-600" />
        ) : (
          <Minus className="w-4 h-4 text-red-600" />
        )}
        <span
          className={cn(
            "text-xs font-medium uppercase tracking-wide",
            isAdded ? "text-green-600" : "text-red-600",
          )}
        >
          {isAdded ? "New" : "Old"}
        </span>
      </div>
      <p className={cn(isAdded ? "" : "line-through opacity-75")}>
        {content || <span className="text-gray-400 italic">Empty</span>}
      </p>
    </div>
  );
}

export default DiffViewer;

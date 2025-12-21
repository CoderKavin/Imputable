"use client";

/**
 * Decisions List Page
 *
 * Route: /decisions
 * Shows all active decisions with search and filters
 * Protected route - requires authentication (handled by middleware)
 */

import { useState } from "react";
import Link from "next/link";
import { useOrganization } from "@clerk/nextjs";
import { useDecisionList } from "@/hooks/use-decisions";
import { Navbar } from "@/components/navbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DecisionListSkeleton } from "@/components/ui/skeleton";
import { cn, formatRelativeTime, formatStatus } from "@/lib/utils";
import type { DecisionSummary } from "@/types/decision";

// Icons as simple SVG components
function PlusIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
      />
    </svg>
  );
}

function LoaderIcon({ className }: { className?: string }) {
  return (
    <svg
      className={cn(className, "animate-spin")}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

function FileTextIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
      />
    </svg>
  );
}

// Helper to get badge variant from status
function getStatusVariant(
  status: string,
):
  | "draft"
  | "pending_review"
  | "approved"
  | "deprecated"
  | "superseded"
  | "default" {
  const validStatuses = [
    "draft",
    "pending_review",
    "approved",
    "deprecated",
    "superseded",
  ];
  return validStatuses.includes(status)
    ? (status as
        | "draft"
        | "pending_review"
        | "approved"
        | "deprecated"
        | "superseded")
    : "default";
}

// Helper to get badge variant from impact level
function getImpactVariant(
  level: string,
): "low" | "medium" | "high" | "critical" | "default" {
  const validLevels = ["low", "medium", "high", "critical"];
  return validLevels.includes(level)
    ? (level as "low" | "medium" | "high" | "critical")
    : "default";
}

export default function DecisionsPage() {
  const [page, setPage] = useState(1);
  const { organization, isLoaded: orgLoaded } = useOrganization();
  const { data, isLoading, error } = useDecisionList(page, 20);

  // Show message if no organization selected
  const noOrganization = orgLoaded && !organization;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      {/* Page Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Decisions</h1>
              <p className="text-sm text-gray-500">
                Engineering and product decision records
              </p>
            </div>
            <Button>
              <PlusIcon className="h-4 w-4 mr-2" />
              New Decision
            </Button>
          </div>

          {/* Search and Filters */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 relative">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search decisions..."
                className={cn(
                  "w-full pl-10 pr-4 py-2 rounded-lg border bg-white text-sm",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/20",
                )}
              />
            </div>
            <Button variant="outline" size="sm">
              <FilterIcon className="h-4 w-4 mr-2" />
              Filters
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {noOrganization ? (
          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <svg
                    className="w-5 h-5 text-amber-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="font-semibold text-amber-900">
                    No Organization Selected
                  </h3>
                  <p className="text-amber-700 text-sm mt-1">
                    To view and manage decisions, you need to select or create
                    an organization. Use the organization switcher in the top
                    navigation bar.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : isLoading ? (
          <DecisionListSkeleton count={6} />
        ) : error ? (
          <div className="text-center py-12 text-red-600">
            Failed to load decisions. Please try again.
          </div>
        ) : data?.items.length === 0 ? (
          <div className="text-center py-12">
            <FileTextIcon className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <h3 className="font-medium text-lg">No decisions yet</h3>
            <p className="text-sm text-gray-500 mt-1">
              Create your first decision to get started
            </p>
            <Button className="mt-4">
              <PlusIcon className="h-4 w-4 mr-2" />
              New Decision
            </Button>
          </div>
        ) : (
          <>
            {/* Decision List */}
            <div className="space-y-3">
              {data?.items.map((decision: DecisionSummary) => (
                <Link
                  key={decision.id}
                  href={`/decisions/${decision.id}`}
                  className="block"
                >
                  <Card className="hover:border-indigo-300 hover:shadow-md transition-all duration-200">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          {/* Header row */}
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-mono text-gray-500">
                              DEC-{decision.decision_number}
                            </span>
                            <Badge variant={getStatusVariant(decision.status)}>
                              {formatStatus(decision.status)}
                            </Badge>
                            <Badge
                              variant={getImpactVariant(decision.impact_level)}
                            >
                              {decision.impact_level.toUpperCase()}
                            </Badge>
                          </div>

                          {/* Title */}
                          <h3 className="font-semibold text-gray-900 truncate">
                            {decision.title}
                          </h3>

                          {/* Meta row */}
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                            <span className="flex items-center gap-1">
                              <UserIcon className="h-3.5 w-3.5" />
                              {decision.created_by.name}
                            </span>
                            <span className="flex items-center gap-1">
                              <HistoryIcon className="h-3.5 w-3.5" />
                              {decision.version_count} version
                              {decision.version_count !== 1 ? "s" : ""}
                            </span>
                            <span>
                              {formatRelativeTime(decision.created_at)}
                            </span>
                          </div>

                          {/* Tags */}
                          {decision.tags.length > 0 && (
                            <div className="flex items-center gap-1.5 mt-2">
                              {decision.tags.slice(0, 4).map((tag: string) => (
                                <Badge
                                  key={tag}
                                  variant="outline"
                                  className="text-xs"
                                >
                                  {tag}
                                </Badge>
                              ))}
                              {decision.tags.length > 4 && (
                                <span className="text-xs text-gray-500">
                                  +{decision.tags.length - 4} more
                                </span>
                              )}
                            </div>
                          )}
                        </div>

                        <ChevronRightIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {data && data.total_pages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span className="text-sm text-gray-500 px-4">
                  Page {page} of {data.total_pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= data.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

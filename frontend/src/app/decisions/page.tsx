"use client";

/**
 * Decisions List Page
 *
 * Route: /decisions
 * Shows all active decisions with search and filters
 * Protected route - requires authentication
 */

import { useState, useEffect, Suspense, lazy } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useOrganization } from "@/contexts/OrganizationContext";
import { useDecisionList } from "@/hooks/use-decisions";
import { AppLayout, DecisionCard } from "@/components/app";
import { Button } from "@/components/ui/button";
import { DecisionListSkeleton } from "@/components/ui/skeleton";
import {
  Plus,
  Filter,
  FileText,
  Building2,
  List,
  GitBranch,
} from "lucide-react";
import type { DecisionSummary } from "@/types/decision";

// Lazy load MindMapView to avoid SSR issues with React Flow
const MindMapView = lazy(() =>
  import("@/components/app/mind-map/MindMapView").then((mod) => ({
    default: mod.MindMapView,
  })),
);

// Lazy load AddRelationshipModal
const AddRelationshipModal = lazy(() =>
  import("@/components/app/mind-map/AddRelationshipModal").then((mod) => ({
    default: mod.AddRelationshipModal,
  })),
);

type StatusFilter = "all" | "approved" | "pending_review" | "draft" | "at_risk";
type ViewMode = "list" | "mindmap";
type DecisionCount = 4 | 6 | 8 | 12 | 16;

export default function DecisionsPage() {
  return (
    <Suspense fallback={<DecisionsPageSkeleton />}>
      <DecisionsPageContent />
    </Suspense>
  );
}

function DecisionsPageSkeleton() {
  return (
    <AppLayout
      title="Decisions"
      subtitle="Engineering and product decision records"
    >
      <DecisionListSkeleton count={6} />
    </AppLayout>
  );
}

function DecisionsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [showAddRelationshipModal, setShowAddRelationshipModal] =
    useState(false);
  const [mindMapDecisionCount, setMindMapDecisionCount] =
    useState<DecisionCount>(8);
  const { currentOrganization, loading: orgLoading } = useOrganization();

  // Determine max decisions allowed based on subscription tier
  const isPro =
    currentOrganization?.subscription_tier === "professional" ||
    currentOrganization?.subscription_tier === "enterprise";
  const maxMindMapDecisions = isPro ? 16 : 6;

  // Read status filter and view mode from URL query params on mount and when URL changes
  useEffect(() => {
    const statusParam = searchParams.get("status");
    if (
      statusParam &&
      ["all", "approved", "pending_review", "draft", "at_risk"].includes(
        statusParam,
      )
    ) {
      setStatusFilter(statusParam as StatusFilter);
    }
    const viewParam = searchParams.get("view");
    if (viewParam === "mindmap") {
      setViewMode("mindmap");
    }
  }, [searchParams]);
  // Use server-side filtering when a status is selected, otherwise fetch a reasonable page size
  const { data, isLoading, error } = useDecisionList(
    page,
    20, // Reduced from 100 - server handles filtering, no need to overfetch
    statusFilter !== "all" ? statusFilter : undefined,
  );

  // Show message if no organization selected
  const noOrganization = !orgLoading && !currentOrganization;

  // Server handles filtering now, just use the data directly
  const decisions = data?.items || [];
  const totalPages = data?.total_pages || 1;

  // Reset to page 1 when filter changes
  const handleFilterChange = (filter: StatusFilter) => {
    setStatusFilter(filter);
    setPage(1);
  };

  return (
    <AppLayout
      title="Decisions"
      subtitle="Engineering and product decision records"
    >
      {noOrganization ? (
        <NoOrganizationState />
      ) : (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {/* View Toggle */}
              <div className="flex items-center bg-gray-100 rounded-full p-0.5 mr-2">
                <button
                  onClick={() => setViewMode("list")}
                  className={`
                    flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200
                    ${
                      viewMode === "list"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }
                  `}
                >
                  <List className="w-3.5 h-3.5" />
                  List
                </button>
                <button
                  onClick={() => setViewMode("mindmap")}
                  className={`
                    flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200
                    ${
                      viewMode === "mindmap"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }
                  `}
                >
                  <GitBranch className="w-3.5 h-3.5" />
                  Mind Map
                </button>
              </div>

              {/* Status filters - show for both views */}
              <FilterPill
                label="All Status"
                active={statusFilter === "all"}
                onClick={() => handleFilterChange("all")}
              />
              <FilterPill
                label="Approved"
                active={statusFilter === "approved"}
                onClick={() => handleFilterChange("approved")}
              />
              <FilterPill
                label="In Review"
                active={statusFilter === "pending_review"}
                onClick={() => handleFilterChange("pending_review")}
              />
              <FilterPill
                label="Draft"
                active={statusFilter === "draft"}
                onClick={() => handleFilterChange("draft")}
              />
              <FilterPill
                label="At Risk"
                active={statusFilter === "at_risk"}
                onClick={() => handleFilterChange("at_risk")}
              />

              {/* Decision count selector - only in mind map view */}
              {viewMode === "mindmap" && (
                <div className="flex items-center gap-2 ml-2 pl-2 border-l border-gray-200">
                  <span className="text-xs text-gray-500">Show:</span>
                  <select
                    value={Math.min(mindMapDecisionCount, maxMindMapDecisions)}
                    onChange={(e) =>
                      setMindMapDecisionCount(
                        Number(e.target.value) as DecisionCount,
                      )
                    }
                    className="text-xs font-medium bg-white border border-gray-200 rounded-lg px-2 py-1.5 focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  >
                    <option value={4}>4 decisions</option>
                    <option value={6}>6 decisions</option>
                    {isPro && <option value={8}>8 decisions</option>}
                    {isPro && <option value={12}>12 decisions</option>}
                    {isPro && <option value={16}>16 decisions</option>}
                  </select>
                  {!isPro && (
                    <span className="text-[10px] text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                      Pro: up to 16
                    </span>
                  )}
                </div>
              )}
            </div>
            <Button
              className="rounded-2xl px-4 gap-2"
              onClick={() => router.push("/decisions/new")}
            >
              <Plus className="w-4 h-4" />
              New Decision
            </Button>
          </div>

          {/* Content */}
          {isLoading ? (
            <DecisionListSkeleton count={6} />
          ) : error ? (
            <ErrorState />
          ) : viewMode === "mindmap" ? (
            /* Mind Map View */
            <Suspense
              fallback={
                <div className="h-[600px] flex items-center justify-center bg-gray-50 rounded-2xl border border-gray-200">
                  <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <span className="text-gray-500">Loading mind map...</span>
                  </div>
                </div>
              }
            >
              <MindMapView
                decisions={decisions}
                maxDecisions={Math.min(
                  mindMapDecisionCount,
                  maxMindMapDecisions,
                )}
                onAddRelationship={() => setShowAddRelationshipModal(true)}
              />
            </Suspense>
          ) : decisions.length === 0 ? (
            statusFilter === "all" ? (
              <EmptyState />
            ) : (
              <NoMatchState
                filter={statusFilter}
                onClear={() => handleFilterChange("all")}
              />
            )
          ) : (
            <>
              {/* Decision Cards Stack */}
              <div className="space-y-4">
                {decisions.map((decision: DecisionSummary) => (
                  <DecisionCard key={decision.id} decision={decision} />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 pt-6">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="rounded-xl"
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-gray-500 px-4">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                    className="rounded-xl"
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )}

          {/* Add Relationship Modal */}
          {showAddRelationshipModal && (
            <AddRelationshipModal
              decisions={data?.items || []}
              onClose={() => setShowAddRelationshipModal(false)}
            />
          )}
        </div>
      )}
    </AppLayout>
  );
}

// Filter Pill Component
function FilterPill({
  label,
  active = false,
  onClick,
}: {
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200
        ${
          active
            ? "bg-gray-900 text-white"
            : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
        }
      `}
    >
      {label}
    </button>
  );
}

// Empty State (no decisions at all)
function EmptyState() {
  const router = useRouter();
  return (
    <div className="text-center py-16">
      <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-6">
        <FileText className="w-8 h-8 text-gray-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        No decisions yet
      </h3>
      <p className="text-gray-500 mb-6 max-w-sm mx-auto">
        Create your first decision to start documenting your engineering
        choices.
      </p>
      <Button
        className="rounded-2xl px-6 gap-2"
        onClick={() => router.push("/decisions/new")}
      >
        <Plus className="w-4 h-4" />
        Create Decision
      </Button>
    </div>
  );
}

// No Match State (filter has no results)
function NoMatchState({
  filter,
  onClear,
}: {
  filter: string;
  onClear: () => void;
}) {
  const filterLabels: Record<string, string> = {
    approved: "approved",
    pending_review: "pending review",
    draft: "draft",
    at_risk: "at risk",
  };

  return (
    <div className="text-center py-16">
      <div className="w-16 h-16 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-6">
        <Filter className="w-8 h-8 text-gray-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        No {filterLabels[filter] || filter} decisions
      </h3>
      <p className="text-gray-500 mb-6 max-w-sm mx-auto">
        There are no decisions with this status yet.
      </p>
      <Button variant="outline" className="rounded-2xl px-6" onClick={onClear}>
        Clear Filter
      </Button>
    </div>
  );
}

// Error State
function ErrorState() {
  return (
    <div className="text-center py-16">
      <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center mx-auto mb-6">
        <FileText className="w-8 h-8 text-red-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">
        Failed to load decisions
      </h3>
      <p className="text-gray-500 mb-6">
        Something went wrong. Please try again.
      </p>
      <Button
        variant="outline"
        className="rounded-2xl"
        onClick={() => window.location.reload()}
      >
        Retry
      </Button>
    </div>
  );
}

// No Organization State
function NoOrganizationState() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-amber-100 flex items-center justify-center mx-auto mb-6">
          <Building2 className="w-8 h-8 text-amber-600" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          No Organization Selected
        </h2>
        <p className="text-gray-500 mb-8">
          To view and manage decisions, you need to select or create an
          organization. Use the organization switcher in the header.
        </p>
      </div>
    </div>
  );
}

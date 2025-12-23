"use client";

/**
 * Decisions List Page
 *
 * Route: /decisions
 * Shows all active decisions with search and filters
 * Protected route - requires authentication
 */

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useOrganization } from "@/contexts/OrganizationContext";
import { useDecisionList } from "@/hooks/use-decisions";
import { AppLayout, DecisionCard } from "@/components/app";
import { Button } from "@/components/ui/button";
import { DecisionListSkeleton } from "@/components/ui/skeleton";
import { Plus, Filter, FileText, Building2 } from "lucide-react";
import type { DecisionSummary } from "@/types/decision";

type StatusFilter = "all" | "approved" | "pending_review" | "draft";

export default function DecisionsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const { currentOrganization, loading: orgLoading } = useOrganization();
  const { data, isLoading, error } = useDecisionList(page, 100); // Fetch more to filter client-side

  // Show message if no organization selected
  const noOrganization = !orgLoading && !currentOrganization;

  // Filter decisions based on selected status
  const filteredDecisions = useMemo(() => {
    if (!data?.items) return [];
    if (statusFilter === "all") return data.items;
    return data.items.filter((d) => d.status === statusFilter);
  }, [data?.items, statusFilter]);

  // Paginate filtered results
  const pageSize = 20;
  const totalPages = Math.ceil(filteredDecisions.length / pageSize);
  const paginatedDecisions = filteredDecisions.slice(
    (page - 1) * pageSize,
    page * pageSize,
  );

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
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" className="rounded-xl gap-2">
                <Filter className="w-4 h-4" />
                Filters
              </Button>
              <div className="flex items-center gap-2">
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
              </div>
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
          ) : filteredDecisions.length === 0 ? (
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
                {paginatedDecisions.map((decision: DecisionSummary) => (
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
      <Button variant="outline" className="rounded-2xl">
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

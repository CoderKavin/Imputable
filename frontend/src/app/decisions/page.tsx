"use client";

/**
 * Decisions List Page
 *
 * Route: /decisions
 * Shows all active decisions with search and filters
 * Protected route - requires authentication (handled by middleware)
 */

import { useState } from "react";
import { useOrganization } from "@clerk/nextjs";
import { useDecisionList } from "@/hooks/use-decisions";
import { AppLayout, DecisionCard } from "@/components/app";
import { Button } from "@/components/ui/button";
import { DecisionListSkeleton } from "@/components/ui/skeleton";
import { Plus, Filter, FileText, Building2 } from "lucide-react";
import type { DecisionSummary } from "@/types/decision";

export default function DecisionsPage() {
  const [page, setPage] = useState(1);
  const { organization, isLoaded: orgLoaded } = useOrganization();
  const { data, isLoading, error } = useDecisionList(page, 20);

  // Show message if no organization selected
  const noOrganization = orgLoaded && !organization;

  const pageActions = (
    <Button className="rounded-2xl px-4 gap-2">
      <Plus className="w-4 h-4" />
      New Decision
    </Button>
  );

  return (
    <AppLayout
      title="Decisions"
      subtitle="Engineering and product decision records"
      actions={pageActions}
    >
      {noOrganization ? (
        <NoOrganizationState />
      ) : (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" className="rounded-xl gap-2">
              <Filter className="w-4 h-4" />
              Filters
            </Button>
            <div className="flex items-center gap-2">
              <FilterPill label="All Status" active />
              <FilterPill label="Approved" />
              <FilterPill label="In Review" />
              <FilterPill label="Draft" />
            </div>
          </div>

          {/* Content */}
          {isLoading ? (
            <DecisionListSkeleton count={6} />
          ) : error ? (
            <ErrorState />
          ) : data?.items.length === 0 ? (
            <EmptyState />
          ) : (
            <>
              {/* Decision Cards Stack */}
              <div className="space-y-4">
                {data?.items.map((decision: DecisionSummary) => (
                  <DecisionCard key={decision.id} decision={decision} />
                ))}
              </div>

              {/* Pagination */}
              {data && data.total_pages > 1 && (
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
                    Page {page} of {data.total_pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= data.total_pages}
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
}: {
  label: string;
  active?: boolean;
}) {
  return (
    <button
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

// Empty State
function EmptyState() {
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
      <Button className="rounded-2xl px-6 gap-2">
        <Plus className="w-4 h-4" />
        Create Decision
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

/**
 * Expiring Decisions List - Table of decisions needing attention
 * With action buttons for snooze, request update, and resolve
 */

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  useSnoozeDecision,
  useRequestUpdate,
  useResolveDecision,
  type ExpiringDecision,
} from "@/hooks/use-risk-dashboard";
import { SnoozeModal } from "./SnoozeModal";
import { ResolveModal } from "./ResolveModal";

interface ExpiringDecisionsListProps {
  decisions: ExpiringDecision[];
  isLoading: boolean;
  totalCount: number;
}

export function ExpiringDecisionsList({
  decisions,
  isLoading,
  totalCount,
}: ExpiringDecisionsListProps) {
  const [snoozeTarget, setSnoozeTarget] = useState<ExpiringDecision | null>(
    null,
  );
  const [resolveTarget, setResolveTarget] = useState<ExpiringDecision | null>(
    null,
  );

  const requestUpdate = useRequestUpdate();

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="animate-pulse flex items-center space-x-4 p-4 bg-gray-50 rounded-2xl"
          >
            <div className="h-4 bg-gray-200 rounded w-16" />
            <div className="h-4 bg-gray-200 rounded flex-1" />
            <div className="h-4 bg-gray-200 rounded w-24" />
          </div>
        ))}
      </div>
    );
  }

  if (decisions.length === 0) {
    return (
      <div className="text-center py-12">
        <CheckIcon className="mx-auto h-12 w-12 text-green-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">
          All caught up!
        </h3>
        <p className="mt-1 text-sm text-gray-500">
          No decisions require attention right now.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Decision
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Team
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Review Date
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {decisions.map((decision) => (
              <DecisionRow
                key={decision.decision_id}
                decision={decision}
                onSnooze={() => setSnoozeTarget(decision)}
                onResolve={() => setResolveTarget(decision)}
                onRequestUpdate={() => {
                  requestUpdate.mutate({
                    decisionId: decision.decision_id,
                    data: { urgency: "normal" },
                  });
                }}
                isRequestingUpdate={requestUpdate.isPending}
              />
            ))}
          </tbody>
        </table>

        {totalCount > decisions.length && (
          <div className="px-4 py-3 bg-gray-50 text-sm text-gray-500 text-center">
            Showing {decisions.length} of {totalCount} decisions
          </div>
        )}
      </div>

      {/* Modals */}
      {snoozeTarget && (
        <SnoozeModal
          decision={snoozeTarget}
          onClose={() => setSnoozeTarget(null)}
        />
      )}

      {resolveTarget && (
        <ResolveModal
          decision={resolveTarget}
          onClose={() => setResolveTarget(null)}
        />
      )}
    </>
  );
}

// =============================================================================
// Decision Row Component
// =============================================================================

interface DecisionRowProps {
  decision: ExpiringDecision;
  onSnooze: () => void;
  onResolve: () => void;
  onRequestUpdate: () => void;
  isRequestingUpdate: boolean;
}

function DecisionRow({
  decision,
  onSnooze,
  onResolve,
  onRequestUpdate,
  isRequestingUpdate,
}: DecisionRowProps) {
  const isExpired = decision.status === "expired";
  const daysText = getDaysText(decision.days_until_expiry);

  return (
    <tr className="hover:bg-gray-50 transition-colors">
      {/* Decision Info */}
      <td className="px-4 py-4">
        <div className="flex items-center">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gray-900">
                #{decision.decision_number}
              </span>
              {decision.is_temporary && (
                <Badge
                  variant="outline"
                  className="text-xs bg-amber-50 text-amber-700 border-amber-200"
                >
                  Temporary
                </Badge>
              )}
            </div>
            <div className="text-sm text-gray-500 truncate max-w-md">
              {decision.title}
            </div>
            <div className="text-xs text-gray-400 mt-1">
              Owner: {decision.creator_name}
            </div>
          </div>
        </div>
      </td>

      {/* Team */}
      <td className="px-4 py-4">
        <span className="text-sm text-gray-600">
          {decision.owner_team_name || "Unassigned"}
        </span>
      </td>

      {/* Status */}
      <td className="px-4 py-4">
        <StatusBadge
          status={decision.status}
          daysUntil={decision.days_until_expiry}
        />
      </td>

      {/* Review Date */}
      <td className="px-4 py-4">
        <div className="text-sm text-gray-900">
          {formatDate(decision.review_by_date)}
        </div>
        <div
          className={`text-xs ${isExpired ? "text-red-600" : "text-gray-500"}`}
        >
          {daysText}
        </div>
      </td>

      {/* Actions */}
      <td className="px-4 py-4 text-right">
        <div className="flex items-center justify-end space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onSnooze}
            className="text-xs"
          >
            Snooze
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onRequestUpdate}
            disabled={isRequestingUpdate}
            className="text-xs"
          >
            Request Update
          </Button>
          <Button
            size="sm"
            onClick={onResolve}
            className="text-xs bg-green-600 hover:bg-green-700 text-white"
          >
            Resolve
          </Button>
        </div>
      </td>
    </tr>
  );
}

// =============================================================================
// Status Badge Component
// =============================================================================

function StatusBadge({
  status,
  daysUntil,
}: {
  status: string;
  daysUntil: number;
}) {
  if (status === "expired") {
    return (
      <Badge className="bg-red-100 text-red-800 border-red-200">Expired</Badge>
    );
  }

  if (status === "at_risk") {
    if (daysUntil <= 1) {
      return (
        <Badge className="bg-red-100 text-red-800 border-red-200">
          Expires Tomorrow
        </Badge>
      );
    }
    if (daysUntil <= 7) {
      return (
        <Badge className="bg-orange-100 text-orange-800 border-orange-200">
          This Week
        </Badge>
      );
    }
    return (
      <Badge className="bg-amber-100 text-amber-800 border-amber-200">
        At Risk
      </Badge>
    );
  }

  return (
    <Badge className="bg-gray-100 text-gray-800 border-gray-200">
      {status}
    </Badge>
  );
}

// =============================================================================
// Helpers
// =============================================================================

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function getDaysText(days: number): string {
  if (days < 0) {
    const absDays = Math.abs(days);
    return `${absDays} day${absDays === 1 ? "" : "s"} overdue`;
  }
  if (days === 0) {
    return "Due today";
  }
  if (days === 1) {
    return "Due tomorrow";
  }
  return `${days} days remaining`;
}

function CheckIcon({ className }: { className?: string }) {
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
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

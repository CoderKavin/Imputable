"use client";

/**
 * AwaitingReviewWidget Component
 *
 * Shows decisions that need the current user's review on the dashboard.
 * Displays a list of pending decisions with quick actions to review them.
 */

import Link from "next/link";
import { usePendingApprovals } from "@/hooks/use-decisions";
import { ImpactPill } from "@/components/app";
import { formatRelativeTime } from "@/lib/utils";
import {
  ClipboardCheck,
  Loader2,
  ArrowRight,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import type { ImpactLevel } from "@/types/decision";

export function AwaitingReviewWidget() {
  const { data, isLoading, error } = usePendingApprovals();

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
            <ClipboardCheck className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Awaiting Your Review</h3>
            <p className="text-xs text-gray-500">
              Decisions that need your approval
            </p>
          </div>
        </div>
        {data && data.total > 0 && (
          <span className="px-2 py-1 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">
            {data.total} pending
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-5">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <AlertCircle className="w-8 h-8 text-red-400 mb-2" />
            <p className="text-sm text-gray-500">Failed to load pending reviews</p>
          </div>
        ) : data && data.items.length > 0 ? (
          <div className="space-y-3">
            {data.items.slice(0, 5).map((item) => (
              <Link
                key={item.id}
                href={`/decisions/${item.id}`}
                className="block group"
              >
                <div className="flex items-start gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-mono text-gray-400">
                        DEC-{item.decision_number}
                      </span>
                      <ImpactPill level={item.impact_level as ImpactLevel} />
                    </div>
                    <p className="text-sm font-medium text-gray-900 truncate group-hover:text-indigo-600 transition-colors">
                      {item.title}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      by {item.created_by.name} {formatRelativeTime(item.created_at)}
                    </p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-indigo-600 transition-colors flex-shrink-0 mt-2" />
                </div>
              </Link>
            ))}

            {data.total > 5 && (
              <Link
                href="/decisions?status=pending_review"
                className="block text-center py-2 text-sm text-indigo-600 hover:text-indigo-700 font-medium"
              >
                View all {data.total} pending reviews
              </Link>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center mb-3">
              <CheckCircle className="w-6 h-6 text-green-500" />
            </div>
            <p className="text-sm font-medium text-gray-900">All caught up!</p>
            <p className="text-xs text-gray-500 mt-1">
              No decisions need your review right now
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AwaitingReviewWidget;

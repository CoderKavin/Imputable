/**
 * Resolve Modal - Mark tech debt as resolved
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useResolveDecision,
  type ExpiringDecision,
} from "@/hooks/use-risk-dashboard";

interface ResolveModalProps {
  decision: ExpiringDecision;
  onClose: () => void;
}

export function ResolveModal({ decision, onClose }: ResolveModalProps) {
  const [resolutionNote, setResolutionNote] = useState("");
  const [shouldSetNewReviewDate, setShouldSetNewReviewDate] = useState(false);
  const [newReviewDate, setNewReviewDate] = useState("");

  const resolve = useResolveDecision();

  const handleResolve = async () => {
    if (!resolutionNote.trim()) return;

    try {
      await resolve.mutateAsync({
        decisionId: decision.decision_id,
        data: {
          resolution_note: resolutionNote,
          new_review_date:
            shouldSetNewReviewDate && newReviewDate
              ? new Date(newReviewDate).toISOString()
              : undefined,
        },
      });
      onClose();
    } catch (error) {
      // Error handling is done by react-query
    }
  };

  // Default new review date to 6 months from now
  const defaultNewDate = new Date();
  defaultNewDate.setMonth(defaultNewDate.getMonth() + 6);
  const minDate = new Date().toISOString().split("T")[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <Card className="relative z-10 w-full max-w-md mx-4 shadow-xl">
        <CardHeader>
          <div className="flex items-center space-x-2">
            <div className="p-2 bg-green-100 rounded-full">
              <CheckIcon className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <CardTitle className="text-lg">Resolve Tech Debt</CardTitle>
              <p className="text-sm text-gray-500">
                Decision #{decision.decision_number}
              </p>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Decision Info */}
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm font-medium text-gray-900 truncate">
              {decision.title}
            </p>
            {decision.is_temporary && (
              <span className="inline-flex items-center mt-2 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                Temporary Decision
              </span>
            )}
          </div>

          {/* Resolution Note */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What was done to resolve this?{" "}
              <span className="text-red-500">*</span>
            </label>
            <textarea
              value={resolutionNote}
              onChange={(e) => setResolutionNote(e.target.value)}
              placeholder="Describe the actions taken to address the tech debt..."
              rows={4}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
            />
            <p className="text-xs text-gray-500 mt-1">
              This will be recorded in the audit log.
            </p>
          </div>

          {/* Optional: Set New Review Date */}
          <div>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={shouldSetNewReviewDate}
                onChange={(e) => setShouldSetNewReviewDate(e.target.checked)}
                className="h-4 w-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">
                Schedule a future review date
              </span>
            </label>

            {shouldSetNewReviewDate && (
              <div className="mt-3 pl-6">
                <input
                  type="date"
                  value={newReviewDate}
                  onChange={(e) => setNewReviewDate(e.target.value)}
                  min={minDate}
                  className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  The decision will be monitored again at this date.
                </p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={handleResolve}
              disabled={!resolutionNote.trim() || resolve.isPending}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {resolve.isPending ? "Resolving..." : "Mark as Resolved"}
            </Button>
          </div>

          {resolve.isError && (
            <p className="text-sm text-red-600 text-center">
              Failed to resolve decision. Please try again.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
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
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

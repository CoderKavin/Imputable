/**
 * Snooze Modal - Extend review date for a decision
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useSnoozeDecision,
  type ExpiringDecision,
} from "@/hooks/use-risk-dashboard";

interface SnoozeModalProps {
  decision: ExpiringDecision;
  onClose: () => void;
}

const SNOOZE_OPTIONS = [
  { days: 7, label: "1 Week" },
  { days: 14, label: "2 Weeks" },
  { days: 30, label: "1 Month" },
  { days: 60, label: "2 Months" },
  { days: 90, label: "3 Months" },
];

export function SnoozeModal({ decision, onClose }: SnoozeModalProps) {
  const [selectedDays, setSelectedDays] = useState<number>(14);
  const [reason, setReason] = useState("");

  const snooze = useSnoozeDecision();

  const handleSnooze = async () => {
    try {
      await snooze.mutateAsync({
        decisionId: decision.decision_id,
        data: {
          days: selectedDays,
          reason: reason || undefined,
        },
      });
      onClose();
    } catch (error) {
      // Error handling is done by react-query
    }
  };

  const newDate = new Date();
  newDate.setDate(newDate.getDate() + selectedDays);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <Card className="relative z-10 w-full max-w-md mx-4 shadow-xl">
        <CardHeader>
          <CardTitle className="text-lg">Snooze Decision</CardTitle>
          <p className="text-sm text-gray-500 mt-1">
            Extend the review date for Decision #{decision.decision_number}
          </p>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Decision Info */}
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-sm font-medium text-gray-900 truncate">
              {decision.title}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Current review date: {formatDate(decision.review_by_date)}
            </p>
          </div>

          {/* Snooze Duration */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Extend by
            </label>
            <div className="grid grid-cols-3 gap-2">
              {SNOOZE_OPTIONS.map((option) => (
                <button
                  key={option.days}
                  onClick={() => setSelectedDays(option.days)}
                  className={`
                    px-3 py-2 text-sm font-medium rounded-xl border transition-colors
                    ${
                      selectedDays === option.days
                        ? "bg-indigo-50 border-indigo-500 text-indigo-700"
                        : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
                    }
                  `}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              New review date: {formatDate(newDate.toISOString())}
            </p>
          </div>

          {/* Reason - MANDATORY */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reason for delay <span className="text-red-500">*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain why this decision review needs to be delayed..."
              rows={3}
              className={`w-full px-3 py-2 text-sm border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none ${
                reason.trim().length === 0
                  ? "border-gray-200"
                  : "border-green-300"
              }`}
            />
            <p className="text-xs text-gray-500 mt-1">
              This explanation will be recorded in the decision&apos;s audit
              history.
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              onClick={handleSnooze}
              disabled={snooze.isPending || reason.trim().length === 0}
              className="bg-indigo-600 hover:bg-indigo-700 text-white disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {snooze.isPending ? "Snoozing..." : "Snooze"}
            </Button>
          </div>

          {snooze.isError && (
            <p className="text-sm text-red-600 text-center">
              Failed to snooze decision. Please try again.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

"use client";

/**
 * ApprovalProgress Component
 *
 * Shows approval progress with:
 * - Text: "2/3 Approved"
 * - Progress bar: green=approved, red=rejected, gray=pending
 * - Compact mode: checkmark and X icons with counts
 */

import { cn } from "@/lib/utils";
import { Check, X } from "lucide-react";

interface ApprovalProgressProps {
  required: number;
  approved: number;
  rejected: number;
  variant?: "default" | "compact";
  className?: string;
}

export function ApprovalProgress({
  required,
  approved,
  rejected,
  variant = "default",
  className,
}: ApprovalProgressProps) {
  if (required === 0) {
    return null;
  }

  const pending = required - approved - rejected;
  const approvedPercent = (approved / required) * 100;
  const rejectedPercent = (rejected / required) * 100;

  if (variant === "compact") {
    return (
      <div className={cn("flex items-center gap-2 text-xs", className)}>
        {approved > 0 && (
          <span className="flex items-center gap-0.5 text-green-600">
            <Check className="w-3 h-3" />
            {approved}
          </span>
        )}
        {rejected > 0 && (
          <span className="flex items-center gap-0.5 text-red-600">
            <X className="w-3 h-3" />
            {rejected}
          </span>
        )}
        {pending > 0 && approved === 0 && rejected === 0 && (
          <span className="text-gray-400">{pending} pending</span>
        )}
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">
          {approved}/{required} approved
        </span>
        {rejected > 0 && (
          <span className="text-red-500">{rejected} rejected</span>
        )}
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full flex">
          <div
            className="bg-green-500 transition-all duration-300"
            style={{ width: `${approvedPercent}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-300"
            style={{ width: `${rejectedPercent}%` }}
          />
        </div>
      </div>
    </div>
  );
}

export default ApprovalProgress;

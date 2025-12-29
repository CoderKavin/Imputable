"use client";

import Link from "next/link";
import { cn, formatRelativeTime } from "@/lib/utils";
import { StatusPill } from "./status-pill";
import { AvatarStack } from "./avatar-stack";
import { ApprovalProgress } from "./approval-progress";
import { Sparkles, ShieldCheck } from "lucide-react";
import type { DecisionSummary } from "@/types/decision";

interface DecisionCardProps {
  decision: DecisionSummary;
  className?: string;
}

// Avatar component for owner/reviewers
function Avatar({ name, size = "sm" }: { name: string; size?: "sm" | "md" }) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const colors = [
    "bg-indigo-100 text-indigo-600",
    "bg-purple-100 text-purple-600",
    "bg-pink-100 text-pink-600",
    "bg-blue-100 text-blue-600",
    "bg-emerald-100 text-emerald-600",
    "bg-amber-100 text-amber-600",
  ];

  // Deterministic color based on name
  const colorIndex =
    name.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0) %
    colors.length;
  const colorClass = colors[colorIndex];

  return (
    <div
      className={cn(
        "rounded-full flex items-center justify-center font-medium",
        colorClass,
        size === "sm" ? "w-6 h-6 text-[10px]" : "w-8 h-8 text-xs",
      )}
      title={name}
    >
      {initials}
    </div>
  );
}

export function DecisionCard({ decision, className }: DecisionCardProps) {
  return (
    <Link href={`/decisions/${decision.id}`} className="block group">
      <div
        className={cn(
          "bg-white rounded-2xl border border-gray-100 p-5",
          "transition-all duration-300 ease-out",
          "hover:-translate-y-1 hover:shadow-xl hover:shadow-gray-200/50 hover:border-gray-200",
          className,
        )}
      >
        {/* Top Row: Title + Status */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Decision Number */}
            <span className="text-xs font-mono text-gray-400 tracking-wide">
              DECISION-{decision.decision_number}
            </span>

            {/* Title */}
            <h3 className="font-semibold text-gray-900 mt-1 group-hover:text-indigo-600 transition-colors truncate">
              {decision.title}
            </h3>
          </div>

          {/* Status Pill */}
          <StatusPill status={decision.status} />
        </div>

        {/* Bottom Row: Meta Info */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-50">
          {/* Left: Owner + Reviewers */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Avatar name={decision.created_by.name} size="sm" />
              <span className="text-xs text-gray-500">
                {decision.created_by.name}
              </span>
            </div>

            {/* Team (if any) */}
            {decision.owner_team && (
              <>
                <div className="w-px h-4 bg-gray-200" />
                <span className="text-xs text-gray-400">
                  {decision.owner_team.name}
                </span>
              </>
            )}
          </div>

          {/* Right: Time + Versions */}
          <div className="flex items-center gap-3 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <svg
                className="w-3.5 h-3.5"
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
              {formatRelativeTime(decision.created_at)}
            </span>
            <span className="flex items-center gap-1">
              <svg
                className="w-3.5 h-3.5"
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
              v{decision.version_count}
            </span>
          </div>
        </div>

        {/* Tags */}
        {decision.tags && decision.tags.length > 0 && (
          <div className="flex items-center gap-1.5 mt-3">
            {/* Show AI badge prominently if AI-generated */}
            {decision.tags.includes("ai-generated") && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-50 text-indigo-600 text-xs rounded-full font-medium">
                <Sparkles className="w-3 h-3" />
                AI
              </span>
            )}
            {/* Regular tags (excluding ai-generated which is shown above) */}
            {decision.tags
              .filter((tag) => tag !== "ai-generated")
              .slice(0, 3)
              .map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-0.5 bg-gray-50 text-gray-500 text-xs rounded-full"
                >
                  {tag}
                </span>
              ))}
            {decision.tags.filter((tag) => tag !== "ai-generated").length >
              3 && (
              <span className="text-xs text-gray-400">
                +
                {decision.tags.filter((tag) => tag !== "ai-generated").length -
                  3}
              </span>
            )}
          </div>
        )}

        {/* Reviewers & Approval Progress - only show if reviewers exist */}
        {decision.reviewers && decision.reviewers.length > 0 && (
          <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Reviewers:</span>
              <AvatarStack users={decision.reviewers} max={4} size="sm" />
            </div>
            {decision.approval_progress && (
              <ApprovalProgress
                required={decision.approval_progress.required}
                approved={decision.approval_progress.approved}
                rejected={decision.approval_progress.rejected}
                variant="compact"
              />
            )}
          </div>
        )}
      </div>
    </Link>
  );
}

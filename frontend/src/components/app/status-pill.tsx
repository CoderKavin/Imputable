"use client";

import { cn } from "@/lib/utils";

type Status = "draft" | "pending_review" | "approved" | "deprecated" | "superseded" | "at_risk";
type ImpactLevel = "low" | "medium" | "high" | "critical";

interface StatusPillProps {
  status: string;
  className?: string;
}

interface ImpactPillProps {
  level: string;
  className?: string;
}

const statusConfig: Record<Status, { label: string; className: string }> = {
  draft: {
    label: "Draft",
    className: "bg-gray-50 text-gray-600 border-gray-200",
  },
  pending_review: {
    label: "In Review",
    className: "bg-amber-50 text-amber-700 border-amber-200",
  },
  approved: {
    label: "Approved",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  deprecated: {
    label: "Deprecated",
    className: "bg-gray-50 text-gray-500 border-gray-200",
  },
  superseded: {
    label: "Superseded",
    className: "bg-purple-50 text-purple-600 border-purple-200",
  },
  at_risk: {
    label: "At Risk",
    className: "bg-red-50 text-red-700 border-red-200",
  },
};

const impactConfig: Record<ImpactLevel, { label: string; className: string }> = {
  low: {
    label: "Low",
    className: "bg-blue-50 text-blue-600 border-blue-200",
  },
  medium: {
    label: "Medium",
    className: "bg-amber-50 text-amber-600 border-amber-200",
  },
  high: {
    label: "High",
    className: "bg-orange-50 text-orange-600 border-orange-200",
  },
  critical: {
    label: "Critical",
    className: "bg-red-50 text-red-700 border-red-200",
  },
};

export function StatusPill({ status, className }: StatusPillProps) {
  const config = statusConfig[status as Status] || {
    label: status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    className: "bg-gray-50 text-gray-600 border-gray-200",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border",
        "transition-colors duration-200",
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  );
}

export function ImpactPill({ level, className }: ImpactPillProps) {
  const config = impactConfig[level as ImpactLevel] || {
    label: level.charAt(0).toUpperCase() + level.slice(1),
    className: "bg-gray-50 text-gray-600 border-gray-200",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold border",
        "transition-colors duration-200",
        config.className,
        className
      )}
    >
      {config.label} Impact
    </span>
  );
}

// Compact version for tight spaces
export function StatusDot({ status, className }: StatusPillProps) {
  const dotColors: Record<string, string> = {
    draft: "bg-gray-400",
    pending_review: "bg-amber-500",
    approved: "bg-emerald-500",
    deprecated: "bg-gray-400",
    superseded: "bg-purple-500",
    at_risk: "bg-red-500",
  };

  return (
    <span
      className={cn(
        "w-2 h-2 rounded-full",
        dotColors[status] || "bg-gray-400",
        className
      )}
      title={statusConfig[status as Status]?.label || status}
    />
  );
}

"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { useRouter } from "next/navigation";
import type { DecisionStatus, ImpactLevel } from "@/types/decision";

export interface DecisionNodeData extends Record<string, unknown> {
  decision_number: number;
  title: string;
  status: DecisionStatus;
  impact_level: ImpactLevel;
  created_at: string;
}

const statusColors: Record<
  DecisionStatus,
  { bg: string; border: string; text: string }
> = {
  draft: { bg: "bg-gray-50", border: "border-gray-300", text: "text-gray-600" },
  pending_review: {
    bg: "bg-amber-50",
    border: "border-amber-300",
    text: "text-amber-700",
  },
  approved: {
    bg: "bg-emerald-50",
    border: "border-emerald-300",
    text: "text-emerald-700",
  },
  deprecated: {
    bg: "bg-red-50",
    border: "border-red-300",
    text: "text-red-600",
  },
  superseded: {
    bg: "bg-slate-100",
    border: "border-slate-400",
    text: "text-slate-600",
  },
};

const impactColors: Record<ImpactLevel, string> = {
  low: "bg-blue-100 text-blue-700",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

function DecisionNodeComponent({
  data,
  id,
  selected,
}: NodeProps & { data: DecisionNodeData }) {
  const router = useRouter();
  const colors = statusColors[data.status] || statusColors.draft;
  const impactColor = impactColors[data.impact_level] || impactColors.medium;

  const handleClick = () => {
    router.push(`/decisions/${id}`);
  };

  // Truncate title
  const displayTitle =
    data.title.length > 40 ? data.title.substring(0, 40) + "..." : data.title;

  return (
    <>
      {/* Connection handles */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-white"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-white"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-white"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-white"
      />

      {/* Node content */}
      <div
        onClick={handleClick}
        className={`
          px-4 py-3 rounded-xl border-2 cursor-pointer
          transition-all duration-200 min-w-[180px] max-w-[240px]
          ${colors.bg} ${colors.border}
          ${selected ? "ring-2 ring-indigo-500 ring-offset-2 shadow-lg scale-105" : "shadow-md hover:shadow-lg hover:scale-[1.02]"}
        `}
      >
        {/* Decision number and impact */}
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-mono font-semibold text-gray-500">
            DECISION-{data.decision_number}
          </span>
          <span
            className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${impactColor}`}
          >
            {data.impact_level}
          </span>
        </div>

        {/* Title */}
        <h3 className={`text-sm font-semibold leading-tight ${colors.text}`}>
          {displayTitle}
        </h3>

        {/* Status indicator */}
        <div className="mt-2 flex items-center gap-1.5">
          <div
            className={`w-2 h-2 rounded-full ${
              data.status === "approved"
                ? "bg-emerald-500"
                : data.status === "pending_review"
                  ? "bg-amber-500"
                  : data.status === "deprecated"
                    ? "bg-red-500"
                    : data.status === "superseded"
                      ? "bg-slate-500"
                      : "bg-gray-400"
            }`}
          />
          <span className="text-[10px] text-gray-500 capitalize">
            {data.status.replace("_", " ")}
          </span>
        </div>
      </div>
    </>
  );
}

export const DecisionNode = memo(DecisionNodeComponent);

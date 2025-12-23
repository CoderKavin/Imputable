"use client";

/**
 * AvatarStack Component
 *
 * Shows overlapping avatar circles for reviewers with approval status indicators.
 * - Green ring = approved
 * - Red ring = rejected
 * - Gray ring = pending/abstained
 */

import { cn } from "@/lib/utils";
import type { ApprovalStatus } from "@/types/decision";

interface AvatarUser {
  id: string;
  name: string;
  email?: string;
  status?: ApprovalStatus;
}

interface AvatarStackProps {
  users: AvatarUser[];
  max?: number;
  size?: "sm" | "md";
  className?: string;
}

// Generate avatar background color from name
function getAvatarColor(name: string): string {
  const colors = [
    "bg-indigo-500",
    "bg-purple-500",
    "bg-pink-500",
    "bg-blue-500",
    "bg-cyan-500",
    "bg-teal-500",
    "bg-green-500",
    "bg-orange-500",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

function getInitials(name: string): string {
  if (!name) return "??";
  return (
    name
      .split(" ")
      .filter((n) => n.length > 0)
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "??"
  );
}

function getStatusRing(status?: ApprovalStatus): string {
  switch (status) {
    case "approved":
      return "ring-2 ring-green-500 ring-offset-1";
    case "rejected":
      return "ring-2 ring-red-500 ring-offset-1";
    case "abstained":
      return "ring-2 ring-gray-300 ring-offset-1";
    default:
      return "ring-1 ring-white";
  }
}

export function AvatarStack({
  users,
  max = 4,
  size = "sm",
  className,
}: AvatarStackProps) {
  const displayedUsers = users.slice(0, max);
  const remainingCount = users.length - max;

  const sizeClasses = {
    sm: "w-6 h-6 text-[10px]",
    md: "w-8 h-8 text-xs",
  };

  const overlapClasses = {
    sm: "-ml-2",
    md: "-ml-3",
  };

  if (users.length === 0) {
    return null;
  }

  return (
    <div className={cn("flex items-center", className)}>
      <div className="flex">
        {displayedUsers.map((user, index) => (
          <div
            key={user.id}
            className={cn(
              "rounded-full flex items-center justify-center text-white font-medium",
              sizeClasses[size],
              getAvatarColor(user.name),
              getStatusRing(user.status),
              index > 0 && overlapClasses[size],
            )}
            title={`${user.name}${user.status ? ` - ${user.status}` : ""}`}
          >
            {getInitials(user.name)}
          </div>
        ))}
        {remainingCount > 0 && (
          <div
            className={cn(
              "rounded-full flex items-center justify-center bg-gray-200 text-gray-600 font-medium ring-1 ring-white",
              sizeClasses[size],
              overlapClasses[size],
            )}
            title={`${remainingCount} more reviewer${remainingCount > 1 ? "s" : ""}`}
          >
            +{remainingCount}
          </div>
        )}
      </div>
    </div>
  );
}

export default AvatarStack;

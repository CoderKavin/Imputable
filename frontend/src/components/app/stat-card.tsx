"use client";

import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: {
    value: number;
    positive?: boolean;
  };
  className?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        "bg-white rounded-2xl border border-gray-100 p-6",
        "transition-all duration-300",
        "hover:shadow-lg hover:shadow-gray-100/50 hover:border-gray-200",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
          )}
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <span
                className={cn(
                  "text-xs font-medium",
                  trend.positive ? "text-emerald-600" : "text-red-600"
                )}
              >
                {trend.positive ? "+" : "-"}{Math.abs(trend.value)}%
              </span>
              <span className="text-xs text-gray-400">vs last month</span>
            </div>
          )}
        </div>
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-gray-400">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// Colored stat card variant
interface ColoredStatCardProps extends StatCardProps {
  color: "indigo" | "emerald" | "amber" | "red" | "purple";
}

export function ColoredStatCard({
  title,
  value,
  subtitle,
  icon,
  color,
  className,
}: ColoredStatCardProps) {
  const colorClasses = {
    indigo: "from-indigo-500 to-indigo-600 shadow-indigo-500/25",
    emerald: "from-emerald-500 to-emerald-600 shadow-emerald-500/25",
    amber: "from-amber-500 to-amber-600 shadow-amber-500/25",
    red: "from-red-500 to-red-600 shadow-red-500/25",
    purple: "from-purple-500 to-purple-600 shadow-purple-500/25",
  };

  return (
    <div
      className={cn(
        "rounded-2xl p-6 text-white",
        "bg-gradient-to-br shadow-lg",
        colorClasses[color],
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-white/80">{title}</p>
          <p className="text-3xl font-bold mt-2">{value}</p>
          {subtitle && (
            <p className="text-xs text-white/60 mt-1">{subtitle}</p>
          )}
        </div>
        {icon && (
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

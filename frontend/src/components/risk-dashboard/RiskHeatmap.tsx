/**
 * Risk Heatmap - Multiple views for tech debt visualization
 *
 * Views:
 * 1. Teams: Accountability view by team (red/yellow/green)
 * 2. Tags: Domain-based grouping
 * 3. Timeline: GitHub-style weekly heatmap
 */

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHeatmapData, useTagHeatmap } from "@/hooks/use-risk-dashboard";
import { TeamHeatmap } from "./TeamHeatmap";

type HeatmapView = "teams" | "tags" | "timeline";

export function RiskHeatmap() {
  const [view, setView] = useState<HeatmapView>("teams");

  return (
    <div className="space-y-4">
      {/* View Selector */}
      <div className="flex items-center space-x-2">
        <span className="text-sm font-medium text-gray-700">View:</span>
        <ViewButton active={view === "teams"} onClick={() => setView("teams")}>
          By Team
        </ViewButton>
        <ViewButton active={view === "tags"} onClick={() => setView("tags")}>
          By Tag
        </ViewButton>
        <ViewButton
          active={view === "timeline"}
          onClick={() => setView("timeline")}
        >
          Timeline
        </ViewButton>
      </div>

      {/* Render selected view */}
      {view === "teams" && <TeamHeatmap />}
      {view === "tags" && <TagHeatmapView />}
      {view === "timeline" && <TimelineHeatmap />}
    </div>
  );
}

function ViewButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        px-3 py-1.5 text-sm font-medium rounded-xl transition-colors
        ${
          active
            ? "bg-indigo-100 text-indigo-700"
            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
        }
      `}
    >
      {children}
    </button>
  );
}

// =============================================================================
// Tag Heatmap View
// =============================================================================

function TagHeatmapView() {
  const { data, isLoading } = useTagHeatmap();

  if (isLoading) {
    return <HeatmapSkeleton title="Tag Analysis" />;
  }

  if (!data || data.tags.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Tag Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12 text-gray-500">
            No tag data available. Add tags to your decisions to see analysis.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Tech Debt by Tag/Domain</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Identify problem areas by category (e.g., security, performance)
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {data.tags.map((tag) => (
            <TagRow key={tag.tag} tag={tag} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function TagRow({
  tag,
}: {
  tag: {
    tag: string;
    expired_count: number;
    at_risk_count: number;
    total_count: number;
    health_score: number;
    color: string;
  };
}) {
  const colorClasses = {
    red: "bg-red-500",
    yellow: "bg-amber-500",
    green: "bg-green-500",
  };

  const barColor =
    colorClasses[tag.color as keyof typeof colorClasses] || "bg-gray-400";

  return (
    <div className="flex items-center space-x-4">
      <div className="w-32 truncate">
        <span className="text-sm font-medium text-gray-900">{tag.tag}</span>
      </div>
      <div className="flex-1">
        <div className="h-6 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full ${barColor} transition-all duration-300 flex items-center justify-end pr-2`}
            style={{ width: `${Math.max(tag.health_score, 10)}%` }}
          >
            <span className="text-xs text-white font-medium">
              {tag.health_score}%
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center space-x-3 text-xs">
        <span className="text-red-600 font-medium">
          {tag.expired_count} expired
        </span>
        <span className="text-amber-600 font-medium">
          {tag.at_risk_count} at risk
        </span>
        <span className="text-gray-500">{tag.total_count} total</span>
      </div>
    </div>
  );
}

// =============================================================================
// Timeline Heatmap (Original GitHub-style)
// =============================================================================

function TimelineHeatmap() {
  const { data, isLoading } = useHeatmapData(12);

  if (isLoading) {
    return <HeatmapSkeleton title="Activity Heatmap" />;
  }

  if (!data || data.data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Activity Heatmap</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12 text-gray-500">
            No decision data available for the heatmap.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">Tech Debt Activity</CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Weekly review dates across the past 12 months
            </p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900">
              {data.total_decisions}
            </p>
            <p className="text-sm text-gray-500">Total decisions tracked</p>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <HeatmapGrid data={data.data} maxCount={data.max_count} />

        {/* Legend */}
        <div className="mt-6 flex items-center justify-end space-x-2 text-sm">
          <span className="text-gray-500">Less</span>
          <div className="flex space-x-1">
            <div className="w-4 h-4 rounded-sm bg-gray-100 border border-gray-200" />
            <div className="w-4 h-4 rounded-sm bg-green-200" />
            <div className="w-4 h-4 rounded-sm bg-green-300" />
            <div className="w-4 h-4 rounded-sm bg-green-500" />
            <div className="w-4 h-4 rounded-sm bg-green-700" />
          </div>
          <span className="text-gray-500">More</span>
        </div>

        {/* Stats */}
        <div className="mt-6 grid grid-cols-3 gap-4">
          <StatBox
            label="Peak Week"
            value={getPeakWeekLabel(data.data)}
            sublabel={`${data.max_count} decisions`}
          />
          <StatBox
            label="Average/Week"
            value={(
              data.total_decisions / Math.max(data.data.length, 1)
            ).toFixed(1)}
            sublabel="decisions"
          />
          <StatBox
            label="Active Weeks"
            value={data.data.filter((d) => d.count > 0).length.toString()}
            sublabel={`of ${data.data.length} weeks`}
          />
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Heatmap Grid Component
// =============================================================================

interface HeatmapGridProps {
  data: Array<{ week: string; count: number }>;
  maxCount: number;
}

function HeatmapGrid({ data, maxCount }: HeatmapGridProps) {
  const { weeks, months } = useMemo(() => {
    const dataMap = new Map(data.map((d) => [d.week, d.count]));

    const weeks: Array<{ weekStart: string; count: number }> = [];

    const now = new Date();
    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - 364);
    startDate.setDate(startDate.getDate() - startDate.getDay());

    const current = new Date(startDate);
    while (current <= now) {
      const weekKey = current.toISOString().split("T")[0];
      weeks.push({
        weekStart: weekKey,
        count: dataMap.get(weekKey) || 0,
      });
      current.setDate(current.getDate() + 7);
    }

    const months: Array<{ label: string; startWeek: number }> = [];
    let lastMonth = -1;

    weeks.forEach((week, index) => {
      const date = new Date(week.weekStart);
      const month = date.getMonth();
      if (month !== lastMonth) {
        months.push({
          label: date.toLocaleDateString("en-US", { month: "short" }),
          startWeek: index,
        });
        lastMonth = month;
      }
    });

    return { weeks, months };
  }, [data]);

  return (
    <div className="overflow-x-auto">
      <div className="flex mb-2 pl-8">
        {months.map((month, index) => (
          <div
            key={index}
            className="text-xs text-gray-500"
            style={{
              marginLeft:
                index === 0
                  ? 0
                  : `${(month.startWeek - (months[index - 1]?.startWeek || 0) - 1) * 14}px`,
            }}
          >
            {month.label}
          </div>
        ))}
      </div>

      <div className="flex">
        <div className="flex flex-col justify-around pr-2 text-xs text-gray-500">
          <span>Mon</span>
          <span>Wed</span>
          <span>Fri</span>
        </div>

        <div className="flex gap-1">
          {weeks.map((week, weekIndex) => (
            <div key={weekIndex} className="flex flex-col gap-1">
              {[0, 1, 2, 3, 4, 5, 6].map((dayOffset) => {
                if (dayOffset !== 3) {
                  return (
                    <div
                      key={dayOffset}
                      className="w-3 h-3 rounded-sm bg-transparent"
                    />
                  );
                }
                return (
                  <HeatmapCell
                    key={dayOffset}
                    count={week.count}
                    maxCount={maxCount}
                    date={week.weekStart}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Heatmap Cell
// =============================================================================

interface HeatmapCellProps {
  count: number;
  maxCount: number;
  date: string;
}

function HeatmapCell({ count, maxCount, date }: HeatmapCellProps) {
  const intensity = maxCount > 0 ? count / maxCount : 0;
  const bgColor = getHeatmapColor(intensity, count);

  const formattedDate = new Date(date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div
      className={`w-3 h-3 rounded-sm ${bgColor} cursor-pointer transition-transform hover:scale-125`}
      title={`Week of ${formattedDate}: ${count} decision${count !== 1 ? "s" : ""}`}
    />
  );
}

function getHeatmapColor(intensity: number, count: number): string {
  if (count === 0) return "bg-gray-100 border border-gray-200";
  if (intensity <= 0.25) return "bg-green-200";
  if (intensity <= 0.5) return "bg-green-300";
  if (intensity <= 0.75) return "bg-green-500";
  return "bg-green-700";
}

// =============================================================================
// Helpers
// =============================================================================

interface StatBoxProps {
  label: string;
  value: string;
  sublabel: string;
}

function StatBox({ label, value, sublabel }: StatBoxProps) {
  return (
    <div className="bg-gray-50 rounded-2xl p-4 text-center">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
      <p className="text-xs text-gray-400">{sublabel}</p>
    </div>
  );
}

function getPeakWeekLabel(
  data: Array<{ week: string; count: number }>,
): string {
  if (data.length === 0) return "-";
  const peak = data.reduce(
    (max, d) => (d.count > max.count ? d : max),
    data[0],
  );
  const date = new Date(peak.week);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function HeatmapSkeleton({ title = "Heatmap" }: { title?: string }) {
  return (
    <Card>
      <CardHeader>
        <div className="h-6 bg-gray-200 rounded w-48 animate-pulse" />
        <div className="h-4 bg-gray-200 rounded w-64 mt-2 animate-pulse" />
      </CardHeader>
      <CardContent>
        <div className="flex gap-1">
          {[...Array(52)].map((_, i) => (
            <div key={i} className="flex flex-col gap-1">
              {[...Array(7)].map((_, j) => (
                <div
                  key={j}
                  className="w-3 h-3 rounded-sm bg-gray-100 animate-pulse"
                />
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

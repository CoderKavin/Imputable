/**
 * Debt Wall Calendar - Visual calendar showing when decisions expire
 *
 * Displays a month view with decision counts per day,
 * color-coded by urgency/count.
 */

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCalendarData, type CalendarDay } from "@/hooks/use-risk-dashboard";

export function DebtWallCalendar() {
  const [currentDate, setCurrentDate] = useState(new Date());

  // Calculate date range for the visible month
  const { startDate, endDate } = useMemo(() => {
    const start = new Date(
      currentDate.getFullYear(),
      currentDate.getMonth(),
      1,
    );
    const end = new Date(
      currentDate.getFullYear(),
      currentDate.getMonth() + 1,
      0,
    );
    return {
      startDate: start.toISOString(),
      endDate: end.toISOString(),
    };
  }, [currentDate]);

  const { data: calendarData, isLoading } = useCalendarData(startDate, endDate);

  // Build a map of date -> decisions for quick lookup
  const decisionsByDate = useMemo(() => {
    if (!calendarData?.days) return new Map<string, CalendarDay>();
    return new Map(calendarData.days.map((day) => [day.date, day]));
  }, [calendarData]);

  const goToPreviousMonth = () => {
    setCurrentDate(
      new Date(currentDate.getFullYear(), currentDate.getMonth() - 1),
    );
  };

  const goToNextMonth = () => {
    setCurrentDate(
      new Date(currentDate.getFullYear(), currentDate.getMonth() + 1),
    );
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Debt Wall</CardTitle>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm" onClick={goToPreviousMonth}>
              <ChevronLeftIcon className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={goToToday}>
              Today
            </Button>
            <Button variant="outline" size="sm" onClick={goToNextMonth}>
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="text-2xl font-bold text-gray-900 mt-2">
          {currentDate.toLocaleDateString("en-US", {
            month: "long",
            year: "numeric",
          })}
        </p>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <CalendarSkeleton />
        ) : (
          <CalendarGrid
            currentDate={currentDate}
            decisionsByDate={decisionsByDate}
          />
        )}

        {/* Legend */}
        <div className="mt-6 flex items-center justify-center space-x-6 text-sm">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 rounded bg-gray-100 border border-gray-200" />
            <span className="text-gray-600">No decisions</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 rounded bg-amber-100 border border-amber-200" />
            <span className="text-gray-600">1-2 decisions</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 rounded bg-orange-200 border border-orange-300" />
            <span className="text-gray-600">3-5 decisions</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 rounded bg-red-300 border border-red-400" />
            <span className="text-gray-600">6+ decisions</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Calendar Grid Component
// =============================================================================

interface CalendarGridProps {
  currentDate: Date;
  decisionsByDate: Map<string, CalendarDay>;
}

function CalendarGrid({ currentDate, decisionsByDate }: CalendarGridProps) {
  const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);

  const days = useMemo(() => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    // First day of the month
    const firstDay = new Date(year, month, 1);
    const startingDayOfWeek = firstDay.getDay();

    // Last day of the month
    const lastDay = new Date(year, month + 1, 0);
    const totalDays = lastDay.getDate();

    // Build array of days
    const daysArray: Array<{
      date: Date;
      dateString: string;
      isCurrentMonth: boolean;
      isToday: boolean;
    }> = [];

    // Add days from previous month to fill the first week
    const prevMonth = new Date(year, month, 0);
    for (let i = startingDayOfWeek - 1; i >= 0; i--) {
      const date = new Date(year, month - 1, prevMonth.getDate() - i);
      daysArray.push({
        date,
        dateString: formatDateString(date),
        isCurrentMonth: false,
        isToday: false,
      });
    }

    // Add days of current month
    const today = new Date();
    for (let day = 1; day <= totalDays; day++) {
      const date = new Date(year, month, day);
      daysArray.push({
        date,
        dateString: formatDateString(date),
        isCurrentMonth: true,
        isToday:
          date.getDate() === today.getDate() &&
          date.getMonth() === today.getMonth() &&
          date.getFullYear() === today.getFullYear(),
      });
    }

    // Add days from next month to complete the grid
    const remainingDays = 42 - daysArray.length; // 6 weeks * 7 days
    for (let day = 1; day <= remainingDays; day++) {
      const date = new Date(year, month + 1, day);
      daysArray.push({
        date,
        dateString: formatDateString(date),
        isCurrentMonth: false,
        isToday: false,
      });
    }

    return daysArray;
  }, [currentDate]);

  return (
    <>
      {/* Weekday Headers */}
      <div className="grid grid-cols-7 gap-1 mb-2">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
          <div
            key={day}
            className="text-center text-xs font-medium text-gray-500 py-2"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar Days */}
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, index) => {
          const dayData = decisionsByDate.get(day.dateString);
          const count = dayData?.decisions.length || 0;

          return (
            <CalendarDayCell
              key={index}
              day={day.date.getDate()}
              isCurrentMonth={day.isCurrentMonth}
              isToday={day.isToday}
              count={count}
              decisions={dayData?.decisions || []}
              onClick={() => dayData && setSelectedDay(dayData)}
            />
          );
        })}
      </div>

      {/* Selected Day Details */}
      {selectedDay && (
        <DayDetailsPanel
          day={selectedDay}
          onClose={() => setSelectedDay(null)}
        />
      )}
    </>
  );
}

// =============================================================================
// Calendar Day Cell
// =============================================================================

interface CalendarDayCellProps {
  day: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  count: number;
  decisions: CalendarDay["decisions"];
  onClick: () => void;
}

function CalendarDayCell({
  day,
  isCurrentMonth,
  isToday,
  count,
  decisions,
  onClick,
}: CalendarDayCellProps) {
  const bgColor = getBackgroundColor(count);
  const hasDecisions = count > 0;

  return (
    <button
      onClick={onClick}
      disabled={!hasDecisions}
      className={`
        relative h-20 p-1 rounded-xl border transition-all
        ${isCurrentMonth ? "text-gray-900" : "text-gray-400"}
        ${isToday ? "ring-2 ring-indigo-500" : ""}
        ${bgColor}
        ${hasDecisions ? "cursor-pointer hover:shadow-md" : "cursor-default"}
      `}
    >
      <span
        className={`
          absolute top-1 left-2 text-sm font-medium
          ${isToday ? "text-indigo-600" : ""}
        `}
      >
        {day}
      </span>

      {count > 0 && (
        <div className="absolute bottom-1 right-1 left-1">
          <div className="text-xs font-medium text-center">
            {count} {count === 1 ? "decision" : "decisions"}
          </div>
          {/* Impact level indicators */}
          <div className="flex justify-center mt-1 space-x-0.5">
            {decisions.slice(0, 4).map((d, i) => (
              <div
                key={i}
                className={`w-2 h-2 rounded-full ${getImpactColor(d.impact_level)}`}
                title={d.title}
              />
            ))}
            {count > 4 && (
              <span className="text-xs text-gray-500">+{count - 4}</span>
            )}
          </div>
        </div>
      )}
    </button>
  );
}

// =============================================================================
// Day Details Panel
// =============================================================================

interface DayDetailsPanelProps {
  day: CalendarDay;
  onClose: () => void;
}

function DayDetailsPanel({ day, onClose }: DayDetailsPanelProps) {
  const date = new Date(day.date);

  return (
    <div className="mt-6 border-t pt-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-medium text-gray-900">
          {date.toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
          })}
        </h3>
        <Button variant="outline" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>

      <div className="space-y-3">
        {day.decisions.map((decision) => (
          <div
            key={decision.id}
            className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center space-x-3">
              <div
                className={`w-3 h-3 rounded-full ${getImpactColor(decision.impact_level)}`}
              />
              <div>
                <p className="text-sm font-medium text-gray-900">
                  #{decision.decision_number}: {decision.title}
                </p>
                <p className="text-xs text-gray-500">
                  {decision.team_name || "Unassigned"} • {decision.impact_level}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {decision.is_temporary && (
                <span className="px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-700">
                  Temporary
                </span>
              )}
              <StatusBadge status={decision.status} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    expired: "bg-red-100 text-red-700",
    at_risk: "bg-amber-100 text-amber-700",
    approved: "bg-green-100 text-green-700",
  };

  return (
    <span
      className={`px-2 py-0.5 text-xs rounded ${colors[status] || "bg-gray-100 text-gray-700"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

// =============================================================================
// Helpers
// =============================================================================

function formatDateString(date: Date): string {
  return date.toISOString().split("T")[0];
}

function getBackgroundColor(count: number): string {
  if (count === 0) return "bg-gray-50 border-gray-200";
  if (count <= 2) return "bg-amber-50 border-amber-200";
  if (count <= 5) return "bg-orange-100 border-orange-300";
  return "bg-red-100 border-red-300";
}

function getImpactColor(level: string): string {
  const colors: Record<string, string> = {
    critical: "bg-red-500",
    high: "bg-orange-500",
    medium: "bg-amber-500",
    low: "bg-green-500",
  };
  return colors[level] || "bg-gray-400";
}

function CalendarSkeleton() {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-7 gap-1">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="h-6 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {[...Array(35)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    </div>
  );
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 19l-7-7 7-7"
      />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 5l7 7-7 7"
      />
    </svg>
  );
}

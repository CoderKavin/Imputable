/**
 * Risk Stats Cards - Overview statistics for the dashboard
 */

import { Card, CardContent } from "@/components/ui/card";
import type { RiskStats } from "@/hooks/use-risk-dashboard";

interface RiskStatsCardsProps {
  stats: RiskStats | undefined;
  isLoading: boolean;
}

export function RiskStatsCards({ stats, isLoading }: RiskStatsCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="p-6">
              <div className="h-4 bg-gray-200 rounded w-24 mb-2" />
              <div className="h-8 bg-gray-200 rounded w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const cards: StatCardProps[] = [
    {
      label: "Expired",
      value: stats?.total_expired ?? 0,
      color: "red",
      icon: ExpiredIcon,
      description: "Past review date",
    },
    {
      label: "At Risk",
      value: stats?.total_at_risk ?? 0,
      color: "amber",
      icon: AtRiskIcon,
      description: "Within 14 days",
    },
    {
      label: "This Week",
      value: stats?.expiring_this_week ?? 0,
      color: "orange",
      icon: WeekIcon,
      description: "Expiring in 7 days",
    },
    {
      label: "This Month",
      value: stats?.expiring_this_month ?? 0,
      color: "blue",
      icon: MonthIcon,
      description: "Expiring in 30 days",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {cards.map((card) => (
        <StatCard key={card.label} {...card} />
      ))}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number;
  color: "red" | "amber" | "orange" | "blue";
  icon: React.FC<{ className?: string }>;
  description: string;
}

function StatCard({
  label,
  value,
  color,
  icon: Icon,
  description,
}: StatCardProps) {
  const colorClasses = {
    red: {
      bg: "bg-red-50",
      text: "text-red-700",
      icon: "text-red-500",
      border: "border-red-200",
    },
    amber: {
      bg: "bg-amber-50",
      text: "text-amber-700",
      icon: "text-amber-500",
      border: "border-amber-200",
    },
    orange: {
      bg: "bg-orange-50",
      text: "text-orange-700",
      icon: "text-orange-500",
      border: "border-orange-200",
    },
    blue: {
      bg: "bg-blue-50",
      text: "text-blue-700",
      icon: "text-blue-500",
      border: "border-blue-200",
    },
  };

  const colors = colorClasses[color];

  return (
    <Card className={`${colors.bg} ${colors.border} border`}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className={`text-sm font-medium ${colors.text}`}>{label}</p>
            <p className={`text-3xl font-bold ${colors.text} mt-1`}>{value}</p>
            <p className="text-xs text-gray-500 mt-1">{description}</p>
          </div>
          <div className={`p-3 rounded-full ${colors.bg}`}>
            <Icon className={`h-6 w-6 ${colors.icon}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Icons
// =============================================================================

function ExpiredIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function AtRiskIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  );
}

function WeekIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  );
}

function MonthIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
      />
    </svg>
  );
}

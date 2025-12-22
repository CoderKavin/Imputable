/**
 * Risk Dashboard - Executive View for Tech Debt Management
 *
 * Provides:
 * - Overview stats (expired, at-risk counts)
 * - Expiring decisions list with actions
 * - Debt Wall calendar view
 * - Activity heatmap
 */

import { useState } from "react";
import { useRiskStats, useExpiringDecisions } from "@/hooks/use-risk-dashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskStatsCards } from "./RiskStatsCards";
import { ExpiringDecisionsList } from "./ExpiringDecisionsList";
import { DebtWallCalendar } from "./DebtWallCalendar";
import { RiskHeatmap } from "./RiskHeatmap";

type TabType = "overview" | "calendar" | "heatmap";

export function RiskDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const { data: stats, isLoading: statsLoading } = useRiskStats();
  const { data: expiringData, isLoading: expiringLoading } =
    useExpiringDecisions({
      status_filter: statusFilter,
      limit: 20,
    });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Risk Dashboard
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                Monitor tech debt and expiring decisions across your
                organization
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-500">Last updated:</span>
              <span className="text-sm font-medium text-gray-700">
                {new Date().toLocaleTimeString()}
              </span>
            </div>
          </div>

          {/* Tabs */}
          <div className="mt-6 border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <TabButton
                active={activeTab === "overview"}
                onClick={() => setActiveTab("overview")}
              >
                Overview
              </TabButton>
              <TabButton
                active={activeTab === "calendar"}
                onClick={() => setActiveTab("calendar")}
              >
                Debt Wall
              </TabButton>
              <TabButton
                active={activeTab === "heatmap"}
                onClick={() => setActiveTab("heatmap")}
              >
                Heatmap
              </TabButton>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === "overview" && (
          <div className="space-y-8">
            {/* Stats Cards */}
            <RiskStatsCards stats={stats} isLoading={statsLoading} />

            {/* Filters */}
            <div className="flex items-center space-x-4">
              <span className="text-sm font-medium text-gray-700">Filter:</span>
              <FilterButton
                active={!statusFilter}
                onClick={() => setStatusFilter(undefined)}
              >
                All
              </FilterButton>
              <FilterButton
                active={statusFilter === "expired"}
                onClick={() => setStatusFilter("expired")}
              >
                Expired Only
              </FilterButton>
              <FilterButton
                active={statusFilter === "at_risk"}
                onClick={() => setStatusFilter("at_risk")}
              >
                At Risk Only
              </FilterButton>
            </div>

            {/* Expiring Decisions List */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  {statusFilter === "expired"
                    ? "Expired Decisions"
                    : statusFilter === "at_risk"
                      ? "At-Risk Decisions"
                      : "Decisions Requiring Attention"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ExpiringDecisionsList
                  decisions={expiringData?.decisions || []}
                  isLoading={expiringLoading}
                  totalCount={expiringData?.total_count || 0}
                />
              </CardContent>
            </Card>

            {/* Team Breakdown */}
            {stats && Object.keys(stats.by_team).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">By Team</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(stats.by_team).map(([team, count]) => (
                      <div
                        key={team}
                        className="bg-gray-50 rounded-2xl p-4 text-center"
                      >
                        <div className="text-2xl font-bold text-gray-900">
                          {count}
                        </div>
                        <div className="text-sm text-gray-500">{team}</div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === "calendar" && <DebtWallCalendar />}

        {activeTab === "heatmap" && <RiskHeatmap />}
      </main>
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

function TabButton({
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
        whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors
        ${
          active
            ? "border-indigo-500 text-indigo-600"
            : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
        }
      `}
    >
      {children}
    </button>
  );
}

function FilterButton({
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
        px-3 py-1.5 text-sm font-medium rounded-full transition-colors
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

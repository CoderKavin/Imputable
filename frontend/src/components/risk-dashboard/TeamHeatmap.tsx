/**
 * Team Heatmap - Shows tech debt accountability by team
 *
 * Color coding:
 * - Red: Teams with expired decisions
 * - Yellow: Teams with at-risk decisions
 * - Green: Teams with zero tech debt
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTeamHeatmap, type TeamHeatmapItem } from "@/hooks/use-risk-dashboard";

export function TeamHeatmap() {
  const { data, isLoading } = useTeamHeatmap();

  if (isLoading) {
    return <TeamHeatmapSkeleton />;
  }

  if (!data || data.teams.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Team Accountability</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12 text-gray-500">
            No team data available.
          </div>
        </CardContent>
      </Card>
    );
  }

  // Separate teams by color for visual grouping
  const redTeams = data.teams.filter((t) => t.color === "red");
  const yellowTeams = data.teams.filter((t) => t.color === "yellow");
  const greenTeams = data.teams.filter((t) => t.color === "green");

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">Team Accountability</CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Tech debt status by team - Red teams need immediate attention
            </p>
          </div>
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-gray-600">{redTeams.length} critical</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 rounded-full bg-amber-500" />
              <span className="text-gray-600">{yellowTeams.length} at risk</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="text-gray-600">{greenTeams.length} healthy</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-6">
          {/* Critical Teams (Red) */}
          {redTeams.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-red-700 mb-3 flex items-center">
                <AlertIcon className="w-4 h-4 mr-1" />
                Needs Immediate Attention
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {redTeams.map((team) => (
                  <TeamCard key={team.team_id || team.team_name} team={team} />
                ))}
              </div>
            </div>
          )}

          {/* At Risk Teams (Yellow) */}
          {yellowTeams.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-amber-700 mb-3 flex items-center">
                <WarningIcon className="w-4 h-4 mr-1" />
                At Risk
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {yellowTeams.map((team) => (
                  <TeamCard key={team.team_id || team.team_name} team={team} />
                ))}
              </div>
            </div>
          )}

          {/* Healthy Teams (Green) */}
          {greenTeams.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-green-700 mb-3 flex items-center">
                <CheckIcon className="w-4 h-4 mr-1" />
                Healthy
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {greenTeams.map((team) => (
                  <TeamCard key={team.team_id || team.team_name} team={team} />
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Team Card Component
// =============================================================================

function TeamCard({ team }: { team: TeamHeatmapItem }) {
  const colorClasses = {
    red: {
      bg: "bg-red-50",
      border: "border-red-200",
      bar: "bg-red-500",
      text: "text-red-700",
    },
    yellow: {
      bg: "bg-amber-50",
      border: "border-amber-200",
      bar: "bg-amber-500",
      text: "text-amber-700",
    },
    green: {
      bg: "bg-green-50",
      border: "border-green-200",
      bar: "bg-green-500",
      text: "text-green-700",
    },
  };

  const colors = colorClasses[team.color];

  return (
    <div className={`${colors.bg} ${colors.border} border rounded-lg p-4`}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-gray-900 truncate">{team.team_name}</h4>
        <span className={`text-sm font-bold ${colors.text}`}>
          {team.health_score}%
        </span>
      </div>

      {/* Health Bar */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-3">
        <div
          className={`h-full ${colors.bar} transition-all duration-300`}
          style={{ width: `${team.health_score}%` }}
        />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <div className="font-bold text-red-600">{team.expired_count}</div>
          <div className="text-gray-500">Expired</div>
        </div>
        <div>
          <div className="font-bold text-amber-600">{team.at_risk_count}</div>
          <div className="text-gray-500">At Risk</div>
        </div>
        <div>
          <div className="font-bold text-green-600">{team.healthy_count}</div>
          <div className="text-gray-500">Healthy</div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Skeleton & Icons
// =============================================================================

function TeamHeatmapSkeleton() {
  return (
    <Card>
      <CardHeader>
        <div className="h-6 bg-gray-200 rounded w-48 animate-pulse" />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function WarningIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

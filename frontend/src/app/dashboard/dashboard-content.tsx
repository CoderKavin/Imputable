"use client";

import Link from "next/link";
import { StatCard, ColoredStatCard } from "@/components/app";
import { AwaitingReviewWidget } from "@/components/dashboard/awaiting-review-widget";
import {
  FileText,
  Clock,
  AlertTriangle,
  Users,
  Plus,
  ArrowRight,
  CheckCircle2,
  Building2,
  Loader2,
} from "lucide-react";
import { useDecisionList } from "@/hooks/use-decisions";
import { useRiskStats } from "@/hooks/use-risk-dashboard";
import { useOrganization } from "@/contexts/OrganizationContext";

interface DashboardContentProps {
  hasOrg: boolean;
}

export function DashboardContent({ hasOrg }: DashboardContentProps) {
  const { data: decisionData, isLoading: decisionsLoading } = useDecisionList(
    1,
    100,
  );
  const { data: riskStats, isLoading: riskLoading } = useRiskStats();
  const { organizations, currentOrganization } = useOrganization();

  if (!hasOrg) {
    return <NoOrganizationState />;
  }

  // Calculate stats from real data
  const totalDecisions = decisionData?.total || 0;
  const pendingReview =
    decisionData?.items?.filter((d) => d.status === "pending_review").length ||
    0;
  const atRisk = riskStats?.total_at_risk || 0;

  // Team members count - for now we don't have an endpoint, so show 1 (current user)
  // In a full implementation, this would come from an org members API
  const teamMembers = 1;

  // Get the 5 most recent decisions for the activity feed
  const recentDecisions = decisionData?.items?.slice(0, 5) || [];

  const isLoading = decisionsLoading || riskLoading;

  return (
    <div className="space-y-8">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <ColoredStatCard
          title="Total Decisions"
          value={isLoading ? "..." : totalDecisions}
          subtitle="Across all statuses"
          icon={
            isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <FileText className="w-5 h-5" />
            )
          }
          color="indigo"
        />
        <StatCard
          title="Pending Review"
          value={isLoading ? "..." : pendingReview}
          subtitle="Awaiting approval"
          icon={
            isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Clock className="w-5 h-5" />
            )
          }
        />
        <StatCard
          title="At Risk"
          value={isLoading ? "..." : atRisk}
          subtitle="Need attention"
          icon={
            isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <AlertTriangle className="w-5 h-5" />
            )
          }
        />
        <StatCard
          title="Team Members"
          value={isLoading ? "..." : teamMembers}
          subtitle="In organization"
          icon={
            isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Users className="w-5 h-5" />
            )
          }
        />
      </div>

      {/* Awaiting Review Widget - Prominent placement */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <AwaitingReviewWidget />
        </div>

        {/* Getting Started */}
        <div className="bg-white rounded-3xl border border-gray-100 p-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">
            Getting Started
          </h2>
          <div className="space-y-4">
            <OnboardingStep
              step={1}
              title="Create or join an organization"
              description="Use the switcher in the header"
              completed={hasOrg}
            />
            <OnboardingStep
              step={2}
              title="Invite your team"
              description="Add members to collaborate"
              completed={teamMembers > 1}
            />
            <OnboardingStep
              step={3}
              title="Create your first decision"
              description="Document important choices"
              completed={totalDecisions > 0}
            />
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-3xl border border-gray-100 p-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          Quick Actions
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <QuickActionCard
            href="/decisions"
            icon={<FileText className="w-5 h-5" />}
            title="View All Decisions"
            description="Browse and search your decision records"
          />
          <QuickActionCard
            href="/decisions/new"
            icon={<Plus className="w-5 h-5" />}
            title="Create Decision"
            description="Document a new engineering decision"
            highlight
          />
          <QuickActionCard
            href="/audit"
            icon={<Clock className="w-5 h-5" />}
            title="Audit Log"
            description="Review activity and changes"
          />
          <QuickActionCard
            href="/settings"
            icon={<Users className="w-5 h-5" />}
            title="Manage Team"
            description="Invite members and set permissions"
          />
        </div>
      </div>

      {/* Recent Activity */}
      <div className="bg-white rounded-3xl border border-gray-100 p-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Activity
          </h2>
          <Link
            href="/decisions"
            className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1"
          >
            View all
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        {decisionsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-gray-300" />
          </div>
        ) : recentDecisions.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Clock className="w-10 h-10 mx-auto mb-3 opacity-50" />
            <p className="text-sm">No recent activity</p>
            <Link
              href="/decisions/new"
              className="inline-flex items-center gap-1 mt-3 text-sm text-indigo-600 hover:text-indigo-700 font-medium"
            >
              Create your first decision
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {recentDecisions.map((decision) => (
              <Link
                key={decision.id}
                href={`/decisions/${decision.id}`}
                className="flex items-center gap-4 p-4 rounded-2xl hover:bg-gray-50 transition-colors group"
              >
                <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center text-gray-500 group-hover:bg-indigo-100 group-hover:text-indigo-600 transition-colors">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gray-400">
                      DECISION-{decision.decision_number}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(decision.status)}`}
                    >
                      {decision.status.replace("_", " ")}
                    </span>
                  </div>
                  <p className="font-medium text-gray-900 truncate mt-0.5">
                    {decision.title}
                  </p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-indigo-500 transition-colors" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Status color helper
function getStatusColor(status: string): string {
  switch (status) {
    case "approved":
      return "bg-emerald-100 text-emerald-700";
    case "pending_review":
      return "bg-amber-100 text-amber-700";
    case "draft":
      return "bg-gray-100 text-gray-600";
    case "deprecated":
      return "bg-red-100 text-red-700";
    case "superseded":
      return "bg-purple-100 text-purple-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

// Quick Action Card
function QuickActionCard({
  href,
  icon,
  title,
  description,
  highlight = false,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  highlight?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`
        group flex items-start gap-4 p-4 rounded-2xl border transition-all duration-200
        ${
          highlight
            ? "bg-indigo-50 border-indigo-100 hover:bg-indigo-100 hover:border-indigo-200"
            : "bg-gray-50 border-gray-100 hover:bg-gray-100 hover:border-gray-200"
        }
      `}
    >
      <div
        className={`
        w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
        ${highlight ? "bg-indigo-500 text-white" : "bg-white text-gray-500 border border-gray-200"}
      `}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <h3
          className={`font-medium ${highlight ? "text-indigo-900" : "text-gray-900"}`}
        >
          {title}
        </h3>
        <p
          className={`text-sm mt-0.5 ${highlight ? "text-indigo-600" : "text-gray-500"}`}
        >
          {description}
        </p>
      </div>
      <ArrowRight
        className={`
        w-4 h-4 mt-1 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0
        transition-all duration-200
        ${highlight ? "text-indigo-500" : "text-gray-400"}
      `}
      />
    </Link>
  );
}

// Onboarding Step
function OnboardingStep({
  step,
  title,
  description,
  completed,
}: {
  step: number;
  title: string;
  description: string;
  completed: boolean;
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={`
        w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold
        ${
          completed
            ? "bg-emerald-100 text-emerald-600"
            : "bg-gray-100 text-gray-400"
        }
      `}
      >
        {completed ? <CheckCircle2 className="w-4 h-4" /> : step}
      </div>
      <div>
        <p
          className={`font-medium ${completed ? "text-emerald-600" : "text-gray-900"}`}
        >
          {title}
        </p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
    </div>
  );
}

// No Organization State
function NoOrganizationState() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-amber-100 flex items-center justify-center mx-auto mb-6">
          <Building2 className="w-8 h-8 text-amber-600" />
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          No Organization Selected
        </h2>
        <p className="text-gray-500 mb-8">
          To create and manage decisions, you need to be part of an
          organization. Use the organization switcher in the header to create or
          join one.
        </p>
        <div className="p-6 bg-amber-50 rounded-2xl border border-amber-100 text-left">
          <h3 className="font-semibold text-amber-900 mb-2">
            How to get started:
          </h3>
          <ol className="space-y-2 text-sm text-amber-700">
            <li className="flex items-start gap-2">
              <span className="font-bold">1.</span>
              Click the organization dropdown in the top right
            </li>
            <li className="flex items-start gap-2">
              <span className="font-bold">2.</span>
              Select &quot;Create Organization&quot; or join an existing one
            </li>
            <li className="flex items-start gap-2">
              <span className="font-bold">3.</span>
              Start documenting your decisions!
            </li>
          </ol>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  Building2,
  CreditCard,
  Users,
  Plug,
  Bell,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { IntegrationsTab } from "@/components/settings/IntegrationsTab";

interface SettingsContentProps {
  hasOrg: boolean;
}

type TabId = "general" | "integrations" | "billing" | "team" | "notifications" | "security";

interface Tab {
  id: TabId;
  label: string;
  icon: React.ElementType;
  description: string;
}

const tabs: Tab[] = [
  {
    id: "general",
    label: "General",
    icon: Building2,
    description: "Organization details and preferences",
  },
  {
    id: "integrations",
    label: "Integrations",
    icon: Plug,
    description: "Connect Slack, Teams, and more",
  },
  {
    id: "billing",
    label: "Billing",
    icon: CreditCard,
    description: "Subscription and payment methods",
  },
  {
    id: "team",
    label: "Team",
    icon: Users,
    description: "Manage members and roles",
  },
  {
    id: "notifications",
    label: "Notifications",
    icon: Bell,
    description: "Email and push notification settings",
  },
  {
    id: "security",
    label: "Security",
    icon: Shield,
    description: "Authentication and access controls",
  },
];

export function SettingsContent({ hasOrg }: SettingsContentProps) {
  const [activeTab, setActiveTab] = useState<TabId>("integrations");

  if (!hasOrg) {
    return <NoOrganizationState />;
  }

  return (
    <div className="flex gap-8">
      {/* Sidebar Navigation */}
      <nav className="w-64 flex-shrink-0">
        <div className="sticky top-24 space-y-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200",
                  isActive
                    ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                )}
              >
                <Icon className={cn("w-5 h-5", isActive && "text-indigo-600 dark:text-indigo-400")} />
                <div>
                  <p className={cn("font-medium text-sm", isActive && "text-indigo-700 dark:text-indigo-300")}>
                    {tab.label}
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-500 mt-0.5 hidden lg:block">
                    {tab.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Content Area */}
      <main className="flex-1 min-w-0">
        <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8">
          {activeTab === "general" && <GeneralTab />}
          {activeTab === "integrations" && <IntegrationsTab />}
          {activeTab === "billing" && <BillingTab />}
          {activeTab === "team" && <TeamTab />}
          {activeTab === "notifications" && <NotificationsTab />}
          {activeTab === "security" && <SecurityTab />}
        </div>
      </main>
    </div>
  );
}

// =============================================================================
// PLACEHOLDER TABS
// =============================================================================

function GeneralTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          General Settings
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage your organization&apos;s basic information and preferences.
        </p>
      </div>
      <PlaceholderContent icon={Building2} message="Organization settings coming soon" />
    </div>
  );
}

function BillingTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Billing & Subscription
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage your subscription plan, payment methods, and billing history.
        </p>
      </div>
      <PlaceholderContent icon={CreditCard} message="Billing settings coming soon" />
    </div>
  );
}

function TeamTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Team Management
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Invite members, manage roles, and configure team permissions.
        </p>
      </div>
      <PlaceholderContent icon={Users} message="Team management coming soon" />
    </div>
  );
}

function NotificationsTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Notification Preferences
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Configure how and when you receive notifications.
        </p>
      </div>
      <PlaceholderContent icon={Bell} message="Notification settings coming soon" />
    </div>
  );
}

function SecurityTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Security Settings
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage authentication methods and security policies.
        </p>
      </div>
      <PlaceholderContent icon={Shield} message="Security settings coming soon" />
    </div>
  );
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function PlaceholderContent({
  icon: Icon,
  message,
}: {
  icon: React.ElementType;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-zinc-400 dark:text-zinc-500" />
      </div>
      <p className="text-zinc-500 dark:text-zinc-400">{message}</p>
    </div>
  );
}

function NoOrganizationState() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-amber-100 dark:bg-amber-950/50 flex items-center justify-center mx-auto mb-6">
          <Building2 className="w-8 h-8 text-amber-600 dark:text-amber-400" />
        </div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 mb-2">
          No Organization Selected
        </h2>
        <p className="text-zinc-500 dark:text-zinc-400 mb-8">
          To access settings, you need to be part of an organization.
          Use the organization switcher in the header to create or join one.
        </p>
      </div>
    </div>
  );
}

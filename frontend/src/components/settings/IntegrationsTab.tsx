"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import {
  MessageSquare,
  Check,
  X,
  ExternalLink,
  Loader2,
  Send,
  Unplug,
  Slack,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

// Use same-origin for Vercel Python functions
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

// =============================================================================
// TYPES
// =============================================================================

interface SlackStatus {
  connected: boolean;
  team_name: string | null;
  channel_name: string | null;
  installed_at: string | null;
}

interface TeamsStatus {
  connected: boolean;
  channel_name: string | null;
  installed_at: string | null;
}

interface IntegrationStatus {
  slack: SlackStatus;
  teams: TeamsStatus;
}

// =============================================================================
// MICROSOFT TEAMS ICON
// =============================================================================

function TeamsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M20.625 8.5h-3.75c-.345 0-.625.28-.625.625v6.75c0 .345.28.625.625.625h3.75c.345 0 .625-.28.625-.625v-6.75c0-.345-.28-.625-.625-.625zM18.75 7a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5zM14.25 4.5a3 3 0 11-6 0 3 3 0 016 0zM2.25 9.625C2.25 9.28 2.53 9 2.875 9h8.25c.345 0 .625.28.625.625v8.25c0 .345-.28.625-.625.625h-8.25a.625.625 0 01-.625-.625v-8.25z" />
    </svg>
  );
}

// =============================================================================
// COMPONENT
// =============================================================================

export function IntegrationsTab() {
  const { getToken } = useAuth();

  // State
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [slackConnecting, setSlackConnecting] = useState(false);
  const [slackDisconnecting, setSlackDisconnecting] = useState(false);
  const [teamsWebhookUrl, setTeamsWebhookUrl] = useState("");
  const [teamsSaving, setTeamsSaving] = useState(false);
  const [teamsDisconnecting, setTeamsDisconnecting] = useState(false);
  const [testingSlack, setTestingSlack] = useState(false);
  const [testingTeams, setTestingTeams] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Fetch integration status on mount
  useEffect(() => {
    fetchStatus();
  }, []);

  // Clear messages after 5 seconds
  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  // =============================================================================
  // API CALLS
  // =============================================================================

  async function fetchStatus() {
    try {
      setLoading(true);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/integrations/status`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        // If 403, user doesn't have Pro tier - show upgrade message
        if (response.status === 403) {
          setError("Integrations require a Pro subscription");
          setStatus({
            slack: {
              connected: false,
              team_name: null,
              channel_name: null,
              installed_at: null,
            },
            teams: { connected: false, channel_name: null, installed_at: null },
          });
          return;
        }
        throw new Error("Failed to fetch integration status");
      }

      const data = await response.json();
      setStatus(data);
    } catch (err) {
      console.error("Error fetching status:", err);
      setError("Failed to load integration status");
    } finally {
      setLoading(false);
    }
  }

  async function connectSlack() {
    try {
      setSlackConnecting(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(
        `${API_BASE_URL}/integrations/slack/install`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to get Slack install URL");
      }

      const data = await response.json();

      // Redirect to Slack OAuth
      window.location.href = data.install_url;
    } catch (err) {
      console.error("Error connecting Slack:", err);
      setError(err instanceof Error ? err.message : "Failed to connect Slack");
      setSlackConnecting(false);
    }
  }

  async function disconnectSlack() {
    try {
      setSlackDisconnecting(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/integrations/slack`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to disconnect Slack");
      }

      setSuccess("Slack disconnected successfully");
      await fetchStatus();
    } catch (err) {
      console.error("Error disconnecting Slack:", err);
      setError("Failed to disconnect Slack");
    } finally {
      setSlackDisconnecting(false);
    }
  }

  async function saveTeamsWebhook() {
    if (!teamsWebhookUrl.trim()) {
      setError("Please enter a webhook URL");
      return;
    }

    try {
      setTeamsSaving(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/integrations/teams`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          webhook_url: teamsWebhookUrl,
          channel_name: "Teams Channel",
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to save Teams webhook");
      }

      setSuccess("Teams webhook saved and tested successfully!");
      setTeamsWebhookUrl("");
      await fetchStatus();
    } catch (err) {
      console.error("Error saving Teams webhook:", err);
      setError(
        err instanceof Error ? err.message : "Failed to save Teams webhook",
      );
    } finally {
      setTeamsSaving(false);
    }
  }

  async function disconnectTeams() {
    try {
      setTeamsDisconnecting(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/integrations/teams`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to disconnect Teams");
      }

      setSuccess("Teams disconnected successfully");
      await fetchStatus();
    } catch (err) {
      console.error("Error disconnecting Teams:", err);
      setError("Failed to disconnect Teams");
    } finally {
      setTeamsDisconnecting(false);
    }
  }

  async function sendTestNotification() {
    try {
      setTestingSlack(true);
      setTestingTeams(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(
        `${API_BASE_URL}/integrations/test-notification`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to send test notification");
      }

      setSuccess("Test notification sent!");
    } catch (err) {
      console.error("Error sending test:", err);
      setError(
        err instanceof Error ? err.message : "Failed to send test notification",
      );
    } finally {
      setTestingSlack(false);
      setTestingTeams(false);
    }
  }

  // =============================================================================
  // RENDER
  // =============================================================================

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Integrations
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Connect Imputable to your team&apos;s communication tools to receive
          notifications when decisions are created, updated, or need review.
        </p>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 rounded-xl bg-green-50 px-4 py-3 text-sm text-green-700 dark:bg-green-950/50 dark:text-green-400">
          <Check className="h-4 w-4 flex-shrink-0" />
          {success}
        </div>
      )}

      {/* Slack Integration */}
      <Card className="overflow-hidden rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader className="border-b border-zinc-100 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#4A154B]">
              <Slack className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1">
              <CardTitle className="text-lg">Slack</CardTitle>
              <CardDescription>
                Get notifications in Slack when decisions change
              </CardDescription>
            </div>
            {status?.slack.connected && (
              <div className="flex items-center gap-2 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700 dark:bg-green-950/50 dark:text-green-400">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                Connected
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {status?.slack.connected ? (
            <div className="space-y-4">
              {/* Connected State */}
              <div className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-900">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    <MessageSquare className="h-4 w-4" />
                    {status.slack.team_name}
                  </div>
                  {status.slack.channel_name && (
                    <p className="text-sm text-zinc-500">
                      Posting to #{status.slack.channel_name}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={sendTestNotification}
                    disabled={testingSlack}
                    className="rounded-xl"
                  >
                    {testingSlack ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    Test
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={disconnectSlack}
                    disabled={slackDisconnecting}
                    className="rounded-xl text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/50"
                  >
                    {slackDisconnecting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Unplug className="mr-2 h-4 w-4" />
                    )}
                    Disconnect
                  </Button>
                </div>
              </div>

              {/* Slash Command Info */}
              <div className="rounded-xl border border-zinc-200 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
                <h4 className="mb-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  Slack Command
                </h4>
                <p className="mb-3 text-sm text-zinc-500">
                  Create decisions directly from Slack:
                </p>
                <code className="block rounded-lg bg-zinc-900 px-3 py-2 text-sm text-green-400 dark:bg-zinc-950">
                  /decision Use PostgreSQL for analytics service
                </code>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Disconnected State */}
              <p className="text-sm text-zinc-500">
                Connect your Slack workspace to receive real-time notifications
                about decision updates, approvals, and review reminders.
              </p>
              <Button
                onClick={connectSlack}
                disabled={slackConnecting}
                className="rounded-xl bg-[#4A154B] hover:bg-[#3a1139]"
              >
                {slackConnecting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Slack className="mr-2 h-4 w-4" />
                )}
                Add to Slack
                <ExternalLink className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Microsoft Teams Integration */}
      <Card className="overflow-hidden rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader className="border-b border-zinc-100 bg-zinc-50/50 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#5558AF]">
              <TeamsIcon className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1">
              <CardTitle className="text-lg">Microsoft Teams</CardTitle>
              <CardDescription>
                Send notifications to a Teams channel via webhook
              </CardDescription>
            </div>
            {status?.teams.connected && (
              <div className="flex items-center gap-2 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700 dark:bg-green-950/50 dark:text-green-400">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                Connected
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {status?.teams.connected ? (
            <div className="space-y-4">
              {/* Connected State */}
              <div className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-900">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    <Check className="h-4 w-4 text-green-500" />
                    Webhook configured
                  </div>
                  {status.teams.channel_name && (
                    <p className="text-sm text-zinc-500">
                      Posting to {status.teams.channel_name}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={sendTestNotification}
                    disabled={testingTeams}
                    className="rounded-xl"
                  >
                    {testingTeams ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    Test
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={disconnectTeams}
                    disabled={teamsDisconnecting}
                    className="rounded-xl text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/50"
                  >
                    {teamsDisconnecting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Unplug className="mr-2 h-4 w-4" />
                    )}
                    Disconnect
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Disconnected State */}
              <p className="text-sm text-zinc-500">
                Configure an incoming webhook to send notifications to your
                Microsoft Teams channel.
              </p>

              {/* Setup Instructions */}
              <div className="rounded-xl border border-zinc-200 bg-zinc-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
                <h4 className="mb-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  How to get a webhook URL:
                </h4>
                <ol className="list-inside list-decimal space-y-1 text-sm text-zinc-500">
                  <li>In Teams, right-click the channel → Connectors</li>
                  <li>Find &quot;Incoming Webhook&quot; and click Configure</li>
                  <li>
                    Name it &quot;Imputable&quot; and copy the webhook URL
                  </li>
                </ol>
              </div>

              {/* Webhook Input */}
              <div className="flex gap-2">
                <Input
                  type="url"
                  placeholder="https://outlook.office.com/webhook/..."
                  value={teamsWebhookUrl}
                  onChange={(e) => setTeamsWebhookUrl(e.target.value)}
                  className="flex-1 rounded-xl"
                />
                <Button
                  onClick={saveTeamsWebhook}
                  disabled={teamsSaving || !teamsWebhookUrl.trim()}
                  className="rounded-xl bg-[#5558AF] hover:bg-[#4547a0]"
                >
                  {teamsSaving ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Check className="mr-2 h-4 w-4" />
                  )}
                  Connect
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Box */}
      <div className="rounded-2xl border border-zinc-200 bg-zinc-50/50 p-6 dark:border-zinc-800 dark:bg-zinc-900/50">
        <h3 className="mb-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
          What notifications will I receive?
        </h3>
        <ul className="space-y-2 text-sm text-zinc-500">
          <li className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
            When a new decision is created
          </li>
          <li className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            When a decision is updated (new version)
          </li>
          <li className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            When a decision status changes (approved, deprecated, etc.)
          </li>
          <li className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-red-500" />
            When a decision needs review (tech debt reminder)
          </li>
        </ul>
      </div>
    </div>
  );
}

export default IntegrationsTab;

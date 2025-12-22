"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  Bell,
  Loader2,
  Save,
  AlertCircle,
  Check,
  Mail,
  MessageSquare,
  FileText,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface NotificationSettings {
  email_new_decision: boolean;
  email_decision_updated: boolean;
  email_status_change: boolean;
  email_review_reminder: boolean;
  email_weekly_digest: boolean;
}

const defaultSettings: NotificationSettings = {
  email_new_decision: true,
  email_decision_updated: true,
  email_status_change: true,
  email_review_reminder: true,
  email_weekly_digest: false,
};

export function NotificationsTab() {
  const { getToken } = useAuth();
  const { currentOrganization } = useOrganization();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<NotificationSettings>(defaultSettings);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (currentOrganization?.id) {
      fetchSettings();
    }
  }, [currentOrganization?.id]);

  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  async function fetchSettings() {
    if (!currentOrganization?.id) return;

    try {
      setLoading(true);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/notifications`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Organization-ID": currentOrganization.id,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setSettings({ ...defaultSettings, ...data });
      }
    } catch (err) {
      console.error("Error fetching notification settings:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!currentOrganization?.id) return;

    try {
      setSaving(true);
      setError(null);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/notifications`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "X-Organization-ID": currentOrganization.id,
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error("Failed to save notification settings");
      }

      setSuccess("Notification preferences saved");
    } catch (err) {
      console.error("Error saving settings:", err);
      setError("Failed to save notification settings");
    } finally {
      setSaving(false);
    }
  }

  function toggleSetting(key: keyof NotificationSettings) {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  const notificationOptions = [
    {
      key: "email_new_decision" as const,
      icon: FileText,
      title: "New Decisions",
      description: "Get notified when a new decision is created in your organization",
    },
    {
      key: "email_decision_updated" as const,
      icon: MessageSquare,
      title: "Decision Updates",
      description: "Get notified when a decision you're involved with is updated",
    },
    {
      key: "email_status_change" as const,
      icon: Check,
      title: "Status Changes",
      description: "Get notified when a decision's status changes (approved, deprecated, etc.)",
    },
    {
      key: "email_review_reminder" as const,
      icon: Clock,
      title: "Review Reminders",
      description: "Get reminded when decisions are due for review (tech debt alerts)",
    },
    {
      key: "email_weekly_digest" as const,
      icon: Mail,
      title: "Weekly Digest",
      description: "Receive a weekly summary of all decision activity in your organization",
    },
  ];

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

      {/* Email Notifications */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100 dark:bg-indigo-950/50">
              <Mail className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
            </div>
            <div>
              <CardTitle className="text-lg">Email Notifications</CardTitle>
              <CardDescription>Choose which emails you want to receive</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {notificationOptions.map((option) => {
              const Icon = option.icon;
              return (
                <div
                  key={option.key}
                  className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50"
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-5 w-5 text-zinc-400" />
                    <div>
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">{option.title}</p>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">{option.description}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleSetting(option.key)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      settings[option.key]
                        ? "bg-indigo-600"
                        : "bg-zinc-200 dark:bg-zinc-700"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        settings[option.key] ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              );
            })}
          </div>

          <div className="mt-6 flex justify-end">
            <Button onClick={handleSave} disabled={saving} className="rounded-xl">
              {saving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save Preferences
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Info */}
      <div className="rounded-2xl border border-zinc-200 bg-zinc-50/50 p-6 dark:border-zinc-800 dark:bg-zinc-900/50">
        <h3 className="mb-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
          About Notifications
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Email notifications are sent to your account email address. You can also connect
          Slack or Microsoft Teams in the Integrations tab to receive real-time notifications
          in your team channels.
        </p>
      </div>
    </div>
  );
}

export default NotificationsTab;

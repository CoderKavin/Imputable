"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  Shield,
  Loader2,
  Key,
  Smartphone,
  Monitor,
  AlertCircle,
  Check,
  LogOut,
  Clock,
  MapPin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface Session {
  id: string;
  device: string;
  browser: string;
  location: string;
  ip_address: string;
  last_active: string;
  is_current: boolean;
}

export function SecurityTab() {
  const { getToken, user } = useAuth();
  const { currentOrganization } = useOrganization();

  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [revokingSession, setRevokingSession] = useState<string | null>(null);

  useEffect(() => {
    fetchSecurityData();
  }, []);

  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  async function fetchSecurityData() {
    try {
      if (sessions.length === 0) setLoading(true);
      // For now, we'll show mock session data since Firebase handles auth
      // In a real implementation, you'd track sessions in your database
      setSessions([
        {
          id: "current",
          device: "Desktop",
          browser: getBrowserName(),
          location: "Current Location",
          ip_address: "Your IP",
          last_active: new Date().toISOString(),
          is_current: true,
        },
      ]);
    } catch (err) {
      console.error("Error fetching security data:", err);
    } finally {
      setLoading(false);
    }
  }

  function getBrowserName() {
    const userAgent = navigator.userAgent;
    if (userAgent.includes("Chrome")) return "Chrome";
    if (userAgent.includes("Firefox")) return "Firefox";
    if (userAgent.includes("Safari")) return "Safari";
    if (userAgent.includes("Edge")) return "Edge";
    return "Unknown Browser";
  }

  async function handleRevokeSession(sessionId: string) {
    try {
      setRevokingSession(sessionId);
      // In a real implementation, you'd call an API to revoke the session
      await new Promise((resolve) => setTimeout(resolve, 500));
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setSuccess("Session revoked successfully");
    } catch (err) {
      setError("Failed to revoke session");
    } finally {
      setRevokingSession(null);
    }
  }

  async function handleRevokeAllSessions() {
    try {
      setRevokingSession("all");
      // In a real implementation, you'd call an API to revoke all sessions
      await new Promise((resolve) => setTimeout(resolve, 500));
      setSessions((prev) => prev.filter((s) => s.is_current));
      setSuccess("All other sessions have been revoked");
    } catch (err) {
      setError("Failed to revoke sessions");
    } finally {
      setRevokingSession(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

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

      {/* Account Security */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Account Security</CardTitle>
          <CardDescription>
            Your authentication and login settings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Auth Provider */}
          <div className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white dark:bg-zinc-700">
                <Key className="h-5 w-5 text-zinc-600 dark:text-zinc-300" />
              </div>
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-100">
                  Sign-in Method
                </p>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  {user?.providerData?.[0]?.providerId === "google.com"
                    ? "Google Account"
                    : user?.providerData?.[0]?.providerId === "github.com"
                      ? "GitHub Account"
                      : "Email & Password"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700 dark:bg-green-950/50 dark:text-green-400">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              Active
            </div>
          </div>

          {/* Email */}
          <div className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white dark:bg-zinc-700">
                <Shield className="h-5 w-5 text-zinc-600 dark:text-zinc-300" />
              </div>
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-100">
                  Account Email
                </p>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  {user?.email}
                </p>
              </div>
            </div>
            {user?.emailVerified && (
              <div className="flex items-center gap-2 rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700 dark:bg-green-950/50 dark:text-green-400">
                <Check className="h-3 w-3" />
                Verified
              </div>
            )}
          </div>

          {/* Two-Factor Authentication */}
          <div className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white dark:bg-zinc-700">
                <Smartphone className="h-5 w-5 text-zinc-600 dark:text-zinc-300" />
              </div>
              <div>
                <p className="font-medium text-zinc-900 dark:text-zinc-100">
                  Two-Factor Authentication
                </p>
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Add an extra layer of security to your account
                </p>
              </div>
            </div>
            <Button variant="outline" className="rounded-xl" disabled>
              Coming Soon
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Active Sessions */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg">Active Sessions</CardTitle>
            <CardDescription>
              Devices where you&apos;re currently logged in
            </CardDescription>
          </div>
          {sessions.length > 1 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRevokeAllSessions}
              disabled={revokingSession === "all"}
              className="rounded-xl text-red-600 hover:bg-red-50 hover:text-red-700"
            >
              {revokingSession === "all" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="mr-2 h-4 w-4" />
              )}
              Sign Out All Other Devices
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white dark:bg-zinc-700">
                    <Monitor className="h-5 w-5 text-zinc-600 dark:text-zinc-300" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">
                        {session.browser} on {session.device}
                      </p>
                      {session.is_current && (
                        <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-950/50 dark:text-green-400">
                          Current
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-sm text-zinc-500 dark:text-zinc-400">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" />
                        {session.location}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {session.is_current
                          ? "Active now"
                          : `Last active ${new Date(session.last_active).toLocaleDateString()}`}
                      </span>
                    </div>
                  </div>
                </div>
                {!session.is_current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRevokeSession(session.id)}
                    disabled={revokingSession === session.id}
                    className="text-red-600 hover:bg-red-50 hover:text-red-700"
                  >
                    {revokingSession === session.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <LogOut className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Security Tips */}
      <div className="rounded-2xl border border-zinc-200 bg-zinc-50/50 p-6 dark:border-zinc-800 dark:bg-zinc-900/50">
        <h3 className="mb-3 text-sm font-medium text-zinc-900 dark:text-zinc-100">
          Security Recommendations
        </h3>
        <ul className="space-y-2 text-sm text-zinc-500 dark:text-zinc-400">
          <li className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500" />
            Use a strong, unique password for your account
          </li>
          <li className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500" />
            Enable two-factor authentication when available
          </li>
          <li className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500" />
            Regularly review active sessions and revoke suspicious ones
          </li>
          <li className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500" />
            Keep your recovery email up to date
          </li>
        </ul>
      </div>
    </div>
  );
}

export default SecurityTab;

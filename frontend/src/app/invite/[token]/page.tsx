"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Mail,
  Building2,
  UserPlus,
  LogIn,
  AlertTriangle,
} from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface InviteDetails {
  email: string;
  role: string;
  organization: {
    id: string;
    name: string;
    slug: string;
  };
  invited_by: string;
  expires_at: string;
  created_at: string;
}

export default function InviteAcceptPage() {
  const params = useParams();
  const router = useRouter();
  const { user, loading: authLoading, signInGoogle, getToken } = useAuth();
  const token = params.token as string;

  const [loading, setLoading] = useState(true);
  const [invite, setInvite] = useState<InviteDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);

  // Fetch invite details
  useEffect(() => {
    if (!token) return;

    async function fetchInvite() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE_URL}/invites/${token}`);
        const data = await response.json();

        if (!response.ok) {
          setError(data.error || data.message || "Invalid invitation");
          return;
        }

        setInvite(data);
      } catch (err) {
        console.error("Error fetching invite:", err);
        setError("Failed to load invitation");
      } finally {
        setLoading(false);
      }
    }

    fetchInvite();
  }, [token]);

  // Accept invitation
  const acceptInvite = useCallback(async () => {
    if (!user || !token) return;

    try {
      setAccepting(true);
      setError(null);
      const authToken = await getToken();

      const response = await fetch(`${API_BASE_URL}/invites/${token}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${authToken}`,
          "Content-Type": "application/json",
        },
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || data.message || "Failed to accept invitation");
        return;
      }

      setAccepted(true);

      // Redirect to dashboard after a brief delay
      setTimeout(() => {
        router.push("/dashboard");
      }, 2000);
    } catch (err) {
      console.error("Error accepting invite:", err);
      setError("Failed to accept invitation");
    } finally {
      setAccepting(false);
    }
  }, [user, token, getToken, router]);

  // Auto-accept when user is logged in with matching email
  useEffect(() => {
    if (user && invite && !accepted && !accepting && !error) {
      // Check if email matches
      if (user.email?.toLowerCase() === invite.email.toLowerCase()) {
        acceptInvite();
      }
    }
  }, [user, invite, accepted, accepting, error, acceptInvite]);

  // Loading state
  if (loading || authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500 mx-auto" />
          <p className="mt-4 text-zinc-600 dark:text-zinc-400">
            Loading invitation...
          </p>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !invite) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-900 rounded-2xl shadow-xl p-8 text-center">
          <div className="h-16 w-16 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto">
            <XCircle className="h-8 w-8 text-red-500" />
          </div>
          <h1 className="mt-6 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Invalid Invitation
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">{error}</p>
          <Button className="mt-6 rounded-xl" onClick={() => router.push("/")}>
            Go to Homepage
          </Button>
        </div>
      </div>
    );
  }

  // Success state
  if (accepted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-900 rounded-2xl shadow-xl p-8 text-center">
          <div className="h-16 w-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto">
            <CheckCircle2 className="h-8 w-8 text-green-500" />
          </div>
          <h1 className="mt-6 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Welcome to {invite?.organization.name}!
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            You&apos;ve successfully joined the organization. Redirecting to
            dashboard...
          </p>
          <Loader2 className="h-5 w-5 animate-spin text-indigo-500 mx-auto mt-4" />
        </div>
      </div>
    );
  }

  // Email mismatch state
  if (
    user &&
    invite &&
    user.email?.toLowerCase() !== invite.email.toLowerCase()
  ) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
        <div className="max-w-md w-full bg-white dark:bg-zinc-900 rounded-2xl shadow-xl p-8 text-center">
          <div className="h-16 w-16 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center mx-auto">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
          </div>
          <h1 className="mt-6 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            Email Mismatch
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            This invitation was sent to <strong>{invite.email}</strong>, but
            you&apos;re signed in as <strong>{user.email}</strong>.
          </p>
          <p className="mt-4 text-sm text-zinc-500 dark:text-zinc-400">
            Please sign in with the invited email address to accept.
          </p>
          {error && (
            <div className="mt-4 rounded-lg bg-red-50 dark:bg-red-900/30 px-4 py-2 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Invite details with sign-in prompt
  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <div className="max-w-md w-full bg-white dark:bg-zinc-900 rounded-2xl shadow-xl p-8">
        <div className="text-center">
          <div className="h-16 w-16 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mx-auto">
            <UserPlus className="h-8 w-8 text-indigo-500" />
          </div>
          <h1 className="mt-6 text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            You&apos;re Invited!
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            You&apos;ve been invited to join an organization on Imputable.
          </p>
        </div>

        {invite && (
          <div className="mt-6 space-y-4">
            <div className="rounded-xl bg-zinc-50 dark:bg-zinc-800/50 p-4 space-y-3">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-zinc-400" />
                <div>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Organization
                  </p>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {invite.organization.name}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-zinc-400" />
                <div>
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">
                    Invited email
                  </p>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {invite.email}
                  </p>
                </div>
              </div>
              {invite.invited_by && (
                <div className="flex items-center gap-3">
                  <UserPlus className="h-5 w-5 text-zinc-400" />
                  <div>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">
                      Invited by
                    </p>
                    <p className="font-medium text-zinc-900 dark:text-zinc-100">
                      {invite.invited_by}
                    </p>
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 dark:bg-red-900/30 px-4 py-2 text-sm text-red-700 dark:text-red-300">
                {error}
              </div>
            )}

            {!user ? (
              <div className="space-y-3">
                <p className="text-sm text-center text-zinc-600 dark:text-zinc-400">
                  Sign in with <strong>{invite.email}</strong> to accept this
                  invitation.
                </p>
                <Button className="w-full rounded-xl" onClick={signInGoogle}>
                  <LogIn className="mr-2 h-4 w-4" />
                  Sign in with Google
                </Button>
              </div>
            ) : accepting ? (
              <div className="text-center py-4">
                <Loader2 className="h-6 w-6 animate-spin text-indigo-500 mx-auto" />
                <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                  Joining organization...
                </p>
              </div>
            ) : (
              <Button className="w-full rounded-xl" onClick={acceptInvite}>
                <UserPlus className="mr-2 h-4 w-4" />
                Accept Invitation
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

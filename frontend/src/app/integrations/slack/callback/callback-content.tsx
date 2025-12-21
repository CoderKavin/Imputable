"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle2, XCircle, Slack } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function SlackCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [teamName, setTeamName] = useState("");

  useEffect(() => {
    // Check URL params for success/error indicators
    const error = searchParams.get("error");
    const errorDescription = searchParams.get("error_description");

    if (error) {
      setStatus("error");
      setMessage(errorDescription || `Authorization failed: ${error}`);
      return;
    }

    // If we have a code, the backend should have processed it
    // Check if we were redirected here with success params
    const success = searchParams.get("success");
    const team = searchParams.get("team_name");

    if (success === "true") {
      setStatus("success");
      setTeamName(team || "your workspace");
      setMessage("Slack has been successfully connected!");
    } else {
      // Assume success if no error (backend redirect)
      // Give it a moment then redirect
      setTimeout(() => {
        setStatus("success");
        setMessage("Slack has been successfully connected!");
      }, 1500);
    }
  }, [searchParams]);

  const handleGoToSettings = () => {
    router.push("/settings");
  };

  const handleTryAgain = () => {
    router.push("/settings");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 text-center">
          {/* Slack Logo */}
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-[#4A154B] flex items-center justify-center">
              <Slack className="w-8 h-8 text-white" />
            </div>
          </div>

          {/* Loading State */}
          {status === "loading" && (
            <>
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Connecting to Slack...
              </h1>
              <p className="text-zinc-500 dark:text-zinc-400">
                Please wait while we complete the authorization.
              </p>
            </>
          )}

          {/* Success State */}
          {status === "success" && (
            <>
              <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-950/50 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Successfully Connected!
              </h1>
              <p className="text-zinc-500 dark:text-zinc-400 mb-6">
                {teamName
                  ? `Imputable is now connected to ${teamName}.`
                  : message}
              </p>
              <div className="space-y-3">
                <Button
                  onClick={handleGoToSettings}
                  className="w-full rounded-xl"
                >
                  Go to Settings
                </Button>
                <p className="text-sm text-zinc-400 dark:text-zinc-500">
                  You&apos;ll receive notifications when decisions are created or updated.
                </p>
              </div>
            </>
          )}

          {/* Error State */}
          {status === "error" && (
            <>
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-950/50 flex items-center justify-center mx-auto mb-4">
                <XCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
              </div>
              <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Connection Failed
              </h1>
              <p className="text-zinc-500 dark:text-zinc-400 mb-6">
                {message || "Something went wrong while connecting to Slack."}
              </p>
              <div className="space-y-3">
                <Button
                  onClick={handleTryAgain}
                  className="w-full rounded-xl"
                >
                  Try Again
                </Button>
                <Button
                  variant="outline"
                  onClick={() => router.push("/dashboard")}
                  className="w-full rounded-xl"
                >
                  Go to Dashboard
                </Button>
              </div>
            </>
          )}
        </div>

        {/* Help Text */}
        <p className="text-center text-sm text-zinc-400 dark:text-zinc-500 mt-4">
          Having trouble?{" "}
          <a
            href="mailto:support@imputable.io"
            className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400"
          >
            Contact support
          </a>
        </p>
      </div>
    </div>
  );
}

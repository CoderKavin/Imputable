import { Suspense } from "react";
import { Loader2, Slack } from "lucide-react";
import SlackCallbackContent from "./callback-content";

/**
 * Slack OAuth Callback Page
 *
 * This page handles the redirect from Slack after OAuth authorization.
 * The actual token exchange happens on the backend - this page just shows
 * the result to the user.
 */
export default function SlackCallbackPage() {
  return (
    <Suspense fallback={<SlackCallbackLoading />}>
      <SlackCallbackContent />
    </Suspense>
  );
}

function SlackCallbackLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-200 dark:border-zinc-800 p-8 text-center">
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-[#4A154B] flex items-center justify-center">
              <Slack className="w-8 h-8 text-white" />
            </div>
          </div>
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
            Connecting to Slack...
          </h1>
          <p className="text-zinc-500 dark:text-zinc-400">
            Please wait while we complete the authorization.
          </p>
        </div>
      </div>
    </div>
  );
}

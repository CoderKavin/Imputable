"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginRedirect() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const returnUrl = searchParams.get("returnUrl");
    if (returnUrl) {
      router.replace(`/sign-in?returnUrl=${encodeURIComponent(returnUrl)}`);
    } else {
      router.replace("/sign-in");
    }
  }, [router, searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-500">Redirecting to sign in...</p>
      </div>
    </div>
  );
}

/**
 * Legacy login page - redirects to the new Firebase sign-in page.
 */
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-500">Loading...</p>
          </div>
        </div>
      }
    >
      <LoginRedirect />
    </Suspense>
  );
}

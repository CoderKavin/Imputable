"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Legacy login page - redirects to the new Firebase sign-in page.
 */
export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/sign-in");
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-500">Redirecting to sign in...</p>
      </div>
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api-client";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Check if authenticated
    if (api.isAuthenticated()) {
      router.push("/decisions");
    } else {
      router.push("/login");
    }
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-gray-500">Loading...</div>
    </div>
  );
}

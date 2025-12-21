"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, DevUser } from "@/lib/api-client";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<DevUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState<string | null>(null);

  useEffect(() => {
    // Check if already logged in
    if (api.isAuthenticated()) {
      router.push("/decisions");
      return;
    }

    // Fetch available dev users
    const fetchUsers = async () => {
      try {
        const devUsers = await api.getDevUsers();
        setUsers(devUsers);
      } catch (err) {
        setError("Failed to load users. Is the backend running?");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, [router]);

  const handleLogin = async (user: DevUser) => {
    setLoggingIn(user.id);
    setError(null);

    try {
      const orgId = user.organizations[0]?.id;
      await api.devLogin({
        email: user.email,
        organization_id: orgId,
      });
      router.push("/decisions");
    } catch (err) {
      setError("Login failed. Please try again.");
      console.error(err);
    } finally {
      setLoggingIn(null);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50/50 p-6">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-indigo-500/20">
            <span className="text-white font-bold text-xl">IM</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Imputable</h1>
          <p className="text-gray-500 mt-1">
            Select a user to log in (Development Mode)
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl border border-gray-100 shadow-sm p-8">
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-2xl text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="py-8 text-center">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">
                Loading available users...
              </p>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              <p>No users found.</p>
              <p className="text-sm mt-1">Please seed the database first.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {users.map((user) => (
                <button
                  key={user.id}
                  onClick={() => handleLogin(user)}
                  disabled={loggingIn !== null}
                  className="w-full p-4 text-left bg-gray-50 border border-gray-100 rounded-2xl hover:bg-gray-100 hover:border-gray-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {/* Avatar */}
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white font-medium text-sm">
                        {user.name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")
                          .slice(0, 2)}
                      </div>
                      <div>
                        <div className="font-medium text-gray-900 group-hover:text-indigo-600 transition-colors">
                          {user.name}
                        </div>
                        <div className="text-sm text-gray-500">
                          {user.email}
                        </div>
                        {user.organizations.length > 0 && (
                          <div className="text-xs text-gray-400 mt-0.5">
                            {user.organizations.map((o) => o.name).join(", ")}
                          </div>
                        )}
                      </div>
                    </div>
                    {loggingIn === user.id ? (
                      <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
                    ) : (
                      <svg
                        className="w-5 h-5 text-gray-300 group-hover:text-indigo-500 group-hover:translate-x-1 transition-all"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-400 mt-6">
          Development mode only. Use Clerk authentication in production.
        </p>
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, DevUser } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">Imputable</CardTitle>
          <CardDescription>
            Select a user to log in (Development Mode)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-sm">
              {error}
            </div>
          )}

          {users.length === 0 ? (
            <div className="text-center text-gray-500 py-4">
              No users found. Please seed the database first.
            </div>
          ) : (
            <div className="space-y-2">
              {users.map((user) => (
                <button
                  key={user.id}
                  onClick={() => handleLogin(user)}
                  disabled={loggingIn !== null}
                  className="w-full p-3 text-left border rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{user.name}</div>
                      <div className="text-sm text-gray-500">{user.email}</div>
                      {user.organizations.length > 0 && (
                        <div className="text-xs text-gray-400 mt-1">
                          {user.organizations.map(o => o.name).join(", ")}
                        </div>
                      )}
                    </div>
                    {loggingIn === user.id && (
                      <div className="text-sm text-gray-400">Logging in...</div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

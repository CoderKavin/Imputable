"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { UserMenu } from "@/components/auth/UserMenu";
import { OrganizationSwitcher } from "@/components/auth/OrganizationSwitcher";

/**
 * Main Navigation Bar
 *
 * Displays different content based on authentication state:
 * - Logged Out: Shows "Sign In" and "Get Started" buttons
 * - Logged In: Shows OrganizationSwitcher and UserMenu
 *
 * The OrganizationSwitcher is crucial for B2B multi-tenancy:
 * - Allows users to switch between organizations
 * - Allows users to create new organizations
 * - Shows the current organization context
 */
export function Navbar() {
  const { user, loading } = useAuth();

  return (
    <header className="bg-white border-b sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          {/* Logo / Brand */}
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">IM</span>
              </div>
              <span className="font-bold text-xl text-gray-900">Imputable</span>
            </Link>

            {/* Navigation Links - Only show when signed in */}
            {user && (
              <nav className="hidden md:flex items-center gap-6">
                <Link
                  href="/dashboard"
                  className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Dashboard
                </Link>
                <Link
                  href="/decisions"
                  className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Decisions
                </Link>
                <Link
                  href="/audit"
                  className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Audit Log
                </Link>
              </nav>
            )}
          </div>

          {/* Right Side - Auth Controls */}
          <div className="flex items-center gap-4">
            {loading ? (
              // Loading state
              <div className="h-9 w-20 bg-gray-200 rounded animate-pulse" />
            ) : !user ? (
              // Signed Out State
              <>
                <Link href="/sign-in">
                  <Button variant="outline" size="sm">
                    Sign In
                  </Button>
                </Link>
                <Link href="/sign-up">
                  <Button size="sm">Get Started</Button>
                </Link>
              </>
            ) : (
              // Signed In State
              <>
                {/* Organization Switcher - Critical for B2B */}
                <OrganizationSwitcher />

                {/* User Menu with dropdown */}
                <UserMenu />
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

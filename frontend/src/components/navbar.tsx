"use client";

import Link from "next/link";
import {
  SignInButton,
  SignedIn,
  SignedOut,
  UserButton,
  OrganizationSwitcher,
} from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

/**
 * Main Navigation Bar
 *
 * Displays different content based on authentication state:
 * - Logged Out: Shows "Sign In" button
 * - Logged In: Shows OrganizationSwitcher and UserButton
 *
 * The OrganizationSwitcher is crucial for B2B multi-tenancy:
 * - Allows users to switch between organizations
 * - Allows users to create new organizations
 * - Shows the current organization context
 */
export function Navbar() {
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
            <SignedIn>
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
            </SignedIn>
          </div>

          {/* Right Side - Auth Controls */}
          <div className="flex items-center gap-4">
            {/* Signed Out State */}
            <SignedOut>
              <SignInButton mode="modal">
                <Button variant="outline" size="sm">
                  Sign In
                </Button>
              </SignInButton>
              <Link href="/sign-up">
                <Button size="sm">Get Started</Button>
              </Link>
            </SignedOut>

            {/* Signed In State */}
            <SignedIn>
              {/* Organization Switcher - Critical for B2B */}
              <OrganizationSwitcher
                hidePersonal={false}
                afterCreateOrganizationUrl="/dashboard"
                afterLeaveOrganizationUrl="/"
                afterSelectOrganizationUrl="/dashboard"
                appearance={{
                  elements: {
                    rootBox: "flex items-center",
                    organizationSwitcherTrigger:
                      "px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors",
                    organizationPreviewMainIdentifier: "font-medium text-sm",
                    organizationSwitcherTriggerIcon: "text-gray-500",
                  },
                }}
                createOrganizationMode="modal"
                organizationProfileMode="modal"
              />

              {/* User Button with dropdown menu */}
              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: {
                    avatarBox: "w-9 h-9",
                    userButtonPopoverCard: "shadow-lg",
                    userButtonPopoverActionButton: "text-sm",
                  },
                }}
                userProfileMode="modal"
              />
            </SignedIn>
          </div>
        </div>
      </div>
    </header>
  );
}

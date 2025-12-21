"use client";

import { ReactNode } from "react";
import {
  SignedIn,
  UserButton,
  OrganizationSwitcher,
} from "@clerk/nextjs";
import { Bell, Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface AppHeaderProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function AppHeader({ title, subtitle, actions }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-30 bg-gray-50/80 backdrop-blur-xl border-b border-gray-200/50">
      <div className="px-8 py-4">
        <div className="flex items-center justify-between">
          {/* Left: Page Title */}
          <div>
            {title && (
              <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
            )}
            {subtitle && (
              <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>
            )}
          </div>

          {/* Right: Actions + User Controls */}
          <div className="flex items-center gap-4">
            {/* Search */}
            <div className="relative hidden md:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search decisions..."
                className={cn(
                  "w-64 pl-10 pr-4 py-2 rounded-2xl border border-gray-200 bg-white text-sm",
                  "placeholder:text-gray-400",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300",
                  "transition-all duration-200"
                )}
              />
              <kbd className="absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 text-[10px] font-mono text-gray-400 bg-gray-100 rounded">
                ⌘K
              </kbd>
            </div>

            {/* Page Actions */}
            {actions}

            {/* Notifications */}
            <button className="relative p-2 rounded-xl hover:bg-gray-100 transition-colors">
              <Bell className="w-5 h-5 text-gray-500" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
            </button>

            {/* Divider */}
            <div className="w-px h-8 bg-gray-200" />

            {/* Clerk Controls */}
            <SignedIn>
              <OrganizationSwitcher
                hidePersonal={false}
                afterCreateOrganizationUrl="/dashboard"
                afterLeaveOrganizationUrl="/"
                afterSelectOrganizationUrl="/dashboard"
                appearance={{
                  elements: {
                    rootBox: "flex items-center",
                    organizationSwitcherTrigger: cn(
                      "px-3 py-2 rounded-xl border border-gray-200 bg-white",
                      "hover:bg-gray-50 transition-colors",
                      "focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    ),
                    organizationPreviewMainIdentifier: "font-medium text-sm text-gray-900",
                    organizationSwitcherTriggerIcon: "text-gray-500",
                  },
                }}
                createOrganizationMode="modal"
                organizationProfileMode="modal"
              />

              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: {
                    avatarBox: "w-9 h-9 rounded-xl",
                    userButtonPopoverCard: "shadow-xl rounded-2xl",
                    userButtonPopoverActionButton: "text-sm rounded-xl",
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

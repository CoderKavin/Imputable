"use client";

import { ReactNode } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { SearchCommand } from "./search-command";
import { NotificationsDropdown } from "./notifications-dropdown";
import { UserMenu } from "@/components/auth/UserMenu";
import { OrganizationSwitcher } from "@/components/auth/OrganizationSwitcher";

interface AppHeaderProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function AppHeader({ title, subtitle, actions }: AppHeaderProps) {
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-[102] bg-gray-50 border-b border-gray-200">
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
            {/* Search Command */}
            <div className="hidden md:block">
              <SearchCommand />
            </div>

            {/* Page Actions */}
            {actions}

            {/* Notifications */}
            <NotificationsDropdown />

            {/* Divider */}
            <div className="w-px h-8 bg-gray-200" />

            {/* Auth Controls */}
            {user && (
              <>
                <OrganizationSwitcher />
                <UserMenu />
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}

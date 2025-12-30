"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  LayoutDashboard,
  FileText,
  ClipboardList,
  Settings,
  HelpCircle,
  Sparkles,
  Crown,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: <LayoutDashboard className="w-5 h-5" />,
  },
  {
    href: "/decisions",
    label: "Decisions",
    icon: <FileText className="w-5 h-5" />,
  },
  {
    href: "/audit",
    label: "Audit Log",
    icon: <ClipboardList className="w-5 h-5" />,
  },
];

const bottomItems: NavItem[] = [
  {
    href: "/settings",
    label: "Settings",
    icon: <Settings className="w-5 h-5" />,
  },
  {
    href: "/help",
    label: "Help",
    icon: <HelpCircle className="w-5 h-5" />,
  },
];

export function FloatingSidebar() {
  const pathname = usePathname();
  const { currentOrganization } = useOrganization();

  // Check if user is on a paid plan
  const isPaidPlan =
    currentOrganization?.subscription_tier === "professional" ||
    currentOrganization?.subscription_tier === "enterprise" ||
    currentOrganization?.subscription_tier === "starter";

  return (
    <aside className="fixed left-4 top-4 bottom-4 w-64 z-40">
      {/* Floating Card Container */}
      <div className="h-full bg-white rounded-3xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
        {/* Logo Section */}
        <div className="p-6 pb-4">
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <Image
              src="/icon.png"
              alt="Imputable"
              width={36}
              height={36}
              className="w-9 h-9 object-contain group-hover:scale-105 transition-transform"
            />
            <div>
              <span className="font-semibold text-gray-900 text-lg">
                Imputable
              </span>
              <span className="block text-xs text-gray-400">
                Decision Ledger
              </span>
            </div>
          </Link>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 px-3 py-2">
          <div className="space-y-1">
            {navItems.map((item) => {
              const isActive =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-gray-900 text-white shadow-lg shadow-gray-900/10"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
                  )}
                >
                  <span
                    className={cn(
                      "transition-colors",
                      isActive
                        ? "text-white"
                        : "text-gray-400 group-hover:text-gray-600",
                    )}
                  >
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Upgrade Banner - only show for free tier */}
          {!isPaidPlan && (
            <div className="mt-6 mx-1">
              <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl p-4 border border-indigo-100">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-indigo-500" />
                  <span className="text-sm font-semibold text-gray-900">
                    Upgrade to Pro
                  </span>
                </div>
                <p className="text-xs text-gray-500 mb-3">
                  Get unlimited decisions and advanced analytics.
                </p>
                <Link
                  href="/settings?tab=billing"
                  className="block w-full py-2 px-3 bg-gray-900 text-white text-xs font-medium rounded-xl hover:bg-gray-800 transition-colors text-center"
                >
                  View Plans
                </Link>
              </div>
            </div>
          )}

          {/* Pro Badge - show for paid users */}
          {isPaidPlan && (
            <div className="mt-6 mx-1">
              <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-2xl p-4 border border-emerald-100">
                <div className="flex items-center gap-2">
                  <Crown className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-semibold text-gray-900">
                    {currentOrganization?.subscription_tier === "enterprise"
                      ? "Enterprise"
                      : "Pro"}{" "}
                    Plan
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  You have access to all features.
                </p>
              </div>
            </div>
          )}
        </nav>

        {/* Bottom Navigation */}
        <div className="px-3 py-4 border-t border-gray-100">
          <div className="space-y-1">
            {bottomItems.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-gray-100 text-gray-900"
                      : "text-gray-500 hover:bg-gray-50 hover:text-gray-700",
                  )}
                >
                  <span className="text-gray-400">{item.icon}</span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}

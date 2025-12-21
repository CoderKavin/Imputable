"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  FileText,
  ClipboardList,
  Settings,
  HelpCircle,
  Sparkles,
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

  return (
    <aside className="fixed left-4 top-4 bottom-4 w-64 z-40">
      {/* Floating Card Container */}
      <div className="h-full bg-white rounded-3xl border border-gray-200 shadow-sm flex flex-col overflow-hidden">
        {/* Logo Section */}
        <div className="p-6 pb-4">
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-shadow">
              <span className="text-white font-bold text-sm">IM</span>
            </div>
            <div>
              <span className="font-semibold text-gray-900 text-lg">Imputable</span>
              <span className="block text-xs text-gray-400">Decision Ledger</span>
            </div>
          </Link>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 px-3 py-2">
          <div className="space-y-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-gray-900 text-white shadow-lg shadow-gray-900/10"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  )}
                >
                  <span className={cn(
                    "transition-colors",
                    isActive ? "text-white" : "text-gray-400 group-hover:text-gray-600"
                  )}>
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </div>

          {/* Upgrade Banner */}
          <div className="mt-6 mx-1">
            <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl p-4 border border-indigo-100">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-indigo-500" />
                <span className="text-sm font-semibold text-gray-900">Upgrade to Pro</span>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                Get unlimited decisions and advanced analytics.
              </p>
              <button className="w-full py-2 px-3 bg-gray-900 text-white text-xs font-medium rounded-xl hover:bg-gray-800 transition-colors">
                View Plans
              </button>
            </div>
          </div>
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
                      : "text-gray-500 hover:bg-gray-50 hover:text-gray-700"
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

"use client";

import { ReactNode } from "react";
import { FloatingSidebar } from "./floating-sidebar";
import { AppHeader } from "./app-header";

interface AppLayoutProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function AppLayout({ children, title, subtitle, actions }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50/50">
      {/* Floating Sidebar */}
      <FloatingSidebar />

      {/* Main Content Area - offset by sidebar width + margins */}
      <div className="ml-72 min-h-screen">
        {/* App Header */}
        <AppHeader title={title} subtitle={subtitle} actions={actions} />

        {/* Page Content */}
        <main className="p-8">
          {children}
        </main>
      </div>
    </div>
  );
}

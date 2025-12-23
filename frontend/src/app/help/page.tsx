"use client";

/**
 * Help Center Page
 *
 * Route: /help
 * Help documentation and support resources
 */

import { AppLayout } from "@/components/app";
import {
  Book,
  FileText,
  MessageCircle,
  ExternalLink,
  ChevronRight,
  Keyboard,
  Zap,
  Shield,
  Users,
  GitBranch,
  Clock,
} from "lucide-react";
import Link from "next/link";

export default function HelpPage() {
  return (
    <AppLayout
      title="Help Center"
      subtitle="Learn how to use Imputable effectively"
    >
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Quick Links */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <QuickLink
            icon={Book}
            title="Documentation"
            description="Full product documentation"
            href="/docs"
          />
          <QuickLink
            icon={MessageCircle}
            title="Contact Support"
            description="Get help from our team"
            href="mailto:support@imputable.io"
            external
          />
        </div>

        {/* Getting Started */}
        <Section title="Getting Started" icon={Zap}>
          <div className="space-y-3">
            <HelpArticle
              title="Creating your first decision"
              description="Learn how to document engineering decisions using the ADR format"
            />
            <HelpArticle
              title="Inviting team members"
              description="Add colleagues to your organization and set permissions"
            />
            <HelpArticle
              title="Setting up Slack integration"
              description="Connect Imputable to your Slack workspace for notifications"
            />
            <HelpArticle
              title="Understanding decision statuses"
              description="Learn about Draft, Pending Review, Approved, and Deprecated states"
            />
          </div>
        </Section>

        {/* Core Features */}
        <Section title="Core Features" icon={FileText}>
          <div className="space-y-3">
            <HelpArticle
              title="Decision versioning"
              description="How immutable versioning works and why it matters"
            />
            <HelpArticle
              title="Approval workflows"
              description="Configure required reviewers and approval processes"
            />
            <HelpArticle
              title="Decision relationships"
              description="Link related decisions with supersedes, blocks, and related-to"
            />
            <HelpArticle
              title="Tags and filtering"
              description="Organize decisions with tags and use advanced filters"
            />
          </div>
        </Section>

        {/* Team & Permissions */}
        <Section title="Team & Permissions" icon={Users}>
          <div className="space-y-3">
            <HelpArticle
              title="User roles explained"
              description="Owner, Admin, and Member role capabilities"
            />
            <HelpArticle
              title="Team-based ownership"
              description="Assign decisions to teams for better organization"
            />
            <HelpArticle
              title="Audit log access"
              description="Who can view audit logs and compliance reports"
            />
          </div>
        </Section>

        {/* Tech Debt & Risk */}
        <Section title="Tech Debt Management" icon={Clock}>
          <div className="space-y-3">
            <HelpArticle
              title="Review dates and expiration"
              description="Set review dates to track decision freshness"
            />
            <HelpArticle
              title="Risk dashboard"
              description="Monitor at-risk and expired decisions (Pro feature)"
            />
            <HelpArticle
              title="Snoozing decisions"
              description="How to extend review dates with accountability"
            />
          </div>
        </Section>

        {/* Integrations */}
        <Section title="Integrations" icon={GitBranch}>
          <div className="space-y-3">
            <HelpArticle
              title="Slack integration setup"
              description="Connect to Slack for notifications and slash commands"
            />
            <HelpArticle
              title="Using Slack commands"
              description="/imputable search, create, and lookup commands"
            />
            <HelpArticle
              title="API access"
              description="Use the REST API for custom integrations"
            />
          </div>
        </Section>

        {/* Security */}
        <Section title="Security & Compliance" icon={Shield}>
          <div className="space-y-3">
            <HelpArticle
              title="Data security"
              description="How we protect your decision data"
            />
            <HelpArticle
              title="SOC2 compliance"
              description="Export audit logs for compliance requirements"
            />
            <HelpArticle
              title="SSO setup"
              description="Configure Single Sign-On for your organization"
            />
          </div>
        </Section>

        {/* Keyboard Shortcuts */}
        <Section title="Keyboard Shortcuts" icon={Keyboard}>
          <div className="bg-gray-50 rounded-2xl p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Shortcut keys={["Cmd", "K"]} description="Open search" />
              <Shortcut keys={["Cmd", "N"]} description="New decision" />
              <Shortcut keys={["Esc"]} description="Close modal" />
              <Shortcut keys={["?"]} description="Show shortcuts" />
            </div>
          </div>
        </Section>

        {/* Contact */}
        <div className="bg-indigo-50 rounded-3xl p-8 text-center">
          <h3 className="text-xl font-semibold text-gray-900 mb-2">
            Still need help?
          </h3>
          <p className="text-gray-600 mb-6">
            Our support team is here to help you succeed.
          </p>
          <div className="flex items-center justify-center gap-4">
            <a
              href="mailto:support@imputable.io"
              className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-medium hover:bg-indigo-700 transition-colors"
            >
              <MessageCircle className="w-4 h-4" />
              Contact Support
            </a>
            <a
              href="https://github.com/CoderKavin/Imputable/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 bg-white text-gray-700 rounded-xl font-medium border border-gray-200 hover:bg-gray-50 transition-colors"
            >
              Report an Issue
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function QuickLink({
  icon: Icon,
  title,
  description,
  href,
  external,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  href: string;
  external?: boolean;
}) {
  const content = (
    <div className="flex items-center gap-4 p-4 bg-white rounded-2xl border border-gray-200 hover:border-indigo-300 hover:shadow-sm transition-all cursor-pointer">
      <div className="w-12 h-12 rounded-xl bg-indigo-50 flex items-center justify-center">
        <Icon className="w-6 h-6 text-indigo-600" />
      </div>
      <div className="flex-1">
        <h3 className="font-semibold text-gray-900">{title}</h3>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      {external ? (
        <ExternalLink className="w-4 h-4 text-gray-400" />
      ) : (
        <ChevronRight className="w-4 h-4 text-gray-400" />
      )}
    </div>
  );

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {content}
      </a>
    );
  }

  return <Link href={href}>{content}</Link>;
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-3xl border border-gray-200 overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-100">
        <Icon className="w-5 h-5 text-indigo-600" />
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

function HelpArticle({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="p-4 rounded-xl bg-gray-50/50">
      <h4 className="font-medium text-gray-900">{title}</h4>
      <p className="text-sm text-gray-500 mt-1">{description}</p>
    </div>
  );
}

function Shortcut({
  keys,
  description,
}: {
  keys: string[];
  description: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-600">{description}</span>
      <div className="flex items-center gap-1">
        {keys.map((key, i) => (
          <span key={i}>
            <kbd className="px-2 py-1 bg-white border border-gray-200 rounded-lg text-xs font-mono text-gray-700">
              {key}
            </kbd>
            {i < keys.length - 1 && (
              <span className="mx-1 text-gray-400">+</span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}

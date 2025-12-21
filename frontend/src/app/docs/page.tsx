import { Metadata } from "next";
import Link from "next/link";
import { LandingNavbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import {
  BookOpen,
  Rocket,
  Code2,
  Webhook,
  Shield,
  HelpCircle,
  FileText,
  Users,
  Zap,
  ArrowRight,
  ExternalLink,
  Terminal,
  Slack,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Documentation | Imputable - The Decision Ledger",
  description:
    "Learn how to use Imputable to document, track, and audit your engineering decisions.",
};

const quickStartSteps = [
  {
    step: 1,
    title: "Create an account",
    description: "Sign up for free and create your organization.",
  },
  {
    step: 2,
    title: "Invite your team",
    description: "Add team members and assign roles.",
  },
  {
    step: 3,
    title: "Document your first decision",
    description: "Create a decision with context, choice, and rationale.",
  },
  {
    step: 4,
    title: "Set up integrations",
    description: "Connect Slack or Teams for notifications.",
  },
];

const docCategories = [
  {
    icon: Rocket,
    title: "Getting Started",
    description: "Learn the basics and get up and running in minutes.",
    links: [
      { title: "Quick Start Guide", href: "#quick-start" },
      { title: "Core Concepts", href: "#concepts" },
      { title: "Creating Your First Decision", href: "#first-decision" },
    ],
    gradient: "from-cyan-500 to-blue-600",
  },
  {
    icon: FileText,
    title: "Decision Management",
    description: "Everything about creating, editing, and organizing decisions.",
    links: [
      { title: "Decision Structure", href: "#structure" },
      { title: "Version History", href: "#versions" },
      { title: "Supersession & Lineage", href: "#supersession" },
      { title: "Tags & Search", href: "#search" },
    ],
    gradient: "from-purple-500 to-pink-600",
  },
  {
    icon: Users,
    title: "Team Collaboration",
    description: "Working with your team on decisions.",
    links: [
      { title: "Roles & Permissions", href: "#roles" },
      { title: "Approval Workflows", href: "#approvals" },
      { title: "Team Assignment", href: "#teams" },
    ],
    gradient: "from-green-500 to-emerald-600",
  },
  {
    icon: Webhook,
    title: "Integrations",
    description: "Connect Imputable to your existing tools.",
    links: [
      { title: "Slack Integration", href: "#slack" },
      { title: "Microsoft Teams", href: "#teams-integration" },
      { title: "Webhooks", href: "#webhooks" },
    ],
    gradient: "from-orange-500 to-red-600",
  },
  {
    icon: Code2,
    title: "API Reference",
    description: "Build custom integrations with our REST API.",
    links: [
      { title: "Authentication", href: "#auth" },
      { title: "Decisions API", href: "#decisions-api" },
      { title: "Audit API", href: "#audit-api" },
      { title: "Rate Limits", href: "#rate-limits" },
    ],
    gradient: "from-indigo-500 to-purple-600",
  },
  {
    icon: Shield,
    title: "Security & Compliance",
    description: "How we keep your data safe and compliant.",
    links: [
      { title: "Data Encryption", href: "#encryption" },
      { title: "Audit Exports", href: "#exports" },
      { title: "SOC 2 Compliance", href: "#soc2" },
      { title: "SSO Configuration", href: "#sso" },
    ],
    gradient: "from-slate-500 to-zinc-600",
  },
];

const slackCommands = [
  {
    command: "/decisions",
    description: "Open the main menu",
  },
  {
    command: "/decisions add <title>",
    description: "Create a new decision with the given title",
  },
  {
    command: "/decisions list",
    description: "View your 10 most recent decisions",
  },
  {
    command: "/decisions help",
    description: "Show all available commands",
  },
];

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-20 right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/4 left-1/4 w-80 h-80 bg-purple-500/10 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10">
        <LandingNavbar />

        {/* Hero Section */}
        <section className="pt-32 pb-16 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-gray-400 mb-8">
              <BookOpen className="w-4 h-4 text-cyan-400" />
              Documentation
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
              Learn Imputable
            </h1>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10">
              Everything you need to know about documenting and managing your
              engineering decisions.
            </p>

            {/* Search Bar */}
            <div className="max-w-xl mx-auto">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search documentation..."
                  className="w-full px-6 py-4 rounded-2xl bg-white/5 border border-white/10 text-white placeholder:text-gray-500 focus:outline-none focus:border-white/30 transition-colors"
                />
                <kbd className="absolute right-4 top-1/2 -translate-y-1/2 px-2 py-1 rounded bg-white/10 text-xs text-gray-500">
                  ⌘K
                </kbd>
              </div>
            </div>
          </div>
        </section>

        {/* Quick Start */}
        <section className="py-16 px-6" id="quick-start">
          <div className="max-w-5xl mx-auto">
            <h2 className="text-2xl font-bold mb-8 flex items-center gap-3">
              <Rocket className="w-6 h-6 text-cyan-400" />
              Quick Start
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {quickStartSteps.map((step) => (
                <div
                  key={step.step}
                  className="p-6 rounded-2xl bg-white/[0.02] border border-white/10"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center text-sm font-bold mb-4">
                    {step.step}
                  </div>
                  <h3 className="font-semibold mb-2">{step.title}</h3>
                  <p className="text-sm text-gray-500">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Doc Categories */}
        <section className="py-16 px-6">
          <div className="max-w-5xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {docCategories.map((category) => (
                <div
                  key={category.title}
                  className="p-6 rounded-2xl bg-white/[0.02] border border-white/10 hover:border-white/20 transition-colors"
                >
                  <div
                    className={`w-12 h-12 rounded-xl bg-gradient-to-br ${category.gradient} flex items-center justify-center mb-4`}
                  >
                    <category.icon className="w-6 h-6 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">
                    {category.title}
                  </h3>
                  <p className="text-sm text-gray-500 mb-4">
                    {category.description}
                  </p>
                  <ul className="space-y-2">
                    {category.links.map((link) => (
                      <li key={link.title}>
                        <a
                          href={link.href}
                          className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-2"
                        >
                          <ArrowRight className="w-3 h-3" />
                          {link.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Slack Commands Reference */}
        <section className="py-16 px-6" id="slack">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold mb-8 flex items-center gap-3">
              <Slack className="w-6 h-6 text-[#4A154B]" />
              Slack Commands
            </h2>
            <div className="rounded-2xl bg-white/[0.02] border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10 bg-white/[0.02]">
                <p className="text-sm text-gray-400">
                  After connecting Slack, use these commands in any channel:
                </p>
              </div>
              <div className="divide-y divide-white/10">
                {slackCommands.map((cmd) => (
                  <div
                    key={cmd.command}
                    className="p-4 flex items-start gap-4"
                  >
                    <code className="px-3 py-1 rounded-lg bg-zinc-900 text-cyan-400 text-sm font-mono whitespace-nowrap">
                      {cmd.command}
                    </code>
                    <span className="text-gray-400 text-sm">
                      {cmd.description}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* API Example */}
        <section className="py-16 px-6" id="decisions-api">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-2xl font-bold mb-8 flex items-center gap-3">
              <Terminal className="w-6 h-6 text-green-400" />
              API Example
            </h2>
            <div className="rounded-2xl bg-zinc-900 border border-white/10 overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-white/[0.02]">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-xs text-gray-500 ml-2">
                  Create a decision
                </span>
              </div>
              <pre className="p-6 text-sm overflow-x-auto">
                <code className="text-gray-300">
{`curl -X POST https://api.imputable.io/v1/decisions \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "title": "Use PostgreSQL for analytics",
    "content": {
      "context": "We need a database for our analytics service.",
      "choice": "PostgreSQL with TimescaleDB extension.",
      "rationale": "Best performance for time-series data.",
      "alternatives": [
        {
          "name": "ClickHouse",
          "rejected_reason": "Operational complexity"
        }
      ]
    },
    "impact_level": "high",
    "tags": ["backend", "database", "analytics"]
  }'`}
                </code>
              </pre>
            </div>
          </div>
        </section>

        {/* Help CTA */}
        <section className="py-16 px-6">
          <div className="max-w-4xl mx-auto">
            <div className="p-10 rounded-3xl bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10 text-center">
              <HelpCircle className="w-12 h-12 text-cyan-400 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-4">Need help?</h2>
              <p className="text-gray-400 mb-8 max-w-xl mx-auto">
                Can&apos;t find what you&apos;re looking for? Our team is here
                to help.
              </p>
              <div className="flex items-center justify-center gap-4 flex-wrap">
                <a
                  href="mailto:support@imputable.io"
                  className="px-6 py-3 rounded-xl bg-white text-black font-semibold hover:bg-gray-100 transition-colors"
                >
                  Contact Support
                </a>
                <a
                  href="https://github.com/imputable/imputable"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 rounded-xl bg-white/10 text-white font-semibold hover:bg-white/20 transition-colors inline-flex items-center gap-2"
                >
                  GitHub
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </section>

        <Footer />
      </div>
    </div>
  );
}

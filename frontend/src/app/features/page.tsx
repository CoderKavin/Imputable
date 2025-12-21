import { Metadata } from "next";
import Link from "next/link";
import { LandingNavbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import {
  FileText,
  History,
  Shield,
  GitCompare,
  Bell,
  BarChart3,
  Users,
  Lock,
  Zap,
  Clock,
  Search,
  FileCheck,
  ArrowRight,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Features | Imputable - The Decision Ledger",
  description:
    "Explore all the features that make Imputable the best platform for documenting and tracking engineering decisions.",
};

const features = [
  {
    icon: FileText,
    title: "Immutable Decision Records",
    description:
      "Every decision is stored as an immutable record. No overwrites, no silent changes. Full accountability for every choice made.",
    gradient: "from-cyan-500 to-blue-600",
  },
  {
    icon: History,
    title: "Complete Version History",
    description:
      "Time-travel through every version of a decision. See exactly what changed, when, and by whom. Compare any two versions side-by-side.",
    gradient: "from-purple-500 to-pink-600",
  },
  {
    icon: Shield,
    title: "Cryptographic Audit Trail",
    description:
      "Every action is logged with cryptographic hashing. Tamper-proof records that satisfy the strictest compliance requirements.",
    gradient: "from-green-500 to-emerald-600",
  },
  {
    icon: GitCompare,
    title: "Visual Diff Viewer",
    description:
      "See exactly what changed between versions with our beautiful diff viewer. Highlights additions, removals, and modifications.",
    gradient: "from-orange-500 to-red-600",
  },
  {
    icon: Bell,
    title: "Slack & Teams Integration",
    description:
      "Get notified in Slack or Microsoft Teams when decisions are created, updated, or need review. Create decisions directly from Slack.",
    gradient: "from-indigo-500 to-purple-600",
  },
  {
    icon: BarChart3,
    title: "Risk Dashboard",
    description:
      "Executive view of tech debt. See expiring decisions, at-risk items, and team health scores at a glance. The Debt Wall calendar.",
    gradient: "from-pink-500 to-rose-600",
  },
  {
    icon: Users,
    title: "Team Collaboration",
    description:
      "Assign decisions to teams, require approvals from stakeholders, and track who's responsible for what across your organization.",
    gradient: "from-teal-500 to-cyan-600",
  },
  {
    icon: Lock,
    title: "Enterprise SSO",
    description:
      "Secure single sign-on with your identity provider. SAML, OIDC, and OAuth 2.0 support. Role-based access control.",
    gradient: "from-slate-500 to-zinc-600",
  },
  {
    icon: Zap,
    title: "Supersession Chains",
    description:
      "When decisions evolve, supersede old ones with new. Track the complete lineage from original decision to current state.",
    gradient: "from-yellow-500 to-orange-600",
  },
  {
    icon: Clock,
    title: "Tech Debt Timer",
    description:
      "Set review dates for temporary decisions. Get reminded before they expire. Never let tech debt slip through the cracks.",
    gradient: "from-red-500 to-pink-600",
  },
  {
    icon: Search,
    title: "Powerful Search",
    description:
      "Full-text search across all decisions. Filter by status, impact level, team, tags, and date range. Find anything instantly.",
    gradient: "from-blue-500 to-indigo-600",
  },
  {
    icon: FileCheck,
    title: "Compliance Export",
    description:
      "Generate official PDF audit reports with verification hashes. Perfect for SOC 2, ISO 27001, and regulatory audits.",
    gradient: "from-emerald-500 to-teal-600",
  },
];

export default function FeaturesPage() {
  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-[120px]" />
        <div className="absolute top-1/3 right-1/4 w-80 h-80 bg-purple-500/10 rounded-full blur-[100px]" />
        <div className="absolute bottom-1/4 left-1/3 w-72 h-72 bg-pink-500/10 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10">
        <LandingNavbar />

        {/* Hero Section */}
        <section className="pt-32 pb-20 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-gray-400 mb-8">
              <Zap className="w-4 h-4 text-cyan-400" />
              Everything you need to manage decisions
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
              Features Built for
              <br />
              Engineering Teams
            </h1>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10">
              From solo developers to enterprise teams, Imputable provides the
              tools you need to document, track, and audit every decision.
            </p>
            <div className="flex items-center justify-center gap-4">
              <Link
                href="/sign-up"
                className="px-8 py-4 rounded-xl bg-gradient-to-r from-cyan-500 to-purple-600 text-white font-semibold hover:opacity-90 transition-opacity"
              >
                Start Free Trial
              </Link>
              <Link
                href="/pricing"
                className="px-8 py-4 rounded-xl bg-white/5 border border-white/10 text-white font-semibold hover:bg-white/10 transition-colors"
              >
                View Pricing
              </Link>
            </div>
          </div>
        </section>

        {/* Features Grid */}
        <section className="py-20 px-6">
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="group relative p-8 rounded-3xl bg-white/[0.02] border border-white/5 hover:border-white/10 transition-all duration-300"
                >
                  {/* Icon */}
                  <div
                    className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300`}
                  >
                    <feature.icon className="w-7 h-7 text-white" />
                  </div>

                  {/* Content */}
                  <h3 className="text-xl font-semibold text-white mb-3">
                    {feature.title}
                  </h3>
                  <p className="text-gray-400 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-20 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <div className="p-12 rounded-3xl bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10">
              <h2 className="text-3xl md:text-4xl font-bold mb-4">
                Ready to get started?
              </h2>
              <p className="text-gray-400 mb-8 max-w-xl mx-auto">
                Join thousands of engineering teams who trust Imputable to
                document their most important decisions.
              </p>
              <Link
                href="/sign-up"
                className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-white text-black font-semibold hover:bg-gray-100 transition-colors"
              >
                Get Started Free
                <ArrowRight className="w-5 h-5" />
              </Link>
            </div>
          </div>
        </section>

        <Footer />
      </div>
    </div>
  );
}

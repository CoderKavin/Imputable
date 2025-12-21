import { Metadata } from "next";
import Link from "next/link";
import { LandingNavbar } from "@/components/landing/navbar";
import { Footer } from "@/components/landing/footer";
import { Check, X, Zap, Building2, Sparkles } from "lucide-react";

export const metadata: Metadata = {
  title: "Pricing | Imputable - The Decision Ledger",
  description:
    "Simple, transparent pricing for teams of all sizes. Start free, upgrade when you need more.",
};

const tiers = [
  {
    name: "Free",
    description: "For individuals and small projects",
    price: "$0",
    period: "forever",
    cta: "Get Started",
    ctaHref: "/sign-up",
    highlight: false,
    features: [
      { text: "Up to 25 decisions", included: true },
      { text: "Up to 3 team members", included: true },
      { text: "Full version history", included: true },
      { text: "Basic search", included: true },
      { text: "Community support", included: true },
      { text: "API access", included: false },
      { text: "Slack/Teams integration", included: false },
      { text: "Risk dashboard", included: false },
      { text: "Audit export", included: false },
      { text: "SSO", included: false },
    ],
  },
  {
    name: "Pro",
    description: "For growing engineering teams",
    price: "$49",
    period: "per month",
    cta: "Start Free Trial",
    ctaHref: "/sign-up?plan=pro",
    highlight: true,
    badge: "Most Popular",
    features: [
      { text: "Up to 500 decisions", included: true },
      { text: "Up to 50 team members", included: true },
      { text: "Full version history", included: true },
      { text: "Advanced search & filters", included: true },
      { text: "Priority support", included: true },
      { text: "API access", included: true },
      { text: "Slack/Teams integration", included: true },
      { text: "Risk dashboard", included: true },
      { text: "Audit export", included: false },
      { text: "SSO", included: true },
    ],
  },
  {
    name: "Enterprise",
    description: "For large organizations",
    price: "Custom",
    period: "contact us",
    cta: "Contact Sales",
    ctaHref: "mailto:sales@imputable.io",
    highlight: false,
    features: [
      { text: "Unlimited decisions", included: true },
      { text: "Unlimited team members", included: true },
      { text: "Full version history", included: true },
      { text: "Advanced search & filters", included: true },
      { text: "Dedicated support", included: true },
      { text: "API access", included: true },
      { text: "Slack/Teams integration", included: true },
      { text: "Risk dashboard", included: true },
      { text: "Audit export (PDF)", included: true },
      { text: "SSO + SCIM", included: true },
    ],
  },
];

const faqs = [
  {
    q: "Can I try before I buy?",
    a: "Yes! All paid plans come with a 14-day free trial. No credit card required to start.",
  },
  {
    q: "What happens if I exceed my decision limit?",
    a: "You'll get a notification to upgrade. Your existing decisions remain accessible, but you won't be able to create new ones until you upgrade.",
  },
  {
    q: "Can I switch plans anytime?",
    a: "Absolutely. Upgrade or downgrade at any time. If you downgrade, changes take effect at the end of your billing cycle.",
  },
  {
    q: "Do you offer discounts for startups or non-profits?",
    a: "Yes! We offer 50% off for qualified startups and non-profit organizations. Contact us to apply.",
  },
  {
    q: "Is my data secure?",
    a: "Yes. We use encryption at rest and in transit, maintain SOC 2 compliance, and never share your data with third parties.",
  },
  {
    q: "What payment methods do you accept?",
    a: "We accept all major credit cards via Stripe. Enterprise customers can pay via invoice.",
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-20 left-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-cyan-500/10 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10">
        <LandingNavbar />

        {/* Hero Section */}
        <section className="pt-32 pb-16 px-6">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-sm text-gray-400 mb-8">
              <Sparkles className="w-4 h-4 text-purple-400" />
              Simple, transparent pricing
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-white via-gray-200 to-gray-400 bg-clip-text text-transparent">
              Start Free,
              <br />
              Scale as You Grow
            </h1>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto">
              No hidden fees. No per-user pricing gotchas. Just straightforward
              plans that grow with your team.
            </p>
          </div>
        </section>

        {/* Pricing Cards */}
        <section className="py-12 px-6">
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
              {tiers.map((tier) => (
                <div
                  key={tier.name}
                  className={`relative p-8 rounded-3xl border transition-all duration-300 ${
                    tier.highlight
                      ? "bg-gradient-to-b from-purple-500/10 to-transparent border-purple-500/50"
                      : "bg-white/[0.02] border-white/10 hover:border-white/20"
                  }`}
                >
                  {/* Badge */}
                  {tier.badge && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="px-4 py-1 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 text-xs font-semibold text-white">
                        {tier.badge}
                      </span>
                    </div>
                  )}

                  {/* Header */}
                  <div className="mb-6">
                    <h3 className="text-xl font-semibold text-white mb-1">
                      {tier.name}
                    </h3>
                    <p className="text-sm text-gray-500">{tier.description}</p>
                  </div>

                  {/* Price */}
                  <div className="mb-6">
                    <span className="text-4xl font-bold text-white">
                      {tier.price}
                    </span>
                    <span className="text-gray-500 ml-2">/{tier.period}</span>
                  </div>

                  {/* CTA */}
                  <Link
                    href={tier.ctaHref}
                    className={`block w-full py-3 rounded-xl text-center font-semibold transition-all duration-200 mb-8 ${
                      tier.highlight
                        ? "bg-white text-black hover:bg-gray-100"
                        : "bg-white/10 text-white hover:bg-white/20"
                    }`}
                  >
                    {tier.cta}
                  </Link>

                  {/* Features */}
                  <ul className="space-y-3">
                    {tier.features.map((feature, idx) => (
                      <li
                        key={idx}
                        className={`flex items-start gap-3 text-sm ${
                          feature.included ? "text-gray-300" : "text-gray-600"
                        }`}
                      >
                        {feature.included ? (
                          <Check className="w-5 h-5 text-green-500 flex-shrink-0" />
                        ) : (
                          <X className="w-5 h-5 text-gray-600 flex-shrink-0" />
                        )}
                        {feature.text}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Enterprise CTA */}
        <section className="py-16 px-6">
          <div className="max-w-4xl mx-auto">
            <div className="p-10 rounded-3xl bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10 flex flex-col md:flex-row items-center gap-8">
              <div className="flex-shrink-0">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
                  <Building2 className="w-8 h-8 text-white" />
                </div>
              </div>
              <div className="flex-1 text-center md:text-left">
                <h3 className="text-2xl font-bold mb-2">Need a custom plan?</h3>
                <p className="text-gray-400">
                  We offer custom pricing for large organizations with specific
                  requirements. Let&apos;s talk about what you need.
                </p>
              </div>
              <Link
                href="mailto:sales@imputable.io"
                className="px-8 py-4 rounded-xl bg-white text-black font-semibold hover:bg-gray-100 transition-colors whitespace-nowrap"
              >
                Contact Sales
              </Link>
            </div>
          </div>
        </section>

        {/* FAQ Section */}
        <section className="py-20 px-6">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-3xl font-bold text-center mb-12">
              Frequently Asked Questions
            </h2>
            <div className="space-y-6">
              {faqs.map((faq, idx) => (
                <div
                  key={idx}
                  className="p-6 rounded-2xl bg-white/[0.02] border border-white/10"
                >
                  <h3 className="text-lg font-semibold mb-2">{faq.q}</h3>
                  <p className="text-gray-400">{faq.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <Footer />
      </div>
    </div>
  );
}

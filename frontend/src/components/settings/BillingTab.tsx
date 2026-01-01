"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  CreditCard,
  Loader2,
  Check,
  Zap,
  Building2,
  Users,
  FileText,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

interface BillingInfo {
  subscription_tier: string;
  member_count: number;
  decision_count: number;
  user_role: string;
}

const plans = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    period: "forever",
    description: "For small teams getting started",
    features: [
      "Up to 5 team members",
      "Up to 50 decisions",
      "Basic audit trail",
      "Email support",
    ],
    limits: {
      members: 5,
      decisions: 50,
    },
  },
  {
    id: "pro",
    name: "Pro",
    price: "$29",
    period: "per month",
    description: "For growing teams with more needs",
    features: [
      "Unlimited team members",
      "Unlimited decisions",
      "Full audit trail & export",
      "Slack & Teams integrations",
      "Priority support",
      "API access",
    ],
    limits: {
      members: Infinity,
      decisions: Infinity,
    },
    popular: true,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "Custom",
    period: "contact us",
    description: "For organizations with advanced needs",
    features: [
      "Everything in Pro",
      "SSO / SAML authentication",
      "Advanced security controls",
      "Custom integrations",
      "Dedicated support",
      "SLA guarantee",
    ],
    limits: {
      members: Infinity,
      decisions: Infinity,
    },
  },
];

export function BillingTab() {
  const { getToken } = useAuth();
  const { currentOrganization } = useOrganization();

  const [loading, setLoading] = useState(true);
  const [billingInfo, setBillingInfo] = useState<BillingInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upgradeMessage, setUpgradeMessage] = useState<string | null>(null);

  useEffect(() => {
    if (currentOrganization?.id) {
      fetchBillingInfo();
    }
  }, [currentOrganization?.id]);

  useEffect(() => {
    if (upgradeMessage) {
      const timer = setTimeout(() => setUpgradeMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [upgradeMessage]);

  function handlePlanChange(planId: string) {
    if (planId === "pro") {
      setUpgradeMessage(
        "Pro plan coming soon! Contact support@imputable.app to get early access.",
      );
    } else if (planId === "free") {
      setUpgradeMessage(
        "To downgrade your plan, please contact support@imputable.app",
      );
    }
  }

  function handleContactSales() {
    window.location.href =
      "mailto:sales@imputable.app?subject=Enterprise%20Plan%20Inquiry";
  }

  async function fetchBillingInfo() {
    if (!currentOrganization?.id) return;

    try {
      if (!billingInfo) setLoading(true);
      const token = await getToken();

      const response = await fetch(`${API_BASE_URL}/me/organization`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Organization-ID": currentOrganization.id,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setBillingInfo(data);
      }
    } catch (err) {
      console.error("Error fetching billing info:", err);
      setError("Failed to load billing information");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  const currentPlan =
    plans.find((p) => p.id === billingInfo?.subscription_tier) || plans[0];
  const isOwner = billingInfo?.user_role === "owner";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Billing & Subscription
        </h2>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Manage your subscription plan and billing information.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}
      {upgradeMessage && (
        <div className="flex items-center gap-2 rounded-xl bg-indigo-50 px-4 py-3 text-sm text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-400">
          <Zap className="h-4 w-4 flex-shrink-0" />
          {upgradeMessage}
        </div>
      )}

      {/* Current Plan */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Current Plan</CardTitle>
          <CardDescription>
            Your organization&apos;s subscription details
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 p-6 text-white">
            <div>
              <p className="text-sm font-medium text-indigo-100">
                Current Plan
              </p>
              <p className="text-3xl font-bold">{currentPlan.name}</p>
              <p className="mt-1 text-sm text-indigo-100">
                {currentPlan.description}
              </p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold">{currentPlan.price}</p>
              <p className="text-sm text-indigo-100">{currentPlan.period}</p>
            </div>
          </div>

          {/* Usage Stats */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-zinc-400" />
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">
                    Team Members
                  </span>
                </div>
                <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                  {billingInfo?.member_count || 0}
                  {currentPlan.limits.members !== Infinity &&
                    ` / ${currentPlan.limits.members}`}
                </span>
              </div>
              {currentPlan.limits.members !== Infinity && (
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                  <div
                    className="h-full rounded-full bg-indigo-500"
                    style={{
                      width: `${Math.min(100, ((billingInfo?.member_count || 0) / currentPlan.limits.members) * 100)}%`,
                    }}
                  />
                </div>
              )}
            </div>

            <div className="rounded-xl bg-zinc-50 p-4 dark:bg-zinc-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-zinc-400" />
                  <span className="text-sm text-zinc-600 dark:text-zinc-400">
                    Decisions
                  </span>
                </div>
                <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                  {billingInfo?.decision_count || 0}
                  {currentPlan.limits.decisions !== Infinity &&
                    ` / ${currentPlan.limits.decisions}`}
                </span>
              </div>
              {currentPlan.limits.decisions !== Infinity && (
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                  <div
                    className="h-full rounded-full bg-indigo-500"
                    style={{
                      width: `${Math.min(100, ((billingInfo?.decision_count || 0) / currentPlan.limits.decisions) * 100)}%`,
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Available Plans */}
      <Card className="rounded-2xl border-zinc-200 dark:border-zinc-800">
        <CardHeader>
          <CardTitle className="text-lg">Available Plans</CardTitle>
          <CardDescription>
            Choose the plan that best fits your needs
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            {plans.map((plan) => {
              const isCurrent = plan.id === currentPlan.id;
              return (
                <div
                  key={plan.id}
                  className={`relative rounded-xl border p-6 ${
                    plan.popular
                      ? "border-indigo-500 ring-2 ring-indigo-500"
                      : "border-zinc-200 dark:border-zinc-700"
                  } ${isCurrent ? "bg-indigo-50/50 dark:bg-indigo-950/20" : ""}`}
                >
                  {plan.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="rounded-full bg-indigo-500 px-3 py-1 text-xs font-medium text-white">
                        Most Popular
                      </span>
                    </div>
                  )}

                  <div className="mb-4">
                    <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
                      {plan.name}
                    </h3>
                    <div className="mt-2">
                      <span className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
                        {plan.price}
                      </span>
                      <span className="text-sm text-zinc-500 dark:text-zinc-400">
                        {" "}
                        {plan.period}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
                      {plan.description}
                    </p>
                  </div>

                  <ul className="mb-6 space-y-2">
                    {plan.features.map((feature) => (
                      <li
                        key={feature}
                        className="flex items-center gap-2 text-sm"
                      >
                        <Check className="h-4 w-4 flex-shrink-0 text-green-500" />
                        <span className="text-zinc-600 dark:text-zinc-400">
                          {feature}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {isCurrent ? (
                    <Button
                      disabled
                      className="w-full rounded-xl"
                      variant="outline"
                    >
                      Current Plan
                    </Button>
                  ) : plan.id === "enterprise" ? (
                    <Button
                      className="w-full rounded-xl"
                      variant="outline"
                      onClick={handleContactSales}
                    >
                      Contact Sales
                      <ExternalLink className="ml-2 h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      className="w-full rounded-xl"
                      variant={plan.popular ? "default" : "outline"}
                      disabled={!isOwner}
                      onClick={() => handlePlanChange(plan.id)}
                    >
                      {plan.id === "free" ? "Downgrade" : "Upgrade"}
                      <Zap className="ml-2 h-4 w-4" />
                    </Button>
                  )}
                </div>
              );
            })}
          </div>

          {!isOwner && (
            <p className="mt-4 text-center text-sm text-zinc-500 dark:text-zinc-400">
              Only organization owners can change the subscription plan.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Billing Info */}
      <div className="rounded-2xl border border-zinc-200 bg-zinc-50/50 p-6 dark:border-zinc-800 dark:bg-zinc-900/50">
        <h3 className="mb-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
          Need help with billing?
        </h3>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Contact our support team at{" "}
          <a
            href="mailto:support@imputable.app"
            className="text-indigo-600 hover:underline"
          >
            support@imputable.app
          </a>{" "}
          for any billing questions or to request custom enterprise pricing.
        </p>
      </div>
    </div>
  );
}

export default BillingTab;

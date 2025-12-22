"use client";

import { ReactNode } from "react";
import { Lock, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// Subscription tier hierarchy
export type SubscriptionTier =
  | "free"
  | "starter"
  | "professional"
  | "enterprise";

const TIER_ORDER: Record<SubscriptionTier, number> = {
  free: 0,
  starter: 1,
  professional: 2,
  enterprise: 3,
};

const TIER_LABELS: Record<SubscriptionTier, string> = {
  free: "Free",
  starter: "Starter",
  professional: "Professional",
  enterprise: "Enterprise",
};

interface PremiumGuardProps {
  /**
   * The minimum tier required to access this feature
   */
  requiredTier: SubscriptionTier;

  /**
   * The user's current subscription tier
   * In production, this comes from your auth/subscription context
   */
  currentTier: SubscriptionTier;

  /**
   * The content to show when the user has access
   */
  children: ReactNode;

  /**
   * Optional: Custom locked state content
   */
  lockedContent?: ReactNode;

  /**
   * Optional: Feature name for the upgrade message
   */
  featureName?: string;

  /**
   * Optional: Upgrade URL (defaults to /settings/billing)
   */
  upgradeUrl?: string;
}

/**
 * PremiumGuard - Gate features based on subscription tier
 *
 * Usage:
 * ```tsx
 * <PremiumGuard
 *   requiredTier="enterprise"
 *   currentTier={subscription.tier}
 *   featureName="Audit Export"
 * >
 *   <AuditExportButton />
 * </PremiumGuard>
 * ```
 */
export function PremiumGuard({
  requiredTier,
  currentTier,
  children,
  lockedContent,
  featureName,
  upgradeUrl = "/settings/billing",
}: PremiumGuardProps) {
  const hasAccess = TIER_ORDER[currentTier] >= TIER_ORDER[requiredTier];

  if (hasAccess) {
    return <>{children}</>;
  }

  // Show locked state
  if (lockedContent) {
    return <>{lockedContent}</>;
  }

  // Default locked button
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            className="relative cursor-not-allowed opacity-60"
            disabled
          >
            <Lock className="mr-2 h-4 w-4" />
            {featureName || "Premium Feature"}
            <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-r from-amber-400 to-orange-500 text-[10px] font-bold text-white">
              <Sparkles className="h-3 w-3" />
            </span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <div className="space-y-2">
            <p className="font-medium">
              Upgrade to {TIER_LABELS[requiredTier]} to unlock
            </p>
            <p className="text-xs text-muted-foreground">
              {featureName
                ? `${featureName} is available on ${TIER_LABELS[requiredTier]} and above.`
                : `This feature requires a ${TIER_LABELS[requiredTier]} subscription.`}
            </p>
            <Button
              size="sm"
              className="mt-2 w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
              onClick={() => (window.location.href = upgradeUrl)}
            >
              <Sparkles className="mr-2 h-3 w-3" />
              Upgrade Now
            </Button>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/**
 * LockedFeatureCard - Full card showing a locked premium feature
 *
 * Usage:
 * ```tsx
 * <LockedFeatureCard
 *   requiredTier="professional"
 *   featureName="Risk Dashboard"
 *   description="Track tech debt and expiring decisions with visual heatmaps."
 * />
 * ```
 */
interface LockedFeatureCardProps {
  requiredTier: SubscriptionTier;
  featureName: string;
  description: string;
  upgradeUrl?: string;
}

export function LockedFeatureCard({
  requiredTier,
  featureName,
  description,
  upgradeUrl = "/settings/billing",
}: LockedFeatureCardProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-muted-foreground/25 bg-muted/10 p-8 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/30">
        <Lock className="h-8 w-8 text-amber-600 dark:text-amber-400" />
      </div>

      <h3 className="mb-2 text-lg font-semibold">{featureName}</h3>

      <p className="mb-4 max-w-md text-sm text-muted-foreground">
        {description}
      </p>

      <div className="mb-4 inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
        <Sparkles className="mr-1 h-3 w-3" />
        {TIER_LABELS[requiredTier]} Feature
      </div>

      <Button
        className="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
        onClick={() => (window.location.href = upgradeUrl)}
      >
        <Sparkles className="mr-2 h-4 w-4" />
        Upgrade to {TIER_LABELS[requiredTier]}
      </Button>
    </div>
  );
}

/**
 * useSubscription - Hook to get current subscription tier
 *
 * In production, this should fetch from your API or use a context provider
 */
export function useSubscription(): {
  tier: SubscriptionTier;
  isLoading: boolean;
  hasFeature: (feature: string) => boolean;
} {
  // TODO: Replace with actual subscription fetching logic
  // This could come from:
  // 1. A React context that's populated at app load
  // 2. An API call with React Query
  // 3. Data from your organization's metadata

  // For now, default to 'free' - in dev mode the backend returns 'enterprise'
  const tier: SubscriptionTier = "free";

  const FEATURE_TIERS: Record<string, SubscriptionTier> = {
    risk_dashboard: "professional",
    audit_export: "enterprise",
    api_access: "starter",
    sso: "professional",
  };

  return {
    tier,
    isLoading: false,
    hasFeature: (feature: string) => {
      const requiredTier = FEATURE_TIERS[feature] || "enterprise";
      return TIER_ORDER[tier] >= TIER_ORDER[requiredTier];
    },
  };
}

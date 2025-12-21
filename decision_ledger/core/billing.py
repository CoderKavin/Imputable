"""Billing and subscription management using Stripe.

This module provides:
1. Subscription tier checking
2. Feature gating based on plan
3. Stripe webhook handling
"""

import logging
from typing import Annotated
from uuid import UUID

import stripe
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_session
from .dependencies import CurrentUser, require_org_context
from ..models import Organization, SubscriptionTier

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Stripe
if settings.stripe_enabled:
    stripe.api_key = settings.stripe_secret_key


# Feature flags per tier
TIER_FEATURES = {
    SubscriptionTier.FREE: {
        "max_decisions": 25,
        "max_team_members": 3,
        "audit_export": False,
        "api_access": False,
        "sso": False,
        "priority_support": False,
        "integrations": False,  # No Slack/Teams
    },
    SubscriptionTier.STARTER: {
        "max_decisions": 100,
        "max_team_members": 10,
        "audit_export": False,
        "api_access": True,
        "sso": False,
        "priority_support": False,
        "integrations": False,  # No Slack/Teams
    },
    SubscriptionTier.PROFESSIONAL: {
        "max_decisions": 500,
        "max_team_members": 50,
        "risk_dashboard": True,  # PRO FEATURE
        "audit_export": False,
        "api_access": True,
        "sso": True,
        "priority_support": False,
        "integrations": True,  # PRO FEATURE - Slack & Teams
    },
    SubscriptionTier.ENTERPRISE: {
        "max_decisions": -1,  # Unlimited
        "max_team_members": -1,  # Unlimited
        "risk_dashboard": True,
        "audit_export": True,  # THE MONEY FEATURE
        "api_access": True,
        "sso": True,
        "priority_support": True,
        "integrations": True,  # Slack & Teams
    },
}


# Tier hierarchy for comparison
TIER_ORDER = {
    SubscriptionTier.FREE: 0,
    SubscriptionTier.STARTER: 1,
    SubscriptionTier.PROFESSIONAL: 2,
    SubscriptionTier.ENTERPRISE: 3,
}


async def get_organization_subscription(
    session: AsyncSession,
    organization_id: UUID,
) -> tuple[SubscriptionTier, dict]:
    """
    Get the subscription tier for an organization.

    The tier is stored directly in the Organization table and updated
    by Stripe webhooks when subscription status changes.

    Returns:
        Tuple of (tier, subscription_metadata)
    """
    # Get organization with subscription info
    result = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        return SubscriptionTier.FREE, {}

    # In development without Stripe, default to Enterprise for testing
    if settings.environment == "development" and not settings.stripe_enabled:
        logger.debug("Development mode - defaulting to Enterprise tier")
        return SubscriptionTier.ENTERPRISE, {"dev_mode": True}

    # Return the tier stored in the database (updated by Stripe webhooks)
    return org.subscription_tier, {
        "stripe_customer_id": org.stripe_customer_id,
        "stripe_subscription_id": org.stripe_subscription_id,
    }


def _map_price_to_tier(price_id: str, org_settings: dict) -> SubscriptionTier:
    """Map a Stripe price ID to a subscription tier."""
    # These would be configured as environment variables or in the database
    tier_mapping = org_settings.get("stripe_tier_mapping", {})

    # Fallback to environment-based mapping
    import os
    if not tier_mapping:
        tier_mapping = {
            os.getenv("STRIPE_STARTER_PRICE_ID", ""): SubscriptionTier.STARTER,
            os.getenv("STRIPE_PROFESSIONAL_PRICE_ID", ""): SubscriptionTier.PROFESSIONAL,
            os.getenv("STRIPE_ENTERPRISE_PRICE_ID", ""): SubscriptionTier.ENTERPRISE,
        }

    return tier_mapping.get(price_id, SubscriptionTier.STARTER)


class SubscriptionContext:
    """Context containing subscription info for the current request."""

    def __init__(
        self,
        tier: SubscriptionTier,
        features: dict,
        subscription_data: dict,
    ):
        self.tier = tier
        self.features = features
        self.subscription_data = subscription_data

    def has_feature(self, feature: str) -> bool:
        """Check if the subscription includes a feature."""
        return self.features.get(feature, False)

    def check_limit(self, feature: str, current_count: int) -> bool:
        """Check if usage is within tier limits."""
        limit = self.features.get(feature, 0)
        if limit == -1:  # Unlimited
            return True
        return current_count < limit


async def get_subscription_context(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SubscriptionContext:
    """Dependency to get subscription context for the current organization."""
    tier, subscription_data = await get_organization_subscription(
        session,
        current_user.organization_id,
    )

    features = TIER_FEATURES.get(tier, TIER_FEATURES[SubscriptionTier.FREE])

    return SubscriptionContext(
        tier=tier,
        features=features,
        subscription_data=subscription_data,
    )


def require_feature(feature: str):
    """
    Dependency factory that requires a specific feature.

    Usage:
        @router.post("/audit-export/generate")
        async def generate_export(
            subscription: Annotated[SubscriptionContext, Depends(require_feature("audit_export"))],
        ):
            ...
    """
    async def _check_feature(
        subscription: Annotated[SubscriptionContext, Depends(get_subscription_context)],
    ) -> SubscriptionContext:
        if not subscription.has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "feature_not_available",
                    "message": f"The '{feature}' feature requires an upgrade to your subscription.",
                    "current_tier": subscription.tier.value,
                    "required_tier": _get_minimum_tier_for_feature(feature),
                    "upgrade_url": "/settings/billing",
                },
            )
        return subscription

    return _check_feature


def _get_minimum_tier_for_feature(feature: str) -> str:
    """Get the minimum tier that includes a feature."""
    for tier in [SubscriptionTier.STARTER, SubscriptionTier.PROFESSIONAL, SubscriptionTier.ENTERPRISE]:
        if TIER_FEATURES[tier].get(feature):
            return tier.value
    return SubscriptionTier.ENTERPRISE.value


def require_enterprise(
    subscription: Annotated[SubscriptionContext, Depends(get_subscription_context)],
) -> SubscriptionContext:
    """Dependency that requires Enterprise tier."""
    if subscription.tier != SubscriptionTier.ENTERPRISE:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "enterprise_required",
                "message": "This feature requires an Enterprise subscription.",
                "current_tier": subscription.tier.value,
                "upgrade_url": "/settings/billing",
            },
        )
    return subscription


def require_tier(minimum_tier: SubscriptionTier):
    """
    Dependency factory that requires a minimum subscription tier.

    Usage:
        @router.get("/dashboard/risk")
        async def get_risk_dashboard(
            subscription: Annotated[SubscriptionContext, Depends(require_tier(SubscriptionTier.PROFESSIONAL))],
        ):
            ...
    """
    async def _check_tier(
        subscription: Annotated[SubscriptionContext, Depends(get_subscription_context)],
    ) -> SubscriptionContext:
        if TIER_ORDER[subscription.tier] < TIER_ORDER[minimum_tier]:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "upgrade_required",
                    "message": f"This feature requires a {minimum_tier.value.title()} subscription or higher.",
                    "current_tier": subscription.tier.value,
                    "required_tier": minimum_tier.value,
                    "upgrade_url": "/settings/billing",
                },
            )
        return subscription

    return _check_tier


# Type aliases for cleaner dependency injection
SubscriptionDep = Annotated[SubscriptionContext, Depends(get_subscription_context)]
EnterpriseDep = Annotated[SubscriptionContext, Depends(require_enterprise)]
AuditExportDep = Annotated[SubscriptionContext, Depends(require_feature("audit_export"))]
RiskDashboardDep = Annotated[SubscriptionContext, Depends(require_tier(SubscriptionTier.PROFESSIONAL))]
IntegrationsDep = Annotated[SubscriptionContext, Depends(require_feature("integrations"))]

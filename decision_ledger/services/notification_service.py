"""
Notification Service: Handles delivery of notifications.

This module is responsible for:
1. Sending emails via SMTP or email service provider
2. Delivering webhooks for integrations
3. Updating notification status in the database
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    NotificationLog,
    NotificationStatus,
    NotificationType,
    Organization,
    User,
)


logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class EmailConfig:
    """Email delivery configuration."""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "notifications@decisionledger.io"
    from_name: str = "Imputable"
    use_tls: bool = True


@dataclass
class WebhookConfig:
    """Webhook delivery configuration."""
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5


# =============================================================================
# NOTIFICATION CHANNELS (Abstract)
# =============================================================================


class NotificationChannel(ABC):
    """Abstract base for notification delivery channels."""

    @abstractmethod
    async def send(
        self,
        recipient: User,
        subject: str,
        content: dict,
        notification_type: NotificationType,
    ) -> tuple[bool, str | None]:
        """
        Send a notification.

        Returns:
            (success, error_message)
        """
        pass


class EmailChannel(NotificationChannel):
    """Email notification channel."""

    def __init__(self, config: EmailConfig):
        self._config = config

    async def send(
        self,
        recipient: User,
        subject: str,
        content: dict,
        notification_type: NotificationType,
    ) -> tuple[bool, str | None]:
        """Send an email notification."""
        try:
            # Build email body based on notification type
            html_body = self._build_email_html(
                recipient_name=recipient.name,
                subject=subject,
                content=content,
                notification_type=notification_type,
            )

            # In production, use aiosmtplib or a service like SendGrid
            # For now, we'll log the email
            logger.info(
                f"[EMAIL] To: {recipient.email}, Subject: {subject}, "
                f"Decision: #{content.get('decision_number')}"
            )

            # TODO: Implement actual email sending
            # import aiosmtplib
            # message = EmailMessage()
            # message["From"] = f"{self._config.from_name} <{self._config.from_email}>"
            # message["To"] = recipient.email
            # message["Subject"] = subject
            # message.set_content(html_body, subtype="html")
            # await aiosmtplib.send(message, ...)

            return True, None

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _build_email_html(
        self,
        recipient_name: str,
        subject: str,
        content: dict,
        notification_type: NotificationType,
    ) -> str:
        """Build HTML email body."""
        decision_number = content.get("decision_number", "")
        title = content.get("title", "")
        review_date = content.get("review_by_date", "")
        days_until = content.get("days_until_expiry", 0)
        team_name = content.get("team_name", "Unassigned")
        is_temporary = content.get("is_temporary", False)

        # Determine urgency styling
        if notification_type == NotificationType.EXPIRED_ALERT:
            urgency_color = "#DC2626"  # Red
            urgency_text = "EXPIRED"
            urgency_message = "This decision has passed its review date and requires immediate attention."
        elif days_until <= 1:
            urgency_color = "#DC2626"  # Red
            urgency_text = "URGENT"
            urgency_message = f"This decision expires tomorrow ({review_date})."
        elif days_until <= 7:
            urgency_color = "#F59E0B"  # Amber
            urgency_text = "WARNING"
            urgency_message = f"This decision expires in {days_until} days ({review_date})."
        else:
            urgency_color = "#3B82F6"  # Blue
            urgency_text = "REMINDER"
            urgency_message = f"This decision is due for review in {days_until} days ({review_date})."

        temporary_badge = ""
        if is_temporary:
            temporary_badge = """
            <span style="background-color: #FEF3C7; color: #92400E; padding: 2px 8px;
                         border-radius: 4px; font-size: 12px; margin-left: 8px;">
                TEMPORARY
            </span>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
             line-height: 1.6; color: #374151; max-width: 600px; margin: 0 auto; padding: 20px;">

    <div style="background-color: {urgency_color}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 18px;">{urgency_text}: Decision Review Required</h1>
    </div>

    <div style="border: 1px solid #E5E7EB; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
        <p>Hi {recipient_name},</p>

        <p>{urgency_message}</p>

        <div style="background-color: #F9FAFB; padding: 16px; border-radius: 8px; margin: 20px 0;">
            <h2 style="margin: 0 0 8px 0; font-size: 16px; color: #111827;">
                Decision #{decision_number}: {title}
                {temporary_badge}
            </h2>
            <p style="margin: 8px 0 0 0; color: #6B7280; font-size: 14px;">
                Team: {team_name}<br>
                Review Date: {review_date}
            </p>
        </div>

        <p>Please take one of the following actions:</p>
        <ul>
            <li><strong>Review & Update:</strong> If the decision is still valid, update the review date</li>
            <li><strong>Supersede:</strong> If the decision needs to be replaced, create a new decision</li>
            <li><strong>Resolve:</strong> If the tech debt has been addressed, mark it as resolved</li>
        </ul>

        <div style="margin-top: 24px;">
            <a href="#" style="display: inline-block; background-color: {urgency_color}; color: white;
                              padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500;">
                View Decision
            </a>
        </div>

        <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;">

        <p style="color: #9CA3AF; font-size: 12px;">
            You're receiving this email because you're the owner or team member associated with this decision.
            <br>
            <a href="#" style="color: #6B7280;">Manage notification preferences</a>
        </p>
    </div>
</body>
</html>
"""


class WebhookChannel(NotificationChannel):
    """Webhook notification channel for integrations (Slack, Teams, etc.)."""

    def __init__(self, config: WebhookConfig):
        self._config = config

    async def send(
        self,
        recipient: User,
        subject: str,
        content: dict,
        notification_type: NotificationType,
    ) -> tuple[bool, str | None]:
        """Send a webhook notification."""
        # This would need the webhook URL from organization settings
        # For now, we just log
        logger.info(
            f"[WEBHOOK] To: {recipient.email}, Subject: {subject}, "
            f"Type: {notification_type.value}"
        )
        return True, None


# =============================================================================
# NOTIFICATION SERVICE
# =============================================================================


class NotificationService:
    """
    Main service for processing and delivering notifications.

    This service:
    1. Processes pending notifications from NotificationLog
    2. Sends via appropriate channel (email, webhook)
    3. Updates delivery status
    """

    def __init__(
        self,
        session: AsyncSession,
        email_config: EmailConfig | None = None,
        webhook_config: WebhookConfig | None = None,
    ):
        self._session = session
        self._email_channel = EmailChannel(email_config or EmailConfig())
        self._webhook_channel = WebhookChannel(webhook_config or WebhookConfig())

    async def process_pending_notifications(
        self,
        batch_size: int = 100,
    ) -> tuple[int, int, list[str]]:
        """
        Process all pending notifications.

        Returns:
            (sent_count, failed_count, errors)
        """
        # Fetch pending notifications
        query = (
            select(NotificationLog)
            .where(NotificationLog.status == NotificationStatus.PENDING)
            .order_by(NotificationLog.created_at.asc())
            .limit(batch_size)
        )

        result = await self._session.execute(query)
        notifications = result.scalars().all()

        sent_count = 0
        failed_count = 0
        errors = []

        for notification in notifications:
            try:
                # Get recipient
                user_query = select(User).where(User.id == notification.recipient_id)
                user_result = await self._session.execute(user_query)
                recipient = user_result.scalar_one_or_none()

                if not recipient:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = "Recipient not found"
                    failed_count += 1
                    continue

                # Select channel
                if notification.channel == "email":
                    channel = self._email_channel
                elif notification.channel == "webhook":
                    channel = self._webhook_channel
                else:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = f"Unknown channel: {notification.channel}"
                    failed_count += 1
                    continue

                # Send
                success, error = await channel.send(
                    recipient=recipient,
                    subject=notification.subject,
                    content=notification.content,
                    notification_type=notification.notification_type,
                )

                if success:
                    notification.status = NotificationStatus.SENT
                    notification.sent_at = datetime.now(timezone.utc)
                    sent_count += 1
                else:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = error
                    failed_count += 1
                    errors.append(f"Notification {notification.id}: {error}")

            except Exception as e:
                notification.status = NotificationStatus.FAILED
                notification.error_message = str(e)
                failed_count += 1
                errors.append(f"Notification {notification.id}: {str(e)}")

        await self._session.flush()

        return sent_count, failed_count, errors

    async def send_daily_digest(
        self,
        organization_id: UUID,
    ) -> int:
        """
        Send a daily digest email to stakeholders.

        Returns:
            Number of digests sent
        """
        from .expiry_engine import ExpiryEngine

        # Get expiry stats
        expiry_engine = ExpiryEngine(self._session)
        stats = await expiry_engine.get_expiry_stats(organization_id)

        if stats.total_expired == 0 and stats.total_at_risk == 0:
            return 0  # Nothing to report

        # Get organization admins
        org_query = select(Organization).where(Organization.id == organization_id)
        org_result = await self._session.execute(org_query)
        org = org_result.scalar_one_or_none()

        if not org:
            return 0

        # For now, create digest notifications for tracked decisions
        # In production, this would go to org admins/executives
        subject = f"Imputable Daily Digest: {stats.total_expired} expired, {stats.total_at_risk} at risk"

        content = {
            "organization_name": org.name,
            "total_expired": stats.total_expired,
            "total_at_risk": stats.total_at_risk,
            "expiring_this_week": stats.expiring_this_week,
            "expiring_this_month": stats.expiring_this_month,
            "by_team": stats.by_team,
            "by_impact": stats.by_impact,
        }

        logger.info(
            f"[DIGEST] Org: {org.name}, "
            f"Expired: {stats.total_expired}, At Risk: {stats.total_at_risk}"
        )

        # TODO: Create NotificationLog entries for org admins

        return 1

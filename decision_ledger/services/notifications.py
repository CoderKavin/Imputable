"""Notification Service for Slack and Microsoft Teams.

Sends beautiful, formatted notifications using:
- Slack Block Kit for rich, interactive messages
- Microsoft Teams Adaptive Cards for enterprise messaging

All notifications are sent asynchronously in the background.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import (
    Organization,
    Decision,
    DecisionVersion,
    DecisionStatus,
    ImpactLevel,
    User,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# COLOR MAPPINGS
# =============================================================================

# Slack uses hex colors without #
SLACK_STATUS_COLORS = {
    DecisionStatus.DRAFT: "808080",        # Gray
    DecisionStatus.PENDING_REVIEW: "f59e0b",  # Amber
    DecisionStatus.APPROVED: "10b981",     # Green
    DecisionStatus.DEPRECATED: "6b7280",   # Gray
    DecisionStatus.SUPERSEDED: "8b5cf6",   # Purple
    DecisionStatus.EXPIRED: "ef4444",      # Red
    DecisionStatus.AT_RISK: "ef4444",      # Red
}

SLACK_IMPACT_COLORS = {
    ImpactLevel.LOW: "3b82f6",      # Blue
    ImpactLevel.MEDIUM: "f59e0b",   # Amber
    ImpactLevel.HIGH: "f97316",     # Orange
    ImpactLevel.CRITICAL: "ef4444", # Red
}

# Teams uses hex colors with #
TEAMS_STATUS_COLORS = {
    DecisionStatus.DRAFT: "#808080",
    DecisionStatus.PENDING_REVIEW: "#f59e0b",
    DecisionStatus.APPROVED: "#10b981",
    DecisionStatus.DEPRECATED: "#6b7280",
    DecisionStatus.SUPERSEDED: "#8b5cf6",
    DecisionStatus.EXPIRED: "#ef4444",
    DecisionStatus.AT_RISK: "#ef4444",
}

STATUS_LABELS = {
    DecisionStatus.DRAFT: "Draft",
    DecisionStatus.PENDING_REVIEW: "Pending Review",
    DecisionStatus.APPROVED: "Approved",
    DecisionStatus.DEPRECATED: "Deprecated",
    DecisionStatus.SUPERSEDED: "Superseded",
    DecisionStatus.EXPIRED: "Expired",
    DecisionStatus.AT_RISK: "At Risk",
}

IMPACT_LABELS = {
    ImpactLevel.LOW: "Low",
    ImpactLevel.MEDIUM: "Medium",
    ImpactLevel.HIGH: "High",
    ImpactLevel.CRITICAL: "Critical",
}

STATUS_EMOJIS = {
    DecisionStatus.DRAFT: "📝",
    DecisionStatus.PENDING_REVIEW: "⏳",
    DecisionStatus.APPROVED: "✅",
    DecisionStatus.DEPRECATED: "📦",
    DecisionStatus.SUPERSEDED: "🔄",
    DecisionStatus.EXPIRED: "⚠️",
    DecisionStatus.AT_RISK: "🚨",
}


# =============================================================================
# NOTIFICATION SERVICE
# =============================================================================


class NotificationService:
    """
    Service for sending notifications to Slack and Teams.

    All methods are designed to be called from FastAPI BackgroundTasks
    to avoid blocking the main request.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()

    # =========================================================================
    # DECRYPT HELPER
    # =========================================================================

    def _decrypt_token(self, encrypted: str) -> str:
        """Decrypt a stored token."""
        if not settings.encryption_enabled:
            return encrypted

        try:
            from cryptography.fernet import Fernet
            f = Fernet(settings.encryption_key.encode())
            return f.decrypt(encrypted.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            return ""

    # =========================================================================
    # MAIN NOTIFICATION METHODS
    # =========================================================================

    async def notify_decision_created(
        self,
        org: Organization,
        decision: Decision,
        version: DecisionVersion,
        creator: User,
    ):
        """Send notification when a new decision is created."""
        if org.slack_access_token:
            await self._send_slack_decision_created(org, decision, version, creator)

        if org.teams_webhook_url:
            await self._send_teams_decision_created(org, decision, version, creator)

    async def notify_decision_updated(
        self,
        org: Organization,
        decision: Decision,
        version: DecisionVersion,
        updater: User,
        change_summary: str,
    ):
        """Send notification when a decision is updated (new version)."""
        if org.slack_access_token:
            await self._send_slack_decision_updated(org, decision, version, updater, change_summary)

        if org.teams_webhook_url:
            await self._send_teams_decision_updated(org, decision, version, updater, change_summary)

    async def notify_status_changed(
        self,
        org: Organization,
        decision: Decision,
        old_status: DecisionStatus,
        new_status: DecisionStatus,
        changed_by: User,
    ):
        """Send notification when decision status changes."""
        if org.slack_access_token:
            await self._send_slack_status_changed(org, decision, old_status, new_status, changed_by)

        if org.teams_webhook_url:
            await self._send_teams_status_changed(org, decision, old_status, new_status, changed_by)

    async def notify_review_needed(
        self,
        org: Organization,
        decision: Decision,
        days_until_review: int,
    ):
        """Send notification when a decision needs review soon."""
        if org.slack_access_token:
            await self._send_slack_review_reminder(org, decision, days_until_review)

        if org.teams_webhook_url:
            await self._send_teams_review_reminder(org, decision, days_until_review)

    # =========================================================================
    # SLACK BLOCK KIT IMPLEMENTATIONS
    # =========================================================================

    async def _send_slack_message(self, org: Organization, blocks: list, text: str, color: str | None = None):
        """Send a message to Slack using Block Kit."""
        try:
            token = self._decrypt_token(org.slack_access_token)
            if not token:
                logger.error(f"Failed to decrypt Slack token for org {org.id}")
                return

            # Build the message payload
            payload: dict[str, Any] = {
                "channel": org.slack_channel_id,
                "text": text,  # Fallback text
            }

            # Use attachments for colored side bar
            if color:
                payload["attachments"] = [{
                    "color": color,
                    "blocks": blocks,
                }]
            else:
                payload["blocks"] = blocks

            response = await self.http_client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )

            data = response.json()
            if not data.get("ok"):
                logger.error(f"Slack API error: {data.get('error')} for org {org.id}")
            else:
                logger.info(f"Slack notification sent for org {org.id}")

        except Exception as e:
            logger.error(f"Failed to send Slack notification for org {org.id}: {e}")

    async def _send_slack_decision_created(
        self,
        org: Organization,
        decision: Decision,
        version: DecisionVersion,
        creator: User,
    ):
        """Build and send Slack Block Kit message for new decision."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        emoji = STATUS_EMOJIS.get(decision.status, "📋")
        color = SLACK_STATUS_COLORS.get(decision.status, "6366f1")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} New Decision Created",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{decision_url}|DECISION-{decision.decision_number}: {version.title}>*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{STATUS_LABELS.get(decision.status, 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Impact:*\n{IMPACT_LABELS.get(version.impact_level, 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Created by:*\n{creator.name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Organization:*\n{org.name}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Tags: {', '.join(version.tags) if version.tags else 'None'}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Details",
                            "emoji": True
                        },
                        "url": decision_url,
                        "style": "primary"
                    }
                ]
            }
        ]

        await self._send_slack_message(
            org,
            blocks,
            f"New decision created: DECISION-{decision.decision_number} - {version.title}",
            color
        )

    async def _send_slack_decision_updated(
        self,
        org: Organization,
        decision: Decision,
        version: DecisionVersion,
        updater: User,
        change_summary: str,
    ):
        """Build and send Slack Block Kit message for decision update."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        color = SLACK_IMPACT_COLORS.get(version.impact_level, "6366f1")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📝 Decision Updated",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{decision_url}|DECISION-{decision.decision_number}: {version.title}>*\n_Version {version.version_number}_"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Change Summary:*\n{change_summary or 'No summary provided'}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Updated by {updater.name} • {datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Changes",
                            "emoji": True
                        },
                        "url": f"{decision_url}?version={version.version_number}",
                        "style": "primary"
                    }
                ]
            }
        ]

        await self._send_slack_message(
            org,
            blocks,
            f"Decision updated: DECISION-{decision.decision_number} - {version.title}",
            color
        )

    async def _send_slack_status_changed(
        self,
        org: Organization,
        decision: Decision,
        old_status: DecisionStatus,
        new_status: DecisionStatus,
        changed_by: User,
    ):
        """Build and send Slack Block Kit message for status change."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        emoji = STATUS_EMOJIS.get(new_status, "📋")
        color = SLACK_STATUS_COLORS.get(new_status, "6366f1")

        # Get current version title
        title = decision.current_version.title if decision.current_version else "Unknown"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Status Changed",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{decision_url}|DECISION-{decision.decision_number}: {title}>*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{STATUS_LABELS.get(old_status)}* → *{STATUS_LABELS.get(new_status)}*"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Changed by {changed_by.name} • {datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Decision",
                            "emoji": True
                        },
                        "url": decision_url,
                        "style": "primary"
                    }
                ]
            }
        ]

        await self._send_slack_message(
            org,
            blocks,
            f"Decision status changed: DECISION-{decision.decision_number} is now {STATUS_LABELS.get(new_status)}",
            color
        )

    async def _send_slack_review_reminder(
        self,
        org: Organization,
        decision: Decision,
        days_until_review: int,
    ):
        """Build and send Slack Block Kit message for review reminder."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        title = decision.current_version.title if decision.current_version else "Unknown"

        urgency = "🚨" if days_until_review <= 3 else "⏰" if days_until_review <= 7 else "📅"
        color = "ef4444" if days_until_review <= 3 else "f59e0b" if days_until_review <= 7 else "3b82f6"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{urgency} Review Reminder",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{decision_url}|DECISION-{decision.decision_number}: {title}>*\n\nThis decision is due for review in *{days_until_review} day{'s' if days_until_review != 1 else ''}*."
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Review date: {decision.review_by_date.strftime('%b %d, %Y') if decision.review_by_date else 'Not set'}"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Review Now",
                            "emoji": True
                        },
                        "url": decision_url,
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Snooze",
                            "emoji": True
                        },
                        "url": f"{decision_url}/snooze",
                    }
                ]
            }
        ]

        await self._send_slack_message(
            org,
            blocks,
            f"Review reminder: DECISION-{decision.decision_number} needs review in {days_until_review} days",
            color
        )

    # =========================================================================
    # TEAMS ADAPTIVE CARDS IMPLEMENTATIONS
    # =========================================================================

    async def _send_teams_message(self, org: Organization, card: dict):
        """Send an Adaptive Card to Teams."""
        try:
            if not org.teams_webhook_url:
                return

            response = await self.http_client.post(
                org.teams_webhook_url,
                json=card,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Teams webhook error: {response.status_code} for org {org.id}")
            else:
                logger.info(f"Teams notification sent for org {org.id}")

        except Exception as e:
            logger.error(f"Failed to send Teams notification for org {org.id}: {e}")

    async def _send_teams_decision_created(
        self,
        org: Organization,
        decision: Decision,
        version: DecisionVersion,
        creator: User,
    ):
        """Build and send Teams Adaptive Card for new decision."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        color = TEAMS_STATUS_COLORS.get(decision.status, "#6366f1")

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.lstrip("#"),
            "summary": f"New Decision: DECISION-{decision.decision_number}",
            "sections": [
                {
                    "activityTitle": f"📋 New Decision Created",
                    "activitySubtitle": f"DECISION-{decision.decision_number}: {version.title}",
                    "activityImage": "https://app.imputable.io/icons/decision.png",
                    "facts": [
                        {"name": "Status", "value": STATUS_LABELS.get(decision.status, "Unknown")},
                        {"name": "Impact", "value": IMPACT_LABELS.get(version.impact_level, "Unknown")},
                        {"name": "Created by", "value": creator.name},
                        {"name": "Organization", "value": org.name},
                        {"name": "Tags", "value": ", ".join(version.tags) if version.tags else "None"},
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View Details",
                    "targets": [
                        {"os": "default", "uri": decision_url}
                    ]
                }
            ]
        }

        await self._send_teams_message(org, card)

    async def _send_teams_decision_updated(
        self,
        org: Organization,
        decision: Decision,
        version: DecisionVersion,
        updater: User,
        change_summary: str,
    ):
        """Build and send Teams Adaptive Card for decision update."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        color = TEAMS_STATUS_COLORS.get(decision.status, "#6366f1")

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.lstrip("#"),
            "summary": f"Decision Updated: DECISION-{decision.decision_number}",
            "sections": [
                {
                    "activityTitle": "📝 Decision Updated",
                    "activitySubtitle": f"DECISION-{decision.decision_number}: {version.title}",
                    "activityImage": "https://app.imputable.io/icons/update.png",
                    "facts": [
                        {"name": "Version", "value": str(version.version_number)},
                        {"name": "Updated by", "value": updater.name},
                        {"name": "Change Summary", "value": change_summary or "No summary provided"},
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View Changes",
                    "targets": [
                        {"os": "default", "uri": f"{decision_url}?version={version.version_number}"}
                    ]
                }
            ]
        }

        await self._send_teams_message(org, card)

    async def _send_teams_status_changed(
        self,
        org: Organization,
        decision: Decision,
        old_status: DecisionStatus,
        new_status: DecisionStatus,
        changed_by: User,
    ):
        """Build and send Teams Adaptive Card for status change."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        color = TEAMS_STATUS_COLORS.get(new_status, "#6366f1")
        emoji = STATUS_EMOJIS.get(new_status, "📋")
        title = decision.current_version.title if decision.current_version else "Unknown"

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.lstrip("#"),
            "summary": f"Status Changed: DECISION-{decision.decision_number}",
            "sections": [
                {
                    "activityTitle": f"{emoji} Status Changed",
                    "activitySubtitle": f"DECISION-{decision.decision_number}: {title}",
                    "activityImage": "https://app.imputable.io/icons/status.png",
                    "facts": [
                        {"name": "Previous Status", "value": STATUS_LABELS.get(old_status, "Unknown")},
                        {"name": "New Status", "value": STATUS_LABELS.get(new_status, "Unknown")},
                        {"name": "Changed by", "value": changed_by.name},
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View Decision",
                    "targets": [
                        {"os": "default", "uri": decision_url}
                    ]
                }
            ]
        }

        await self._send_teams_message(org, card)

    async def _send_teams_review_reminder(
        self,
        org: Organization,
        decision: Decision,
        days_until_review: int,
    ):
        """Build and send Teams Adaptive Card for review reminder."""
        decision_url = f"https://app.imputable.io/decisions/{decision.id}"
        title = decision.current_version.title if decision.current_version else "Unknown"

        color = "#ef4444" if days_until_review <= 3 else "#f59e0b" if days_until_review <= 7 else "#3b82f6"
        urgency = "🚨 Urgent" if days_until_review <= 3 else "⏰ Soon" if days_until_review <= 7 else "📅 Upcoming"

        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color.lstrip("#"),
            "summary": f"Review Reminder: DECISION-{decision.decision_number}",
            "sections": [
                {
                    "activityTitle": f"📅 Review Reminder ({urgency})",
                    "activitySubtitle": f"DECISION-{decision.decision_number}: {title}",
                    "activityImage": "https://app.imputable.io/icons/reminder.png",
                    "text": f"This decision is due for review in **{days_until_review} day{'s' if days_until_review != 1 else ''}**.",
                    "facts": [
                        {"name": "Review Date", "value": decision.review_by_date.strftime('%b %d, %Y') if decision.review_by_date else "Not set"},
                    ],
                    "markdown": True
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "Review Now",
                    "targets": [
                        {"os": "default", "uri": decision_url}
                    ]
                }
            ]
        }

        await self._send_teams_message(org, card)

    # =========================================================================
    # TEST NOTIFICATIONS
    # =========================================================================

    async def send_test_slack(self, org: Organization):
        """Send a test notification to Slack."""
        decision_url = "https://app.imputable.io/decisions/test"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎉 Test Notification",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Imputable is connected to {org.slack_team_name}!*\n\nYou'll receive notifications here when decisions are created, updated, or need review."
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Organization:*\n{org.name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Channel:*\n#{org.slack_channel_name or 'Default'}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Connected at {datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')}"
                    }
                ]
            }
        ]

        await self._send_slack_message(org, blocks, "Imputable test notification", "6366f1")

    async def send_test_teams(self, org: Organization):
        """Send a test notification to Teams."""
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "6366f1",
            "summary": "Imputable Test Notification",
            "sections": [
                {
                    "activityTitle": "🎉 Test Notification",
                    "activitySubtitle": f"Imputable is connected to {org.name}!",
                    "activityImage": "https://app.imputable.io/logo.png",
                    "text": "You'll receive notifications here when decisions are created, updated, or need review.",
                    "facts": [
                        {"name": "Organization", "value": org.name},
                        {"name": "Channel", "value": org.teams_channel_name or "Default"},
                        {"name": "Connected at", "value": datetime.utcnow().strftime('%b %d, %Y at %H:%M UTC')},
                    ],
                    "markdown": True
                }
            ]
        }

        await self._send_teams_message(org, card)

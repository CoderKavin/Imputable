"""
Slack Service: Complete slash command routing, modals, and interactions.

Handles:
- /decisions command routing (add, list, help, main menu)
- Modal views (create decision form)
- View submission handling
- Block Kit builders
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import (
    Decision,
    DecisionStatus,
    DecisionVersion,
    ImpactLevel,
    Organization,
    OrganizationMember,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# BLOCK KIT BUILDERS
# =============================================================================


class SlackBlocks:
    """Factory for creating Slack Block Kit structures."""

    @staticmethod
    def main_menu() -> list[dict]:
        """Build the main menu blocks with action buttons."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Welcome to Imputable* :clipboard:\nManage your engineering decisions directly from Slack."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Create Decision",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "open_create_decision_modal",
                        "value": "create"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Decisions",
                            "emoji": True
                        },
                        "action_id": "list_decisions",
                        "value": "list"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Help",
                            "emoji": True
                        },
                        "action_id": "show_help",
                        "value": "help"
                    }
                ]
            }
        ]

    @staticmethod
    def help_message() -> list[dict]:
        """Build the help message blocks."""
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Imputable Slash Commands* :book:"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "`/decisions` - Open the main menu\n"
                        "`/decisions add <title>` - Create a new decision\n"
                        "`/decisions create <title>` - Create a new decision\n"
                        "`/decisions list` - View recent decisions\n"
                        "`/decisions show` - View recent decisions\n"
                        "`/decisions help` - Show this help message"
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Example: `/decisions add Use PostgreSQL for analytics`"
                    }
                ]
            }
        ]

    @staticmethod
    def decision_list(decisions: list[dict]) -> list[dict]:
        """Build the decision list blocks."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Recent Decisions* :clipboard:"
                }
            },
            {
                "type": "divider"
            }
        ]

        if not decisions:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No decisions found. Create one with `/decisions add <title>`_"
                }
            })
        else:
            for decision in decisions[:10]:  # Limit to 10
                status_emoji = {
                    "draft": ":pencil2:",
                    "pending_review": ":hourglass:",
                    "approved": ":white_check_mark:",
                    "deprecated": ":package:",
                    "superseded": ":arrows_counterclockwise:",
                    "at_risk": ":warning:",
                }.get(decision.get("status", "draft"), ":page_facing_up:")

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status_emoji} *DEC-{decision.get('number')}* | {decision.get('title')}"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View",
                            "emoji": True
                        },
                        "url": decision.get("url", "#"),
                        "action_id": f"view_decision_{decision.get('id')}"
                    }
                })
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Status: *{decision.get('status', 'draft').replace('_', ' ').title()}* | Created: {decision.get('created_at', 'Unknown')}"
                        }
                    ]
                })

        return blocks

    @staticmethod
    def decision_created(
        decision_number: int,
        title: str,
        decision_id: str,
        user_id: str,
    ) -> list[dict]:
        """Build the decision created confirmation blocks."""
        decision_url = f"{settings.frontend_url}/decisions/{decision_id}"

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":white_check_mark: *Decision Created Successfully*\n\n`DEC-{decision_number}` {title}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Created by <@{user_id}> | Status: *Draft*"
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
                            "text": "View & Edit",
                            "emoji": True
                        },
                        "style": "primary",
                        "url": decision_url,
                        "action_id": "view_decision"
                    }
                ]
            }
        ]


class SlackModals:
    """Factory for creating Slack Modal views."""

    @staticmethod
    def create_decision(prefill_title: str = "", channel_id: str = "") -> dict:
        """Build the create decision modal view."""
        return {
            "type": "modal",
            "callback_id": "create_decision_modal",
            "private_metadata": channel_id,  # Store channel_id for source tracking
            "title": {
                "type": "plain_text",
                "text": "Create Decision",
                "emoji": True
            },
            "submit": {
                "type": "plain_text",
                "text": "Create",
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
                "emoji": True
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": "title_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "e.g., Use PostgreSQL for analytics service"
                        },
                        "initial_value": prefill_title,
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Decision Title",
                        "emoji": True
                    },
                    "hint": {
                        "type": "plain_text",
                        "text": "A clear, concise title for the decision"
                    }
                },
                {
                    "type": "input",
                    "block_id": "context_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "context_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "What problem are we solving? What's the background?"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Context",
                        "emoji": True
                    },
                    "optional": True,
                    "hint": {
                        "type": "plain_text",
                        "text": "Background and problem statement"
                    }
                },
                {
                    "type": "input",
                    "block_id": "choice_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "choice_input",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "What did we decide to do?"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Decision",
                        "emoji": True
                    },
                    "optional": True,
                    "hint": {
                        "type": "plain_text",
                        "text": "The actual decision being made"
                    }
                },
                {
                    "type": "input",
                    "block_id": "impact_block",
                    "element": {
                        "type": "static_select",
                        "action_id": "impact_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select impact level"
                        },
                        "initial_option": {
                            "text": {
                                "type": "plain_text",
                                "text": "Medium"
                            },
                            "value": "medium"
                        },
                        "options": [
                            {
                                "text": {"type": "plain_text", "text": "Low"},
                                "value": "low"
                            },
                            {
                                "text": {"type": "plain_text", "text": "Medium"},
                                "value": "medium"
                            },
                            {
                                "text": {"type": "plain_text", "text": "High"},
                                "value": "high"
                            },
                            {
                                "text": {"type": "plain_text", "text": "Critical"},
                                "value": "critical"
                            }
                        ]
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Impact Level",
                        "emoji": True
                    }
                },
                {
                    "type": "input",
                    "block_id": "tags_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "tags_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "backend, database, infrastructure"
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Tags (comma-separated)",
                        "emoji": True
                    },
                    "optional": True
                }
            ]
        }

    @staticmethod
    def main_menu_modal() -> dict:
        """Build the main menu as a modal."""
        return {
            "type": "modal",
            "callback_id": "main_menu_modal",
            "title": {
                "type": "plain_text",
                "text": "Imputable",
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Close",
                "emoji": True
            },
            "blocks": SlackBlocks.main_menu()
        }


# =============================================================================
# COMMAND ROUTER
# =============================================================================


class SlackCommandRouter:
    """
    Routes /decisions slash commands based on text input.

    Supported intents:
    - Empty: Show main menu modal
    - add/create <title>: Open create decision modal with prefilled title
    - list/show: Show recent decisions
    - help: Show help message
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def parse_intent(self, text: str) -> tuple[str, str]:
        """
        Parse the command text to determine intent.

        Returns: (intent, argument)
        """
        text = text.strip().lower()

        if not text:
            return ("menu", "")

        if text == "help":
            return ("help", "")

        if text in ("list", "show"):
            return ("list", "")

        if text.startswith("list ") or text.startswith("show "):
            return ("list", text.split(" ", 1)[1] if " " in text else "")

        if text.startswith("add ") or text.startswith("create "):
            # Extract the title after the keyword
            parts = text.split(" ", 1)
            title = parts[1] if len(parts) > 1 else ""
            return ("add", title)

        # Default: treat entire text as a title for quick creation
        return ("add", text)

    async def route(
        self,
        text: str,
        team_id: str,
        user_id: str,
        trigger_id: str,
        channel_id: str,
    ) -> dict[str, Any]:
        """
        Route the command to the appropriate handler.

        Returns the Slack response payload.
        """
        intent, argument = self.parse_intent(text)

        # Find organization
        org = await self._get_organization(team_id)
        if not org:
            return {
                "response_type": "ephemeral",
                "text": ":warning: This Slack workspace is not connected to Imputable. Please install the app first.",
            }

        if intent == "menu":
            return await self._handle_menu(trigger_id)

        elif intent == "help":
            return self._handle_help()

        elif intent == "list":
            return await self._handle_list(org)

        elif intent == "add":
            return await self._handle_add(trigger_id, argument, channel_id)

        return self._handle_help()

    async def _get_organization(self, team_id: str) -> Organization | None:
        """Get organization by Slack team ID."""
        result = await self.session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        return result.scalar_one_or_none()

    async def _handle_menu(self, trigger_id: str) -> dict:
        """Open the main menu modal."""
        # Open modal via Slack API
        await self._open_modal(trigger_id, SlackModals.main_menu_modal())

        # Return empty acknowledgment (modal handles the rest)
        return {"response_type": "ephemeral", "text": ""}

    def _handle_help(self) -> dict:
        """Return help message."""
        return {
            "response_type": "ephemeral",
            "blocks": SlackBlocks.help_message(),
        }

    async def _handle_list(self, org: Organization) -> dict:
        """Fetch and return recent decisions."""
        # Query recent decisions
        result = await self.session.execute(
            select(Decision)
            .where(Decision.organization_id == org.id)
            .where(Decision.deleted_at.is_(None))
            .order_by(Decision.created_at.desc())
            .limit(10)
        )
        decisions_db = result.scalars().all()

        # Format for Block Kit
        decisions = []
        for d in decisions_db:
            # Get current version for title
            if d.current_version:
                title = d.current_version.title
            else:
                title = "Untitled"

            decisions.append({
                "id": str(d.id),
                "number": d.decision_number,
                "title": title,
                "status": d.status.value if d.status else "draft",
                "url": f"{settings.frontend_url}/decisions/{d.id}",
                "created_at": d.created_at.strftime("%b %d, %Y") if d.created_at else "Unknown",
            })

        return {
            "response_type": "ephemeral",
            "blocks": SlackBlocks.decision_list(decisions),
        }

    async def _handle_add(self, trigger_id: str, prefill_title: str, channel_id: str = "") -> dict:
        """Open the create decision modal with prefilled title."""
        modal = SlackModals.create_decision(prefill_title=prefill_title, channel_id=channel_id)
        await self._open_modal(trigger_id, modal)

        return {"response_type": "ephemeral", "text": ""}

    async def _open_modal(self, trigger_id: str, view: dict) -> bool:
        """Open a Slack modal using the views.open API."""
        if not settings.slack_enabled:
            logger.error("Slack not configured")
            return False

        # We need the bot token to open modals
        # For now, we'll need to get it from the org
        # In production, you'd want to store and decrypt the token

        # This is a placeholder - in your actual implementation,
        # you'd get the decrypted token from the organization
        logger.warning("Modal opening requires bot token - implement token retrieval")
        return False


# =============================================================================
# SUBMISSION HANDLER
# =============================================================================


class SlackSubmissionHandler:
    """Handles view submissions from Slack modals."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def handle_create_decision(
        self,
        payload: dict,
        team_id: str,
        user_id: str,
    ) -> dict | None:
        """
        Handle the create_decision_modal submission.

        Returns: Error response dict if validation fails, None on success.
        """
        # Extract values from the submission
        values = payload.get("view", {}).get("state", {}).get("values", {})

        # Extract channel_id from private_metadata (for source tracking)
        channel_id = payload.get("view", {}).get("private_metadata", "") or ""

        title = values.get("title_block", {}).get("title_input", {}).get("value", "").strip()
        context = values.get("context_block", {}).get("context_input", {}).get("value", "") or ""
        choice = values.get("choice_block", {}).get("choice_input", {}).get("value", "") or ""
        impact = values.get("impact_block", {}).get("impact_select", {}).get("selected_option", {}).get("value", "medium")
        tags_str = values.get("tags_block", {}).get("tags_input", {}).get("value", "") or ""

        # Validation
        if not title:
            return {
                "response_action": "errors",
                "errors": {
                    "title_block": "Please enter a decision title"
                }
            }

        # Get organization
        result = await self.session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        org = result.scalar_one_or_none()

        if not org:
            return {
                "response_action": "errors",
                "errors": {
                    "title_block": "Organization not found. Please reinstall the app."
                }
            }

        # Get admin user for attribution
        admin_result = await self.session.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
            .where(OrganizationMember.role == "admin")
            .limit(1)
        )
        admin_member = admin_result.scalar_one_or_none()

        if not admin_member:
            return {
                "response_action": "errors",
                "errors": {
                    "title_block": "No admin found for this organization."
                }
            }

        # Parse tags
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        tags.append("slack-created")

        # Map impact level
        impact_map = {
            "low": ImpactLevel.LOW,
            "medium": ImpactLevel.MEDIUM,
            "high": ImpactLevel.HIGH,
            "critical": ImpactLevel.CRITICAL,
        }
        impact_level = impact_map.get(impact, ImpactLevel.MEDIUM)

        # =====================================================================
        # DATABASE: Create Decision
        # =====================================================================

        # Get next decision number
        max_num_result = await self.session.execute(
            select(func.max(Decision.decision_number))
            .where(Decision.organization_id == org.id)
        )
        max_num = max_num_result.scalar() or 0

        # Create the decision with Slack source tracking
        decision = Decision(
            organization_id=org.id,
            decision_number=max_num + 1,
            status=DecisionStatus.DRAFT,
            created_by=admin_member.user_id,
            source="slack",
            slack_channel_id=channel_id if channel_id else None,
        )
        self.session.add(decision)
        await self.session.flush()

        # Create initial version
        version = DecisionVersion(
            decision_id=decision.id,
            version_number=1,
            title=title,
            impact_level=impact_level,
            content={
                "context": context or f"Created via Slack by user {user_id}",
                "choice": choice,
                "rationale": "",
                "alternatives": [],
            },
            tags=tags,
            created_by=admin_member.user_id,
            change_summary="Created via Slack",
        )
        self.session.add(version)
        await self.session.flush()

        # Link current version
        decision.current_version_id = version.id

        await self.session.commit()

        logger.info(f"Decision DEC-{decision.decision_number} created via Slack for org {org.id}")

        # =====================================================================
        # SUCCESS: Send DM confirmation
        # =====================================================================

        # TODO: Send DM to user confirming creation
        # This requires the bot token and chat.postMessage API
        # await self._send_dm(user_id, decision, org)

        # Return None to close the modal (success)
        return None

    async def _send_dm(self, user_id: str, decision: Decision, org: Organization):
        """Send a DM to the user confirming decision creation."""
        # Placeholder - implement with decrypted bot token
        pass


# =============================================================================
# INTERACTION HANDLER
# =============================================================================


class SlackInteractionHandler:
    """Handles button clicks and other interactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def handle(self, payload: dict) -> dict | None:
        """
        Route interaction to appropriate handler.

        Returns response dict or None.
        """
        action_type = payload.get("type")

        if action_type == "view_submission":
            callback_id = payload.get("view", {}).get("callback_id")

            if callback_id == "create_decision_modal":
                handler = SlackSubmissionHandler(self.session)
                return await handler.handle_create_decision(
                    payload,
                    team_id=payload.get("team", {}).get("id"),
                    user_id=payload.get("user", {}).get("id"),
                )

        elif action_type == "block_actions":
            actions = payload.get("actions", [])
            for action in actions:
                action_id = action.get("action_id")

                if action_id == "open_create_decision_modal":
                    # Open create modal
                    trigger_id = payload.get("trigger_id")
                    # TODO: Open modal with trigger_id
                    pass

                elif action_id == "list_decisions":
                    # Return decision list
                    # TODO: Fetch and return decisions
                    pass

                elif action_id == "show_help":
                    return {
                        "response_type": "ephemeral",
                        "blocks": SlackBlocks.help_message(),
                    }

        return None

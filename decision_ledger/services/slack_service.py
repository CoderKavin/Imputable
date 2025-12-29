"""
Slack Service: Complete slash command routing, modals, and interactions.

Handles:
- /decisions command routing (add, list, search, poll, help, main menu)
- Message shortcuts (Log as Decision)
- Consensus polling with vote buttons
- Modal views (create decision form, log message form)
- View submission handling
- Block Kit builders
"""

import json
import logging
import re
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models import (
    Decision,
    DecisionStatus,
    DecisionVersion,
    ImpactLevel,
    LoggedMessage,
    Organization,
    OrganizationMember,
    PollVote,
    PollVoteType,
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
                        "`/decisions list` - View recent decisions\n"
                        "`/decisions search <keyword>` - Search for decisions\n"
                        "`/decisions poll <DECISION-123 or question>` - Start a consensus poll\n"
                        "`/decisions help` - Show this help message\n\n"
                        "*Message Actions:*\n"
                        "Right-click any message → *Log as Decision* to capture it"
                    )
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Examples:\n`/decisions add Use PostgreSQL for analytics`\n`/decisions search database`\n`/decisions poll DECISION-42`"
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
                        "text": f"{status_emoji} *DECISION-{decision.get('number')}* | {decision.get('title')}"
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
                    "text": f":white_check_mark: *Decision Created Successfully*\n\n`DECISION-{decision_number}` {title}"
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

    @staticmethod
    def search_results(query: str, decisions: list[tuple]) -> list[dict]:
        """Build search results blocks (ephemeral response)."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Search Results for \"{query}\"",
                    "emoji": True
                }
            },
            {"type": "divider"}
        ]

        if not decisions:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":mag: No decisions found matching \"{query}\"\n\nTry a different search term or use `/decisions list` to see recent decisions."
                }
            })
            return blocks

        for decision, version in decisions[:5]:  # Limit to 5 results
            status_emoji = {
                "draft": ":pencil2:",
                "pending_review": ":hourglass:",
                "approved": ":white_check_mark:",
                "deprecated": ":package:",
                "superseded": ":arrows_counterclockwise:",
                "at_risk": ":warning:",
            }.get(decision.status.value if decision.status else "draft", ":page_facing_up:")

            decision_url = f"{settings.frontend_url}/decisions/{decision.id}"
            created_date = decision.created_at.strftime("%b %d, %Y") if decision.created_at else "Unknown"
            status_text = decision.status.value.replace("_", " ").title() if decision.status else "Draft"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *<{decision_url}|DECISION-{decision.decision_number}: {version.title}>*\n_{status_text}_ | {created_date}"
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View", "emoji": True},
                    "url": decision_url,
                    "action_id": f"view_decision_{decision.id}"
                }
            })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Showing top {min(len(decisions), 5)} results"}
            ]
        })

        return blocks

    @staticmethod
    def consensus_poll(
        decision_id: str,
        decision_number: int,
        title: str,
        votes: dict[str, int],
        voters: dict[str, list[str]],
    ) -> list[dict]:
        """Build consensus poll blocks with vote buttons."""
        decision_url = f"{settings.frontend_url}/decisions/{decision_id}"

        # Build voter lists for display
        agree_list = ", ".join(voters.get("agree", [])) or "_No votes yet_"
        concern_list = ", ".join(voters.get("concern", [])) or "_No votes yet_"
        block_list = ", ".join(voters.get("block", [])) or "_No votes yet_"

        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Consensus Poll: DECISION-{decision_number}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n\nVote on this decision:"
                }
            },
            {
                "type": "actions",
                "block_id": f"poll_{decision_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f"Agree ({votes.get('agree', 0)})", "emoji": True},
                        "style": "primary",
                        "action_id": "poll_vote_agree",
                        "value": decision_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f"Concern ({votes.get('concern', 0)})", "emoji": True},
                        "action_id": "poll_vote_concern",
                        "value": decision_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f"Block ({votes.get('block', 0)})", "emoji": True},
                        "style": "danger",
                        "action_id": "poll_vote_block",
                        "value": decision_id,
                    },
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":white_check_mark: *Agree:* {agree_list}"},
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":thinking_face: *Concerns:* {concern_list}"},
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":no_entry: *Blocking:* {block_list}"},
                ]
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"<{decision_url}|View full decision in Imputable>"}
                ]
            }
        ]

    @staticmethod
    def message_logged_as_decision(
        decision_number: int,
        title: str,
        decision_id: str,
        user_id: str,
        source_link: str | None = None,
    ) -> list[dict]:
        """Build confirmation blocks when a message is logged as a decision."""
        decision_url = f"{settings.frontend_url}/decisions/{decision_id}"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":clipboard: *Message Logged as Decision*\n\n`DECISION-{decision_number}` {title}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Logged by <@{user_id}> | Status: *Draft*"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View & Edit", "emoji": True},
                        "style": "primary",
                        "url": decision_url,
                        "action_id": "view_decision"
                    }
                ]
            }
        ]

        return blocks

    @staticmethod
    def duplicate_message_warning(
        decision_number: int,
        title: str,
        decision_id: str,
    ) -> list[dict]:
        """Build warning blocks when a message has already been logged."""
        decision_url = f"{settings.frontend_url}/decisions/{decision_id}"

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *This message has already been logged*\n\nExisting decision: `DECISION-{decision_number}` {title}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Existing Decision", "emoji": True},
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

    @staticmethod
    def log_message_modal(
        prefill_title: str,
        message_text: str,
        author_name: str,
        permalink: str | None,
        channel_id: str,
        message_ts: str,
        thread_ts: str | None,
    ) -> dict:
        """Build modal for logging a Slack message as a decision."""
        # Store metadata for processing
        metadata = json.dumps({
            "channel_id": channel_id,
            "message_ts": message_ts,
            "thread_ts": thread_ts,
            "permalink": permalink,
            "author_name": author_name,
        })

        # Truncate message for display
        display_message = message_text[:500] + "..." if len(message_text) > 500 else message_text

        return {
            "type": "modal",
            "callback_id": "log_message_modal",
            "private_metadata": metadata,
            "title": {
                "type": "plain_text",
                "text": "Log as Decision",
                "emoji": True
            },
            "submit": {
                "type": "plain_text",
                "text": "Save Decision",
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
                "emoji": True
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Original Message:*\n>{display_message}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"From: *{author_name}*"}
                    ]
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "title_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title_input",
                        "initial_value": prefill_title[:150],  # Slack limit
                        "placeholder": {"type": "plain_text", "text": "Decision title"}
                    },
                    "label": {"type": "plain_text", "text": "Decision Title", "emoji": True}
                },
                {
                    "type": "input",
                    "block_id": "context_block",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "context_input",
                        "multiline": True,
                        "initial_value": f"Captured from Slack discussion.\n\nOriginal message by {author_name}:\n{message_text[:1000]}",
                        "placeholder": {"type": "plain_text", "text": "Additional context"}
                    },
                    "label": {"type": "plain_text", "text": "Context", "emoji": True}
                },
                {
                    "type": "input",
                    "block_id": "impact_block",
                    "element": {
                        "type": "static_select",
                        "action_id": "impact_select",
                        "initial_option": {
                            "text": {"type": "plain_text", "text": "Medium"},
                            "value": "medium"
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Low"}, "value": "low"},
                            {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                            {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                            {"text": {"type": "plain_text", "text": "Critical"}, "value": "critical"},
                        ]
                    },
                    "label": {"type": "plain_text", "text": "Impact Level", "emoji": True}
                },
            ]
        }

    @staticmethod
    def ai_prefilled_modal(
        analysis: "AIAnalysisResult",
        channel_id: str,
        message_ts: str,
        thread_ts: str | None,
    ) -> dict:
        """
        Build modal pre-filled with AI-analyzed decision content.

        Shows AI confidence score and allows user to verify/edit.
        """
        from .ai_analyzer import AIAnalysisResult

        # Format alternatives for display
        alternatives_text = ""
        if analysis.alternatives:
            alt_lines = []
            for alt in analysis.alternatives[:5]:  # Max 5 alternatives
                alt_lines.append(f"- {alt.get('name', 'Unknown')}: {alt.get('rejected_reason', 'No reason given')}")
            alternatives_text = "\n".join(alt_lines)

        # Format dissenters
        dissenters_text = ", ".join(analysis.key_dissenters[:5]) if analysis.key_dissenters else "None identified"

        # Format deadlines
        deadlines_text = ", ".join(analysis.deadlines[:3]) if analysis.deadlines else "None mentioned"

        # Confidence display
        confidence_pct = int(analysis.confidence_score * 100)
        if confidence_pct >= 80:
            confidence_emoji = ":white_check_mark:"
            confidence_text = "High confidence"
        elif confidence_pct >= 50:
            confidence_emoji = ":large_yellow_circle:"
            confidence_text = "Medium confidence"
        else:
            confidence_emoji = ":warning:"
            confidence_text = "Low confidence - please review carefully"

        # Map impact to display text
        impact_map = {
            "low": {"text": "Low", "value": "low"},
            "medium": {"text": "Medium", "value": "medium"},
            "high": {"text": "High", "value": "high"},
            "critical": {"text": "Critical", "value": "critical"},
        }
        impact_option = impact_map.get(analysis.suggested_impact, impact_map["medium"])

        # Store metadata including AI analysis info
        metadata = json.dumps({
            "channel_id": channel_id,
            "message_ts": message_ts,
            "thread_ts": thread_ts,
            "ai_generated": True,
            "confidence_score": analysis.confidence_score,
            "suggested_status": analysis.suggested_status,
        })

        blocks = [
            # AI confidence banner
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{confidence_emoji} *AI Analysis Complete* ({confidence_pct}% confidence)\n_{confidence_text}_"
                }
            },
            {"type": "divider"},
            # Title
            {
                "type": "input",
                "block_id": "title_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_input",
                    "initial_value": analysis.title[:150],
                    "placeholder": {"type": "plain_text", "text": "Decision title"}
                },
                "label": {"type": "plain_text", "text": "Decision Title", "emoji": True}
            },
            # Context
            {
                "type": "input",
                "block_id": "context_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "context_input",
                    "multiline": True,
                    "initial_value": analysis.context[:3000],
                    "placeholder": {"type": "plain_text", "text": "Background and problem statement"}
                },
                "label": {"type": "plain_text", "text": "Context (Problem)", "emoji": True}
            },
            # Choice/Decision
            {
                "type": "input",
                "block_id": "choice_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "choice_input",
                    "multiline": True,
                    "initial_value": analysis.choice[:3000],
                    "placeholder": {"type": "plain_text", "text": "What was decided"}
                },
                "label": {"type": "plain_text", "text": "Decision (What)", "emoji": True}
            },
            # Rationale
            {
                "type": "input",
                "block_id": "rationale_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "rationale_input",
                    "multiline": True,
                    "initial_value": analysis.rationale[:3000],
                    "placeholder": {"type": "plain_text", "text": "Why this choice was made"}
                },
                "label": {"type": "plain_text", "text": "Rationale (Why)", "emoji": True}
            },
            # Alternatives
            {
                "type": "input",
                "block_id": "alternatives_block",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "alternatives_input",
                    "multiline": True,
                    "initial_value": alternatives_text[:3000],
                    "placeholder": {"type": "plain_text", "text": "- Option: Reason rejected"}
                },
                "label": {"type": "plain_text", "text": "Alternatives Considered", "emoji": True},
                "hint": {"type": "plain_text", "text": "Format: - Option: Reason rejected"}
            },
            # Impact level
            {
                "type": "input",
                "block_id": "impact_block",
                "element": {
                    "type": "static_select",
                    "action_id": "impact_select",
                    "initial_option": {
                        "text": {"type": "plain_text", "text": impact_option["text"]},
                        "value": impact_option["value"]
                    },
                    "options": [
                        {"text": {"type": "plain_text", "text": "Low"}, "value": "low"},
                        {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                        {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                        {"text": {"type": "plain_text", "text": "Critical"}, "value": "critical"},
                    ]
                },
                "label": {"type": "plain_text", "text": "Impact Level", "emoji": True}
            },
            {"type": "divider"},
            # Discussion metadata (read-only context)
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":busts_in_silhouette: *Key Dissenters:* {dissenters_text}"},
                ]
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":calendar: *Deadlines Mentioned:* {deadlines_text}"},
                ]
            },
        ]

        # Add suggested status context
        status_emoji = {
            "approved": ":white_check_mark:",
            "pending_review": ":hourglass:",
            "draft": ":pencil2:",
        }
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"{status_emoji.get(analysis.suggested_status, ':pencil2:')} *Suggested Status:* {analysis.suggested_status.replace('_', ' ').title()}"},
            ]
        })

        return {
            "type": "modal",
            "callback_id": "ai_decision_modal",
            "private_metadata": metadata,
            "title": {
                "type": "plain_text",
                "text": "AI Decision Draft",
                "emoji": True
            },
            "submit": {
                "type": "plain_text",
                "text": "Save to Imputable",
                "emoji": True
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
                "emoji": True
            },
            "blocks": blocks
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
    - search <query>: Search for decisions
    - poll <DECISION-123 or question>: Start a consensus poll
    - help: Show help message
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def parse_intent(self, text: str) -> tuple[str, str]:
        """
        Parse the command text to determine intent.

        Returns: (intent, argument)
        """
        text = text.strip()
        text_lower = text.lower()

        if not text:
            return ("menu", "")

        if text_lower == "help":
            return ("help", "")

        if text_lower in ("list", "show"):
            return ("list", "")

        if text_lower.startswith("list ") or text_lower.startswith("show "):
            return ("list", text.split(" ", 1)[1] if " " in text else "")

        if text_lower.startswith("search "):
            # Extract the search query (preserve original case)
            parts = text.split(" ", 1)
            query = parts[1].strip() if len(parts) > 1 else ""
            return ("search", query)

        if text_lower.startswith("poll "):
            # Extract the poll argument (decision number or question)
            parts = text.split(" ", 1)
            argument = parts[1].strip() if len(parts) > 1 else ""
            return ("poll", argument)

        if text_lower.startswith("add ") or text_lower.startswith("create "):
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

        elif intent == "search":
            return await self._handle_search(org, argument)

        elif intent == "poll":
            return await self._handle_poll(org, argument, channel_id, user_id)

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

    async def _handle_search(self, org: Organization, query: str) -> dict:
        """Search decisions and return ephemeral results."""
        if not query or len(query) < 2:
            return {
                "response_type": "ephemeral",
                "text": ":mag: Please provide a search term (at least 2 characters).\n\nExample: `/decisions search database`"
            }

        # Search in title and content
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(Decision, DecisionVersion)
            .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
            .where(Decision.organization_id == org.id)
            .where(Decision.deleted_at.is_(None))
            .where(
                or_(
                    DecisionVersion.title.ilike(search_pattern),
                    DecisionVersion.content["context"].astext.ilike(search_pattern),
                    DecisionVersion.content["choice"].astext.ilike(search_pattern),
                    DecisionVersion.content["rationale"].astext.ilike(search_pattern),
                )
            )
            .order_by(Decision.created_at.desc())
            .limit(5)
        )

        decisions = result.all()

        return {
            "response_type": "ephemeral",
            "blocks": SlackBlocks.search_results(query, decisions),
        }

    async def _handle_poll(
        self,
        org: Organization,
        argument: str,
        channel_id: str,
        user_id: str,
    ) -> dict:
        """
        Handle /decisions poll <DECISION-123> or /decisions poll "Question text"

        If a decision number is provided, creates poll for that decision.
        If question text, creates a new draft decision and poll.
        """
        if not argument:
            return {
                "response_type": "ephemeral",
                "text": ":ballot_box: Please provide a decision number or question.\n\nExamples:\n`/decisions poll DECISION-42`\n`/decisions poll Should we use PostgreSQL?`"
            }

        # Check if it's a decision reference (DECISION-123 or just 123)
        match = re.match(r"(?:DECISION-)?(\d+)", argument, re.IGNORECASE)

        if match:
            decision_number = int(match.group(1))
            # Find existing decision
            result = await self.session.execute(
                select(Decision)
                .where(Decision.organization_id == org.id)
                .where(Decision.decision_number == decision_number)
                .where(Decision.deleted_at.is_(None))
            )
            decision = result.scalar_one_or_none()

            if not decision:
                return {
                    "response_type": "ephemeral",
                    "text": f":x: Decision DECISION-{decision_number} not found."
                }

            title = decision.current_version.title if decision.current_version else "Untitled"
        else:
            # Create new decision from poll question
            decision, title = await self._create_decision_from_poll(
                org=org,
                title=argument,
                creator_slack_id=user_id,
                channel_id=channel_id,
            )

        # Get current vote counts
        votes, voters = await self._get_vote_summary(str(decision.id))

        # Build and send poll message (in_channel so everyone can see and vote)
        return {
            "response_type": "in_channel",
            "blocks": SlackBlocks.consensus_poll(
                decision_id=str(decision.id),
                decision_number=decision.decision_number,
                title=title,
                votes=votes,
                voters=voters,
            ),
        }

    async def _create_decision_from_poll(
        self,
        org: Organization,
        title: str,
        creator_slack_id: str,
        channel_id: str,
    ) -> tuple[Decision, str]:
        """Create a new decision from a poll question."""
        # Get admin user for attribution
        admin_result = await self.session.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
            .where(OrganizationMember.role.in_(["admin", "owner"]))
            .limit(1)
        )
        admin_member = admin_result.scalar_one_or_none()

        if not admin_member:
            # Fallback to any member
            member_result = await self.session.execute(
                select(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
                .limit(1)
            )
            admin_member = member_result.scalar_one()

        # Get next decision number
        max_num_result = await self.session.execute(
            select(func.max(Decision.decision_number))
            .where(Decision.organization_id == org.id)
        )
        max_num = max_num_result.scalar() or 0

        # Create decision
        decision = Decision(
            organization_id=org.id,
            decision_number=max_num + 1,
            status=DecisionStatus.DRAFT,
            created_by=admin_member.user_id,
            source="slack",
            slack_channel_id=channel_id,
        )
        self.session.add(decision)
        await self.session.flush()

        # Create initial version
        version = DecisionVersion(
            decision_id=decision.id,
            version_number=1,
            title=title,
            impact_level=ImpactLevel.MEDIUM,
            content={
                "context": f"Created via Slack poll by user <@{creator_slack_id}>",
                "choice": "",
                "rationale": "",
                "alternatives": [],
            },
            tags=["slack-poll"],
            created_by=admin_member.user_id,
            change_summary="Created via Slack poll",
        )
        self.session.add(version)
        await self.session.flush()

        # Link current version
        decision.current_version_id = version.id
        await self.session.commit()

        logger.info(f"Decision DECISION-{decision.decision_number} created via Slack poll for org {org.id}")

        return decision, title

    async def _get_vote_summary(self, decision_id: str) -> tuple[dict[str, int], dict[str, list[str]]]:
        """Get vote counts and voter names for a decision."""
        result = await self.session.execute(
            select(PollVote)
            .where(PollVote.decision_id == UUID(decision_id))
        )
        votes_db = result.scalars().all()

        votes = {"agree": 0, "concern": 0, "block": 0}
        voters: dict[str, list[str]] = {"agree": [], "concern": [], "block": []}

        for vote in votes_db:
            vote_type = vote.vote_type.value
            votes[vote_type] += 1

            # Get display name
            if vote.external_user_name:
                name = vote.external_user_name
            elif vote.external_user_id:
                name = f"<@{vote.external_user_id}>"
            elif vote.user:
                name = vote.user.name
            else:
                name = "Unknown"

            voters[vote_type].append(name)

        return votes, voters

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

        logger.info(f"Decision DECISION-{decision.decision_number} created via Slack for org {org.id}")

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
    """Handles button clicks, modal submissions, and other interactions."""

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

            elif callback_id == "log_message_modal":
                return await self._handle_log_message_submission(payload)

            elif callback_id == "ai_decision_modal":
                return await self._handle_ai_decision_submission(payload)

        elif action_type == "block_actions":
            actions = payload.get("actions", [])
            for action in actions:
                action_id = action.get("action_id")

                # Poll vote buttons
                if action_id.startswith("poll_vote_"):
                    return await self._handle_poll_vote(payload, action)

                elif action_id == "open_create_decision_modal":
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

    async def _handle_log_message_submission(self, payload: dict) -> dict | None:
        """Handle the log_message_modal submission."""
        team_id = payload.get("team", {}).get("id")
        user_id = payload.get("user", {}).get("id")
        values = payload.get("view", {}).get("state", {}).get("values", {})

        # Parse metadata
        metadata_str = payload.get("view", {}).get("private_metadata", "{}")
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}

        channel_id = metadata.get("channel_id", "")
        message_ts = metadata.get("message_ts", "")
        thread_ts = metadata.get("thread_ts")
        permalink = metadata.get("permalink")
        author_name = metadata.get("author_name", "Unknown")

        # Extract form values
        title = values.get("title_block", {}).get("title_input", {}).get("value", "").strip()
        context = values.get("context_block", {}).get("context_input", {}).get("value", "") or ""
        impact = values.get("impact_block", {}).get("impact_select", {}).get("selected_option", {}).get("value", "medium")

        # Validation
        if not title:
            return {
                "response_action": "errors",
                "errors": {"title_block": "Please enter a decision title"}
            }

        # Get organization
        result = await self.session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        org = result.scalar_one_or_none()

        if not org:
            return {
                "response_action": "errors",
                "errors": {"title_block": "Organization not found. Please reinstall the app."}
            }

        # Check for duplicate (message already logged)
        if message_ts and channel_id:
            existing = await self.session.execute(
                select(LoggedMessage)
                .where(LoggedMessage.source == "slack")
                .where(LoggedMessage.message_id == message_ts)
                .where(LoggedMessage.channel_id == channel_id)
            )
            logged = existing.scalar_one_or_none()
            if logged:
                # Already logged - fetch the decision
                decision_result = await self.session.execute(
                    select(Decision).where(Decision.id == logged.decision_id)
                )
                decision = decision_result.scalar_one_or_none()
                if decision:
                    return {
                        "response_action": "errors",
                        "errors": {
                            "title_block": f"This message was already logged as DECISION-{decision.decision_number}"
                        }
                    }

        # Get admin user for attribution
        admin_result = await self.session.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
            .where(OrganizationMember.role.in_(["admin", "owner"]))
            .limit(1)
        )
        admin_member = admin_result.scalar_one_or_none()

        if not admin_member:
            member_result = await self.session.execute(
                select(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
                .limit(1)
            )
            admin_member = member_result.scalar_one_or_none()

        if not admin_member:
            return {
                "response_action": "errors",
                "errors": {"title_block": "No members found for this organization."}
            }

        # Map impact level
        impact_map = {
            "low": ImpactLevel.LOW,
            "medium": ImpactLevel.MEDIUM,
            "high": ImpactLevel.HIGH,
            "critical": ImpactLevel.CRITICAL,
        }
        impact_level = impact_map.get(impact, ImpactLevel.MEDIUM)

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
            slack_message_ts=message_ts if message_ts else None,
            slack_thread_ts=thread_ts if thread_ts else None,
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
                "context": context,
                "choice": "",
                "rationale": "",
                "alternatives": [],
                "slack_permalink": permalink,
                "original_author": author_name,
            },
            tags=["slack-logged"],
            created_by=admin_member.user_id,
            change_summary="Logged from Slack message",
        )
        self.session.add(version)
        await self.session.flush()

        # Link current version
        decision.current_version_id = version.id

        # Record in logged_messages for duplicate detection
        if message_ts and channel_id:
            logged_message = LoggedMessage(
                source="slack",
                message_id=message_ts,
                channel_id=channel_id,
                decision_id=decision.id,
            )
            self.session.add(logged_message)

        await self.session.commit()

        logger.info(f"Decision DECISION-{decision.decision_number} logged from Slack message for org {org.id}")

        # Return None to close the modal (success)
        return None

    async def _handle_ai_decision_submission(self, payload: dict) -> dict | None:
        """Handle the ai_decision_modal submission with AI-generated content."""
        team_id = payload.get("team", {}).get("id")
        user_id = payload.get("user", {}).get("id")
        values = payload.get("view", {}).get("state", {}).get("values", {})

        # Parse metadata
        metadata_str = payload.get("view", {}).get("private_metadata", "{}")
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}

        channel_id = metadata.get("channel_id", "")
        message_ts = metadata.get("message_ts", "")
        thread_ts = metadata.get("thread_ts")
        ai_generated = metadata.get("ai_generated", False)
        confidence_score = metadata.get("confidence_score", 0.0)
        suggested_status = metadata.get("suggested_status", "draft")

        # Extract form values
        title = values.get("title_block", {}).get("title_input", {}).get("value", "").strip()
        context = values.get("context_block", {}).get("context_input", {}).get("value", "") or ""
        choice = values.get("choice_block", {}).get("choice_input", {}).get("value", "") or ""
        rationale = values.get("rationale_block", {}).get("rationale_input", {}).get("value", "") or ""
        alternatives_text = values.get("alternatives_block", {}).get("alternatives_input", {}).get("value", "") or ""
        impact = values.get("impact_block", {}).get("impact_select", {}).get("selected_option", {}).get("value", "medium")

        # Validation
        if not title:
            return {
                "response_action": "errors",
                "errors": {"title_block": "Please enter a decision title"}
            }

        # Parse alternatives from text format
        alternatives = []
        if alternatives_text:
            for line in alternatives_text.strip().split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    line = line[2:]
                if ": " in line:
                    name, reason = line.split(": ", 1)
                    alternatives.append({"name": name.strip(), "rejected_reason": reason.strip()})
                elif line:
                    alternatives.append({"name": line, "rejected_reason": ""})

        # Get organization
        result = await self.session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        org = result.scalar_one_or_none()

        if not org:
            return {
                "response_action": "errors",
                "errors": {"title_block": "Organization not found. Please reinstall the app."}
            }

        # Check for duplicate using thread_ts (for AI we track by thread, not individual message)
        check_ts = thread_ts or message_ts
        if check_ts and channel_id:
            existing = await self.session.execute(
                select(LoggedMessage)
                .where(LoggedMessage.source == "slack")
                .where(LoggedMessage.message_id == check_ts)
                .where(LoggedMessage.channel_id == channel_id)
            )
            logged = existing.scalar_one_or_none()
            if logged:
                decision_result = await self.session.execute(
                    select(Decision).where(Decision.id == logged.decision_id)
                )
                decision = decision_result.scalar_one_or_none()
                if decision:
                    return {
                        "response_action": "errors",
                        "errors": {
                            "title_block": f"This thread was already logged as DECISION-{decision.decision_number}"
                        }
                    }

        # Get admin user for attribution
        admin_result = await self.session.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
            .where(OrganizationMember.role.in_(["admin", "owner"]))
            .limit(1)
        )
        admin_member = admin_result.scalar_one_or_none()

        if not admin_member:
            member_result = await self.session.execute(
                select(OrganizationMember)
                .where(OrganizationMember.organization_id == org.id)
                .limit(1)
            )
            admin_member = member_result.scalar_one_or_none()

        if not admin_member:
            return {
                "response_action": "errors",
                "errors": {"title_block": "No members found for this organization."}
            }

        # Map impact level
        impact_map = {
            "low": ImpactLevel.LOW,
            "medium": ImpactLevel.MEDIUM,
            "high": ImpactLevel.HIGH,
            "critical": ImpactLevel.CRITICAL,
        }
        impact_level = impact_map.get(impact, ImpactLevel.MEDIUM)

        # Map suggested status - user verified so we can use the AI suggestion
        status_map = {
            "draft": DecisionStatus.DRAFT,
            "pending_review": DecisionStatus.PENDING_REVIEW,
            "approved": DecisionStatus.APPROVED,
        }
        # Default to DRAFT for safety, but use AI suggestion if high confidence
        if confidence_score >= 0.8 and suggested_status in status_map:
            decision_status = status_map[suggested_status]
        else:
            decision_status = DecisionStatus.DRAFT

        # Get next decision number
        max_num_result = await self.session.execute(
            select(func.max(Decision.decision_number))
            .where(Decision.organization_id == org.id)
        )
        max_num = max_num_result.scalar() or 0

        # Create the decision with AI metadata
        decision = Decision(
            organization_id=org.id,
            decision_number=max_num + 1,
            status=decision_status,
            created_by=admin_member.user_id,
            source="slack",
            slack_channel_id=channel_id if channel_id else None,
            slack_message_ts=message_ts if message_ts else None,
            slack_thread_ts=thread_ts if thread_ts else None,
        )
        self.session.add(decision)
        await self.session.flush()

        # Create initial version with AI-generated content
        version = DecisionVersion(
            decision_id=decision.id,
            version_number=1,
            title=title,
            impact_level=impact_level,
            content={
                "context": context,
                "choice": choice,
                "rationale": rationale,
                "alternatives": alternatives,
            },
            tags=["ai-generated", "slack-logged"],
            created_by=admin_member.user_id,
            change_summary="AI-analyzed from Slack thread",
            custom_fields={
                "ai_generated": ai_generated,
                "ai_confidence_score": confidence_score,
                "verified_by_user": True,
                "verified_by_slack_user_id": user_id,
            },
        )
        self.session.add(version)
        await self.session.flush()

        # Link current version
        decision.current_version_id = version.id

        # Record in logged_messages for duplicate detection
        if check_ts and channel_id:
            logged_message = LoggedMessage(
                source="slack",
                message_id=check_ts,
                channel_id=channel_id,
                decision_id=decision.id,
            )
            self.session.add(logged_message)

        await self.session.commit()

        logger.info(
            f"AI-generated Decision DECISION-{decision.decision_number} created from Slack thread "
            f"(confidence: {confidence_score:.0%}) for org {org.id}"
        )

        # Return None to close the modal (success)
        return None

    async def _handle_poll_vote(self, payload: dict, action: dict) -> dict | None:
        """Handle a poll vote button click. Updates message in-place."""
        action_id = action.get("action_id", "")
        decision_id = action.get("value", "")

        user_id = payload.get("user", {}).get("id")
        user_name = payload.get("user", {}).get("name") or payload.get("user", {}).get("username", "")
        team_id = payload.get("team", {}).get("id")
        channel_id = payload.get("channel", {}).get("id")
        message_ts = payload.get("message", {}).get("ts")

        if not decision_id or not user_id:
            return None

        # Determine vote type from action_id
        vote_type_str = action_id.replace("poll_vote_", "")  # agree, concern, block
        vote_type_map = {
            "agree": PollVoteType.AGREE,
            "concern": PollVoteType.CONCERN,
            "block": PollVoteType.BLOCK,
        }
        vote_type = vote_type_map.get(vote_type_str)
        if not vote_type:
            return None

        # Upsert vote in database
        existing_vote = await self.session.execute(
            select(PollVote)
            .where(PollVote.decision_id == UUID(decision_id))
            .where(PollVote.external_user_id == user_id)
            .where(PollVote.source == "slack")
        )
        vote = existing_vote.scalar_one_or_none()

        if vote:
            # Update existing vote
            vote.vote_type = vote_type
            vote.external_user_name = user_name
            vote.updated_at = datetime.utcnow()
        else:
            # Create new vote
            vote = PollVote(
                decision_id=UUID(decision_id),
                external_user_id=user_id,
                external_user_name=user_name,
                vote_type=vote_type,
                source="slack",
            )
            self.session.add(vote)

        await self.session.commit()

        # Get updated vote counts
        votes_result = await self.session.execute(
            select(PollVote).where(PollVote.decision_id == UUID(decision_id))
        )
        votes_db = votes_result.scalars().all()

        votes = {"agree": 0, "concern": 0, "block": 0}
        voters: dict[str, list[str]] = {"agree": [], "concern": [], "block": []}

        for v in votes_db:
            vt = v.vote_type.value
            votes[vt] += 1
            name = v.external_user_name or f"<@{v.external_user_id}>" if v.external_user_id else "Unknown"
            voters[vt].append(name)

        # Get decision info
        decision_result = await self.session.execute(
            select(Decision).where(Decision.id == UUID(decision_id))
        )
        decision = decision_result.scalar_one_or_none()

        if not decision:
            return None

        title = decision.current_version.title if decision.current_version else "Untitled"

        # Build updated blocks
        updated_blocks = SlackBlocks.consensus_poll(
            decision_id=decision_id,
            decision_number=decision.decision_number,
            title=title,
            votes=votes,
            voters=voters,
        )

        # Return updated message (Slack will replace the original)
        return {
            "blocks": updated_blocks,
            "replace_original": True,
        }


# =============================================================================
# MESSAGE SHORTCUT HANDLER
# =============================================================================


class SlackMessageShortcutHandler:
    """Handles message shortcuts (actions) triggered from message context menu."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def handle_log_as_decision(
        self,
        payload: dict,
        bot_token: str | None = None,
    ) -> dict:
        """
        Handle the 'log_message_as_decision' shortcut.

        Opens a modal for the user to confirm/edit the decision details.
        """
        message = payload.get("message", {})
        channel = payload.get("channel", {})
        trigger_id = payload.get("trigger_id")
        team_id = payload.get("team", {}).get("id")
        user = payload.get("user", {})

        # Extract message details
        message_text = message.get("text", "")
        message_ts = message.get("ts", "")
        thread_ts = message.get("thread_ts")
        author_id = message.get("user", "")
        channel_id = channel.get("id", "")

        # Get organization
        result = await self.session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        org = result.scalar_one_or_none()

        if not org:
            return {
                "response_type": "ephemeral",
                "text": ":warning: This Slack workspace is not connected to Imputable. Please install the app first.",
            }

        # Check for duplicate
        if message_ts and channel_id:
            existing = await self.session.execute(
                select(LoggedMessage)
                .where(LoggedMessage.source == "slack")
                .where(LoggedMessage.message_id == message_ts)
                .where(LoggedMessage.channel_id == channel_id)
            )
            logged = existing.scalar_one_or_none()
            if logged:
                # Already logged - return info about existing decision
                decision_result = await self.session.execute(
                    select(Decision).where(Decision.id == logged.decision_id)
                )
                decision = decision_result.scalar_one_or_none()
                if decision:
                    title = decision.current_version.title if decision.current_version else "Untitled"
                    return {
                        "response_type": "ephemeral",
                        "blocks": SlackBlocks.duplicate_message_warning(
                            decision_number=decision.decision_number,
                            title=title,
                            decision_id=str(decision.id),
                        ),
                    }

        # Get author name (best effort)
        author_name = f"<@{author_id}>" if author_id else "Unknown"

        # Build permalink (best effort - actual permalink requires API call)
        permalink = None
        if team_id and channel_id and message_ts:
            # Construct approximate permalink
            permalink = f"https://app.slack.com/client/{team_id}/{channel_id}/p{message_ts.replace('.', '')}"

        # Extract a title from the message (first line or first 100 chars)
        first_line = message_text.split("\n")[0] if message_text else ""
        prefill_title = first_line[:100] if first_line else "Decision from Slack"

        # Build modal
        modal = SlackModals.log_message_modal(
            prefill_title=prefill_title,
            message_text=message_text,
            author_name=author_name,
            permalink=permalink,
            channel_id=channel_id,
            message_ts=message_ts,
            thread_ts=thread_ts,
        )

        # Open modal via Slack API (requires bot token)
        if bot_token and trigger_id:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://slack.com/api/views.open",
                        headers={"Authorization": f"Bearer {bot_token}"},
                        json={"trigger_id": trigger_id, "view": modal},
                    )
                    data = response.json()
                    if not data.get("ok"):
                        logger.error(f"Failed to open modal: {data.get('error')}")
                        return {
                            "response_type": "ephemeral",
                            "text": f":x: Failed to open form: {data.get('error', 'Unknown error')}",
                        }
            except Exception as e:
                logger.error(f"Error opening modal: {e}")
                return {
                    "response_type": "ephemeral",
                    "text": ":x: Failed to open form. Please try again.",
                }

        # Return empty response (modal handles the rest)
        return {}

    async def handle_ai_summarize_decision(
        self,
        payload: dict,
        bot_token: str | None = None,
    ) -> dict:
        """
        Handle the 'ai_summarize_decision' shortcut.

        Fetches the entire thread, sends to AI for analysis,
        and opens a pre-filled modal for user verification.
        """
        from .ai_analyzer import AIAnalyzerService, SlackThreadFetcher

        message = payload.get("message", {})
        channel = payload.get("channel", {})
        trigger_id = payload.get("trigger_id")
        team_id = payload.get("team", {}).get("id")
        user = payload.get("user", {})

        message_ts = message.get("ts", "")
        thread_ts = message.get("thread_ts") or message_ts  # Use message as thread root if not in thread
        channel_id = channel.get("id", "")

        # Get organization
        result = await self.session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        org = result.scalar_one_or_none()

        if not org:
            return {
                "response_type": "ephemeral",
                "text": ":warning: This Slack workspace is not connected to Imputable. Please install the app first.",
            }

        # Check for duplicate
        if thread_ts and channel_id:
            existing = await self.session.execute(
                select(LoggedMessage)
                .where(LoggedMessage.source == "slack")
                .where(LoggedMessage.message_id == thread_ts)
                .where(LoggedMessage.channel_id == channel_id)
            )
            logged = existing.scalar_one_or_none()
            if logged:
                decision_result = await self.session.execute(
                    select(Decision).where(Decision.id == logged.decision_id)
                )
                decision = decision_result.scalar_one_or_none()
                if decision:
                    title = decision.current_version.title if decision.current_version else "Untitled"
                    return {
                        "response_type": "ephemeral",
                        "blocks": SlackBlocks.duplicate_message_warning(
                            decision_number=decision.decision_number,
                            title=title,
                            decision_id=str(decision.id),
                        ),
                    }

        if not bot_token:
            return {
                "response_type": "ephemeral",
                "text": ":x: Bot token not available. Please reinstall the app.",
            }

        # Check if AI is configured
        ai_service = AIAnalyzerService()
        if not ai_service.is_configured:
            # Fallback to regular log modal
            return await self.handle_log_as_decision(payload, bot_token)

        try:
            # Fetch the thread
            thread_fetcher = SlackThreadFetcher()

            if thread_ts and thread_ts != message_ts:
                # Fetch full thread
                messages = await thread_fetcher.fetch_thread(bot_token, channel_id, thread_ts)
            else:
                # Just the single message
                msg = await thread_fetcher.fetch_single_message(bot_token, channel_id, message_ts)
                messages = [msg]

            # Resolve user names
            messages = await thread_fetcher.resolve_user_names(bot_token, messages)

            # Get channel name for context
            channel_name = channel.get("name", "")

            # Analyze with AI
            analysis = await ai_service.analyze_thread(messages, channel_name)

            # Build AI-prefilled modal
            modal = SlackModals.ai_prefilled_modal(
                analysis=analysis,
                channel_id=channel_id,
                message_ts=message_ts,
                thread_ts=thread_ts,
            )

            # Open modal
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/views.open",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    json={"trigger_id": trigger_id, "view": modal},
                )
                data = response.json()
                if not data.get("ok"):
                    logger.error(f"Failed to open AI modal: {data.get('error')}")
                    return {
                        "response_type": "ephemeral",
                        "text": f":x: Failed to open form: {data.get('error', 'Unknown error')}",
                    }

            return {}

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Fallback to regular modal
            return await self.handle_log_as_decision(payload, bot_token)

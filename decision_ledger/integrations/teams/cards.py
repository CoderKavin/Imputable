"""Microsoft Teams Adaptive Card builders.

Provides card templates for:
- Consensus polls with vote buttons
- Search results
- Log as Decision form
- Decision confirmation
- Help/menu
"""

from typing import Any

from ...core.config import get_settings

settings = get_settings()


class TeamsCards:
    """Adaptive Card builders for Teams integration."""

    @staticmethod
    def poll_card(
        decision_id: str,
        decision_number: int,
        title: str,
        votes: dict[str, list[str]],
    ) -> dict:
        """
        Build consensus poll Adaptive Card.

        Args:
            decision_id: UUID of the decision
            decision_number: Human-readable decision number
            title: Decision title
            votes: Dict with keys 'agree', 'concern', 'block' mapping to voter names
        """
        agree_count = len(votes.get("agree", []))
        concern_count = len(votes.get("concern", []))
        block_count = len(votes.get("block", []))
        total = agree_count + concern_count + block_count

        # Build voter lists
        vote_details = []
        if votes.get("agree"):
            vote_details.append({
                "type": "TextBlock",
                "text": f"**Agree** ({agree_count}): {', '.join(votes['agree'])}",
                "wrap": True,
                "color": "good",
                "size": "small",
            })
        if votes.get("concern"):
            vote_details.append({
                "type": "TextBlock",
                "text": f"**Concern** ({concern_count}): {', '.join(votes['concern'])}",
                "wrap": True,
                "color": "warning",
                "size": "small",
            })
        if votes.get("block"):
            vote_details.append({
                "type": "TextBlock",
                "text": f"**Block** ({block_count}): {', '.join(votes['block'])}",
                "wrap": True,
                "color": "attention",
                "size": "small",
            })

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"DECISION-{decision_number}",
                    "weight": "bolder",
                    "color": "accent",
                    "size": "small",
                },
                {
                    "type": "TextBlock",
                    "text": title,
                    "weight": "bolder",
                    "size": "medium",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": f"Consensus Poll - {total} vote{'s' if total != 1 else ''}",
                    "spacing": "small",
                    "isSubtle": True,
                    "size": "small",
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": f"Agree ({agree_count})",
                    "style": "positive",
                    "data": {
                        "action": "poll_vote_agree",
                        "decision_id": decision_id,
                    },
                },
                {
                    "type": "Action.Submit",
                    "title": f"Concern ({concern_count})",
                    "data": {
                        "action": "poll_vote_concern",
                        "decision_id": decision_id,
                    },
                },
                {
                    "type": "Action.Submit",
                    "title": f"Block ({block_count})",
                    "style": "destructive",
                    "data": {
                        "action": "poll_vote_block",
                        "decision_id": decision_id,
                    },
                },
            ],
        }

        # Add vote details if any votes exist
        if vote_details:
            card["body"].append({
                "type": "Container",
                "separator": True,
                "spacing": "medium",
                "items": vote_details,
            })

        # Add link to full decision
        card["body"].append({
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "View in Imputable",
                    "url": f"{settings.frontend_url}/decisions/{decision_id}",
                }
            ],
        })

        return card

    @staticmethod
    def search_results_card(query: str, decisions: list) -> dict:
        """
        Build search results Adaptive Card.

        Args:
            query: Search query string
            decisions: List of Decision objects matching the query
        """
        if not decisions:
            return {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": f"Search: \"{query}\"",
                        "weight": "bolder",
                        "size": "medium",
                    },
                    {
                        "type": "TextBlock",
                        "text": "No decisions found matching your query.",
                        "wrap": True,
                        "isSubtle": True,
                    },
                ],
            }

        # Build result items
        result_items = []
        for d in decisions[:5]:  # Limit to 5 results
            title = d.current_version.title if d.current_version else "Untitled"
            status = d.status.value if d.status else "unknown"

            status_emoji = {
                "proposed": "🟡",
                "approved": "🟢",
                "rejected": "🔴",
                "superseded": "⚪",
                "deprecated": "⚫",
            }.get(status, "⚪")

            result_items.append({
                "type": "Container",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"DECISION-{d.decision_number}",
                                        "weight": "bolder",
                                        "color": "accent",
                                        "size": "small",
                                    }
                                ],
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": title,
                                        "wrap": True,
                                        "size": "small",
                                    }
                                ],
                            },
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": f"{status_emoji} {status.title()}",
                                        "size": "small",
                                    }
                                ],
                            },
                        ],
                    }
                ],
                "selectAction": {
                    "type": "Action.OpenUrl",
                    "url": f"{settings.frontend_url}/decisions/{d.id}",
                },
            })

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"Search: \"{query}\"",
                    "weight": "bolder",
                    "size": "medium",
                },
                {
                    "type": "TextBlock",
                    "text": f"Found {len(decisions)} decision{'s' if len(decisions) != 1 else ''}",
                    "isSubtle": True,
                    "size": "small",
                    "spacing": "small",
                },
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "medium",
                    "items": result_items,
                },
            ],
        }

    @staticmethod
    def log_decision_form(
        prefill_title: str = "",
        message_text: str = "",
        message_id: str = "",
        conversation_id: str = "",
    ) -> dict:
        """
        Build log as decision form Adaptive Card (for task module).

        Args:
            prefill_title: Pre-filled title from message
            message_text: Original message text for context
            message_id: Teams message ID for duplicate tracking
            conversation_id: Teams conversation ID
        """
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Log this message as a decision record",
                    "weight": "bolder",
                    "size": "medium",
                },
                {
                    "type": "Input.Text",
                    "id": "title",
                    "label": "Decision Title",
                    "placeholder": "What was decided?",
                    "value": prefill_title,
                    "isRequired": True,
                    "errorMessage": "Please enter a title",
                },
                {
                    "type": "Input.Text",
                    "id": "context",
                    "label": "Additional Context",
                    "placeholder": "Why was this decision made?",
                    "isMultiline": True,
                    "value": message_text if len(message_text) > 100 else "",
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "impact",
                    "label": "Risk Impact",
                    "value": "medium",
                    "choices": [
                        {"title": "Low - Minor changes", "value": "low"},
                        {"title": "Medium - Moderate impact", "value": "medium"},
                        {"title": "High - Significant changes", "value": "high"},
                        {"title": "Critical - Major implications", "value": "critical"},
                    ],
                },
                # Hidden fields for duplicate tracking
                {
                    "type": "Input.Text",
                    "id": "message_id",
                    "value": message_id,
                    "isVisible": False,
                },
                {
                    "type": "Input.Text",
                    "id": "conversation_id",
                    "value": conversation_id,
                    "isVisible": False,
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Log Decision",
                    "style": "positive",
                    "data": {
                        "action": "log_as_decision",
                    },
                },
            ],
        }

    @staticmethod
    def decision_created_card(
        decision_number: int,
        title: str,
        decision_id: str,
    ) -> dict:
        """
        Build decision created confirmation card.

        Args:
            decision_number: Human-readable decision number
            title: Decision title
            decision_id: UUID of the decision
        """
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Decision Logged",
                    "weight": "bolder",
                    "size": "medium",
                    "color": "good",
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "ID", "value": f"DECISION-{decision_number}"},
                        {"title": "Title", "value": title},
                    ],
                },
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "View in Imputable",
                    "url": f"{settings.frontend_url}/decisions/{decision_id}",
                },
            ],
        }

    @staticmethod
    def help_card() -> dict:
        """Build help/menu Adaptive Card."""
        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Imputable Bot",
                    "weight": "bolder",
                    "size": "large",
                },
                {
                    "type": "TextBlock",
                    "text": "Track and manage your team's decisions",
                    "isSubtle": True,
                    "wrap": True,
                },
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Commands**",
                            "weight": "bolder",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {
                                    "title": "search [query]",
                                    "value": "Search for decisions",
                                },
                                {
                                    "title": "poll [question]",
                                    "value": "Start a consensus poll",
                                },
                                {
                                    "title": "poll DECISION-123",
                                    "value": "Poll on existing decision",
                                },
                                {
                                    "title": "help",
                                    "value": "Show this help message",
                                },
                            ],
                        },
                    ],
                },
                {
                    "type": "Container",
                    "spacing": "medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "**Message Actions**",
                            "weight": "bolder",
                        },
                        {
                            "type": "TextBlock",
                            "text": "Right-click any message and select \"Log as Decision\" to capture it as a decision record.",
                            "wrap": True,
                            "size": "small",
                        },
                    ],
                },
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "Open Imputable",
                    "url": settings.frontend_url,
                },
            ],
        }

    @staticmethod
    def ai_decision_form(
        analysis: "AIAnalysisResult",
        message_id: str = "",
        conversation_id: str = "",
    ) -> dict:
        """
        Build AI-prefilled decision form Adaptive Card.

        Shows AI confidence score and allows user to verify/edit.
        """
        # Format alternatives for display
        alternatives_text = ""
        if analysis.alternatives:
            alt_lines = []
            for alt in analysis.alternatives[:5]:
                alt_lines.append(f"- {alt.get('name', 'Unknown')}: {alt.get('rejected_reason', 'No reason given')}")
            alternatives_text = "\n".join(alt_lines)

        # Format dissenters
        dissenters_text = ", ".join(analysis.key_dissenters[:5]) if analysis.key_dissenters else "None identified"

        # Confidence display
        confidence_pct = int(analysis.confidence_score * 100)
        if confidence_pct >= 80:
            confidence_color = "good"
            confidence_text = "High confidence"
        elif confidence_pct >= 50:
            confidence_color = "warning"
            confidence_text = "Medium confidence"
        else:
            confidence_color = "attention"
            confidence_text = "Low confidence - please review carefully"

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                # AI Confidence Banner
                {
                    "type": "TextBlock",
                    "text": f"AI Analysis Complete ({confidence_pct}% confidence)",
                    "weight": "bolder",
                    "size": "medium",
                    "color": confidence_color,
                },
                {
                    "type": "TextBlock",
                    "text": confidence_text,
                    "size": "small",
                    "isSubtle": True,
                    "spacing": "none",
                },
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "medium",
                    "items": [
                        # Title
                        {
                            "type": "Input.Text",
                            "id": "title",
                            "label": "Decision Title",
                            "placeholder": "What was decided?",
                            "value": analysis.title[:255],
                            "isRequired": True,
                            "errorMessage": "Please enter a title",
                        },
                        # Context
                        {
                            "type": "Input.Text",
                            "id": "context",
                            "label": "Context (Problem)",
                            "placeholder": "Background and problem statement",
                            "isMultiline": True,
                            "value": analysis.context[:2000] if analysis.context else "",
                        },
                        # Choice/Decision
                        {
                            "type": "Input.Text",
                            "id": "choice",
                            "label": "Decision (What)",
                            "placeholder": "What was decided",
                            "isMultiline": True,
                            "value": analysis.choice[:2000] if analysis.choice else "",
                        },
                        # Rationale
                        {
                            "type": "Input.Text",
                            "id": "rationale",
                            "label": "Rationale (Why)",
                            "placeholder": "Why this choice was made",
                            "isMultiline": True,
                            "value": analysis.rationale[:2000] if analysis.rationale else "",
                        },
                        # Alternatives
                        {
                            "type": "Input.Text",
                            "id": "alternatives",
                            "label": "Alternatives Considered",
                            "placeholder": "- Option: Reason rejected",
                            "isMultiline": True,
                            "value": alternatives_text[:2000] if alternatives_text else "",
                        },
                        # Impact
                        {
                            "type": "Input.ChoiceSet",
                            "id": "impact",
                            "label": "Impact Level",
                            "value": analysis.suggested_impact,
                            "choices": [
                                {"title": "Low - Minor changes", "value": "low"},
                                {"title": "Medium - Moderate impact", "value": "medium"},
                                {"title": "High - Significant changes", "value": "high"},
                                {"title": "Critical - Major implications", "value": "critical"},
                            ],
                        },
                    ],
                },
                # Metadata section
                {
                    "type": "Container",
                    "separator": True,
                    "spacing": "medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"**Key Dissenters:** {dissenters_text}",
                            "wrap": True,
                            "size": "small",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**Suggested Status:** {analysis.suggested_status.replace('_', ' ').title()}",
                            "wrap": True,
                            "size": "small",
                        },
                    ],
                },
                # Hidden fields
                {
                    "type": "Input.Text",
                    "id": "message_id",
                    "value": message_id,
                    "isVisible": False,
                },
                {
                    "type": "Input.Text",
                    "id": "conversation_id",
                    "value": conversation_id,
                    "isVisible": False,
                },
                {
                    "type": "Input.Text",
                    "id": "ai_confidence",
                    "value": str(analysis.confidence_score),
                    "isVisible": False,
                },
                {
                    "type": "Input.Text",
                    "id": "suggested_status",
                    "value": analysis.suggested_status,
                    "isVisible": False,
                },
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Save to Imputable",
                    "style": "positive",
                    "data": {
                        "action": "log_ai_decision",
                    },
                },
            ],
        }

    @staticmethod
    def notification_card(
        decision_number: int,
        title: str,
        decision_id: str,
        action: str = "created",
        author: str = "Someone",
    ) -> dict:
        """
        Build notification card for decision events.

        Args:
            decision_number: Human-readable decision number
            title: Decision title
            decision_id: UUID of the decision
            action: What happened (created, approved, etc.)
            author: Who performed the action
        """
        action_colors = {
            "created": "accent",
            "approved": "good",
            "rejected": "attention",
            "updated": "default",
        }

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"Decision {action.title()}",
                    "weight": "bolder",
                    "size": "medium",
                    "color": action_colors.get(action, "default"),
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "ID", "value": f"DECISION-{decision_number}"},
                        {"title": "Title", "value": title},
                        {"title": "By", "value": author},
                    ],
                },
            ],
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "View Decision",
                    "url": f"{settings.frontend_url}/decisions/{decision_id}",
                },
            ],
        }

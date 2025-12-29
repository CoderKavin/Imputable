"""AI Analyzer Service for Intelligent Decision Capture.

Uses Google Gemini to analyze Slack/Teams conversation threads and extract:
- Decision title
- Context/problem summary
- Alternatives considered
- Key dissenters
- Deadlines
- Suggested status (APPROVED if consensus, DRAFT if ambiguous)
- Confidence score for the extraction
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AIAnalysisResult:
    """Result of AI analysis on a conversation thread."""

    # Extracted decision details
    title: str
    context: str
    choice: str
    rationale: str
    alternatives: list[dict[str, str]]  # [{"name": "...", "rejected_reason": "..."}]

    # Discussion metadata
    key_dissenters: list[str]  # Names/IDs of people who disagreed
    deadlines: list[str]  # Any mentioned deadlines
    required_approver: str | None  # Person who must approve before proceeding (e.g., "@Sarah")

    # AI assessment
    suggested_status: str  # "draft", "pending_review", or "approved"
    suggested_impact: str  # "low", "medium", "high", "critical"
    confidence_score: float  # 0.0 to 1.0

    # Warnings for user
    has_conflict: bool  # True if there's unresolved disagreement
    missing_info_warning: str | None  # Warning if context/alternatives are unclear

    # Raw analysis for debugging
    raw_analysis: dict[str, Any] | None = None


class AIAnalyzerService:
    """
    Service for analyzing conversation threads using Google Gemini.

    Extracts structured decision information from unstructured chat threads.
    """

    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

    # System prompt for decision extraction
    SYSTEM_PROMPT = """You are an AI assistant specialized in extracting engineering decisions from team chat conversations.

Your task is to analyze the provided conversation transcript and extract a structured decision record.

IMPORTANT GUIDELINES:
1. Be concise but complete - summarize don't copy verbatim
2. If something isn't clear from the conversation, indicate uncertainty
3. Look for explicit decisions, not just discussions
4. Identify who disagreed and why (key dissenters)
5. Note any deadlines or timelines mentioned
6. Assess whether there was clear consensus
7. DETECT GATEKEEPERS: If someone mentions that a specific person needs to approve/sign off before proceeding, capture that person as "required_approver" and set status to "pending_review"
8. DETECT CONFLICTS: If there's active disagreement with no resolution (e.g., "I disagree", "I'm against this", "strictly against"), set "has_conflict" to true and status to "draft"
9. DETECT MISSING INFO: If the conversation lacks context, alternatives, or clear decision details, set "missing_info_warning" with a helpful message

OUTPUT FORMAT (JSON):
{
    "title": "Short descriptive title for the decision (max 100 chars)",
    "context": "Summary of the problem being solved and why a decision was needed. If unclear, use empty string.",
    "choice": "What was actually decided - the chosen approach. If no clear decision, use empty string.",
    "rationale": "Why this choice was made - the reasoning",
    "alternatives": [
        {"name": "Alternative option name", "rejected_reason": "Why it wasn't chosen"}
    ],
    "key_dissenters": ["Names of people who disagreed or raised concerns"],
    "deadlines": ["Any deadlines or timelines mentioned"],
    "required_approver": "@PersonName or null - person explicitly mentioned as needing to approve/sign off",
    "suggested_status": "approved|pending_review|draft",
    "suggested_impact": "low|medium|high|critical",
    "confidence_score": 0.0-1.0,
    "has_conflict": false,
    "missing_info_warning": "Warning message if information is insufficient, or null if adequate",
    "analysis_notes": "Brief notes on analysis certainty"
}

STATUS GUIDELINES:
- "approved": Clear consensus, everyone agreed, decision is final, NO ONE mentioned needing additional approval
- "pending_review": Decision made but:
  * Someone specific was mentioned as needing to approve (gatekeeper pattern), OR
  * There are unresolved concerns that need addressing
- "draft": Use when:
  * The discussion is still ongoing with no resolution
  * There's active conflict/disagreement without consensus
  * The conversation is too vague to determine a decision
  * Very little information is available

GATEKEEPER DETECTION (CRITICAL):
Look for patterns like:
- "@PersonName needs to approve this"
- "but [Name] needs to sign off"
- "waiting for [Name]'s approval"
- "[Name] has final say on this"
- "check with [Name] before we proceed"
If detected, set required_approver to that person's name (include @ if mentioned) and status to "pending_review"

CONFLICT DETECTION (CRITICAL):
Look for unresolved disagreements:
- "I disagree" / "I'm against this" / "strictly against"
- Back-and-forth debate with no final agreement
- Someone says "no" or blocks without resolution
If detected, set has_conflict to true, status to "draft"

MISSING INFO DETECTION (CRITICAL):
Set missing_info_warning if:
- No clear problem/context is stated → "Context not specified in thread"
- No alternatives were discussed → "No alternatives mentioned"
- The entire message is just "Let's go with X" with no explanation → "Minimal context provided - please fill in details manually"
- Very short conversation with little substance → "Limited discussion found - please verify details"

IMPACT GUIDELINES:
- "low": Minor change, easily reversible, limited scope
- "medium": Moderate change, some effort to reverse, affects a team
- "high": Significant change, hard to reverse, affects multiple teams
- "critical": Major architectural decision, very hard to reverse, org-wide impact

CONFIDENCE GUIDELINES:
- 0.9-1.0: Very clear decision with explicit consensus
- 0.7-0.9: Clear decision but some interpretation needed
- 0.5-0.7: Decision exists but context is incomplete
- 0.3-0.5: Possible decision, significant uncertainty
- 0.0-0.3: Very unclear, may not be a decision at all (has_conflict or missing_info likely true)"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.gemini_api_key

    @property
    def is_configured(self) -> bool:
        """Check if Gemini API is configured."""
        return bool(self.api_key)

    async def analyze_thread(
        self,
        messages: list[dict[str, str]],
        channel_name: str | None = None,
    ) -> AIAnalysisResult:
        """
        Analyze a conversation thread and extract decision information.

        Args:
            messages: List of messages with 'author' and 'text' keys
            channel_name: Optional channel name for context

        Returns:
            AIAnalysisResult with extracted decision details
        """
        if not self.is_configured:
            raise ValueError("Gemini API key not configured")

        # Format messages into transcript
        transcript = self._format_transcript(messages, channel_name)

        # Call Gemini API
        try:
            response = await self._call_gemini(transcript)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            # Return a minimal result on error
            return AIAnalysisResult(
                title="Decision from conversation",
                context="Unable to analyze conversation - please fill in manually.",
                choice="",
                rationale="",
                alternatives=[],
                key_dissenters=[],
                deadlines=[],
                required_approver=None,
                suggested_status="draft",
                suggested_impact="medium",
                confidence_score=0.0,
                has_conflict=False,
                missing_info_warning="AI analysis failed - please fill in all details manually",
                raw_analysis={"error": str(e)},
            )

    def _format_transcript(
        self,
        messages: list[dict[str, str]],
        channel_name: str | None = None,
    ) -> str:
        """Format messages into a readable transcript."""
        lines = []

        if channel_name:
            lines.append(f"Channel: #{channel_name}")
            lines.append("")

        lines.append("=== CONVERSATION TRANSCRIPT ===")
        lines.append("")

        for msg in messages:
            author = msg.get("author", "Unknown")
            text = msg.get("text", "")
            timestamp = msg.get("timestamp", "")

            if timestamp:
                lines.append(f"[{timestamp}] {author}:")
            else:
                lines.append(f"{author}:")

            # Indent message text
            for line in text.split("\n"):
                lines.append(f"  {line}")
            lines.append("")

        lines.append("=== END TRANSCRIPT ===")

        return "\n".join(lines)

    async def _call_gemini(self, transcript: str) -> dict[str, Any]:
        """Call Gemini API with the transcript."""
        url = f"{self.GEMINI_API_URL}?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": self.SYSTEM_PROMPT},
                        {"text": f"\n\nAnalyze this conversation and extract the decision:\n\n{transcript}"},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,  # Low temperature for more consistent extraction
                "topP": 0.8,
                "topK": 40,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                raise RuntimeError(f"Gemini API error: {response.status_code}")

            return response.json()

    def _parse_response(self, response: dict[str, Any]) -> AIAnalysisResult:
        """Parse Gemini response into AIAnalysisResult."""
        try:
            # Extract text from Gemini response
            candidates = response.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in response")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise ValueError("No parts in response")

            text = parts[0].get("text", "")

            # Parse JSON from response
            # Handle potential markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text.strip())

            # Build result
            return AIAnalysisResult(
                title=data.get("title", "Untitled Decision")[:255],
                context=data.get("context", ""),
                choice=data.get("choice", ""),
                rationale=data.get("rationale", ""),
                alternatives=[
                    {
                        "name": alt.get("name", ""),
                        "rejected_reason": alt.get("rejected_reason", ""),
                    }
                    for alt in data.get("alternatives", [])
                ],
                key_dissenters=data.get("key_dissenters", []),
                deadlines=data.get("deadlines", []),
                required_approver=data.get("required_approver"),
                suggested_status=self._validate_status(data.get("suggested_status", "draft")),
                suggested_impact=self._validate_impact(data.get("suggested_impact", "medium")),
                confidence_score=min(1.0, max(0.0, float(data.get("confidence_score", 0.5)))),
                has_conflict=bool(data.get("has_conflict", False)),
                missing_info_warning=data.get("missing_info_warning"),
                raw_analysis=data,
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.debug(f"Raw response: {response}")

            return AIAnalysisResult(
                title="Decision from conversation",
                context="AI analysis completed but parsing failed. Please review and edit.",
                choice="",
                rationale="",
                alternatives=[],
                key_dissenters=[],
                deadlines=[],
                required_approver=None,
                suggested_status="draft",
                suggested_impact="medium",
                confidence_score=0.3,
                has_conflict=False,
                missing_info_warning="AI parsing failed - please fill in details manually",
                raw_analysis={"parse_error": str(e), "raw": response},
            )

    def _validate_status(self, status: str) -> str:
        """Validate and normalize status value."""
        valid = {"draft", "pending_review", "approved"}
        status = status.lower().strip()
        return status if status in valid else "draft"

    def _validate_impact(self, impact: str) -> str:
        """Validate and normalize impact value."""
        valid = {"low", "medium", "high", "critical"}
        impact = impact.lower().strip()
        return impact if impact in valid else "medium"


# =============================================================================
# SLACK THREAD FETCHER
# =============================================================================


class SlackThreadFetcher:
    """Fetches conversation threads from Slack API."""

    async def fetch_thread(
        self,
        bot_token: str,
        channel_id: str,
        thread_ts: str,
    ) -> list[dict[str, str]]:
        """
        Fetch all messages in a Slack thread.

        Args:
            bot_token: Slack bot OAuth token
            channel_id: Channel containing the thread
            thread_ts: Thread timestamp (parent message ts)

        Returns:
            List of messages with author, text, timestamp
        """
        messages = []
        cursor = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params = {
                    "channel": channel_id,
                    "ts": thread_ts,
                    "limit": 100,
                }
                if cursor:
                    params["cursor"] = cursor

                response = await client.get(
                    "https://slack.com/api/conversations.replies",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    params=params,
                )

                data = response.json()

                if not data.get("ok"):
                    logger.error(f"Slack API error: {data.get('error')}")
                    raise RuntimeError(f"Slack API error: {data.get('error')}")

                for msg in data.get("messages", []):
                    # Skip bot messages and join/leave messages
                    if msg.get("subtype") in ("bot_message", "channel_join", "channel_leave"):
                        continue

                    messages.append({
                        "author": msg.get("user", "Unknown"),
                        "text": msg.get("text", ""),
                        "timestamp": msg.get("ts", ""),
                    })

                # Check for pagination
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        return messages

    async def fetch_single_message(
        self,
        bot_token: str,
        channel_id: str,
        message_ts: str,
    ) -> dict[str, str]:
        """
        Fetch a single message from Slack.

        Args:
            bot_token: Slack bot OAuth token
            channel_id: Channel containing the message
            message_ts: Message timestamp

        Returns:
            Message dict with author, text, timestamp
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://slack.com/api/conversations.history",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={
                    "channel": channel_id,
                    "latest": message_ts,
                    "inclusive": True,
                    "limit": 1,
                },
            )

            data = response.json()

            if not data.get("ok"):
                logger.error(f"Slack API error: {data.get('error')}")
                raise RuntimeError(f"Slack API error: {data.get('error')}")

            messages = data.get("messages", [])
            if not messages:
                raise ValueError("Message not found")

            msg = messages[0]
            return {
                "author": msg.get("user", "Unknown"),
                "text": msg.get("text", ""),
                "timestamp": msg.get("ts", ""),
            }

    async def resolve_user_names(
        self,
        bot_token: str,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """
        Resolve Slack user IDs to display names.

        Modifies messages in place to replace user IDs with names.
        """
        # Collect unique user IDs
        user_ids = set()
        for msg in messages:
            author = msg.get("author", "")
            if author.startswith("U"):  # Slack user IDs start with U
                user_ids.add(author)

        if not user_ids:
            return messages

        # Fetch user info
        user_names = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for user_id in user_ids:
                try:
                    response = await client.get(
                        "https://slack.com/api/users.info",
                        headers={"Authorization": f"Bearer {bot_token}"},
                        params={"user": user_id},
                    )
                    data = response.json()
                    if data.get("ok"):
                        user = data.get("user", {})
                        name = user.get("real_name") or user.get("name") or user_id
                        user_names[user_id] = name
                except Exception as e:
                    logger.warning(f"Failed to resolve user {user_id}: {e}")
                    user_names[user_id] = user_id

        # Update messages with names
        for msg in messages:
            author = msg.get("author", "")
            if author in user_names:
                msg["author"] = user_names[author]

        return messages


# =============================================================================
# TEAMS THREAD FETCHER
# =============================================================================


class TeamsThreadFetcher:
    """Fetches conversation threads from Microsoft Teams Graph API."""

    GRAPH_API_URL = "https://graph.microsoft.com/v1.0"

    async def fetch_thread(
        self,
        access_token: str,
        team_id: str,
        channel_id: str,
        message_id: str,
    ) -> list[dict[str, str]]:
        """
        Fetch all messages in a Teams thread/reply chain.

        Args:
            access_token: Microsoft Graph API access token
            team_id: Teams team ID
            channel_id: Channel ID
            message_id: Root message ID

        Returns:
            List of messages with author, text, timestamp
        """
        messages = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # First get the root message
            root_url = f"{self.GRAPH_API_URL}/teams/{team_id}/channels/{channel_id}/messages/{message_id}"
            root_response = await client.get(
                root_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if root_response.status_code == 200:
                root_msg = root_response.json()
                messages.append({
                    "author": root_msg.get("from", {}).get("user", {}).get("displayName", "Unknown"),
                    "text": self._extract_text(root_msg.get("body", {})),
                    "timestamp": root_msg.get("createdDateTime", ""),
                })

            # Then get replies
            replies_url = f"{root_url}/replies"
            next_link = replies_url

            while next_link:
                response = await client.get(
                    next_link,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code != 200:
                    logger.error(f"Graph API error: {response.status_code}")
                    break

                data = response.json()

                for msg in data.get("value", []):
                    messages.append({
                        "author": msg.get("from", {}).get("user", {}).get("displayName", "Unknown"),
                        "text": self._extract_text(msg.get("body", {})),
                        "timestamp": msg.get("createdDateTime", ""),
                    })

                next_link = data.get("@odata.nextLink")

        return messages

    def _extract_text(self, body: dict) -> str:
        """Extract plain text from Teams message body."""
        content = body.get("content", "")
        content_type = body.get("contentType", "text")

        if content_type == "html":
            # Simple HTML stripping - for production use a proper HTML parser
            import re
            content = re.sub(r"<[^>]+>", "", content)
            content = content.replace("&nbsp;", " ")
            content = content.replace("&amp;", "&")
            content = content.replace("&lt;", "<")
            content = content.replace("&gt;", ">")

        return content.strip()

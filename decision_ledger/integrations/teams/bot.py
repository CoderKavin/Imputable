"""Microsoft Teams Bot Framework service.

Handles authentication, message sending, and activity processing for Teams integration.
Uses the Bot Framework REST API directly (no SDK dependency).
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient, ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import get_settings
from ...models import Organization, Decision, LoggedMessage, PollVote, PollVoteType

logger = logging.getLogger(__name__)
settings = get_settings()


class TeamsBotService:
    """
    Service for Microsoft Teams Bot Framework operations.

    Handles:
    - Bot Framework OAuth token acquisition
    - JWT validation for incoming requests
    - Sending Adaptive Cards to conversations
    - Processing bot activities (messages, card actions)
    """

    # Bot Framework endpoints
    LOGIN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
    OPENID_METADATA_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"

    # Token cache
    _access_token: str | None = None
    _token_expires: datetime | None = None

    def __init__(self, session: AsyncSession):
        self.session = session
        self.app_id = settings.teams_app_id
        self.app_password = settings.teams_app_password

    @property
    def is_configured(self) -> bool:
        """Check if Teams Bot Framework credentials are configured."""
        return bool(self.app_id and self.app_password)

    async def get_access_token(self) -> str:
        """
        Get Bot Framework access token for API calls.

        Caches the token and refreshes when expired.
        """
        # Check cache
        if self._access_token and self._token_expires:
            if datetime.utcnow() < self._token_expires - timedelta(minutes=5):
                return self._access_token

        if not self.is_configured:
            raise ValueError("Teams Bot Framework is not configured")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.LOGIN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.app_id,
                    "client_secret": self.app_password,
                    "scope": "https://api.botframework.com/.default",
                },
            )

            if response.status_code != 200:
                logger.error(f"Failed to get Teams token: {response.text}")
                raise RuntimeError("Failed to authenticate with Bot Framework")

            data = response.json()
            TeamsBotService._access_token = data["access_token"]
            TeamsBotService._token_expires = datetime.utcnow() + timedelta(
                seconds=data.get("expires_in", 3600)
            )

            return TeamsBotService._access_token

    async def verify_token(self, auth_header: str) -> dict | None:
        """
        Verify Bot Framework JWT token from incoming request.

        Returns decoded token claims if valid, None otherwise.

        See: https://docs.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-authentication
        """
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            return None

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            # Get OpenID configuration
            async with httpx.AsyncClient() as client:
                oid_response = await client.get(self.OPENID_METADATA_URL)
                oid_config = oid_response.json()
                jwks_uri = oid_config.get("jwks_uri")

            if not jwks_uri:
                logger.error("Could not get JWKS URI from OpenID config")
                return None

            # Get signing keys
            jwks_client = PyJWKClient(jwks_uri)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Verify and decode token
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.app_id,
                issuer="https://api.botframework.com",
                options={"verify_exp": True},
            )

            return decoded

        except ExpiredSignatureError:
            logger.warning("Teams JWT token has expired")
            return None
        except InvalidTokenError as e:
            logger.warning(f"Invalid Teams JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying Teams token: {e}")
            return None

    async def send_message(
        self,
        service_url: str,
        conversation_id: str,
        message: dict,
    ) -> dict | None:
        """
        Send a message or Adaptive Card to a Teams conversation.

        Args:
            service_url: The Bot Framework service URL for the tenant
            conversation_id: The Teams conversation/channel ID
            message: The activity payload (can include Adaptive Card attachments)

        Returns:
            The API response dict or None on failure
        """
        token = await self.get_access_token()

        url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=message,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Failed to send Teams message: {response.text}")
                return None

            return response.json()

    async def update_message(
        self,
        service_url: str,
        conversation_id: str,
        activity_id: str,
        message: dict,
    ) -> dict | None:
        """
        Update an existing message (for poll vote updates).

        Args:
            service_url: The Bot Framework service URL
            conversation_id: The Teams conversation ID
            activity_id: The ID of the message to update
            message: The new activity payload

        Returns:
            The API response dict or None on failure
        """
        token = await self.get_access_token()

        url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities/{activity_id}"

        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=message,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Failed to update Teams message: {response.text}")
                return None

            return response.json()

    async def send_adaptive_card(
        self,
        service_url: str,
        conversation_id: str,
        card: dict,
        summary: str = "Imputable Notification",
    ) -> dict | None:
        """
        Send an Adaptive Card to a Teams conversation.

        Args:
            service_url: The Bot Framework service URL
            conversation_id: The Teams conversation ID
            card: The Adaptive Card JSON
            summary: Fallback text for notifications
        """
        message = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
            "summary": summary,
        }

        return await self.send_message(service_url, conversation_id, message)

    async def get_organization_by_tenant(self, tenant_id: str) -> Organization | None:
        """Get organization by Teams tenant ID."""
        result = await self.session.execute(
            select(Organization).where(Organization.teams_tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def process_message_activity(
        self,
        activity: dict,
        org: Organization,
    ) -> dict:
        """
        Process an incoming message activity (bot commands).

        Handles:
        - /decisions search <query>
        - /decisions poll <question>
        - /decisions help
        """
        from .cards import TeamsCards

        text = activity.get("text", "").strip()

        # Remove bot mention from text
        if activity.get("entities"):
            for entity in activity["entities"]:
                if entity.get("type") == "mention":
                    mention_text = entity.get("text", "")
                    text = text.replace(mention_text, "").strip()

        # Parse command
        text_lower = text.lower()

        if text_lower.startswith("search "):
            query = text[7:].strip()
            return await self._handle_search(query, org)

        elif text_lower.startswith("poll "):
            question = text[5:].strip()
            return await self._handle_poll(question, org, activity)

        elif text_lower in ("help", "?"):
            return {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": TeamsCards.help_card(),
                    }
                ],
            }

        else:
            # Default: show help
            return {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": TeamsCards.help_card(),
                    }
                ],
            }

    async def _handle_search(self, query: str, org: Organization) -> dict:
        """Handle search command."""
        from .cards import TeamsCards
        from sqlalchemy import or_

        if not query:
            return {
                "type": "message",
                "text": "Please provide a search query. Example: `search API design`",
            }

        # Search decisions
        result = await self.session.execute(
            select(Decision)
            .where(Decision.organization_id == org.id)
            .where(Decision.current_version_id.isnot(None))
            .order_by(Decision.created_at.desc())
            .limit(50)
        )
        decisions = result.scalars().all()

        # Filter by query (simple text match)
        query_lower = query.lower()
        matches = []
        for d in decisions:
            if d.current_version:
                title = d.current_version.title or ""
                content = d.current_version.content or ""
                if query_lower in title.lower() or query_lower in content.lower():
                    matches.append(d)
                    if len(matches) >= 5:
                        break

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": TeamsCards.search_results_card(query, matches),
                }
            ],
        }

    async def _handle_poll(
        self,
        question: str,
        org: Organization,
        activity: dict,
    ) -> dict:
        """Handle poll command - create decision and poll card."""
        from .cards import TeamsCards
        from ...models import DecisionVersion, DecisionStatus
        import re
        from uuid import UUID

        if not question:
            return {
                "type": "message",
                "text": "Please provide a question. Example: `poll Should we use Redis for caching?`",
            }

        # Check if referencing existing decision (DEC-123 format)
        dec_match = re.match(r"^DEC-(\d+)\s*(.*)$", question, re.IGNORECASE)

        if dec_match:
            decision_number = int(dec_match.group(1))
            result = await self.session.execute(
                select(Decision)
                .where(Decision.organization_id == org.id)
                .where(Decision.decision_number == decision_number)
            )
            decision = result.scalar_one_or_none()

            if not decision:
                return {
                    "type": "message",
                    "text": f"Decision DEC-{decision_number} not found.",
                }
        else:
            # Create new decision from question
            # Get next decision number
            result = await self.session.execute(
                select(Decision.decision_number)
                .where(Decision.organization_id == org.id)
                .order_by(Decision.decision_number.desc())
                .limit(1)
            )
            last_number = result.scalar_one_or_none() or 0
            next_number = last_number + 1

            # Create decision
            decision = Decision(
                organization_id=org.id,
                decision_number=next_number,
                status=DecisionStatus.PROPOSED,
                source="teams",
                teams_conversation_id=activity.get("conversation", {}).get("id"),
            )
            self.session.add(decision)
            await self.session.flush()

            # Create version
            version = DecisionVersion(
                decision_id=decision.id,
                version_number=1,
                title=question[:255],
                content=f"Poll created from Teams by {activity.get('from', {}).get('name', 'Unknown')}",
            )
            self.session.add(version)
            await self.session.flush()

            decision.current_version_id = version.id
            await self.session.commit()

        # Get current votes
        votes_result = await self.session.execute(
            select(PollVote).where(PollVote.decision_id == decision.id)
        )
        votes = votes_result.scalars().all()

        vote_summary = {"agree": [], "concern": [], "block": []}
        for v in votes:
            name = v.external_user_name or "Unknown"
            vote_summary[v.vote_type.value].append(name)

        title = decision.current_version.title if decision.current_version else question

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": TeamsCards.poll_card(
                        decision_id=str(decision.id),
                        decision_number=decision.decision_number,
                        title=title,
                        votes=vote_summary,
                    ),
                }
            ],
        }

    async def process_card_action(
        self,
        activity: dict,
        org: Organization,
    ) -> dict:
        """
        Process Adaptive Card action (button clicks, form submissions).

        Handles:
        - Poll votes (agree/concern/block)
        - Log as Decision form submission
        """
        from .cards import TeamsCards
        from uuid import UUID

        action_data = activity.get("value", {})
        action_type = action_data.get("action")
        user = activity.get("from", {})
        user_id = user.get("id", "")
        user_name = user.get("name", "Unknown")

        if action_type in ("poll_vote_agree", "poll_vote_concern", "poll_vote_block"):
            # Handle poll vote
            decision_id = action_data.get("decision_id")
            vote_type_str = action_type.replace("poll_vote_", "")

            try:
                decision_uuid = UUID(decision_id)
            except (ValueError, TypeError):
                return {"type": "message", "text": "Invalid decision ID"}

            # Get decision
            result = await self.session.execute(
                select(Decision).where(Decision.id == decision_uuid)
            )
            decision = result.scalar_one_or_none()

            if not decision:
                return {"type": "message", "text": "Decision not found"}

            # Upsert vote
            vote_type = PollVoteType(vote_type_str)

            existing_vote = await self.session.execute(
                select(PollVote)
                .where(PollVote.decision_id == decision_uuid)
                .where(PollVote.external_user_id == user_id)
                .where(PollVote.source == "teams")
            )
            vote = existing_vote.scalar_one_or_none()

            if vote:
                vote.vote_type = vote_type
                vote.external_user_name = user_name
            else:
                vote = PollVote(
                    decision_id=decision_uuid,
                    external_user_id=user_id,
                    external_user_name=user_name,
                    vote_type=vote_type,
                    source="teams",
                )
                self.session.add(vote)

            await self.session.commit()

            # Get updated votes
            votes_result = await self.session.execute(
                select(PollVote).where(PollVote.decision_id == decision_uuid)
            )
            votes = votes_result.scalars().all()

            vote_summary = {"agree": [], "concern": [], "block": []}
            for v in votes:
                name = v.external_user_name or "Unknown"
                vote_summary[v.vote_type.value].append(name)

            title = decision.current_version.title if decision.current_version else "Untitled"

            # Return updated card
            return {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": TeamsCards.poll_card(
                            decision_id=str(decision.id),
                            decision_number=decision.decision_number,
                            title=title,
                            votes=vote_summary,
                        ),
                    }
                ],
            }

        elif action_type == "log_as_decision":
            # Handle log as decision form submission
            return await self._create_decision_from_form(action_data, org, user_name, user_id, ai_generated=False)

        elif action_type == "log_ai_decision":
            # Handle AI-generated decision form submission
            return await self._create_decision_from_form(action_data, org, user_name, user_id, ai_generated=True)

        return {"type": "message", "text": "Unknown action"}

    async def _create_decision_from_form(
        self,
        action_data: dict,
        org: Organization,
        user_name: str,
        user_id: str,
        ai_generated: bool = False,
    ) -> dict:
        """Create a decision from form submission data."""
        from .cards import TeamsCards
        from ...models import DecisionVersion, DecisionStatus, ImpactLevel
        from sqlalchemy import func

        title = action_data.get("title", "").strip()
        context = action_data.get("context", "").strip()
        choice = action_data.get("choice", "").strip()
        rationale = action_data.get("rationale", "").strip()
        alternatives_text = action_data.get("alternatives", "").strip()
        impact = action_data.get("impact", "medium")
        message_id = action_data.get("message_id")
        conversation_id = action_data.get("conversation_id")

        # AI-specific fields
        ai_confidence = float(action_data.get("ai_confidence", 0.0)) if ai_generated else 0.0
        suggested_status = action_data.get("suggested_status", "draft") if ai_generated else "draft"

        if not title:
            return {"type": "message", "text": "Please provide a decision title."}

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

        # Check for duplicate
        if message_id and conversation_id:
            existing = await self.session.execute(
                select(LoggedMessage)
                .where(LoggedMessage.source == "teams")
                .where(LoggedMessage.message_id == message_id)
                .where(LoggedMessage.channel_id == conversation_id)
            )
            if existing.scalar_one_or_none():
                return {
                    "type": "message",
                    "text": "This message has already been logged as a decision.",
                }

        # Get next decision number
        result = await self.session.execute(
            select(func.max(Decision.decision_number))
            .where(Decision.organization_id == org.id)
        )
        max_num = result.scalar() or 0
        next_number = max_num + 1

        # Map impact level
        impact_map = {
            "low": ImpactLevel.LOW,
            "medium": ImpactLevel.MEDIUM,
            "high": ImpactLevel.HIGH,
            "critical": ImpactLevel.CRITICAL,
        }
        impact_level = impact_map.get(impact, ImpactLevel.MEDIUM)

        # Determine status
        status_map = {
            "draft": DecisionStatus.DRAFT,
            "pending_review": DecisionStatus.PENDING_REVIEW,
            "approved": DecisionStatus.APPROVED,
        }
        if ai_generated and ai_confidence >= 0.8 and suggested_status in status_map:
            decision_status = status_map[suggested_status]
        else:
            decision_status = DecisionStatus.DRAFT

        # Get a user for attribution
        from ...models import OrganizationMember
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
            return {"type": "message", "text": "No organization members found."}

        # Create decision
        decision = Decision(
            organization_id=org.id,
            decision_number=next_number,
            status=decision_status,
            created_by=admin_member.user_id,
            source="teams",
            teams_conversation_id=conversation_id,
            teams_message_id=message_id,
        )
        self.session.add(decision)
        await self.session.flush()

        # Build tags
        tags = ["teams-logged"]
        if ai_generated:
            tags.append("ai-generated")

        # Create version
        version = DecisionVersion(
            decision_id=decision.id,
            version_number=1,
            title=title[:255],
            impact_level=impact_level,
            content={
                "context": context or f"Logged from Teams by {user_name}",
                "choice": choice,
                "rationale": rationale,
                "alternatives": alternatives,
            },
            tags=tags,
            created_by=admin_member.user_id,
            change_summary="AI-analyzed from Teams" if ai_generated else "Logged from Teams message",
            custom_fields={
                "ai_generated": ai_generated,
                "ai_confidence_score": ai_confidence,
                "verified_by_user": True,
                "verified_by_teams_user_id": user_id,
            } if ai_generated else {},
        )
        self.session.add(version)
        await self.session.flush()

        decision.current_version_id = version.id

        # Track message for duplicate detection
        if message_id and conversation_id:
            logged_msg = LoggedMessage(
                source="teams",
                message_id=message_id,
                channel_id=conversation_id,
                decision_id=decision.id,
            )
            self.session.add(logged_msg)

        await self.session.commit()

        logger.info(
            f"{'AI-generated ' if ai_generated else ''}Decision DEC-{decision.decision_number} "
            f"created from Teams for org {org.id}"
        )

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": TeamsCards.decision_created_card(
                        decision_number=decision.decision_number,
                        title=title,
                        decision_id=str(decision.id),
                    ),
                }
            ],
        }

    async def process_compose_extension(
        self,
        activity: dict,
        org: Organization,
    ) -> dict:
        """
        Process compose extension (messaging extension) activity.

        Handles the "Log as Decision" and "Summarize & Log Decision" message actions.
        """
        from .cards import TeamsCards

        command_id = activity.get("value", {}).get("commandId")

        if command_id == "logAsDecision":
            # Get the message being acted upon
            message_payload = activity.get("value", {}).get("messagePayload", {})
            message_text = message_payload.get("body", {}).get("content", "")
            message_id = message_payload.get("id", "")

            # Extract plain text from HTML if needed
            if "<" in message_text:
                import re
                message_text = re.sub(r"<[^>]+>", "", message_text)

            # Return task module (modal) with form
            return {
                "task": {
                    "type": "continue",
                    "value": {
                        "title": "Log as Decision",
                        "card": {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": TeamsCards.log_decision_form(
                                prefill_title=message_text[:100] if message_text else "",
                                message_text=message_text,
                                message_id=message_id,
                                conversation_id=activity.get("conversation", {}).get("id", ""),
                            ),
                        },
                    },
                }
            }

        elif command_id == "aiSummarizeDecision":
            # AI-powered decision extraction
            return await self._handle_ai_summarize(activity, org)

        return {}

    async def _handle_ai_summarize(
        self,
        activity: dict,
        org: Organization,
    ) -> dict:
        """
        Handle AI-powered decision summarization from Teams message.

        Fetches thread context if available, analyzes with AI,
        and returns pre-filled form.
        """
        from .cards import TeamsCards
        from ...services.ai_analyzer import AIAnalyzerService, TeamsThreadFetcher
        from ...core.config import get_settings

        settings = get_settings()

        message_payload = activity.get("value", {}).get("messagePayload", {})
        message_text = message_payload.get("body", {}).get("content", "")
        message_id = message_payload.get("id", "")
        conversation_id = activity.get("conversation", {}).get("id", "")

        # Extract plain text from HTML
        if "<" in message_text:
            import re
            message_text = re.sub(r"<[^>]+>", "", message_text)
            message_text = message_text.replace("&nbsp;", " ")
            message_text = message_text.replace("&amp;", "&")

        # Check if AI is configured
        ai_service = AIAnalyzerService()
        if not ai_service.is_configured:
            # Fallback to regular form
            return {
                "task": {
                    "type": "continue",
                    "value": {
                        "title": "Log as Decision",
                        "card": {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": TeamsCards.log_decision_form(
                                prefill_title=message_text[:100] if message_text else "",
                                message_text=message_text,
                                message_id=message_id,
                                conversation_id=conversation_id,
                            ),
                        },
                    },
                }
            }

        try:
            # For now, analyze just the message (thread fetching requires Graph API permissions)
            # In production, you'd fetch the full thread using TeamsThreadFetcher
            messages = [{
                "author": activity.get("from", {}).get("name", "Unknown"),
                "text": message_text,
                "timestamp": "",
            }]

            # If we have reply chain info, we could fetch more context
            # This would require delegated Graph API permissions

            # Analyze with AI
            analysis = await ai_service.analyze_thread(messages, channel_name="Teams")

            # Return AI-prefilled form
            return {
                "task": {
                    "type": "continue",
                    "value": {
                        "title": "AI Decision Draft",
                        "height": "large",
                        "card": {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": TeamsCards.ai_decision_form(
                                analysis=analysis,
                                message_id=message_id,
                                conversation_id=conversation_id,
                            ),
                        },
                    },
                }
            }

        except Exception as e:
            logger.error(f"AI analysis failed for Teams: {e}")
            # Fallback to regular form
            return {
                "task": {
                    "type": "continue",
                    "value": {
                        "title": "Log as Decision",
                        "card": {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": TeamsCards.log_decision_form(
                                prefill_title=message_text[:100] if message_text else "",
                                message_text=message_text,
                                message_id=message_id,
                                conversation_id=conversation_id,
                            ),
                        },
                    },
                }
            }

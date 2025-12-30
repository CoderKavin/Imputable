"""Integration Router for Slack and Microsoft Teams.

Provides OAuth flows for Slack and webhook configuration for Teams.
All integration features require PRO tier or higher.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Header, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.billing import IntegrationsDep
from ..core.config import get_settings
from ..core.database import get_session
from ..core.dependencies import CurrentUser, require_org_context
from ..models import Organization, Decision, DecisionStatus
from ..services.notifications import NotificationService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/integrations", tags=["integrations"])


# =============================================================================
# SCHEMAS
# =============================================================================


class SlackInstallResponse(BaseModel):
    """Response for Slack install initiation."""
    install_url: str
    message: str = "Redirect user to install_url to authorize Slack"


class SlackCallbackResponse(BaseModel):
    """Response after successful Slack OAuth callback."""
    success: bool
    team_name: str
    channel_name: str | None
    message: str


class SlackStatusResponse(BaseModel):
    """Current Slack integration status."""
    connected: bool
    team_name: str | None
    channel_name: str | None
    installed_at: datetime | None


class TeamsWebhookRequest(BaseModel):
    """Request to configure Teams webhook."""
    webhook_url: HttpUrl
    channel_name: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_teams_url(cls, v: HttpUrl) -> HttpUrl:
        url_str = str(v)
        if "webhook.office.com" not in url_str and "microsoft.com" not in url_str:
            raise ValueError("URL must be a valid Microsoft Teams webhook URL")
        return v


class TeamsStatusResponse(BaseModel):
    """Current Teams integration status."""
    connected: bool
    channel_name: str | None
    installed_at: datetime | None


class IntegrationStatusResponse(BaseModel):
    """Combined integration status."""
    slack: SlackStatusResponse
    teams: TeamsStatusResponse


class SlackCommandResponse(BaseModel):
    """Response for Slack slash command."""
    response_type: str = "ephemeral"  # or "in_channel"
    text: str
    blocks: list[dict] | None = None


# =============================================================================
# ENCRYPTION HELPERS
# =============================================================================


def encrypt_token(token: str) -> str:
    """Encrypt a token for secure storage."""
    if not settings.encryption_enabled:
        logger.warning("Encryption not configured - storing token in plaintext")
        return token

    try:
        from cryptography.fernet import Fernet
        f = Fernet(settings.encryption_key.encode())
        return f.encrypt(token.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely store credentials"
        )


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token."""
    if not settings.encryption_enabled:
        return encrypted

    try:
        from cryptography.fernet import Fernet
        f = Fernet(settings.encryption_key.encode())
        return f.decrypt(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credentials"
        )


# =============================================================================
# SLACK MEMBER IMPORT
# =============================================================================


async def import_slack_workspace_members(
    session: AsyncSession,
    access_token: str,
    organization_id: UUID,
    installer_user_id: UUID,
) -> int:
    """
    Import all members from a Slack workspace into the organization.

    - Installer becomes owner (active)
    - First 5 members (including owner) are active on free tier
    - Remaining members are inactive until plan upgrade or manual activation
    - If workspace has > 28 members, this will still import all but log a warning

    Returns the number of members imported.
    """
    from ..models import Organization, User, OrganizationMember, MemberStatus

    # Get org's subscription tier
    result = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        return 0

    tier = org.subscription_tier.value if org.subscription_tier else "free"

    # Determine member limit
    if tier in ("professional", "enterprise"):
        member_limit = -1  # unlimited
    elif tier == "starter":
        member_limit = 20
    else:
        member_limit = 5  # free tier

    # Fetch all workspace members from Slack
    slack_members = []
    cursor = None

    async with httpx.AsyncClient() as client:
        while True:
            params = {"limit": 200}
            if cursor:
                params["cursor"] = cursor

            response = await client.get(
                "https://slack.com/api/users.list",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            data = response.json()

            if not data.get("ok"):
                logger.error(f"Failed to fetch Slack users: {data.get('error')}")
                break

            for member in data.get("members", []):
                # Skip bots, deleted users, and Slackbot
                if member.get("is_bot") or member.get("deleted") or member.get("id") == "USLACKBOT":
                    continue

                slack_members.append({
                    "id": member.get("id"),
                    "email": member.get("profile", {}).get("email"),
                    "name": member.get("real_name") or member.get("name") or "Slack User",
                    "avatar_url": member.get("profile", {}).get("image_192"),
                })

            # Check for pagination
            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    if len(slack_members) > 28:
        logger.warning(f"Large workspace ({len(slack_members)} members) - importing all but consider prompting user")

    # Get existing members to avoid duplicates
    result = await session.execute(
        select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization_id
        )
    )
    existing_user_ids = {row[0] for row in result.fetchall()}

    # Get installer's user to find their email for matching
    result = await session.execute(
        select(User).where(User.id == installer_user_id)
    )
    installer_user = result.scalar_one_or_none()
    installer_email = installer_user.email.lower() if installer_user else None

    imported_count = 0
    active_count = len(existing_user_ids)  # Start with existing members

    for slack_member in slack_members:
        email = slack_member.get("email")
        if not email:
            continue  # Skip users without email (single-channel guests, etc.)

        email_lower = email.lower()

        # Check if user already exists by email
        result = await session.execute(
            select(User).where(User.email == email_lower, User.deleted_at.is_(None))
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            # Update slack_user_id if not set
            if not existing_user.slack_user_id:
                existing_user.slack_user_id = slack_member["id"]

            # Check if already a member
            if existing_user.id in existing_user_ids:
                continue

            user_id = existing_user.id
        else:
            # Create new user
            from uuid import uuid4
            user_id = uuid4()
            new_user = User(
                id=user_id,
                email=email_lower,
                name=slack_member["name"],
                avatar_url=slack_member.get("avatar_url"),
                auth_provider="slack",
                slack_user_id=slack_member["id"],
            )
            session.add(new_user)

        # Determine role and status
        is_installer = email_lower == installer_email
        role = "owner" if is_installer else "member"

        # Determine if should be active
        if member_limit == -1:
            status = MemberStatus.ACTIVE
        elif active_count < member_limit:
            status = MemberStatus.ACTIVE
            active_count += 1
        else:
            status = MemberStatus.INACTIVE

        # Always make installer active
        if is_installer:
            status = MemberStatus.ACTIVE

        # Create membership
        from uuid import uuid4
        membership = OrganizationMember(
            id=uuid4(),
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            status=status,
            invited_by=installer_user_id,
        )
        session.add(membership)
        imported_count += 1

    await session.commit()
    return imported_count


# =============================================================================
# SLACK OAUTH ENDPOINTS
# =============================================================================


@router.get("/slack/install", response_model=SlackInstallResponse)
async def get_slack_install_url(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
) -> SlackInstallResponse:
    """
    Get the Slack OAuth installation URL.

    Requires: PRO tier or higher

    The returned URL should be used to redirect the user to Slack's
    authorization page. After authorization, Slack will redirect back
    to our callback endpoint.
    """
    if not settings.slack_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Slack integration is not configured on this server"
        )

    # Build OAuth URL with required scopes
    scopes = [
        "chat:write",           # Post messages
        "channels:read",        # List public channels
        "groups:read",          # List private channels
        "commands",             # Handle slash commands
        "incoming-webhook",     # Webhook for posting
        "users:read",           # List workspace members
        "users:read.email",     # Read user emails for matching
    ]

    # Include organization ID in state for callback verification
    state = f"{current_user.organization_id}:{current_user.user_id}"

    params = {
        "client_id": settings.slack_client_id,
        "scope": ",".join(scopes),
        "redirect_uri": settings.slack_redirect_uri or f"{settings.api_prefix}/integrations/slack/callback",
        "state": state,
    }

    install_url = f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

    return SlackInstallResponse(install_url=install_url)


@router.get("/slack/callback")
async def slack_oauth_callback(
    code: str,
    state: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SlackCallbackResponse:
    """
    Handle Slack OAuth callback.

    This endpoint is called by Slack after the user authorizes the app.
    It exchanges the authorization code for an access token and stores
    the integration details.
    """
    if not settings.slack_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Slack integration is not configured"
        )

    # Parse state to get organization ID
    try:
        org_id_str, user_id_str = state.split(":")
        organization_id = UUID(org_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "code": code,
                "redirect_uri": settings.slack_redirect_uri,
            },
        )

        data = response.json()

        if not data.get("ok"):
            logger.error(f"Slack OAuth error: {data.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slack authorization failed: {data.get('error')}"
            )

    # Extract token and metadata
    access_token = data.get("access_token")
    team_info = data.get("team", {})
    incoming_webhook = data.get("incoming_webhook", {})
    bot_user_id = data.get("bot_user_id")

    # Get organization and update
    result = await session.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Store encrypted token and metadata
    org.slack_access_token = encrypt_token(access_token)
    org.slack_team_id = team_info.get("id")
    org.slack_team_name = team_info.get("name")
    org.slack_channel_id = incoming_webhook.get("channel_id")
    org.slack_channel_name = incoming_webhook.get("channel")
    org.slack_bot_user_id = bot_user_id
    org.slack_installed_at = datetime.utcnow()

    await session.commit()

    logger.info(f"Slack integration installed for org {organization_id} (team: {team_info.get('name')})")

    # Import workspace members
    imported_count = 0
    try:
        imported_count = await import_slack_workspace_members(
            session=session,
            access_token=access_token,
            organization_id=organization_id,
            installer_user_id=UUID(user_id_str),
        )
        logger.info(f"Imported {imported_count} members from Slack workspace")
    except Exception as e:
        logger.error(f"Failed to import Slack workspace members: {e}")
        # Don't fail the whole flow - Slack is connected, members can be imported later

    # Redirect to frontend callback page with success params
    redirect_url = f"{settings.frontend_url}/integrations/slack/callback?success=true&team_name={team_info.get('name', 'Unknown')}&imported={imported_count}"

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/slack/status", response_model=SlackStatusResponse)
async def get_slack_status(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SlackStatusResponse:
    """Get current Slack integration status."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return SlackStatusResponse(
        connected=bool(org.slack_access_token),
        team_name=org.slack_team_name,
        channel_name=org.slack_channel_name,
        installed_at=org.slack_installed_at,
    )


@router.delete("/slack")
async def disconnect_slack(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Disconnect Slack integration."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Clear all Slack fields
    org.slack_access_token = None
    org.slack_team_id = None
    org.slack_team_name = None
    org.slack_channel_id = None
    org.slack_channel_name = None
    org.slack_bot_user_id = None
    org.slack_installed_at = None

    await session.commit()

    return {"message": "Slack integration disconnected"}


# =============================================================================
# MICROSOFT TEAMS WEBHOOK ENDPOINTS
# =============================================================================


@router.post("/teams", response_model=TeamsStatusResponse)
async def configure_teams_webhook(
    request: TeamsWebhookRequest,
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamsStatusResponse:
    """
    Configure Microsoft Teams incoming webhook.

    Requires: PRO tier or higher

    The webhook URL should be obtained from Teams by:
    1. Right-click a channel -> Connectors
    2. Add "Incoming Webhook"
    3. Configure and copy the webhook URL
    """
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Test the webhook with a validation message
    async with httpx.AsyncClient() as client:
        try:
            test_response = await client.post(
                str(request.webhook_url),
                json={
                    "@type": "MessageCard",
                    "@context": "http://schema.org/extensions",
                    "themeColor": "6366f1",
                    "summary": "Imputable Connected",
                    "sections": [{
                        "activityTitle": "Imputable Integration Test",
                        "activitySubtitle": "This channel is now connected to Imputable",
                        "activityImage": "https://imputable.app/logo.png",
                        "facts": [
                            {"name": "Status", "value": "Connected"},
                            {"name": "Organization", "value": org.name},
                        ],
                        "markdown": True
                    }]
                },
                timeout=10.0,
            )

            if test_response.status_code not in (200, 201):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Webhook test failed with status {test_response.status_code}"
                )

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to reach webhook URL: {str(e)}"
            )

    # Store webhook configuration
    org.teams_webhook_url = str(request.webhook_url)
    org.teams_channel_name = request.channel_name
    org.teams_installed_at = datetime.utcnow()

    await session.commit()

    logger.info(f"Teams webhook configured for org {current_user.organization_id}")

    return TeamsStatusResponse(
        connected=True,
        channel_name=request.channel_name,
        installed_at=org.teams_installed_at,
    )


@router.get("/teams/status", response_model=TeamsStatusResponse)
async def get_teams_status(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamsStatusResponse:
    """Get current Teams integration status."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return TeamsStatusResponse(
        connected=bool(org.teams_webhook_url),
        channel_name=org.teams_channel_name,
        installed_at=org.teams_installed_at,
    )


@router.delete("/teams")
async def disconnect_teams(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Disconnect Teams integration."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.teams_webhook_url = None
    org.teams_channel_name = None
    org.teams_installed_at = None

    await session.commit()

    return {"message": "Teams integration disconnected"}


# =============================================================================
# COMBINED STATUS ENDPOINT
# =============================================================================


@router.get("/status", response_model=IntegrationStatusResponse)
async def get_integration_status(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IntegrationStatusResponse:
    """Get status of all integrations."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return IntegrationStatusResponse(
        slack=SlackStatusResponse(
            connected=bool(org.slack_access_token),
            team_name=org.slack_team_name,
            channel_name=org.slack_channel_name,
            installed_at=org.slack_installed_at,
        ),
        teams=TeamsStatusResponse(
            connected=bool(org.teams_webhook_url),
            channel_name=org.teams_channel_name,
            installed_at=org.teams_installed_at,
        ),
    )


# =============================================================================
# SLACK SLASH COMMAND HANDLER
# =============================================================================


def verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """
    Verify Slack request signature using HMAC-SHA256.

    See: https://api.slack.com/authentication/verifying-requests-from-slack
    """
    if not settings.slack_signing_secret:
        logger.warning("Slack signing secret not configured")
        return False

    # Check timestamp to prevent replay attacks (5 minutes)
    try:
        request_timestamp = int(timestamp)
        if abs(time.time() - request_timestamp) > 60 * 5:
            logger.warning("Slack request timestamp too old")
            return False
    except ValueError:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected_sig = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature)


@router.post("/slack/command")
async def handle_slack_command(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_slack_signature: Annotated[str | None, Header()] = None,
    x_slack_request_timestamp: Annotated[str | None, Header()] = None,
):
    """
    Handle Slack slash command (/decisions).

    Routes commands based on text input:
    - Empty: Show main menu
    - add/create <title>: Create decision with prefilled title
    - list/show: View recent decisions
    - help: Show help message

    Usage examples:
    - /decisions
    - /decisions add Use PostgreSQL for analytics
    - /decisions list
    - /decisions help
    """
    from ..services.slack_service import SlackCommandRouter, SlackBlocks

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature (skip in development if not configured)
    if settings.environment != "development" or settings.slack_signing_secret:
        if not x_slack_signature or not x_slack_request_timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Slack signature headers"
            )

        if not verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Slack signature"
            )

    # Parse form data
    form_data = await request.form()

    team_id = form_data.get("team_id", "")
    channel_id = form_data.get("channel_id", "")
    user_id = form_data.get("user_id", "")
    user_name = form_data.get("user_name", "")
    trigger_id = form_data.get("trigger_id", "")
    text = form_data.get("text", "").strip()

    # Use the router to handle the command
    router_service = SlackCommandRouter(session)
    intent, argument = router_service.parse_intent(text)

    # Find organization by Slack team ID
    result = await session.execute(
        select(Organization).where(Organization.slack_team_id == team_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        return {
            "response_type": "ephemeral",
            "text": ":warning: This Slack workspace is not connected to Imputable. Please install the app first.",
        }

    # Use the SlackCommandRouter to handle all intents
    # This routes to: menu, help, list, search, poll, add
    return await router_service.route(
        text=text,
        team_id=team_id,
        user_id=user_id,
        trigger_id=trigger_id,
        channel_id=channel_id,
    )


@router.post("/slack/interactions")
async def handle_slack_interactions(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_slack_signature: Annotated[str | None, Header()] = None,
    x_slack_request_timestamp: Annotated[str | None, Header()] = None,
):
    """
    Handle Slack interactive components (button clicks, modal submissions, shortcuts).

    This endpoint receives:
    - block_actions: When users click buttons (including poll votes)
    - view_submission: When users submit modals
    - message_action: When users trigger message shortcuts (context menu)
    - shortcut: When users trigger global shortcuts
    """
    import json
    from ..services.slack_service import (
        SlackInteractionHandler,
        SlackMessageShortcutHandler,
        SlackBlocks,
    )

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    if settings.environment != "development" or settings.slack_signing_secret:
        if not x_slack_signature or not x_slack_request_timestamp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Slack signature headers"
            )

        if not verify_slack_signature(body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Slack signature"
            )

    # Parse form data (payload is URL-encoded JSON)
    form_data = await request.form()
    payload_str = form_data.get("payload", "{}")
    payload = json.loads(payload_str)

    interaction_type = payload.get("type")
    team_id = payload.get("team", {}).get("id")
    user_id = payload.get("user", {}).get("id")

    # Get organization and bot token for API calls
    bot_token = None
    if team_id:
        result = await session.execute(
            select(Organization).where(Organization.slack_team_id == team_id)
        )
        org = result.scalar_one_or_none()
        if org and org.slack_access_token:
            bot_token = decrypt_token(org.slack_access_token)

    # Handle message shortcuts (context menu actions)
    if interaction_type == "message_action":
        callback_id = payload.get("callback_id")

        if callback_id == "log_message_as_decision":
            handler = SlackMessageShortcutHandler(session)
            return await handler.handle_log_as_decision(payload, bot_token=bot_token)

        elif callback_id == "ai_summarize_decision":
            handler = SlackMessageShortcutHandler(session)
            return await handler.handle_ai_summarize_decision(payload, bot_token=bot_token)

    # Handle view submissions (modal forms)
    elif interaction_type == "view_submission":
        handler = SlackInteractionHandler(session)
        result = await handler.handle(payload)
        return result if result else {}

    # Handle block actions (button clicks including poll votes)
    elif interaction_type == "block_actions":
        handler = SlackInteractionHandler(session)
        result = await handler.handle(payload)
        if result:
            return result

        # Fallback for any unhandled actions
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id")

            if action_id == "show_help":
                return {
                    "response_type": "ephemeral",
                    "blocks": SlackBlocks.help_message(),
                    "replace_original": False,
                }

    # Default: acknowledge without response
    return {}


# =============================================================================
# MICROSOFT TEAMS BOT FRAMEWORK ENDPOINT
# =============================================================================


@router.post("/teams/messages")
async def handle_teams_messages(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Handle Microsoft Teams Bot Framework activities.

    This endpoint receives:
    - message: Bot commands (search, poll, help)
    - invoke: Card actions (poll votes, log as decision form)
    - composeExtension: Messaging extension actions (Log as Decision)

    Authentication is handled via Bot Framework JWT tokens.
    """
    from ..integrations.teams import TeamsBotService

    # Get authorization header
    auth_header = request.headers.get("Authorization", "")

    # Parse request body
    try:
        activity = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body"
        )

    activity_type = activity.get("type")
    conversation = activity.get("conversation", {})
    tenant_id = conversation.get("tenantId") or activity.get("channelData", {}).get("tenant", {}).get("id")

    # Initialize bot service
    bot_service = TeamsBotService(session)

    # Skip auth in development if not configured
    if settings.environment != "development" or bot_service.is_configured:
        if not bot_service.is_configured:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Teams Bot Framework is not configured"
            )

        # Verify JWT token
        claims = await bot_service.verify_token(auth_header)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Bot Framework token"
            )

    # Get organization by tenant ID
    org = await bot_service.get_organization_by_tenant(tenant_id) if tenant_id else None

    if not org:
        # Try to find org by service URL (fallback for initial setup)
        service_url = activity.get("serviceUrl", "")
        if service_url:
            result = await session.execute(
                select(Organization).where(Organization.teams_service_url == service_url)
            )
            org = result.scalar_one_or_none()

    if not org:
        return {
            "type": "message",
            "text": "This Teams workspace is not connected to Imputable. Please install the app from your organization's settings.",
        }

    # Store service URL for future API calls (may change per tenant)
    if activity.get("serviceUrl") and org.teams_service_url != activity.get("serviceUrl"):
        org.teams_service_url = activity.get("serviceUrl")
        await session.commit()

    # Route by activity type
    if activity_type == "message":
        # Bot command
        response = await bot_service.process_message_activity(activity, org)
        return response

    elif activity_type == "invoke":
        invoke_name = activity.get("name", "")

        # Compose extension (messaging extension)
        if invoke_name == "composeExtension/fetchTask":
            response = await bot_service.process_compose_extension(activity, org)
            return response

        elif invoke_name == "composeExtension/submitAction":
            # Form submission from compose extension
            response = await bot_service.process_card_action(activity, org)
            return {
                "task": {
                    "type": "message",
                    "value": "Decision logged successfully!" if response else "Failed to log decision",
                }
            }

        elif invoke_name == "adaptiveCard/action":
            # Adaptive Card action (button click)
            response = await bot_service.process_card_action(activity, org)
            return {
                "statusCode": 200,
                "type": "application/vnd.microsoft.card.adaptive",
                "value": response.get("attachments", [{}])[0].get("content", {}),
            }

        else:
            # Unknown invoke
            return {"statusCode": 200}

    elif activity_type == "conversationUpdate":
        # Bot added to conversation - send welcome message
        members_added = activity.get("membersAdded", [])
        bot_id = activity.get("recipient", {}).get("id")

        for member in members_added:
            if member.get("id") == bot_id:
                # Bot was added - store tenant info
                if tenant_id and not org.teams_tenant_id:
                    org.teams_tenant_id = tenant_id
                    org.teams_bot_id = bot_id
                    org.teams_service_url = activity.get("serviceUrl")
                    await session.commit()

                from ..integrations.teams import TeamsCards
                return {
                    "type": "message",
                    "attachments": [
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": TeamsCards.help_card(),
                        }
                    ],
                }

        return {}

    # Default acknowledgment
    return {}


# =============================================================================
# TEST NOTIFICATION ENDPOINT
# =============================================================================


@router.post("/test-notification")
async def send_test_notification(
    current_user: Annotated[CurrentUser, Depends(require_org_context)],
    subscription: IntegrationsDep,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Send a test notification to configured integrations."""
    result = await session.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not org.slack_access_token and not org.teams_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No integrations configured. Please connect Slack or Teams first."
        )

    # Send test notifications in background
    notification_service = NotificationService(session)

    if org.slack_access_token:
        background_tasks.add_task(
            notification_service.send_test_slack,
            org,
        )

    if org.teams_webhook_url:
        background_tasks.add_task(
            notification_service.send_test_teams,
            org,
        )

    return {
        "message": "Test notifications queued",
        "slack": bool(org.slack_access_token),
        "teams": bool(org.teams_webhook_url),
    }

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

    # Redirect to frontend callback page with success params
    redirect_url = f"{settings.frontend_url}/integrations/slack/callback?success=true&team_name={team_info.get('name', 'Unknown')}"

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

    # Route based on intent
    if intent == "help":
        return {
            "response_type": "ephemeral",
            "blocks": SlackBlocks.help_message(),
        }

    elif intent == "menu":
        # Return main menu inline (modal requires bot token)
        return {
            "response_type": "ephemeral",
            "blocks": SlackBlocks.main_menu(),
        }

    elif intent == "list":
        # Fetch recent decisions
        decisions_result = await session.execute(
            select(Decision)
            .where(Decision.organization_id == org.id)
            .where(Decision.deleted_at.is_(None))
            .order_by(Decision.created_at.desc())
            .limit(10)
        )
        decisions_db = decisions_result.scalars().all()

        decisions = []
        for d in decisions_db:
            title = d.current_version.title if d.current_version else "Untitled"
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

    elif intent == "add":
        # Create decision directly (argument is the title)
        title = argument if argument else "Untitled Decision"

        from ..models import OrganizationMember
        from sqlalchemy import func

        # Get an admin user for this org
        admin_result = await session.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == org.id)
            .where(OrganizationMember.role == "admin")
            .limit(1)
        )
        admin_member = admin_result.scalar_one_or_none()

        if not admin_member:
            return {
                "response_type": "ephemeral",
                "text": ":x: Unable to create decision: No admin found for this organization.",
            }

        # Get next decision number
        max_num_result = await session.execute(
            select(func.max(Decision.decision_number))
            .where(Decision.organization_id == org.id)
        )
        max_num = max_num_result.scalar() or 0

        # Create the decision
        from ..models import DecisionVersion, ImpactLevel

        decision = Decision(
            organization_id=org.id,
            decision_number=max_num + 1,
            status=DecisionStatus.DRAFT,
            created_by=admin_member.user_id,
        )
        session.add(decision)
        await session.flush()

        # Create initial version
        version = DecisionVersion(
            decision_id=decision.id,
            version_number=1,
            title=title,
            impact_level=ImpactLevel.MEDIUM,
            content={
                "context": f"Created via Slack by @{user_name}",
                "choice": "",
                "rationale": "",
                "alternatives": [],
            },
            tags=["slack-created"],
            created_by=admin_member.user_id,
            change_summary="Created via Slack command",
        )
        session.add(version)
        await session.flush()

        # Link current version
        decision.current_version_id = version.id
        await session.commit()

        # Return success message
        return {
            "response_type": "in_channel",
            "blocks": SlackBlocks.decision_created(
                decision_number=decision.decision_number,
                title=title,
                decision_id=str(decision.id),
                user_id=user_id,
            ),
        }

    # Default: show help
    return {
        "response_type": "ephemeral",
        "blocks": SlackBlocks.help_message(),
    }


@router.post("/slack/interactions")
async def handle_slack_interactions(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_slack_signature: Annotated[str | None, Header()] = None,
    x_slack_request_timestamp: Annotated[str | None, Header()] = None,
):
    """
    Handle Slack interactive components (button clicks, modal submissions).

    This endpoint receives:
    - block_actions: When users click buttons
    - view_submission: When users submit modals
    """
    import json
    from ..services.slack_service import SlackInteractionHandler, SlackBlocks

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

    # Handle view submissions (modal forms)
    if interaction_type == "view_submission":
        callback_id = payload.get("view", {}).get("callback_id")

        if callback_id == "create_decision_modal":
            handler = SlackInteractionHandler(session)
            result = await handler.handle(payload)
            return result if result else {}

    # Handle block actions (button clicks)
    elif interaction_type == "block_actions":
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

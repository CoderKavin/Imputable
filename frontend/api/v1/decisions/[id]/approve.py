"""Approval API - POST /api/v1/decisions/{id}/approve"""

from http.server import BaseHTTPRequestHandler
import json
import os
from uuid import uuid4
from datetime import datetime
import urllib.request
import urllib.error


def send_slack_approval_notification(
    slack_token: str,
    channel_id: str,
    decision_number: int,
    decision_id: str,
    title: str,
    approver_name: str,
    approval_status: str,
    comment: str,
    approved_count: int,
    required_count: int,
    decision_became_approved: bool,
):
    """Send approval notification to Slack."""
    try:
        from cryptography.fernet import Fernet
        encryption_key = os.environ.get("ENCRYPTION_KEY", "")
        if encryption_key:
            f = Fernet(encryption_key.encode())
            token = f.decrypt(slack_token.encode()).decode()
        else:
            token = slack_token
    except Exception:
        token = slack_token

    if not token or not channel_id:
        return

    decision_url = f"https://app.imputable.io/decisions/{decision_id}"

    # Choose emoji and color based on approval status
    if approval_status == "approved":
        emoji = "✅"
        color = "10b981"
        action_text = "approved"
    elif approval_status == "rejected":
        emoji = "❌"
        color = "ef4444"
        action_text = "rejected"
    else:
        emoji = "⏭️"
        color = "6b7280"
        action_text = "abstained from"

    # Build the header based on whether decision is fully approved
    if decision_became_approved:
        header_text = "🎉 Decision Approved"
        progress_text = f"All {required_count} required reviewers have approved!"
    else:
        header_text = f"{emoji} Vote Submitted"
        progress_text = f"Progress: {approved_count}/{required_count} approved"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text, "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{decision_url}|DEC-{decision_number}: {title}>*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{approver_name}* {action_text} this decision."
            }
        },
    ]

    if comment:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_\"{comment}\"_"}
        })

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": progress_text}]
    })

    blocks.append({
        "type": "actions",
        "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "View Decision", "emoji": True},
            "url": decision_url,
            "style": "primary"
        }]
    })

    payload = json.dumps({
        "channel": channel_id,
        "text": f"{approver_name} {action_text} DEC-{decision_number}",
        "attachments": [{"color": color, "blocks": blocks}]
    }).encode()

    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def send_teams_approval_notification(
    webhook_url: str,
    decision_number: int,
    decision_id: str,
    title: str,
    approver_name: str,
    approval_status: str,
    comment: str,
    approved_count: int,
    required_count: int,
    decision_became_approved: bool,
):
    """Send approval notification to Teams."""
    if not webhook_url:
        return

    decision_url = f"https://app.imputable.io/decisions/{decision_id}"

    # Choose color based on status
    if decision_became_approved:
        color = "10b981"
        header = "🎉 Decision Approved"
    elif approval_status == "approved":
        color = "10b981"
        header = "✅ Vote Submitted"
    elif approval_status == "rejected":
        color = "ef4444"
        header = "❌ Vote Submitted"
    else:
        color = "6b7280"
        header = "⏭️ Vote Submitted"

    action_text = {
        "approved": "approved",
        "rejected": "rejected",
        "abstained": "abstained from"
    }.get(approval_status, "voted on")

    facts = [
        {"name": "Action", "value": f"{approver_name} {action_text} this decision"},
        {"name": "Progress", "value": f"{approved_count}/{required_count} approved"},
    ]
    if comment:
        facts.append({"name": "Comment", "value": comment})

    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "summary": f"{approver_name} {action_text} DEC-{decision_number}",
        "sections": [{
            "activityTitle": header,
            "activitySubtitle": f"DEC-{decision_number}: {title}",
            "facts": facts,
            "markdown": True
        }],
        "potentialAction": [{
            "@type": "OpenUri",
            "name": "View Decision",
            "targets": [{"os": "default", "uri": decision_url}]
        }]
    }

    payload = json.dumps(card).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, {})

    def do_POST(self):
        try:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self._send(401, {"error": "Not authenticated"})
                return

            org_id = self.headers.get("X-Organization-ID")
            if not org_id:
                self._send(400, {"error": "X-Organization-ID header required"})
                return

            # Extract decision_id from path: /api/v1/decisions/{id}/approve
            path_parts = self.path.split("/")
            decision_id = None
            for i, part in enumerate(path_parts):
                if part == "decisions" and i + 1 < len(path_parts):
                    decision_id = path_parts[i + 1].split("?")[0]
                    break

            if not decision_id:
                self._send(400, {"error": "Decision ID required"})
                return

            token = auth[7:]

            import firebase_admin
            from firebase_admin import credentials, auth as fb_auth
            from sqlalchemy import create_engine, text

            try:
                try:
                    firebase_admin.get_app()
                except ValueError:
                    project_id = os.environ.get("FIREBASE_PROJECT_ID")
                    client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
                    private_key = os.environ.get("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")

                    if not all([project_id, client_email, private_key]):
                        self._send(500, {"error": "Firebase not configured"})
                        return

                    cred = credentials.Certificate({
                        "type": "service_account",
                        "project_id": project_id,
                        "private_key": private_key,
                        "client_email": client_email,
                        "token_uri": "https://oauth2.googleapis.com/token",
                    })
                    firebase_admin.initialize_app(cred)

                decoded = fb_auth.verify_id_token(token)
                firebase_uid = decoded.get("uid") or decoded.get("user_id")
            except Exception as e:
                self._send(401, {"error": f"Invalid token: {str(e)}"})
                return

            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                self._send(500, {"error": "Database not configured"})
                return

            engine = create_engine(db_url, connect_args={"sslmode": "require"})

            with engine.connect() as conn:
                # Get user
                result = conn.execute(text("""
                    SELECT id, name, email FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if not user_row:
                    self._send(401, {"error": "User not found"})
                    return

                user_id = user_row[0]
                user_name = user_row[1]
                user_email = user_row[2]

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                # Get decision, current version, and org notification settings
                result = conn.execute(text("""
                    SELECT d.id, d.status, d.current_version_id, d.organization_id,
                           d.decision_number, dv.title,
                           o.slack_access_token, o.slack_channel_id, o.teams_webhook_url
                    FROM decisions d
                    JOIN decision_versions dv ON d.current_version_id = dv.id
                    JOIN organizations o ON d.organization_id = o.id
                    WHERE d.id = :decision_id AND d.deleted_at IS NULL
                """), {"decision_id": decision_id})
                decision_row = result.fetchone()

                if not decision_row:
                    self._send(404, {"error": "Decision not found"})
                    return

                if str(decision_row[3]) != org_id:
                    self._send(403, {"error": "Decision not in this organization"})
                    return

                current_version_id = decision_row[2]
                decision_status = decision_row[1]
                decision_number = decision_row[4]
                decision_title = decision_row[5]
                slack_token = decision_row[6]
                slack_channel_id = decision_row[7]
                teams_webhook_url = decision_row[8]

                # Check if user is a required reviewer for this version
                result = conn.execute(text("""
                    SELECT id FROM required_reviewers
                    WHERE decision_version_id = :version_id AND user_id = :user_id
                """), {"version_id": current_version_id, "user_id": user_id})

                if not result.fetchone():
                    self._send(403, {"error": "You are not a required reviewer for this decision"})
                    return

                # Parse request body
                content_len = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                approval_status = body.get("status", "").lower()
                comment = body.get("comment", "")

                if approval_status not in ("approved", "rejected", "abstained"):
                    self._send(400, {"error": "Invalid status. Must be: approved, rejected, or abstained"})
                    return

                # Check if user already submitted an approval
                result = conn.execute(text("""
                    SELECT id FROM approvals
                    WHERE decision_version_id = :version_id AND user_id = :user_id
                """), {"version_id": current_version_id, "user_id": user_id})
                existing = result.fetchone()

                if existing:
                    # Update existing approval
                    conn.execute(text("""
                        UPDATE approvals
                        SET status = :status, comment = :comment, created_at = NOW()
                        WHERE id = :id
                    """), {"status": approval_status, "comment": comment, "id": existing[0]})
                    approval_id = str(existing[0])
                else:
                    # Insert new approval
                    approval_id = str(uuid4())
                    conn.execute(text("""
                        INSERT INTO approvals (id, decision_version_id, user_id, status, comment, created_at)
                        VALUES (:id, :version_id, :user_id, :status, :comment, NOW())
                    """), {
                        "id": approval_id,
                        "version_id": current_version_id,
                        "user_id": user_id,
                        "status": approval_status,
                        "comment": comment
                    })

                # Check if all required reviewers have approved
                result = conn.execute(text("""
                    SELECT
                        (SELECT COUNT(*) FROM required_reviewers WHERE decision_version_id = :version_id) as required_count,
                        (SELECT COUNT(*) FROM approvals WHERE decision_version_id = :version_id AND status = 'approved') as approved_count,
                        (SELECT COUNT(*) FROM approvals WHERE decision_version_id = :version_id AND status = 'rejected') as rejected_count
                """), {"version_id": current_version_id})
                counts = result.fetchone()
                required_count = counts[0]
                approved_count = counts[1]
                rejected_count = counts[2]

                # Auto-transition decision status if all required reviewers approved
                new_decision_status = decision_status
                decision_became_approved = False
                if required_count > 0 and approved_count >= required_count:
                    conn.execute(text("""
                        UPDATE decisions SET status = 'approved' WHERE id = :decision_id
                    """), {"decision_id": decision_id})
                    new_decision_status = "approved"
                    decision_became_approved = True

                conn.commit()

                # Send notifications to Slack and Teams (non-blocking)
                try:
                    if slack_token and slack_channel_id:
                        send_slack_approval_notification(
                            slack_token=slack_token,
                            channel_id=slack_channel_id,
                            decision_number=decision_number,
                            decision_id=decision_id,
                            title=decision_title,
                            approver_name=user_name,
                            approval_status=approval_status,
                            comment=comment,
                            approved_count=approved_count,
                            required_count=required_count,
                            decision_became_approved=decision_became_approved,
                        )
                except Exception:
                    pass  # Don't fail the request if notification fails

                try:
                    if teams_webhook_url:
                        send_teams_approval_notification(
                            webhook_url=teams_webhook_url,
                            decision_number=decision_number,
                            decision_id=decision_id,
                            title=decision_title,
                            approver_name=user_name,
                            approval_status=approval_status,
                            comment=comment,
                            approved_count=approved_count,
                            required_count=required_count,
                            decision_became_approved=decision_became_approved,
                        )
                except Exception:
                    pass  # Don't fail the request if notification fails

                self._send(200, {
                    "success": True,
                    "approval": {
                        "id": approval_id,
                        "decision_version_id": str(current_version_id),
                        "user": {
                            "id": str(user_id),
                            "name": user_name,
                            "email": user_email
                        },
                        "status": approval_status,
                        "comment": comment
                    },
                    "decision_status": new_decision_status,
                    "approval_progress": {
                        "required": required_count,
                        "approved": approved_count,
                        "rejected": rejected_count
                    }
                })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

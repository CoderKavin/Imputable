"""Decision detail API - GET, PUT, POST (approve) /api/v1/decisions/[id]"""

from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from datetime import datetime
import urllib.request


# Email sending via Resend
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "Imputable <notifications@imputable.io>")


def send_email_notification(to_email: str, subject: str, html_content: str):
    """Send an email notification via Resend API."""
    if not RESEND_API_KEY:
        return False
    try:
        payload = json.dumps({
            "from": EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False


def send_status_change_emails(conn, org_id: str, decision_id: str, decision_number: int,
                              title: str, old_status: str, new_status: str,
                              changer_name: str, changer_id: str, org_name: str):
    """Send email notifications for status changes to org members who have it enabled."""
    from sqlalchemy import text
    if not RESEND_API_KEY:
        return
    try:
        result = conn.execute(text("""
            SELECT u.id, u.email, u.name, u.settings
            FROM organization_members om
            JOIN users u ON om.user_id = u.id
            WHERE om.organization_id = :org_id AND u.id != :changer_id AND u.deleted_at IS NULL
        """), {"org_id": org_id, "changer_id": changer_id})

        decision_url = f"https://app.imputable.io/decisions/{decision_id}"
        status_colors = {"draft": "#6b7280", "pending_review": "#f59e0b", "approved": "#10b981", "deprecated": "#ef4444", "superseded": "#8b5cf6"}

        for row in result.fetchall():
            user_id, email, name, settings = row[0], row[1], row[2], row[3]
            if settings:
                user_settings = settings if isinstance(settings, dict) else json.loads(settings) if settings else {}
                if not user_settings.get("notifications", {}).get("email_status_change", True):
                    continue

            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8"></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">Decision Status Changed</h1>
                </div>
                <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p style="margin: 0 0 20px;">Hi {name or 'there'},</p>
                    <p style="margin: 0 0 20px;">A decision status has been updated in <strong>{org_name}</strong>:</p>
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h2 style="margin: 0 0 10px; font-size: 18px; color: #111;">DECISION-{decision_number}: {title}</h2>
                        <p style="margin: 0 0 15px; color: #6b7280; font-size: 14px;">Changed by {changer_name}</p>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="background: {status_colors.get(old_status, '#6b7280')}20; color: {status_colors.get(old_status, '#6b7280')}; padding: 4px 12px; border-radius: 20px; font-size: 12px; text-decoration: line-through;">{old_status.replace('_', ' ').title()}</span>
                            <span style="color: #9ca3af;">→</span>
                            <span style="background: {status_colors.get(new_status, '#6b7280')}20; color: {status_colors.get(new_status, '#6b7280')}; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">{new_status.replace('_', ' ').title()}</span>
                        </div>
                    </div>
                    <a href="{decision_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin-top: 10px;">View Decision</a>
                    <p style="margin: 30px 0 0; color: #9ca3af; font-size: 12px;">
                        You're receiving this because you have status change notifications enabled for {org_name}.<br>
                        <a href="https://app.imputable.io/settings?tab=notifications" style="color: #6366f1;">Manage notification preferences</a>
                    </p>
                </div>
            </body></html>
            """
            send_email_notification(email, f"[{org_name}] Decision Status Changed: DECISION-{decision_number} is now {new_status.replace('_', ' ').title()}", html_content)
    except Exception as e:
        print(f"Error sending status change emails: {e}")


def send_decision_updated_emails(conn, org_id: str, decision_id: str, decision_number: int,
                                 title: str, version_number: int, change_summary: str,
                                 updater_name: str, updater_id: str, org_name: str):
    """Send email notifications for decision updates to org members who have it enabled."""
    from sqlalchemy import text
    if not RESEND_API_KEY:
        return
    try:
        result = conn.execute(text("""
            SELECT u.id, u.email, u.name, u.settings
            FROM organization_members om
            JOIN users u ON om.user_id = u.id
            WHERE om.organization_id = :org_id AND u.id != :updater_id AND u.deleted_at IS NULL
        """), {"org_id": org_id, "updater_id": updater_id})

        decision_url = f"https://app.imputable.io/decisions/{decision_id}"

        for row in result.fetchall():
            user_id, email, name, settings = row[0], row[1], row[2], row[3]
            if settings:
                user_settings = settings if isinstance(settings, dict) else json.loads(settings) if settings else {}
                if not user_settings.get("notifications", {}).get("email_decision_updated", True):
                    continue

            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8"></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">Decision Updated</h1>
                </div>
                <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p style="margin: 0 0 20px;">Hi {name or 'there'},</p>
                    <p style="margin: 0 0 20px;">A decision has been amended in <strong>{org_name}</strong>:</p>
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h2 style="margin: 0 0 10px; font-size: 18px; color: #111;">DECISION-{decision_number}: {title}</h2>
                        <p style="margin: 0 0 15px; color: #6b7280; font-size: 14px;">Updated by {updater_name} • Version {version_number}</p>
                        <div style="background: #f3f4f6; border-left: 3px solid #6366f1; padding: 12px 16px; margin: 15px 0;">
                            <p style="margin: 0; font-size: 14px; color: #374151;"><strong>Change Summary:</strong><br>{change_summary}</p>
                        </div>
                    </div>
                    <a href="{decision_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin-top: 10px;">View Changes</a>
                    <p style="margin: 30px 0 0; color: #9ca3af; font-size: 12px;">
                        You're receiving this because you have decision update notifications enabled for {org_name}.<br>
                        <a href="https://app.imputable.io/settings?tab=notifications" style="color: #6366f1;">Manage notification preferences</a>
                    </p>
                </div>
            </body></html>
            """
            send_email_notification(email, f"[{org_name}] Decision Updated: DECISION-{decision_number} - {title} (v{version_number})", html_content)
    except Exception as e:
        print(f"Error sending decision updated emails: {e}")


def send_approval_emails(conn, org_id: str, decision_id: str, decision_number: int,
                         title: str, approver_name: str, approver_id: str, approval_status: str,
                         comment: str, org_name: str, decision_became_approved: bool, creator_id: str):
    """Send email notifications for approvals to decision creator and org admins."""
    from sqlalchemy import text
    if not RESEND_API_KEY:
        return
    try:
        # Notify the decision creator (if not the approver) and admins
        result = conn.execute(text("""
            SELECT DISTINCT u.id, u.email, u.name, u.settings
            FROM users u
            LEFT JOIN organization_members om ON u.id = om.user_id AND om.organization_id = :org_id
            WHERE u.deleted_at IS NULL
              AND u.id != :approver_id
              AND (u.id = :creator_id OR om.role = 'admin')
        """), {"org_id": org_id, "approver_id": approver_id, "creator_id": creator_id})

        decision_url = f"https://app.imputable.io/decisions/{decision_id}"
        status_emoji = {"approved": "✅", "rejected": "❌", "abstained": "⏭️"}.get(approval_status, "")
        status_color = {"approved": "#10b981", "rejected": "#ef4444", "abstained": "#6b7280"}.get(approval_status, "#6b7280")

        for row in result.fetchall():
            user_id, email, name, settings = row[0], row[1], row[2], row[3]
            if settings:
                user_settings = settings if isinstance(settings, dict) else json.loads(settings) if settings else {}
                if not user_settings.get("notifications", {}).get("email_status_change", True):
                    continue

            if decision_became_approved:
                subject = f"[{org_name}] 🎉 Decision Approved: DECISION-{decision_number} - {title}"
                header = "🎉 Decision Fully Approved"
                message = f"Great news! <strong>DECISION-{decision_number}: {title}</strong> has received all required approvals and is now officially approved."
            else:
                subject = f"[{org_name}] {status_emoji} Vote on DECISION-{decision_number}: {approver_name} {approval_status}"
                header = f"{status_emoji} Vote Submitted"
                message = f"<strong>{approver_name}</strong> has {approval_status} <strong>DECISION-{decision_number}: {title}</strong>."

            html_content = f"""
            <!DOCTYPE html><html><head><meta charset="utf-8"></head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, {status_color} 0%, {'#059669' if decision_became_approved else status_color} 100%); padding: 30px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">{header}</h1>
                </div>
                <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p style="margin: 0 0 20px;">Hi {name or 'there'},</p>
                    <p style="margin: 0 0 20px;">{message}</p>
                    {'<div style="background: #f3f4f6; border-left: 3px solid ' + status_color + '; padding: 12px 16px; margin: 15px 0;"><p style="margin: 0; font-size: 14px; color: #374151;"><em>"' + comment + '"</em></p></div>' if comment else ''}
                    <a href="{decision_url}" style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 500; margin-top: 10px;">View Decision</a>
                    <p style="margin: 30px 0 0; color: #9ca3af; font-size: 12px;">
                        <a href="https://app.imputable.io/settings?tab=notifications" style="color: #6366f1;">Manage notification preferences</a>
                    </p>
                </div>
            </body></html>
            """
            send_email_notification(email, subject, html_content)
    except Exception as e:
        print(f"Error sending approval emails: {e}")


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

    if decision_became_approved:
        header_text = "🎉 Decision Approved"
        progress_text = f"All {required_count} required reviewers have approved!"
    else:
        header_text = f"{emoji} Vote Submitted"
        progress_text = f"Progress: {approved_count}/{required_count} approved"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header_text, "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*<{decision_url}|DECISION-{decision_number}: {title}>*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{approver_name}* {action_text} this decision."}},
    ]
    if comment:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"_\"{comment}\"_"}})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": progress_text}]})
    blocks.append({"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "View Decision", "emoji": True}, "url": decision_url, "style": "primary"}]})

    payload = json.dumps({"channel": channel_id, "text": f"{approver_name} {action_text} DECISION-{decision_number}", "attachments": [{"color": color, "blocks": blocks}]}).encode()
    req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
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

    action_text = {"approved": "approved", "rejected": "rejected", "abstained": "abstained from"}.get(approval_status, "voted on")
    facts = [{"name": "Action", "value": f"{approver_name} {action_text} this decision"}, {"name": "Progress", "value": f"{approved_count}/{required_count} approved"}]
    if comment:
        facts.append({"name": "Comment", "value": comment})

    card = {"@type": "MessageCard", "@context": "http://schema.org/extensions", "themeColor": color, "summary": f"{approver_name} {action_text} DECISION-{decision_number}", "sections": [{"activityTitle": header, "activitySubtitle": f"DECISION-{decision_number}: {title}", "facts": facts, "markdown": True}], "potentialAction": [{"@type": "OpenUri", "name": "View Decision", "targets": [{"os": "default", "uri": decision_url}]}]}

    payload = json.dumps(card).encode()
    req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if isinstance(body, dict) else body.encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        self._handle("GET")

    def do_PUT(self):
        self._handle("PUT")

    def do_POST(self):
        self._handle("POST")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method):
        try:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self._send(401, {"error": "Not authenticated"})
                return

            org_id = self.headers.get("X-Organization-ID")
            if not org_id:
                self._send(400, {"error": "X-Organization-ID header required"})
                return

            # Extract decision ID from path
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            decision_id = path_parts[-1] if path_parts else ""

            if not decision_id:
                self._send(400, {"error": "Decision ID required"})
                return

            query_params = parse_qs(parsed.query)
            token = auth[7:]

            import firebase_admin
            from firebase_admin import credentials, auth as fb_auth
            from sqlalchemy import create_engine, text

            # Verify Firebase token
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
                if not firebase_uid:
                    self._send(401, {"error": "Invalid token: missing user ID"})
                    return
                firebase_email = decoded.get("email")
                firebase_name = decoded.get("name")
            except Exception as e:
                self._send(401, {"error": "Invalid token"})
                return

            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                self._send(500, {"error": "Database not configured"})
                return

            engine = create_engine(db_url, connect_args={"sslmode": "require"})

            with engine.connect() as conn:
                # Get or create user
                result = conn.execute(text("""
                    SELECT id, email, name FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if user_row:
                    user_id = user_row[0]
                    user_email = user_row[1]
                    user_name = user_row[2]
                else:
                    email = firebase_email or f"{firebase_uid}@firebase.local"
                    name = firebase_name or email.split("@")[0]
                    result = conn.execute(text("""
                        INSERT INTO users (id, email, name, auth_provider, auth_provider_id, created_at, updated_at)
                        VALUES (gen_random_uuid(), :email, :name, 'firebase', :uid, NOW(), NOW())
                        RETURNING id, email, name
                    """), {"email": email, "name": name, "uid": firebase_uid})
                    row = result.fetchone()
                    user_id = row[0]
                    user_email = row[1]
                    user_name = row[2]
                    conn.commit()

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                if method == "GET":
                    # Get requested version number if provided
                    version_num = query_params.get("version", [None])[0]
                    version_num = int(version_num) if version_num else None

                    # Get decision (including source and slack/teams fields for "View in Slack/Teams" links)
                    result = conn.execute(text("""
                        SELECT d.id, d.organization_id, d.decision_number, d.status,
                               d.current_version_id, d.created_at,
                               u.id as creator_id, u.name as creator_name, u.email as creator_email,
                               d.source, d.slack_channel_id, d.slack_message_ts,
                               o.slack_team_id,
                               d.teams_conversation_id, d.teams_message_id,
                               o.teams_tenant_id
                        FROM decisions d
                        JOIN users u ON d.created_by = u.id
                        JOIN organizations o ON d.organization_id = o.id
                        WHERE d.id = :did AND d.deleted_at IS NULL
                    """), {"did": decision_id})
                    decision = result.fetchone()

                    if not decision:
                        self._send(404, {"error": "Decision not found"})
                        return

                    # Verify decision belongs to org
                    if str(decision[1]) != org_id:
                        self._send(403, {"error": "Decision not in this organization"})
                        return

                    # Get version (specific or current)
                    if version_num:
                        result = conn.execute(text("""
                            SELECT dv.id, dv.version_number, dv.title, dv.impact_level,
                                   dv.content, dv.tags, dv.created_at, dv.change_summary, dv.content_hash,
                                   u.id as author_id, u.name as author_name, dv.custom_fields
                            FROM decision_versions dv
                            JOIN users u ON dv.created_by = u.id
                            WHERE dv.decision_id = :did AND dv.version_number = :vnum
                        """), {"did": decision_id, "vnum": version_num})
                    else:
                        result = conn.execute(text("""
                            SELECT dv.id, dv.version_number, dv.title, dv.impact_level,
                                   dv.content, dv.tags, dv.created_at, dv.change_summary, dv.content_hash,
                                   u.id as author_id, u.name as author_name, dv.custom_fields
                            FROM decision_versions dv
                            JOIN users u ON dv.created_by = u.id
                            WHERE dv.id = :vid
                        """), {"vid": decision[4]})

                    version = result.fetchone()
                    if not version:
                        self._send(404, {"error": "Version not found"})
                        return

                    # Get version count
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM decision_versions WHERE decision_id = :did
                    """), {"did": decision_id})
                    version_count = result.fetchone()[0]

                    # Get reviewers and their approval status for current version
                    current_version_id = decision[4]
                    result = conn.execute(text("""
                        SELECT rr.user_id, u.name, u.email,
                               COALESCE(a.status, 'pending') as approval_status,
                               a.comment as approval_comment
                        FROM required_reviewers rr
                        JOIN users u ON rr.user_id = u.id
                        LEFT JOIN approvals a ON a.decision_version_id = rr.decision_version_id
                                             AND a.user_id = rr.user_id
                        WHERE rr.decision_version_id = :version_id
                    """), {"version_id": current_version_id})

                    reviewers = []
                    for row in result.fetchall():
                        reviewers.append({
                            "id": str(row[0]),
                            "name": row[1],
                            "email": row[2],
                            "status": row[3],
                            "comment": row[4]
                        })

                    # Check if current user is a required reviewer
                    is_reviewer = any(r["id"] == str(user_id) for r in reviewers)

                    # Get current user's approval status if they are a reviewer
                    current_user_approval = None
                    for r in reviewers:
                        if r["id"] == str(user_id):
                            current_user_approval = r["status"]
                            break

                    # Calculate approval progress
                    required_count = len(reviewers)
                    approved_count = sum(1 for r in reviewers if r["status"] == "approved")
                    rejected_count = sum(1 for r in reviewers if r["status"] == "rejected")

                    # Parse content if it's a string
                    content = version[4]
                    if isinstance(content, str):
                        try:
                            content = json.loads(content)
                        except:
                            content = {}

                    # Parse custom_fields for AI metadata
                    custom_fields = version[11] if len(version) > 11 else None
                    if isinstance(custom_fields, str):
                        try:
                            custom_fields = json.loads(custom_fields)
                        except:
                            custom_fields = {}

                    # Extract AI metadata from custom_fields
                    ai_metadata = None
                    if custom_fields and custom_fields.get("ai_generated"):
                        ai_metadata = {
                            "ai_generated": custom_fields.get("ai_generated", False),
                            "ai_confidence_score": custom_fields.get("ai_confidence_score", 0.0),
                            "verified_by_user": custom_fields.get("verified_by_user", False),
                            "verified_by_slack_user_id": custom_fields.get("verified_by_slack_user_id"),
                            "verified_by_teams_user_id": custom_fields.get("verified_by_teams_user_id"),
                        }

                    # Build Slack link if decision was created from Slack
                    # decision[9] = source, decision[10] = slack_channel_id,
                    # decision[11] = slack_message_ts, decision[12] = slack_team_id
                    # decision[13] = teams_conversation_id, decision[14] = teams_message_id,
                    # decision[15] = teams_tenant_id
                    source = decision[9] or "web"
                    slack_link = None
                    if source == "slack" and decision[10] and decision[12]:
                        # Slack deep link format: slack://channel?team=T123&id=C123&message=1234567890.123456
                        slack_link = f"slack://channel?team={decision[12]}&id={decision[10]}"
                        if decision[11]:  # slack_message_ts
                            slack_link += f"&message={decision[11]}"

                    # Build Teams link if decision was created from Teams
                    teams_link = None
                    if source == "teams" and decision[13] and decision[15]:
                        # Teams deep link format
                        teams_link = f"https://teams.microsoft.com/l/message/{decision[13]}/{decision[14] or ''}"

                    # Get poll votes from poll_votes table
                    poll_votes = None
                    try:
                        poll_result = conn.execute(text("""
                            SELECT vote_type, COUNT(*) as count
                            FROM poll_votes
                            WHERE decision_id = :did
                            GROUP BY vote_type
                        """), {"did": decision_id})
                        vote_counts = {"agree": 0, "concern": 0, "block": 0}
                        for row in poll_result.fetchall():
                            vote_type = row[0]
                            count = row[1]
                            if vote_type in vote_counts:
                                vote_counts[vote_type] = count
                        if sum(vote_counts.values()) > 0:
                            poll_votes = vote_counts
                    except Exception:
                        # poll_votes table may not exist yet
                        pass

                    self._send(200, {
                        "id": str(decision[0]),
                        "organization_id": str(decision[1]),
                        "decision_number": decision[2],
                        "status": decision[3],
                        "created_by": {
                            "id": str(decision[6]),
                            "name": decision[7],
                            "email": decision[8]
                        },
                        "created_at": decision[5].isoformat() if decision[5] else None,
                        "version": {
                            "id": str(version[0]),
                            "version_number": version[1],
                            "title": version[2],
                            "impact_level": version[3],
                            "content": content,
                            "tags": version[5] or [],
                            "created_at": version[6].isoformat() if version[6] else None,
                            "change_summary": version[7],
                            "content_hash": version[8],
                            "created_by": {
                                "id": str(version[9]),
                                "name": version[10]
                            },
                            "is_current": str(version[0]) == str(decision[4]),
                            "ai_metadata": ai_metadata
                        },
                        "version_count": version_count,
                        "requested_version": version_num,
                        "reviewers": reviewers,
                        "is_reviewer": is_reviewer,
                        "current_user_approval": current_user_approval,
                        "approval_progress": {
                            "required": required_count,
                            "approved": approved_count,
                            "rejected": rejected_count
                        },
                        "source": source,
                        "slack_link": slack_link,
                        "teams_link": teams_link,
                        "poll_votes": poll_votes
                    })

                elif method == "PUT":
                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    # Check if this is a status update or a new version
                    new_status = body.get("status")

                    if new_status and not body.get("title"):
                        # Status update only
                        valid_statuses = ['draft', 'pending_review', 'approved', 'deprecated', 'superseded']
                        if new_status not in valid_statuses:
                            self._send(400, {"error": f"Invalid status. Must be one of: {valid_statuses}"})
                            return

                        # Get current status, decision details, and org name for email notification
                        result = conn.execute(text("""
                            SELECT d.status, d.decision_number, dv.title, o.name as org_name
                            FROM decisions d
                            JOIN decision_versions dv ON d.current_version_id = dv.id
                            JOIN organizations o ON d.organization_id = o.id
                            WHERE d.id = :did
                        """), {"did": decision_id})
                        dec_info = result.fetchone()
                        old_status = dec_info[0] if dec_info else "unknown"
                        dec_number = dec_info[1] if dec_info else 0
                        dec_title = dec_info[2] if dec_info else "Unknown"
                        org_name = dec_info[3] if dec_info else "Your Organization"

                        conn.execute(text("""
                            UPDATE decisions SET status = :status WHERE id = :did
                        """), {"status": new_status, "did": decision_id})
                        conn.commit()

                        # Send email notifications for status change
                        try:
                            send_status_change_emails(
                                conn=conn, org_id=org_id, decision_id=decision_id,
                                decision_number=dec_number, title=dec_title,
                                old_status=old_status, new_status=new_status,
                                changer_name=user_name, changer_id=str(user_id), org_name=org_name
                            )
                        except Exception:
                            pass

                        self._send(200, {"success": True, "status": new_status})
                        return

                    # Create new version
                    title = body.get("title", "").strip()
                    content = body.get("content", {})
                    impact_level = body.get("impact_level", "medium")
                    tags = body.get("tags", [])
                    change_summary = body.get("change_summary", "").strip()

                    if not title:
                        self._send(400, {"error": "Title is required"})
                        return

                    if not change_summary:
                        self._send(400, {"error": "Change summary is required for amendments"})
                        return

                    # Get decision info for notification
                    result = conn.execute(text("""
                        SELECT d.decision_number, o.name as org_name
                        FROM decisions d
                        JOIN organizations o ON d.organization_id = o.id
                        WHERE d.id = :did
                    """), {"did": decision_id})
                    dec_info = result.fetchone()
                    decision_number = dec_info[0] if dec_info else 0
                    org_name = dec_info[1] if dec_info else "Your Organization"

                    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

                    # Create new version with retry logic for race conditions
                    version_id = str(uuid4())
                    new_version_num = None
                    for attempt in range(3):  # Retry up to 3 times
                        try:
                            # Get current max version number
                            result = conn.execute(text("""
                                SELECT COALESCE(MAX(version_number), 0) + 1
                                FROM decision_versions
                                WHERE decision_id = :did
                            """), {"did": decision_id})
                            new_version_num = result.fetchone()[0]

                            # Create new version
                            conn.execute(text("""
                                INSERT INTO decision_versions
                                (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, change_summary, content_hash)
                                VALUES (:id, :did, :vnum, :title, :impact, :content, :tags, :user_id, NOW(), :summary, :hash)
                            """), {
                                "id": version_id, "did": decision_id, "vnum": new_version_num,
                                "title": title, "impact": impact_level, "content": json.dumps(content),
                                "tags": tags, "user_id": user_id, "summary": change_summary, "hash": content_hash
                            })
                            break  # Success, exit retry loop
                        except Exception as insert_error:
                            error_str = str(insert_error).lower()
                            if "duplicate" in error_str or "unique" in error_str:
                                if attempt < 2:
                                    # Regenerate version_id and retry
                                    version_id = str(uuid4())
                                    conn.rollback()
                                    continue
                            raise  # Re-raise if not a duplicate error or max retries reached
                    else:
                        # If we exhausted all retries without success
                        self._send(500, {"error": "Failed to create version after retries"})
                        return

                    # Update decision's current version
                    conn.execute(text("""
                        UPDATE decisions SET current_version_id = :vid WHERE id = :did
                    """), {"vid": version_id, "did": decision_id})

                    conn.commit()

                    # Send email notifications for decision update
                    try:
                        send_decision_updated_emails(
                            conn=conn, org_id=org_id, decision_id=decision_id,
                            decision_number=decision_number, title=title,
                            version_number=new_version_num, change_summary=change_summary,
                            updater_name=user_name, updater_id=str(user_id), org_name=org_name
                        )
                    except Exception:
                        pass

                    self._send(200, {
                        "success": True,
                        "version": {
                            "id": version_id,
                            "version_number": new_version_num,
                            "title": title,
                            "impact_level": impact_level,
                            "content": content,
                            "tags": tags,
                            "change_summary": change_summary,
                            "content_hash": content_hash,
                            "created_by": {"id": str(user_id), "name": user_name},
                            "created_at": datetime.utcnow().isoformat(),
                            "is_current": True
                        }
                    })

                elif method == "POST":
                    # POST is used for approvals (approve/reject/abstain)
                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    approval_status = body.get("status", "").lower()
                    comment = body.get("comment", "")

                    if approval_status not in ("approved", "rejected", "abstained"):
                        self._send(400, {"error": "Invalid status. Must be: approved, rejected, or abstained"})
                        return

                    # Get decision with notification settings
                    result = conn.execute(text("""
                        SELECT d.id, d.status, d.current_version_id, d.decision_number, dv.title,
                               o.slack_access_token, o.slack_channel_id, o.teams_webhook_url
                        FROM decisions d
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        JOIN organizations o ON d.organization_id = o.id
                        WHERE d.id = :did AND d.deleted_at IS NULL
                    """), {"did": decision_id})
                    dec_row = result.fetchone()

                    if not dec_row:
                        self._send(404, {"error": "Decision not found"})
                        return

                    current_version_id = dec_row[2]
                    decision_number = dec_row[3]
                    decision_title = dec_row[4]
                    slack_token = dec_row[5]
                    slack_channel_id = dec_row[6]
                    teams_webhook_url = dec_row[7]

                    # Check if user is a required reviewer
                    result = conn.execute(text("""
                        SELECT id FROM required_reviewers
                        WHERE decision_version_id = :version_id AND user_id = :user_id
                    """), {"version_id": current_version_id, "user_id": user_id})

                    if not result.fetchone():
                        self._send(403, {"error": "You are not a required reviewer for this decision"})
                        return

                    # Check for existing approval
                    result = conn.execute(text("""
                        SELECT id FROM approvals
                        WHERE decision_version_id = :version_id AND user_id = :user_id
                    """), {"version_id": current_version_id, "user_id": user_id})
                    existing = result.fetchone()

                    if existing:
                        conn.execute(text("""
                            UPDATE approvals SET status = :status, comment = :comment, created_at = NOW()
                            WHERE id = :id
                        """), {"status": approval_status, "comment": comment, "id": existing[0]})
                        approval_id = str(existing[0])
                    else:
                        approval_id = str(uuid4())
                        conn.execute(text("""
                            INSERT INTO approvals (id, decision_version_id, user_id, status, comment, created_at)
                            VALUES (:id, :version_id, :user_id, :status, :comment, NOW())
                        """), {"id": approval_id, "version_id": current_version_id, "user_id": user_id, "status": approval_status, "comment": comment})

                    # Get counts
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

                    # Auto-approve if all reviewers approved
                    decision_became_approved = False
                    new_decision_status = dec_row[1]
                    if required_count > 0 and approved_count >= required_count:
                        conn.execute(text("UPDATE decisions SET status = 'approved' WHERE id = :did"), {"did": decision_id})
                        new_decision_status = "approved"
                        decision_became_approved = True

                    conn.commit()

                    # Send notifications
                    try:
                        if slack_token and slack_channel_id:
                            send_slack_approval_notification(slack_token, slack_channel_id, decision_number, decision_id, decision_title, user_name, approval_status, comment, approved_count, required_count, decision_became_approved)
                    except Exception:
                        pass
                    try:
                        if teams_webhook_url:
                            send_teams_approval_notification(teams_webhook_url, decision_number, decision_id, decision_title, user_name, approval_status, comment, approved_count, required_count, decision_became_approved)
                    except Exception:
                        pass

                    # Send email notifications for approval
                    try:
                        # Get org name and creator_id for email notifications
                        org_info = conn.execute(text("""
                            SELECT o.name, d.created_by FROM organizations o
                            JOIN decisions d ON d.organization_id = o.id
                            WHERE d.id = :did
                        """), {"did": decision_id}).fetchone()
                        org_name = org_info[0] if org_info else "Your Organization"
                        creator_id = str(org_info[1]) if org_info else ""

                        send_approval_emails(
                            conn=conn, org_id=org_id, decision_id=decision_id,
                            decision_number=decision_number, title=decision_title,
                            approver_name=user_name, approver_id=str(user_id),
                            approval_status=approval_status, comment=comment,
                            org_name=org_name, decision_became_approved=decision_became_approved,
                            creator_id=creator_id
                        )
                    except Exception:
                        pass

                    self._send(200, {
                        "success": True,
                        "approval": {"id": approval_id, "decision_version_id": str(current_version_id), "user": {"id": str(user_id), "name": user_name, "email": user_email}, "status": approval_status, "comment": comment},
                        "decision_status": new_decision_status,
                        "approval_progress": {"required": required_count, "approved": approved_count, "rejected": rejected_count}
                    })

                elif method == "DELETE":
                    # Soft delete
                    conn.execute(text("""
                        UPDATE decisions SET deleted_at = NOW() WHERE id = :did
                    """), {"did": decision_id})
                    conn.commit()
                    self._send(200, {"success": True, "deleted": True})

                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

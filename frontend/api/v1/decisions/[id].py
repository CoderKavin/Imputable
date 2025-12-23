"""Decision detail API - GET, PUT, POST (approve) /api/v1/decisions/[id]"""

from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from datetime import datetime
import urllib.request


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
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*<{decision_url}|DEC-{decision_number}: {title}>*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{approver_name}* {action_text} this decision."}},
    ]
    if comment:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"_\"{comment}\"_"}})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": progress_text}]})
    blocks.append({"type": "actions", "elements": [{"type": "button", "text": {"type": "plain_text", "text": "View Decision", "emoji": True}, "url": decision_url, "style": "primary"}]})

    payload = json.dumps({"channel": channel_id, "text": f"{approver_name} {action_text} DEC-{decision_number}", "attachments": [{"color": color, "blocks": blocks}]}).encode()
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

    card = {"@type": "MessageCard", "@context": "http://schema.org/extensions", "themeColor": color, "summary": f"{approver_name} {action_text} DEC-{decision_number}", "sections": [{"activityTitle": header, "activitySubtitle": f"DEC-{decision_number}: {title}", "facts": facts, "markdown": True}], "potentialAction": [{"@type": "OpenUri", "name": "View Decision", "targets": [{"os": "default", "uri": decision_url}]}]}

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
                firebase_email = decoded.get("email")
                firebase_name = decoded.get("name")
            except Exception as e:
                self._send(401, {"error": f"Invalid token: {str(e)}"})
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

                    # Get decision (including source and slack fields for "View in Slack" link)
                    result = conn.execute(text("""
                        SELECT d.id, d.organization_id, d.decision_number, d.status,
                               d.current_version_id, d.created_at,
                               u.id as creator_id, u.name as creator_name, u.email as creator_email,
                               d.source, d.slack_channel_id, d.slack_message_ts,
                               o.slack_team_id
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
                                   u.id as author_id, u.name as author_name
                            FROM decision_versions dv
                            JOIN users u ON dv.created_by = u.id
                            WHERE dv.decision_id = :did AND dv.version_number = :vnum
                        """), {"did": decision_id, "vnum": version_num})
                    else:
                        result = conn.execute(text("""
                            SELECT dv.id, dv.version_number, dv.title, dv.impact_level,
                                   dv.content, dv.tags, dv.created_at, dv.change_summary, dv.content_hash,
                                   u.id as author_id, u.name as author_name
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

                    # Build Slack link if decision was created from Slack
                    # decision[9] = source, decision[10] = slack_channel_id,
                    # decision[11] = slack_message_ts, decision[12] = slack_team_id
                    source = decision[9] or "web"
                    slack_link = None
                    if source == "slack" and decision[10] and decision[12]:
                        # Slack deep link format: slack://channel?team=T123&id=C123&message=1234567890.123456
                        slack_link = f"slack://channel?team={decision[12]}&id={decision[10]}"
                        if decision[11]:  # slack_message_ts
                            slack_link += f"&message={decision[11]}"

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
                            "is_current": str(version[0]) == str(decision[4])
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
                        "slack_link": slack_link
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

                        conn.execute(text("""
                            UPDATE decisions SET status = :status WHERE id = :did
                        """), {"status": new_status, "did": decision_id})
                        conn.commit()

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

                    # Get current max version
                    result = conn.execute(text("""
                        SELECT COALESCE(MAX(version_number), 0) + 1 FROM decision_versions
                        WHERE decision_id = :did
                    """), {"did": decision_id})
                    new_version_num = result.fetchone()[0]

                    version_id = str(uuid4())
                    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

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

                    # Update decision's current version
                    conn.execute(text("""
                        UPDATE decisions SET current_version_id = :vid WHERE id = :did
                    """), {"vid": version_id, "did": decision_id})

                    conn.commit()

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

"""Decisions API - GET (list) and POST (create) /api/v1/decisions"""

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


def send_email_notification(
    to_email: str,
    to_name: str,
    subject: str,
    html_content: str,
):
    """Send an email notification via Resend API."""
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not configured, skipping email")
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
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
        )
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read().decode())
        print(f"Email sent to {to_email}: {result.get('id', 'unknown')}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False


def send_decision_created_emails(conn, org_id: str, decision_id: str, decision_number: int,
                                  title: str, impact_level: str, creator_name: str,
                                  creator_id: str, org_name: str, tags: list):
    """Send email notifications to org members who have email_new_decision enabled."""
    from sqlalchemy import text

    if not RESEND_API_KEY:
        return

    try:
        # Get all org members except the creator, with their notification settings
        result = conn.execute(text("""
            SELECT u.id, u.email, u.name, u.settings
            FROM organization_members om
            JOIN users u ON om.user_id = u.id
            WHERE om.organization_id = :org_id
              AND u.id != :creator_id
              AND u.deleted_at IS NULL
        """), {"org_id": org_id, "creator_id": creator_id})

        decision_url = f"https://app.imputable.io/decisions/{decision_id}"

        for row in result.fetchall():
            user_id, email, name, settings = row[0], row[1], row[2], row[3]

            # Check notification preferences
            if settings:
                user_settings = settings if isinstance(settings, dict) else json.loads(settings) if settings else {}
                notifications = user_settings.get("notifications", {})
                if not notifications.get("email_new_decision", True):
                    continue

            # Send the email
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">New Decision Created</h1>
                </div>
                <div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                    <p style="margin: 0 0 20px;">Hi {name or 'there'},</p>
                    <p style="margin: 0 0 20px;">A new decision has been created in <strong>{org_name}</strong>:</p>

                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <h2 style="margin: 0 0 10px; font-size: 18px; color: #111;">
                            DECISION-{decision_number}: {title}
                        </h2>
                        <p style="margin: 0 0 15px; color: #6b7280; font-size: 14px;">
                            Created by {creator_name}
                        </p>
                        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                            <span style="background: {'#fef3c7' if impact_level == 'high' else '#dbeafe' if impact_level == 'medium' else '#d1fae5'};
                                         color: {'#92400e' if impact_level == 'high' else '#1e40af' if impact_level == 'medium' else '#065f46'};
                                         padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500;">
                                {impact_level.capitalize()} Impact
                            </span>
                            <span style="background: #f3f4f6; color: #374151; padding: 4px 12px; border-radius: 20px; font-size: 12px;">
                                Draft
                            </span>
                        </div>
                        {f'<p style="margin: 15px 0 0; color: #6b7280; font-size: 13px;">Tags: {", ".join(tags)}</p>' if tags else ''}
                    </div>

                    <a href="{decision_url}"
                       style="display: inline-block; background: #4f46e5; color: white; padding: 12px 24px;
                              border-radius: 8px; text-decoration: none; font-weight: 500; margin-top: 10px;">
                        View Decision
                    </a>

                    <p style="margin: 30px 0 0; color: #9ca3af; font-size: 12px;">
                        You're receiving this because you have email notifications enabled for {org_name}.<br>
                        <a href="https://app.imputable.io/settings?tab=notifications" style="color: #6366f1;">Manage notification preferences</a>
                    </p>
                </div>
            </body>
            </html>
            """

            send_email_notification(
                to_email=email,
                to_name=name or email.split("@")[0],
                subject=f"[{org_name}] New Decision: DECISION-{decision_number} - {title}",
                html_content=html_content
            )
    except Exception as e:
        print(f"Error sending decision created emails: {e}")


def send_slack_decision_created(
    slack_token: str,
    channel_id: str,
    decision_number: int,
    decision_id: str,
    title: str,
    impact_level: str,
    creator_name: str,
    org_name: str,
    tags: list,
):
    """Send notification to Slack when a decision is created."""
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

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📋 New Decision Created", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{decision_url}|DECISION-{decision_number}: {title}>*"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status:*\nDraft"},
                {"type": "mrkdwn", "text": f"*Impact:*\n{impact_level.capitalize()}"},
                {"type": "mrkdwn", "text": f"*Created by:*\n{creator_name}"},
                {"type": "mrkdwn", "text": f"*Organization:*\n{org_name}"}
            ]
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Tags: {', '.join(tags) if tags else 'None'}"}]
        },
        {
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "View Details", "emoji": True},
                "url": decision_url,
                "style": "primary"
            }]
        }
    ]

    payload = json.dumps({
        "channel": channel_id,
        "text": f"New decision created: DECISION-{decision_number} - {title}",
        "attachments": [{"color": "808080", "blocks": blocks}]
    }).encode()

    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def send_teams_decision_created(
    webhook_url: str,
    decision_number: int,
    decision_id: str,
    title: str,
    impact_level: str,
    creator_name: str,
    org_name: str,
    tags: list,
):
    """Send notification to Teams when a decision is created."""
    if not webhook_url:
        return

    decision_url = f"https://app.imputable.io/decisions/{decision_id}"

    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "808080",
        "summary": f"New Decision: DECISION-{decision_number}",
        "sections": [{
            "activityTitle": "📋 New Decision Created",
            "activitySubtitle": f"DECISION-{decision_number}: {title}",
            "facts": [
                {"name": "Status", "value": "Draft"},
                {"name": "Impact", "value": impact_level.capitalize()},
                {"name": "Created by", "value": creator_name},
                {"name": "Organization", "value": org_name},
                {"name": "Tags", "value": ", ".join(tags) if tags else "None"},
            ],
            "markdown": True
        }],
        "potentialAction": [{
            "@type": "OpenUri",
            "name": "View Details",
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if isinstance(body, dict) or isinstance(body, list) else body.encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

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
                    # Parse query params
                    parsed = urlparse(self.path)
                    params = parse_qs(parsed.query)
                    page = max(1, int(params.get("page", ["1"])[0]))
                    page_size = min(100, max(1, int(params.get("page_size", ["20"])[0])))  # Limit to 100 max
                    status_filter = params.get("status", [None])[0]
                    search = params.get("search", [None])[0]

                    # Validate status filter
                    valid_statuses = ['draft', 'pending_review', 'approved', 'deprecated', 'superseded', 'at_risk']
                    if status_filter and status_filter not in valid_statuses:
                        status_filter = None

                    # Build query
                    where_clauses = ["d.organization_id = :org_id", "d.deleted_at IS NULL"]
                    query_params = {"org_id": org_id}

                    if status_filter:
                        where_clauses.append("d.status = :status")
                        query_params["status"] = status_filter

                    if search:
                        where_clauses.append("dv.title ILIKE :search")
                        query_params["search"] = f"%{search}%"

                    where_sql = " AND ".join(where_clauses)

                    # Get total count
                    count_result = conn.execute(text(f"""
                        SELECT COUNT(*) FROM decisions d
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        WHERE {where_sql}
                    """), query_params)
                    total = count_result.fetchone()[0]

                    # Get items
                    offset = (page - 1) * page_size
                    query_params["limit"] = page_size
                    query_params["offset"] = offset

                    result = conn.execute(text(f"""
                        SELECT
                            d.id, d.organization_id, d.decision_number, d.status,
                            d.created_at,
                            dv.id as version_id, dv.title, dv.impact_level, dv.tags,
                            u.id as user_id, u.name as user_name, u.email as user_email
                        FROM decisions d
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        JOIN users u ON d.created_by = u.id
                        WHERE {where_sql}
                        ORDER BY d.created_at DESC
                        LIMIT :limit OFFSET :offset
                    """), query_params)

                    items = []
                    for row in result.fetchall():
                        decision_id = row[0]
                        version_id = row[5]

                        # Get version count
                        vc_result = conn.execute(text("""
                            SELECT COUNT(*) FROM decision_versions WHERE decision_id = :did
                        """), {"did": decision_id})
                        version_count = vc_result.fetchone()[0]

                        # Get reviewers and their approval status
                        reviewers_result = conn.execute(text("""
                            SELECT rr.user_id, u.name, u.email,
                                   COALESCE(a.status, 'pending') as approval_status
                            FROM required_reviewers rr
                            JOIN users u ON rr.user_id = u.id
                            LEFT JOIN approvals a ON a.decision_version_id = rr.decision_version_id
                                                 AND a.user_id = rr.user_id
                            WHERE rr.decision_version_id = :version_id
                        """), {"version_id": version_id})

                        reviewers = []
                        approved_count = 0
                        rejected_count = 0
                        for r in reviewers_result.fetchall():
                            status = r[3]
                            reviewers.append({
                                "id": str(r[0]),
                                "name": r[1],
                                "email": r[2],
                                "status": status
                            })
                            if status == "approved":
                                approved_count += 1
                            elif status == "rejected":
                                rejected_count += 1

                        item = {
                            "id": str(decision_id),
                            "organization_id": str(row[1]),
                            "decision_number": row[2],
                            "status": row[3],
                            "created_at": row[4].isoformat() if row[4] else None,
                            "title": row[6],
                            "impact_level": row[7],
                            "tags": row[8] or [],
                            "created_by": {
                                "id": str(row[9]),
                                "name": row[10],
                                "email": row[11]
                            },
                            "version_count": version_count
                        }

                        # Only include reviewer data if there are reviewers
                        if reviewers:
                            item["reviewers"] = reviewers
                            item["approval_progress"] = {
                                "required": len(reviewers),
                                "approved": approved_count,
                                "rejected": rejected_count
                            }

                        items.append(item)

                    self._send(200, {
                        "items": items,
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
                    })

                elif method == "POST":
                    content_len = int(self.headers.get("Content-Length", 0))
                    # Limit request body size to 1MB
                    if content_len > 1024 * 1024:
                        self._send(413, {"error": "Request body too large"})
                        return
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    title = body.get("title", "").strip()[:500]  # Limit title length
                    content = body.get("content", {})
                    impact_level = body.get("impact_level", "medium")
                    tags = body.get("tags", [])[:20]  # Limit number of tags
                    reviewer_ids = body.get("reviewer_ids", [])[:50]  # Limit reviewers

                    # Validate impact level
                    if impact_level not in ["low", "medium", "high", "critical"]:
                        impact_level = "medium"

                    if not title:
                        self._send(400, {"error": "Title is required"})
                        return

                    # Get organization details including subscription tier
                    org_result = conn.execute(text("""
                        SELECT name, slack_access_token, slack_channel_id, teams_webhook_url,
                               COALESCE(subscription_tier, 'free') as subscription_tier
                        FROM organizations WHERE id = :org_id
                    """), {"org_id": org_id})
                    org_row = org_result.fetchone()
                    if not org_row:
                        self._send(404, {"error": "Organization not found"})
                        return

                    org_name = org_row[0]
                    slack_token = org_row[1]
                    slack_channel_id = org_row[2]
                    teams_webhook_url = org_row[3]
                    subscription_tier = org_row[4]

                    # Enforce plan limits for free tier
                    if subscription_tier == "free":
                        # Check decision count limit (50 for free plan)
                        count_result = conn.execute(text("""
                            SELECT COUNT(*) FROM decisions
                            WHERE organization_id = :org_id AND deleted_at IS NULL
                        """), {"org_id": org_id})
                        decision_count = count_result.fetchone()[0]

                        if decision_count >= 50:
                            self._send(403, {
                                "error": "Decision limit reached",
                                "message": "Free plan is limited to 50 decisions. Upgrade to Pro for unlimited decisions.",
                                "limit": 50,
                                "current": decision_count
                            })
                            return

                    # Get next decision number with retry for race conditions
                    decision_id = str(uuid4())
                    version_id = str(uuid4())
                    decision_number = None

                    for attempt in range(3):  # Retry up to 3 times
                        try:
                            result = conn.execute(text("""
                                SELECT COALESCE(MAX(decision_number), 0) + 1 FROM decisions
                                WHERE organization_id = :org_id
                            """), {"org_id": org_id})
                            decision_number = result.fetchone()[0]

                            # Create decision
                            conn.execute(text("""
                                INSERT INTO decisions (id, organization_id, decision_number, status, created_by, created_at, is_temporary)
                                VALUES (:id, :org_id, :num, 'draft', :user_id, NOW(), false)
                            """), {"id": decision_id, "org_id": org_id, "num": decision_number, "user_id": user_id})
                            break  # Success, exit retry loop
                        except Exception as insert_error:
                            if "duplicate" in str(insert_error).lower() or "unique" in str(insert_error).lower():
                                if attempt < 2:
                                    decision_id = str(uuid4())  # Generate new ID for retry
                                    continue
                            raise

                    if decision_number is None:
                        self._send(500, {"error": "Failed to create decision"})
                        return

                    # Create version
                    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
                    conn.execute(text("""
                        INSERT INTO decision_versions
                        (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, change_summary, content_hash, custom_fields)
                        VALUES (:id, :did, 1, :title, :impact, :content, :tags, :user_id, NOW(), 'Initial version', :hash, '{}')
                    """), {
                        "id": version_id, "did": decision_id, "title": title,
                        "impact": impact_level, "content": json.dumps(content),
                        "tags": tags, "user_id": user_id, "hash": content_hash
                    })

                    # Update decision with current version
                    conn.execute(text("""
                        UPDATE decisions SET current_version_id = :vid WHERE id = :did
                    """), {"vid": version_id, "did": decision_id})

                    # Add required reviewers if specified
                    for reviewer_id in reviewer_ids:
                        conn.execute(text("""
                            INSERT INTO required_reviewers (id, decision_version_id, user_id, added_by, added_at)
                            VALUES (gen_random_uuid(), :version_id, :reviewer_id, :user_id, NOW())
                        """), {"version_id": version_id, "reviewer_id": reviewer_id, "user_id": user_id})

                    conn.commit()

                    # Send notifications to Slack and Teams (non-blocking)
                    try:
                        if slack_token and slack_channel_id:
                            send_slack_decision_created(
                                slack_token=slack_token,
                                channel_id=slack_channel_id,
                                decision_number=decision_number,
                                decision_id=decision_id,
                                title=title,
                                impact_level=impact_level,
                                creator_name=user_name,
                                org_name=org_name,
                                tags=tags,
                            )
                    except Exception:
                        pass

                    try:
                        if teams_webhook_url:
                            send_teams_decision_created(
                                webhook_url=teams_webhook_url,
                                decision_number=decision_number,
                                decision_id=decision_id,
                                title=title,
                                impact_level=impact_level,
                                creator_name=user_name,
                                org_name=org_name,
                                tags=tags,
                            )
                    except Exception:
                        pass

                    # Send email notifications to org members (non-blocking)
                    try:
                        send_decision_created_emails(
                            conn=conn,
                            org_id=org_id,
                            decision_id=decision_id,
                            decision_number=decision_number,
                            title=title,
                            impact_level=impact_level,
                            creator_name=user_name,
                            creator_id=str(user_id),
                            org_name=org_name,
                            tags=tags,
                        )
                    except Exception:
                        pass

                    self._send(201, {
                        "id": decision_id,
                        "organization_id": org_id,
                        "decision_number": decision_number,
                        "status": "draft",
                        "created_by": {
                            "id": str(user_id),
                            "name": user_name,
                            "email": user_email
                        },
                        "created_at": datetime.utcnow().isoformat(),
                        "version": {
                            "id": version_id,
                            "version_number": 1,
                            "title": title,
                            "impact_level": impact_level,
                            "content": content,
                            "tags": tags,
                            "content_hash": content_hash,
                            "created_by": {"id": str(user_id), "name": user_name},
                            "created_at": datetime.utcnow().isoformat(),
                            "change_summary": "Initial version",
                            "is_current": True
                        },
                        "version_count": 1
                    })
                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

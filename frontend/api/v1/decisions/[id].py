"""Decision detail API - GET, PUT /api/v1/decisions/[id]"""

from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from datetime import datetime


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if isinstance(body, dict) else body.encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        self._handle("GET")

    def do_PUT(self):
        self._handle("PUT")

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

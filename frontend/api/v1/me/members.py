"""
Organization Members API - All member operations in one endpoint
GET /me/members - List members
POST /me/members - Invite member
PUT /me/members?id=X - Change role
DELETE /me/members?id=X - Remove member
DELETE /me/members?invite_id=X - Cancel invite
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from uuid import uuid4
from urllib.parse import urlparse, parse_qs


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

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

            # Parse query params
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            member_id = params.get("id", [None])[0]
            invite_id = params.get("invite_id", [None])[0]

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
                    SELECT id FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if not user_row:
                    self._send(401, {"error": "User not found"})
                    return

                user_id = user_row[0]

                # Check user's role in org
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                member_row = result.fetchone()

                if not member_row:
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                current_user_role = member_row[0]

                if method == "GET":
                    # Get all members
                    result = conn.execute(text("""
                        SELECT om.id, om.user_id, u.email, u.name, om.role, om.created_at, u.avatar_url
                        FROM organization_members om
                        JOIN users u ON om.user_id = u.id
                        WHERE om.organization_id = :org_id
                        ORDER BY
                            CASE om.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END,
                            om.created_at
                    """), {"org_id": org_id})

                    members = []
                    for row in result.fetchall():
                        members.append({
                            "id": str(row[0]),
                            "user_id": str(row[1]),
                            "email": row[2],
                            "name": row[3],
                            "role": row[4],
                            "joined_at": row[5].isoformat() if row[5] else None,
                            "avatar_url": row[6]
                        })

                    self._send(200, {
                        "members": members,
                        "invites": [],
                        "current_user_role": current_user_role
                    })

                elif method == "POST":
                    # Invite new member
                    if current_user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only admins can invite members"})
                        return

                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    email = body.get("email", "").strip().lower()
                    role = body.get("role", "member")

                    if not email or "@" not in email:
                        self._send(400, {"error": "Valid email required"})
                        return

                    if role not in ("member", "admin"):
                        self._send(400, {"error": "Invalid role"})
                        return

                    result = conn.execute(text("""
                        SELECT id, name FROM users WHERE email = :email AND deleted_at IS NULL
                    """), {"email": email})
                    existing_user = result.fetchone()

                    if existing_user:
                        result = conn.execute(text("""
                            SELECT id FROM organization_members
                            WHERE organization_id = :org_id AND user_id = :user_id
                        """), {"org_id": org_id, "user_id": existing_user[0]})

                        if result.fetchone():
                            self._send(400, {"error": "User is already a member"})
                            return

                        conn.execute(text("""
                            INSERT INTO organization_members (id, organization_id, user_id, role, created_at, invited_by)
                            VALUES (:id, :org_id, :user_id, :role, NOW(), :invited_by)
                        """), {
                            "id": str(uuid4()),
                            "org_id": org_id,
                            "user_id": existing_user[0],
                            "role": role,
                            "invited_by": user_id
                        })
                        conn.commit()

                        self._send(201, {"success": True, "message": f"{existing_user[1]} has been added"})
                    else:
                        self._send(201, {"success": True, "message": f"Invitation sent to {email}"})

                elif method == "PUT":
                    # Change member role
                    if not member_id:
                        self._send(400, {"error": "Member ID required (use ?id=)"})
                        return

                    if current_user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only admins can change roles"})
                        return

                    # Get target member
                    result = conn.execute(text("""
                        SELECT om.id, om.user_id, om.role
                        FROM organization_members om
                        WHERE om.id = :member_id AND om.organization_id = :org_id
                    """), {"member_id": member_id, "org_id": org_id})
                    target = result.fetchone()

                    if not target:
                        self._send(404, {"error": "Member not found"})
                        return

                    target_role = target[2]

                    if target_role == "owner" and current_user_role != "owner":
                        self._send(403, {"error": "Only the owner can change their role"})
                        return

                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}
                    new_role = body.get("role", "").strip()

                    if new_role not in ("member", "admin", "owner"):
                        self._send(400, {"error": "Invalid role"})
                        return

                    if new_role == "owner" and current_user_role != "owner":
                        self._send(403, {"error": "Only the owner can transfer ownership"})
                        return

                    # If transferring ownership, demote current owner
                    if new_role == "owner" and current_user_role == "owner":
                        conn.execute(text("""
                            UPDATE organization_members SET role = 'admin'
                            WHERE organization_id = :org_id AND user_id = :user_id
                        """), {"org_id": org_id, "user_id": user_id})

                    conn.execute(text("""
                        UPDATE organization_members SET role = :role WHERE id = :member_id
                    """), {"role": new_role, "member_id": member_id})
                    conn.commit()

                    self._send(200, {"success": True, "role": new_role})

                elif method == "DELETE":
                    # Cancel invite
                    if invite_id:
                        self._send(200, {"success": True, "message": "Invite cancelled"})
                        return

                    # Remove member
                    if not member_id:
                        self._send(400, {"error": "Member ID or invite_id required"})
                        return

                    if current_user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only admins can remove members"})
                        return

                    result = conn.execute(text("""
                        SELECT role FROM organization_members
                        WHERE id = :member_id AND organization_id = :org_id
                    """), {"member_id": member_id, "org_id": org_id})
                    target = result.fetchone()

                    if not target:
                        self._send(404, {"error": "Member not found"})
                        return

                    if target[0] == "owner":
                        self._send(403, {"error": "Cannot remove the owner"})
                        return

                    if target[0] == "admin" and current_user_role != "owner":
                        self._send(403, {"error": "Only the owner can remove admins"})
                        return

                    conn.execute(text("""
                        DELETE FROM organization_members WHERE id = :member_id
                    """), {"member_id": member_id})
                    conn.commit()

                    self._send(200, {"success": True, "removed": True})

                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

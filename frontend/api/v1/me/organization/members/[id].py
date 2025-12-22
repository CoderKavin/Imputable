"""Organization Member API - PUT, DELETE /api/v1/me/organization/members/[id]"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, {})

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

            # Extract member ID from path
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            member_id = path_parts[-1] if path_parts else ""

            if not member_id:
                self._send(400, {"error": "Member ID required"})
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
                # Get current user
                result = conn.execute(text("""
                    SELECT id FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if not user_row:
                    self._send(401, {"error": "User not found"})
                    return

                user_id = user_row[0]

                # Check current user's role
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                current_member = result.fetchone()

                if not current_member:
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                current_user_role = current_member[0]

                # Get target member info
                result = conn.execute(text("""
                    SELECT om.id, om.user_id, om.role, u.name
                    FROM organization_members om
                    JOIN users u ON om.user_id = u.id
                    WHERE om.id = :member_id AND om.organization_id = :org_id
                """), {"member_id": member_id, "org_id": org_id})
                target_member = result.fetchone()

                if not target_member:
                    self._send(404, {"error": "Member not found"})
                    return

                target_role = target_member[2]

                if method == "PUT":
                    # Change role - only admins/owners can do this
                    if current_user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only admins can change roles"})
                        return

                    # Can't change owner's role unless you're the owner
                    if target_role == "owner" and current_user_role != "owner":
                        self._send(403, {"error": "Only the owner can change their role"})
                        return

                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    new_role = body.get("role", "").strip()

                    if new_role not in ("member", "admin", "owner"):
                        self._send(400, {"error": "Invalid role"})
                        return

                    # Only owner can make someone else owner
                    if new_role == "owner" and current_user_role != "owner":
                        self._send(403, {"error": "Only the owner can transfer ownership"})
                        return

                    # If transferring ownership, demote current owner to admin
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
                    # Remove member - only admins/owners, and can't remove owner
                    if current_user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only admins can remove members"})
                        return

                    if target_role == "owner":
                        self._send(403, {"error": "Cannot remove the owner"})
                        return

                    # Admins can't remove other admins, only owner can
                    if target_role == "admin" and current_user_role != "owner":
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

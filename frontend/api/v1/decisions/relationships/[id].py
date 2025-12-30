"""Delete relationship endpoint - DELETE /api/v1/decisions/relationships/[id]"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse

class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        if body:
            self.wfile.write(json.dumps(body).encode() if isinstance(body, dict) else body.encode())

    def do_OPTIONS(self):
        self._send(204, None)

    def do_DELETE(self):
        try:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self._send(401, {"error": "Not authenticated"})
                return

            org_id = self.headers.get("X-Organization-ID")
            if not org_id:
                self._send(400, {"error": "X-Organization-ID header required"})
                return

            # Extract relationship ID from path
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) < 5:
                self._send(400, {"error": "Relationship ID required"})
                return
            relationship_id = path_parts[-1]

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
                    self._send(401, {"error": "Invalid token"})
                    return
            except Exception:
                self._send(401, {"error": "Invalid token"})
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

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": str(user_row[0])})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                user_id = str(user_row[0])

                # Soft delete the relationship (set invalidated_at)
                result = conn.execute(text("""
                    UPDATE decision_relationships
                    SET invalidated_at = NOW(), invalidated_by = :user_id
                    WHERE id = :rel_id
                      AND (organization_id = :org_id OR organization_id IS NULL)
                      AND invalidated_at IS NULL
                    RETURNING id
                """), {"rel_id": relationship_id, "org_id": org_id, "user_id": user_id})

                deleted = result.fetchone()
                conn.commit()

                if not deleted:
                    self._send(404, {"error": "Relationship not found"})
                    return

                self._send(200, {"deleted": True, "id": relationship_id})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

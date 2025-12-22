"""Decision versions API - GET /api/v1/decisions/[id]/versions"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if isinstance(body, (dict, list)) else body.encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        try:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self._send(401, {"error": "Not authenticated"})
                return

            org_id = self.headers.get("X-Organization-ID")
            if not org_id:
                self._send(400, {"error": "X-Organization-ID header required"})
                return

            # Extract decision ID from path: /api/v1/decisions/{id}/versions
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            decision_id = path_parts[-2] if len(path_parts) >= 2 else ""

            if not decision_id:
                self._send(400, {"error": "Decision ID required"})
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

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                # Check decision exists
                result = conn.execute(text("""
                    SELECT id, current_version_id FROM decisions
                    WHERE id = :did AND deleted_at IS NULL
                """), {"did": decision_id})
                decision = result.fetchone()

                if not decision:
                    self._send(404, {"error": "Decision not found"})
                    return

                current_version_id = decision[1]

                # Get all versions
                result = conn.execute(text("""
                    SELECT dv.id, dv.version_number, dv.title, dv.impact_level,
                           dv.content_hash, dv.created_at, dv.change_summary,
                           u.id as author_id, u.name as author_name
                    FROM decision_versions dv
                    JOIN users u ON dv.created_by = u.id
                    WHERE dv.decision_id = :did
                    ORDER BY dv.version_number DESC
                """), {"did": decision_id})

                versions = []
                for row in result.fetchall():
                    versions.append({
                        "id": str(row[0]),
                        "version_number": row[1],
                        "title": row[2],
                        "impact_level": row[3],
                        "content_hash": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "change_summary": row[6],
                        "created_by": {
                            "id": str(row[7]),
                            "name": row[8]
                        },
                        "is_current": str(row[0]) == str(current_version_id)
                    })

                self._send(200, versions)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

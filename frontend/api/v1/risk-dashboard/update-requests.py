"""Update Requests API - GET /api/v1/risk-dashboard/update-requests

Returns pending update requests for decision reviews.
This is used by the notifications dropdown.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlparse


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, None)

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

                user_id = str(user_row[0])

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                # Parse query params
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                my_decisions_only = params.get("my_decisions_only", ["false"])[0].lower() == "true"

                # Check if update_requests table exists
                try:
                    result = conn.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'update_requests'
                        )
                    """))
                    table_exists = result.fetchone()[0]
                except:
                    table_exists = False

                if not table_exists:
                    # Table doesn't exist yet - return empty array
                    self._send(200, [])
                    return

                # Fetch update requests
                if my_decisions_only:
                    # Get requests for decisions created by this user
                    result = conn.execute(text("""
                        SELECT
                            ur.id,
                            ur.decision_id,
                            d.decision_number,
                            dv.title as decision_title,
                            u.name as requested_by_name,
                            ur.message,
                            ur.urgency,
                            ur.created_at
                        FROM update_requests ur
                        JOIN decisions d ON ur.decision_id = d.id
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        JOIN users u ON ur.requested_by = u.id
                        WHERE d.organization_id = :org_id
                          AND d.created_by = :user_id
                          AND ur.resolved_at IS NULL
                        ORDER BY ur.created_at DESC
                        LIMIT 50
                    """), {"org_id": org_id, "user_id": user_id})
                else:
                    # Get all update requests for org
                    result = conn.execute(text("""
                        SELECT
                            ur.id,
                            ur.decision_id,
                            d.decision_number,
                            dv.title as decision_title,
                            u.name as requested_by_name,
                            ur.message,
                            ur.urgency,
                            ur.created_at
                        FROM update_requests ur
                        JOIN decisions d ON ur.decision_id = d.id
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        JOIN users u ON ur.requested_by = u.id
                        WHERE d.organization_id = :org_id
                          AND ur.resolved_at IS NULL
                        ORDER BY ur.created_at DESC
                        LIMIT 50
                    """), {"org_id": org_id})

                requests = []
                for row in result.fetchall():
                    requests.append({
                        "id": str(row[0]),
                        "decision_id": str(row[1]),
                        "decision_number": row[2],
                        "decision_title": row[3],
                        "requested_by_name": row[4],
                        "message": row[5],
                        "urgency": row[6] or "normal",
                        "created_at": row[7].isoformat() if row[7] else None
                    })

                self._send(200, requests)

        except Exception as e:
            import traceback
            traceback.print_exc()
            # Return empty array on error to avoid breaking the UI
            self._send(200, [])

"""Integrations Status API - GET /api/v1/integrations/status"""

from http.server import BaseHTTPRequestHandler
import json
import os


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, {})

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

                user_id = user_row[0]

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                # Check organization subscription tier
                result = conn.execute(text("""
                    SELECT subscription_tier FROM organizations WHERE id = :org_id AND deleted_at IS NULL
                """), {"org_id": org_id})
                org_row = result.fetchone()

                if not org_row:
                    self._send(404, {"error": "Organization not found"})
                    return

                # Check actual Slack connection status from organization
                result = conn.execute(text("""
                    SELECT slack_team_id, slack_access_token, slack_team_name, slack_channel_name, slack_connected_at
                    FROM organizations WHERE id = :org_id AND deleted_at IS NULL
                """), {"org_id": org_id})
                org_data = result.fetchone()

                slack_connected = False
                slack_team_name = None
                slack_channel_name = None
                slack_connected_at = None

                if org_data and org_data[0] and org_data[1]:
                    # Has team_id and access_token = connected
                    slack_connected = True
                    slack_team_name = org_data[2] if len(org_data) > 2 else None
                    slack_channel_name = org_data[3] if len(org_data) > 3 else None
                    slack_connected_at = str(org_data[4]) if len(org_data) > 4 and org_data[4] else None

                self._send(200, {
                    "slack": {
                        "connected": slack_connected,
                        "team_name": slack_team_name,
                        "channel_name": slack_channel_name,
                        "installed_at": slack_connected_at
                    },
                    "teams": {
                        "connected": False,
                        "channel_name": None,
                        "installed_at": None
                    }
                })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

"""Pending Approvals API - GET /api/v1/decisions/pending-approvals

Returns decisions where the current user is a required reviewer but hasn't voted yet.
"""

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
                # Get user - first try by Firebase UID, then by email
                result = conn.execute(text("""
                    SELECT id, name, email FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if not user_row and firebase_email:
                    # Try to find by email (may have been created via Slack)
                    result = conn.execute(text("""
                        SELECT id, name, email FROM users
                        WHERE email = :email AND deleted_at IS NULL
                    """), {"email": firebase_email})
                    user_row = result.fetchone()

                    if user_row:
                        # Found user by email - link Firebase auth to this user
                        conn.execute(text("""
                            UPDATE users SET auth_provider = 'firebase', auth_provider_id = :uid, updated_at = NOW()
                            WHERE id = :user_id
                        """), {"uid": firebase_uid, "user_id": user_row[0]})
                        conn.commit()

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

                # Get decisions where user is a required reviewer but hasn't voted
                result = conn.execute(text("""
                    SELECT
                        d.id as decision_id,
                        d.decision_number,
                        dv.id as version_id,
                        dv.title,
                        dv.impact_level,
                        d.status,
                        d.created_at,
                        u.id as creator_id,
                        u.name as creator_name,
                        u.email as creator_email
                    FROM decisions d
                    JOIN decision_versions dv ON d.current_version_id = dv.id
                    JOIN required_reviewers rr ON rr.decision_version_id = dv.id
                    JOIN users u ON d.created_by = u.id
                    WHERE rr.user_id = :user_id
                      AND d.organization_id = :org_id
                      AND d.status = 'pending_review'
                      AND d.deleted_at IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM approvals a
                          WHERE a.decision_version_id = dv.id
                          AND a.user_id = :user_id
                      )
                    ORDER BY d.created_at DESC
                    LIMIT 10
                """), {"user_id": user_id, "org_id": org_id})

                items = []
                for row in result.fetchall():
                    items.append({
                        "id": str(row[0]),
                        "decision_number": row[1],
                        "version_id": str(row[2]),
                        "title": row[3],
                        "impact_level": row[4],
                        "status": row[5],
                        "created_at": row[6].isoformat() if row[6] else None,
                        "created_by": {
                            "id": str(row[7]),
                            "name": row[8],
                            "email": row[9]
                        }
                    })

                self._send(200, {
                    "items": items,
                    "total": len(items)
                })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

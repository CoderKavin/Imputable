"""
Invitation Accept API
GET /api/v1/invites/[token] - Get invitation details
POST /api/v1/invites/[token] - Accept invitation
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from uuid import uuid4
from urllib.parse import urlparse
from datetime import datetime


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        try:
            # Extract token from path
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            # Path should be: api/v1/invites/[token]
            token = path_parts[-1] if path_parts else None

            if not token or token == "invites":
                self._send(400, {"error": "Invitation token required"})
                return

            from sqlalchemy import create_engine, text

            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                self._send(500, {"error": "Database not configured"})
                return

            engine = create_engine(db_url, connect_args={"sslmode": "require"})

            with engine.connect() as conn:
                # Get invitation
                result = conn.execute(text("""
                    SELECT i.id, i.organization_id, i.email, i.role, i.status, i.expires_at, i.created_at,
                           o.name as org_name, o.slug as org_slug, u.name as invited_by_name
                    FROM invitations i
                    JOIN organizations o ON i.organization_id = o.id
                    LEFT JOIN users u ON i.invited_by = u.id
                    WHERE i.token = :token
                """), {"token": token})
                invite = result.fetchone()

                if not invite:
                    self._send(404, {"error": "Invitation not found"})
                    return

                invite_id = invite[0]
                org_id = invite[1]
                invite_email = invite[2]
                invite_role = invite[3]
                invite_status = invite[4]
                expires_at = invite[5]
                created_at = invite[6]
                org_name = invite[7]
                org_slug = invite[8]
                invited_by = invite[9]

                # Check if expired
                if expires_at and datetime.utcnow() > expires_at:
                    if invite_status == "pending":
                        conn.execute(text("""
                            UPDATE invitations SET status = 'expired' WHERE id = :id
                        """), {"id": invite_id})
                        conn.commit()
                    self._send(410, {
                        "error": "Invitation expired",
                        "message": "This invitation has expired. Please ask for a new invitation."
                    })
                    return

                # Check if already used
                if invite_status != "pending":
                    self._send(410, {
                        "error": f"Invitation {invite_status}",
                        "message": f"This invitation has already been {invite_status}."
                    })
                    return

                if method == "GET":
                    # Return invitation details (no auth required)
                    self._send(200, {
                        "email": invite_email,
                        "role": invite_role,
                        "organization": {
                            "id": str(org_id),
                            "name": org_name,
                            "slug": org_slug
                        },
                        "invited_by": invited_by,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                        "created_at": created_at.isoformat() if created_at else None
                    })

                elif method == "POST":
                    # Accept invitation - requires authentication
                    auth = self.headers.get("Authorization", "")
                    if not auth.startswith("Bearer "):
                        self._send(401, {"error": "Authentication required to accept invitation"})
                        return

                    firebase_token = auth[7:]

                    import firebase_admin
                    from firebase_admin import credentials, auth as fb_auth

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

                        decoded = fb_auth.verify_id_token(firebase_token)
                        firebase_uid = decoded.get("uid") or decoded.get("user_id")
                        firebase_email = decoded.get("email", "").lower()
                        firebase_name = decoded.get("name") or decoded.get("email", "").split("@")[0]
                    except Exception as e:
                        self._send(401, {"error": f"Invalid token: {str(e)}"})
                        return

                    # Check email matches (case insensitive)
                    if firebase_email.lower() != invite_email.lower():
                        self._send(403, {
                            "error": "Email mismatch",
                            "message": f"This invitation was sent to {invite_email}. Please sign in with that email address."
                        })
                        return

                    # Check if user exists
                    result = conn.execute(text("""
                        SELECT id, name FROM users WHERE email = :email AND deleted_at IS NULL
                    """), {"email": firebase_email})
                    user_row = result.fetchone()

                    if user_row:
                        user_id = user_row[0]
                        # Update auth provider if needed
                        conn.execute(text("""
                            UPDATE users SET auth_provider = 'firebase', auth_provider_id = :uid, updated_at = NOW()
                            WHERE id = :user_id AND (auth_provider != 'firebase' OR auth_provider_id IS NULL OR auth_provider_id != :uid)
                        """), {"uid": firebase_uid, "user_id": user_id})
                    else:
                        # Create new user
                        user_id = str(uuid4())
                        conn.execute(text("""
                            INSERT INTO users (id, email, name, auth_provider, auth_provider_id, created_at, updated_at)
                            VALUES (:id, :email, :name, 'firebase', :uid, NOW(), NOW())
                        """), {
                            "id": user_id,
                            "email": firebase_email,
                            "name": firebase_name,
                            "uid": firebase_uid
                        })

                    # Check if already a member
                    result = conn.execute(text("""
                        SELECT id, COALESCE(status, 'active') as status FROM organization_members
                        WHERE organization_id = :org_id AND user_id = :user_id
                    """), {"org_id": org_id, "user_id": user_id})
                    existing_member = result.fetchone()

                    if existing_member:
                        if existing_member[1] == "inactive":
                            # Reactivate
                            conn.execute(text("""
                                UPDATE organization_members
                                SET status = 'active', role = :role
                                WHERE id = :member_id
                            """), {"role": invite_role, "member_id": existing_member[0]})
                        # else already active - that's fine
                    else:
                        # Check plan limits
                        count_result = conn.execute(text("""
                            SELECT COUNT(*) FROM organization_members
                            WHERE organization_id = :org_id AND COALESCE(status, 'active') = 'active'
                        """), {"org_id": org_id})
                        active_count = count_result.fetchone()[0]

                        tier_result = conn.execute(text("""
                            SELECT COALESCE(subscription_tier, 'free') FROM organizations WHERE id = :org_id
                        """), {"org_id": org_id})
                        tier = tier_result.fetchone()[0]

                        limit = {"free": 5, "starter": 20}.get(tier, -1)

                        if limit != -1 and active_count >= limit:
                            self._send(403, {
                                "error": "Organization at capacity",
                                "message": f"This organization has reached its member limit. Please contact the admin to upgrade or make space."
                            })
                            return

                        # Add as member
                        conn.execute(text("""
                            INSERT INTO organization_members (id, organization_id, user_id, role, status, created_at)
                            VALUES (:id, :org_id, :user_id, :role, 'active', NOW())
                        """), {
                            "id": str(uuid4()),
                            "org_id": org_id,
                            "user_id": user_id,
                            "role": invite_role
                        })

                    # Mark invitation as accepted
                    conn.execute(text("""
                        UPDATE invitations
                        SET status = 'accepted', accepted_at = NOW(), accepted_by = :user_id
                        WHERE id = :invite_id
                    """), {"user_id": user_id, "invite_id": invite_id})

                    conn.commit()

                    self._send(200, {
                        "success": True,
                        "message": f"Welcome to {org_name}!",
                        "organization": {
                            "id": str(org_id),
                            "name": org_name,
                            "slug": org_slug
                        }
                    })

                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

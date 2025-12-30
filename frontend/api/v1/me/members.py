"""
Organization Members API - All member operations in one endpoint
GET /me/members - List members and pending invites
POST /me/members - Add member (existing user) or create invitation
PUT /me/members?id=X - Change role or status (activate/deactivate)
DELETE /me/members?id=X - Remove member
DELETE /me/members?invite_id=X - Cancel invite
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import secrets
from uuid import uuid4
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta


def get_plan_limits(subscription_tier: str) -> dict:
    """Get plan limits based on subscription tier."""
    limits = {
        "free": {"active_members": 5, "decisions": 50},
        "starter": {"active_members": 20, "decisions": -1},
        "professional": {"active_members": -1, "decisions": -1},  # -1 = unlimited
        "enterprise": {"active_members": -1, "decisions": -1},
    }
    return limits.get(subscription_tier, limits["free"])


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
                firebase_email = decoded.get("email")
            except Exception as e:
                self._send(401, {"error": f"Invalid token: {str(e)}"})
                return

            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                self._send(500, {"error": "Database not configured"})
                return

            engine = create_engine(db_url, connect_args={"sslmode": "require"})

            with engine.connect() as conn:
                # Get user - try by Firebase UID first, then by email
                result = conn.execute(text("""
                    SELECT id FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if not user_row and firebase_email:
                    # Try to find by email
                    result = conn.execute(text("""
                        SELECT id FROM users WHERE email = :email AND deleted_at IS NULL
                    """), {"email": firebase_email})
                    user_row = result.fetchone()
                    if user_row:
                        # Link Firebase auth
                        conn.execute(text("""
                            UPDATE users SET auth_provider = 'firebase', auth_provider_id = :uid, updated_at = NOW()
                            WHERE id = :user_id
                        """), {"uid": firebase_uid, "user_id": user_row[0]})
                        conn.commit()

                if not user_row:
                    self._send(401, {"error": "User not found"})
                    return

                user_id = str(user_row[0])

                # Check user's role and status in org
                result = conn.execute(text("""
                    SELECT role, COALESCE(status, 'active') as status FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                member_row = result.fetchone()

                if not member_row:
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                current_user_role = member_row[0]
                current_user_status = member_row[1]

                # Get org info for plan limits
                org_result = conn.execute(text("""
                    SELECT COALESCE(subscription_tier, 'free') as subscription_tier, name
                    FROM organizations WHERE id = :org_id
                """), {"org_id": org_id})
                org_row = org_result.fetchone()
                subscription_tier = org_row[0] if org_row else "free"
                org_name = org_row[1] if org_row else "Organization"
                plan_limits = get_plan_limits(subscription_tier)

                # Get counts
                count_result = conn.execute(text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE COALESCE(status, 'active') = 'active') as active
                    FROM organization_members
                    WHERE organization_id = :org_id
                """), {"org_id": org_id})
                counts = count_result.fetchone()
                total_members = counts[0]
                active_members = counts[1]

                if method == "GET":
                    # Get all members with status
                    result = conn.execute(text("""
                        SELECT om.id, om.user_id, u.email, u.name, om.role,
                               COALESCE(om.status, 'active') as status, om.created_at, u.avatar_url
                        FROM organization_members om
                        JOIN users u ON om.user_id = u.id
                        WHERE om.organization_id = :org_id
                        ORDER BY
                            CASE om.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END,
                            CASE COALESCE(om.status, 'active') WHEN 'active' THEN 1 ELSE 2 END,
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
                            "status": row[5],
                            "joined_at": row[6].isoformat() if row[6] else None,
                            "avatar_url": row[7]
                        })

                    # Get pending invites
                    invite_result = conn.execute(text("""
                        SELECT i.id, i.email, i.role, i.created_at, i.expires_at, u.name as invited_by_name
                        FROM invitations i
                        LEFT JOIN users u ON i.invited_by = u.id
                        WHERE i.organization_id = :org_id AND i.status = 'pending' AND i.expires_at > NOW()
                        ORDER BY i.created_at DESC
                    """), {"org_id": org_id})

                    invites = []
                    for row in invite_result.fetchall():
                        invites.append({
                            "id": str(row[0]),
                            "email": row[1],
                            "role": row[2],
                            "created_at": row[3].isoformat() if row[3] else None,
                            "expires_at": row[4].isoformat() if row[4] else None,
                            "invited_by": row[5]
                        })

                    self._send(200, {
                        "members": members,
                        "invites": invites,
                        "current_user_role": current_user_role,
                        "current_user_status": current_user_status,
                        "plan": {
                            "tier": subscription_tier,
                            "active_member_limit": plan_limits["active_members"],
                            "active_members": active_members,
                            "total_members": total_members,
                        }
                    })

                elif method == "POST":
                    # Add member or create invitation
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

                    # Check if plan allows adding active members
                    if plan_limits["active_members"] != -1 and active_members >= plan_limits["active_members"]:
                        self._send(403, {
                            "error": "Active member limit reached",
                            "message": f"{subscription_tier.title()} plan is limited to {plan_limits['active_members']} active members. Upgrade to add more or deactivate existing members.",
                            "limit": plan_limits["active_members"],
                            "current": active_members
                        })
                        return

                    # Check if user already exists
                    result = conn.execute(text("""
                        SELECT id, name FROM users WHERE email = :email AND deleted_at IS NULL
                    """), {"email": email})
                    existing_user = result.fetchone()

                    if existing_user:
                        # Check if already a member
                        result = conn.execute(text("""
                            SELECT id, COALESCE(status, 'active') as status FROM organization_members
                            WHERE organization_id = :org_id AND user_id = :user_id
                        """), {"org_id": org_id, "user_id": existing_user[0]})
                        existing_member = result.fetchone()

                        if existing_member:
                            if existing_member[1] == "inactive":
                                # Reactivate inactive member
                                conn.execute(text("""
                                    UPDATE organization_members
                                    SET status = 'active', role = :role
                                    WHERE id = :member_id
                                """), {"role": role, "member_id": existing_member[0]})
                                conn.commit()
                                self._send(200, {"success": True, "message": f"{existing_user[1]} has been reactivated"})
                                return
                            else:
                                self._send(400, {"error": "User is already an active member"})
                                return

                        # Add as new member
                        conn.execute(text("""
                            INSERT INTO organization_members (id, organization_id, user_id, role, status, created_at, invited_by)
                            VALUES (:id, :org_id, :user_id, :role, 'active', NOW(), :invited_by)
                        """), {
                            "id": str(uuid4()),
                            "org_id": org_id,
                            "user_id": str(existing_user[0]),
                            "role": role,
                            "invited_by": user_id
                        })
                        conn.commit()
                        self._send(201, {"success": True, "message": f"{existing_user[1]} has been added"})
                    else:
                        # Create invitation for non-existing user
                        # Check for existing pending invite
                        result = conn.execute(text("""
                            SELECT id FROM invitations
                            WHERE organization_id = :org_id AND email = :email AND status = 'pending' AND expires_at > NOW()
                        """), {"org_id": org_id, "email": email})
                        existing_invite = result.fetchone()

                        if existing_invite:
                            self._send(400, {"error": "An invitation is already pending for this email"})
                            return

                        # Create new invitation
                        invite_token = secrets.token_urlsafe(32)
                        expires_at = datetime.utcnow() + timedelta(days=7)

                        conn.execute(text("""
                            INSERT INTO invitations (id, organization_id, email, role, status, token, invited_by, expires_at, created_at)
                            VALUES (:id, :org_id, :email, :role, 'pending', :token, :invited_by, :expires_at, NOW())
                        """), {
                            "id": str(uuid4()),
                            "org_id": org_id,
                            "email": email,
                            "role": role,
                            "token": invite_token,
                            "invited_by": user_id,
                            "expires_at": expires_at
                        })
                        conn.commit()

                        # TODO: Send invitation email with link
                        frontend_url = os.environ.get("FRONTEND_URL", "https://imputable.vercel.app")
                        invite_link = f"{frontend_url}/invite/{invite_token}"

                        self._send(201, {
                            "success": True,
                            "message": f"Invitation created for {email}",
                            "invite_link": invite_link,
                            "expires_at": expires_at.isoformat()
                        })

                elif method == "PUT":
                    # Change member role or status
                    if not member_id:
                        self._send(400, {"error": "Member ID required (use ?id=)"})
                        return

                    if current_user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only admins can modify members"})
                        return

                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    new_role = body.get("role")
                    new_status = body.get("status")

                    # Get target member
                    result = conn.execute(text("""
                        SELECT om.id, om.user_id, om.role, COALESCE(om.status, 'active') as status
                        FROM organization_members om
                        WHERE om.id = :member_id AND om.organization_id = :org_id
                    """), {"member_id": member_id, "org_id": org_id})
                    target = result.fetchone()

                    if not target:
                        self._send(404, {"error": "Member not found"})
                        return

                    target_role = target[2]
                    target_status = target[3]

                    # Handle role change
                    if new_role:
                        if target_role == "owner" and current_user_role != "owner":
                            self._send(403, {"error": "Only the owner can change their role"})
                            return

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

                    # Handle status change (activate/deactivate)
                    if new_status:
                        if new_status not in ("active", "inactive"):
                            self._send(400, {"error": "Invalid status. Use 'active' or 'inactive'"})
                            return

                        # Cannot deactivate owner
                        if target_role == "owner" and new_status == "inactive":
                            self._send(403, {"error": "Cannot deactivate the owner"})
                            return

                        # Cannot deactivate yourself
                        if str(target[1]) == user_id and new_status == "inactive":
                            self._send(403, {"error": "Cannot deactivate yourself"})
                            return

                        # Check plan limit when activating
                        if new_status == "active" and target_status == "inactive":
                            if plan_limits["active_members"] != -1 and active_members >= plan_limits["active_members"]:
                                self._send(403, {
                                    "error": "Active member limit reached",
                                    "message": f"Cannot activate member. {subscription_tier.title()} plan is limited to {plan_limits['active_members']} active members.",
                                    "limit": plan_limits["active_members"],
                                    "current": active_members
                                })
                                return

                        conn.execute(text("""
                            UPDATE organization_members SET status = :status WHERE id = :member_id
                        """), {"status": new_status, "member_id": member_id})

                    conn.commit()
                    self._send(200, {
                        "success": True,
                        "role": new_role or target_role,
                        "status": new_status or target_status
                    })

                elif method == "DELETE":
                    # Cancel invite
                    if invite_id:
                        if current_user_role not in ("owner", "admin"):
                            self._send(403, {"error": "Only admins can cancel invites"})
                            return

                        conn.execute(text("""
                            UPDATE invitations SET status = 'cancelled'
                            WHERE id = :invite_id AND organization_id = :org_id AND status = 'pending'
                        """), {"invite_id": invite_id, "org_id": org_id})
                        conn.commit()
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
                        SELECT role, user_id FROM organization_members
                        WHERE id = :member_id AND organization_id = :org_id
                    """), {"member_id": member_id, "org_id": org_id})
                    target = result.fetchone()

                    if not target:
                        self._send(404, {"error": "Member not found"})
                        return

                    if target[0] == "owner":
                        self._send(403, {"error": "Cannot remove the owner"})
                        return

                    if str(target[1]) == user_id:
                        self._send(403, {"error": "Cannot remove yourself"})
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

"""
API endpoint for managing individual invites.
Handles DELETE for cancelling pending invites.
"""
import json
import os
from http.server import BaseHTTPRequestHandler

import firebase_admin
from firebase_admin import auth, credentials
from sqlalchemy import create_engine, text

# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    if firebase_creds:
        cred_dict = json.loads(firebase_creds)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_db_connection():
    """Create a database connection."""
    if not DATABASE_URL:
        return None
    engine = create_engine(DATABASE_URL)
    return engine.connect()


def verify_token(authorization: str):
    """Verify Firebase token and return user info."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as e:
        print(f"Token verification error: {e}")
        return None


def check_admin_permission(conn, user_id: str, org_id: str) -> bool:
    """Check if user is admin or owner of the organization."""
    result = conn.execute(
        text("""
            SELECT role FROM organization_members
            WHERE organization_id = :org_id AND user_id = :user_id
        """),
        {"org_id": org_id, "user_id": user_id}
    )
    row = result.fetchone()
    if row:
        return row[0] in ("admin", "owner")
    return False


class handler(BaseHTTPRequestHandler):
    def send_json_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()

    def do_DELETE(self):
        """Cancel a pending invite."""
        # Verify authentication
        auth_header = self.headers.get("Authorization", "")
        user_info = verify_token(auth_header)
        if not user_info:
            self.send_json_response(401, {"error": "Unauthorized"})
            return

        # Get organization ID from header
        org_id = self.headers.get("X-Organization-ID")
        if not org_id:
            self.send_json_response(400, {"error": "Organization ID required"})
            return

        # Extract invite ID from path
        path_parts = self.path.split("/")
        invite_id = path_parts[-1].split("?")[0] if path_parts else None

        if not invite_id:
            self.send_json_response(400, {"error": "Invite ID required"})
            return

        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                self.send_json_response(500, {"error": "Database connection failed"})
                return

            user_id = user_info.get("uid")

            # Check admin permission
            if not check_admin_permission(conn, user_id, org_id):
                self.send_json_response(403, {"error": "Admin permission required"})
                return

            # Delete the invite (only if it belongs to this org)
            result = conn.execute(
                text("""
                    DELETE FROM organization_invites
                    WHERE id = :invite_id AND organization_id = :org_id
                    RETURNING id
                """),
                {"invite_id": invite_id, "org_id": org_id}
            )
            deleted = result.fetchone()
            conn.commit()

            if not deleted:
                self.send_json_response(404, {"error": "Invite not found"})
                return

            self.send_json_response(200, {"success": True, "message": "Invite cancelled"})

        except Exception as e:
            print(f"Error cancelling invite: {e}")
            self.send_json_response(500, {"error": str(e)})
        finally:
            if conn:
                conn.close()

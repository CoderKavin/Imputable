"""
API endpoint for user notification preferences.
Handles GET (fetch settings) and PUT (update settings).
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


def get_user_id(conn, firebase_uid: str):
    """Get internal user ID from Firebase UID."""
    result = conn.execute(
        text("""
            SELECT id FROM users
            WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
        """),
        {"uid": firebase_uid}
    )
    row = result.fetchone()
    return str(row[0]) if row else None


class handler(BaseHTTPRequestHandler):
    def send_json_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()

    def do_GET(self):
        """Get user notification preferences."""
        auth_header = self.headers.get("Authorization", "")
        user_info = verify_token(auth_header)
        if not user_info:
            self.send_json_response(401, {"error": "Unauthorized"})
            return

        org_id = self.headers.get("X-Organization-ID")
        if not org_id:
            self.send_json_response(400, {"error": "Organization ID required"})
            return

        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                self.send_json_response(500, {"error": "Database connection failed"})
                return

            firebase_uid = user_info.get("uid")
            user_id = get_user_id(conn, firebase_uid)

            if not user_id:
                self.send_json_response(401, {"error": "User not found"})
                return

            # Try to get existing notification settings from user_settings or users table
            result = conn.execute(
                text("""
                    SELECT settings FROM users WHERE id = :user_id
                """),
                {"user_id": user_id}
            )
            row = result.fetchone()

            # Default notification settings
            default_settings = {
                "email_new_decision": True,
                "email_decision_updated": True,
                "email_status_change": True,
                "email_review_reminder": True,
                "email_weekly_digest": False,
            }

            if row and row[0]:
                user_settings = row[0] if isinstance(row[0], dict) else json.loads(row[0]) if row[0] else {}
                notifications = user_settings.get("notifications", default_settings)
                self.send_json_response(200, {**default_settings, **notifications})
            else:
                self.send_json_response(200, default_settings)

        except Exception as e:
            print(f"Error fetching notifications: {e}")
            self.send_json_response(500, {"error": str(e)})
        finally:
            if conn:
                conn.close()

    def do_PUT(self):
        """Update user notification preferences."""
        auth_header = self.headers.get("Authorization", "")
        user_info = verify_token(auth_header)
        if not user_info:
            self.send_json_response(401, {"error": "Unauthorized"})
            return

        org_id = self.headers.get("X-Organization-ID")
        if not org_id:
            self.send_json_response(400, {"error": "Organization ID required"})
            return

        # Parse request body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
        except json.JSONDecodeError:
            self.send_json_response(400, {"error": "Invalid JSON"})
            return

        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                self.send_json_response(500, {"error": "Database connection failed"})
                return

            firebase_uid = user_info.get("uid")
            user_id = get_user_id(conn, firebase_uid)

            if not user_id:
                self.send_json_response(401, {"error": "User not found"})
                return

            # Get current settings
            result = conn.execute(
                text("""SELECT settings FROM users WHERE id = :user_id"""),
                {"user_id": user_id}
            )
            row = result.fetchone()

            current_settings = {}
            if row and row[0]:
                current_settings = row[0] if isinstance(row[0], dict) else json.loads(row[0]) if row[0] else {}

            # Update notifications within settings
            current_settings["notifications"] = {
                "email_new_decision": body.get("email_new_decision", True),
                "email_decision_updated": body.get("email_decision_updated", True),
                "email_status_change": body.get("email_status_change", True),
                "email_review_reminder": body.get("email_review_reminder", True),
                "email_weekly_digest": body.get("email_weekly_digest", False),
            }

            # Save updated settings
            conn.execute(
                text("""
                    UPDATE users SET settings = :settings WHERE id = :user_id
                """),
                {"settings": json.dumps(current_settings), "user_id": user_id}
            )
            conn.commit()

            self.send_json_response(200, {"success": True, **current_settings["notifications"]})

        except Exception as e:
            print(f"Error saving notifications: {e}")
            self.send_json_response(500, {"error": str(e)})
        finally:
            if conn:
                conn.close()

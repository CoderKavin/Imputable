"""Organizations API - Simplified for Vercel"""

from http.server import BaseHTTPRequestHandler
import json
import os

def get_response(status, body):
    """Helper to format response."""
    return status, json.dumps(body)

class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        try:
            # Check auth header
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                self._send(401, {"error": "Not authenticated"})
                return

            token = auth[7:]

            # Import heavy deps only when needed
            import ssl
            import firebase_admin
            from firebase_admin import credentials, auth as fb_auth
            from sqlalchemy import create_engine, text

            # Verify Firebase token
            try:
                # Initialize Firebase if needed
                try:
                    app = firebase_admin.get_app()
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
                firebase_name = decoded.get("name")
            except Exception as e:
                self._send(401, {"error": f"Invalid token: {str(e)}"})
                return

            # Connect to database (sync for simplicity)
            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                self._send(500, {"error": "Database not configured"})
                return

            # Create sync engine with SSL
            engine = create_engine(
                db_url,
                connect_args={"sslmode": "require"}
            )

            with engine.connect() as conn:
                # Get or create user
                result = conn.execute(text("""
                    SELECT id, email, name FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if user_row:
                    user_id = user_row[0]
                else:
                    # Create user
                    email = firebase_email or f"{firebase_uid}@firebase.local"
                    name = firebase_name or email.split("@")[0]
                    result = conn.execute(text("""
                        INSERT INTO users (id, email, name, auth_provider, auth_provider_id, created_at, updated_at)
                        VALUES (gen_random_uuid(), :email, :name, 'firebase', :uid, NOW(), NOW())
                        RETURNING id
                    """), {"email": email, "name": name, "uid": firebase_uid})
                    user_id = result.fetchone()[0]
                    conn.commit()

                if method == "GET":
                    # Get user's organizations
                    result = conn.execute(text("""
                        SELECT o.id, o.name, o.slug, om.role, o.subscription_tier
                        FROM organizations o
                        JOIN organization_members om ON om.organization_id = o.id
                        WHERE om.user_id = :user_id AND o.deleted_at IS NULL
                        ORDER BY o.name
                    """), {"user_id": user_id})

                    orgs = [{"id": str(r[0]), "name": r[1], "slug": r[2], "role": r[3], "subscription_tier": r[4] or "free"} for r in result.fetchall()]
                    self._send(200, {"organizations": orgs})

                elif method == "POST":
                    # Create organization
                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    name = body.get("name", "").strip()
                    slug = body.get("slug", "").strip().lower()

                    if not name or not slug:
                        self._send(400, {"error": "Name and slug required"})
                        return

                    # Clean slug
                    import re
                    slug = re.sub(r'[^a-z0-9-]', '-', slug)
                    slug = re.sub(r'-+', '-', slug).strip('-')

                    if len(slug) < 3:
                        self._send(400, {"error": "Slug must be at least 3 characters"})
                        return

                    # Create org with retry logic for slug uniqueness race condition
                    org_id = None
                    for attempt in range(3):
                        try:
                            # Check if slug exists
                            result = conn.execute(text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": slug})
                            if result.fetchone():
                                self._send(400, {"error": "Slug already exists"})
                                return

                            # Create org
                            result = conn.execute(text("""
                                INSERT INTO organizations (id, name, slug, settings, subscription_tier, created_at)
                                VALUES (gen_random_uuid(), :name, :slug, '{}', 'free', NOW())
                                RETURNING id
                            """), {"name": name, "slug": slug})
                            org_id = result.fetchone()[0]

                            # Add user as owner
                            conn.execute(text("""
                                INSERT INTO organization_members (id, organization_id, user_id, role, created_at)
                                VALUES (gen_random_uuid(), :org_id, :user_id, 'owner', NOW())
                            """), {"org_id": org_id, "user_id": user_id})

                            conn.commit()
                            break  # Success
                        except Exception as insert_error:
                            error_str = str(insert_error).lower()
                            if "duplicate" in error_str or "unique" in error_str:
                                if attempt < 2:
                                    conn.rollback()
                                    # Slug was taken between check and insert
                                    self._send(400, {"error": "Slug already exists"})
                                    return
                            raise

                    if org_id is None:
                        self._send(500, {"error": "Failed to create organization"})
                        return

                    self._send(201, {"id": str(org_id), "name": name, "slug": slug, "role": "owner"})
                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

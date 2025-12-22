"""Organization Settings API - Single Org Operations"""

from http.server import BaseHTTPRequestHandler
import json
import os
import re


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(body.encode() if isinstance(body, str) else json.dumps(body).encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        self._handle("GET")

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

                # Check user is member of org and get role
                result = conn.execute(text("""
                    SELECT om.role FROM organization_members om
                    WHERE om.organization_id = :org_id AND om.user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                member_row = result.fetchone()

                if not member_row:
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                user_role = member_row[0]

                if method == "GET":
                    # Get organization details
                    result = conn.execute(text("""
                        SELECT id, name, slug, settings, created_at, subscription_tier
                        FROM organizations
                        WHERE id = :org_id AND deleted_at IS NULL
                    """), {"org_id": org_id})
                    org = result.fetchone()

                    if not org:
                        self._send(404, {"error": "Organization not found"})
                        return

                    # Get member count
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM organization_members WHERE organization_id = :org_id
                    """), {"org_id": org_id})
                    member_count = result.fetchone()[0]

                    # Get decision count
                    result = conn.execute(text("""
                        SELECT COUNT(*) FROM decisions WHERE organization_id = :org_id AND deleted_at IS NULL
                    """), {"org_id": org_id})
                    decision_count = result.fetchone()[0]

                    self._send(200, {
                        "id": str(org[0]),
                        "name": org[1],
                        "slug": org[2],
                        "settings": org[3] or {},
                        "created_at": org[4].isoformat() if org[4] else None,
                        "subscription_tier": org[5] or "free",
                        "member_count": member_count,
                        "decision_count": decision_count,
                        "user_role": user_role
                    })

                elif method == "PUT":
                    # Only owner/admin can update
                    if user_role not in ("owner", "admin"):
                        self._send(403, {"error": "Only owners and admins can update organization"})
                        return

                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    name = body.get("name", "").strip()
                    slug = body.get("slug", "").strip().lower()
                    settings = body.get("settings")

                    if not name:
                        self._send(400, {"error": "Name is required"})
                        return

                    if slug:
                        slug = re.sub(r'[^a-z0-9-]', '-', slug)
                        slug = re.sub(r'-+', '-', slug).strip('-')

                        if len(slug) < 3:
                            self._send(400, {"error": "Slug must be at least 3 characters"})
                            return

                        # Check slug uniqueness (excluding current org)
                        result = conn.execute(text("""
                            SELECT id FROM organizations WHERE slug = :slug AND id != :org_id
                        """), {"slug": slug, "org_id": org_id})
                        if result.fetchone():
                            self._send(400, {"error": "Slug already exists"})
                            return

                    # Update org
                    if settings is not None:
                        conn.execute(text("""
                            UPDATE organizations SET name = :name, slug = :slug, settings = :settings
                            WHERE id = :org_id
                        """), {"name": name, "slug": slug, "settings": json.dumps(settings), "org_id": org_id})
                    else:
                        conn.execute(text("""
                            UPDATE organizations SET name = :name, slug = :slug
                            WHERE id = :org_id
                        """), {"name": name, "slug": slug, "org_id": org_id})

                    conn.commit()
                    self._send(200, {"success": True, "name": name, "slug": slug})

                elif method == "DELETE":
                    # Only owner can delete
                    if user_role != "owner":
                        self._send(403, {"error": "Only the owner can delete the organization"})
                        return

                    # Soft delete
                    conn.execute(text("""
                        UPDATE organizations SET deleted_at = NOW() WHERE id = :org_id
                    """), {"org_id": org_id})
                    conn.commit()
                    self._send(200, {"success": True, "deleted": True})

                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

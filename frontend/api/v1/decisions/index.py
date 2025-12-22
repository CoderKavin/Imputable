"""Decisions API - GET (list) and POST (create) /api/v1/decisions"""

from http.server import BaseHTTPRequestHandler
import json
import os
import hashlib
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from datetime import datetime


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode() if isinstance(body, dict) or isinstance(body, list) else body.encode())

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

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
                firebase_email = decoded.get("email")
                firebase_name = decoded.get("name")
            except Exception as e:
                self._send(401, {"error": f"Invalid token: {str(e)}"})
                return

            db_url = os.environ.get("DATABASE_URL", "")
            if not db_url:
                self._send(500, {"error": "Database not configured"})
                return

            engine = create_engine(db_url, connect_args={"sslmode": "require"})

            with engine.connect() as conn:
                # Get or create user
                result = conn.execute(text("""
                    SELECT id, email, name FROM users
                    WHERE auth_provider = 'firebase' AND auth_provider_id = :uid AND deleted_at IS NULL
                """), {"uid": firebase_uid})
                user_row = result.fetchone()

                if user_row:
                    user_id = user_row[0]
                    user_email = user_row[1]
                    user_name = user_row[2]
                else:
                    email = firebase_email or f"{firebase_uid}@firebase.local"
                    name = firebase_name or email.split("@")[0]
                    result = conn.execute(text("""
                        INSERT INTO users (id, email, name, auth_provider, auth_provider_id, created_at, updated_at)
                        VALUES (gen_random_uuid(), :email, :name, 'firebase', :uid, NOW(), NOW())
                        RETURNING id, email, name
                    """), {"email": email, "name": name, "uid": firebase_uid})
                    row = result.fetchone()
                    user_id = row[0]
                    user_email = row[1]
                    user_name = row[2]
                    conn.commit()

                # Check membership
                result = conn.execute(text("""
                    SELECT role FROM organization_members
                    WHERE organization_id = :org_id AND user_id = :user_id
                """), {"org_id": org_id, "user_id": user_id})
                if not result.fetchone():
                    self._send(403, {"error": "Not a member of this organization"})
                    return

                if method == "GET":
                    # Parse query params
                    parsed = urlparse(self.path)
                    params = parse_qs(parsed.query)
                    page = int(params.get("page", ["1"])[0])
                    page_size = int(params.get("page_size", ["20"])[0])
                    status_filter = params.get("status", [None])[0]
                    search = params.get("search", [None])[0]

                    # Build query
                    where_clauses = ["d.organization_id = :org_id", "d.deleted_at IS NULL"]
                    query_params = {"org_id": org_id}

                    if status_filter:
                        where_clauses.append("d.status = :status")
                        query_params["status"] = status_filter

                    if search:
                        where_clauses.append("dv.title ILIKE :search")
                        query_params["search"] = f"%{search}%"

                    where_sql = " AND ".join(where_clauses)

                    # Get total count
                    count_result = conn.execute(text(f"""
                        SELECT COUNT(*) FROM decisions d
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        WHERE {where_sql}
                    """), query_params)
                    total = count_result.fetchone()[0]

                    # Get items
                    offset = (page - 1) * page_size
                    query_params["limit"] = page_size
                    query_params["offset"] = offset

                    result = conn.execute(text(f"""
                        SELECT
                            d.id, d.organization_id, d.decision_number, d.status,
                            d.created_at,
                            dv.id as version_id, dv.title, dv.impact_level, dv.tags,
                            u.id as user_id, u.name as user_name, u.email as user_email
                        FROM decisions d
                        JOIN decision_versions dv ON d.current_version_id = dv.id
                        JOIN users u ON d.created_by = u.id
                        WHERE {where_sql}
                        ORDER BY d.created_at DESC
                        LIMIT :limit OFFSET :offset
                    """), query_params)

                    items = []
                    for row in result.fetchall():
                        # Get version count
                        vc_result = conn.execute(text("""
                            SELECT COUNT(*) FROM decision_versions WHERE decision_id = :did
                        """), {"did": row[0]})
                        version_count = vc_result.fetchone()[0]

                        items.append({
                            "id": str(row[0]),
                            "organization_id": str(row[1]),
                            "decision_number": row[2],
                            "status": row[3],
                            "created_at": row[4].isoformat() if row[4] else None,
                            "title": row[6],
                            "impact_level": row[7],
                            "tags": row[8] or [],
                            "created_by": {
                                "id": str(row[9]),
                                "name": row[10],
                                "email": row[11]
                            },
                            "version_count": version_count
                        })

                    self._send(200, {
                        "items": items,
                        "total": total,
                        "page": page,
                        "page_size": page_size,
                        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
                    })

                elif method == "POST":
                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    title = body.get("title", "").strip()
                    content = body.get("content", {})
                    impact_level = body.get("impact_level", "medium")
                    tags = body.get("tags", [])

                    if not title:
                        self._send(400, {"error": "Title is required"})
                        return

                    # Get next decision number
                    result = conn.execute(text("""
                        SELECT COALESCE(MAX(decision_number), 0) + 1 FROM decisions
                        WHERE organization_id = :org_id
                    """), {"org_id": org_id})
                    decision_number = result.fetchone()[0]

                    decision_id = str(uuid4())
                    version_id = str(uuid4())

                    # Create decision
                    conn.execute(text("""
                        INSERT INTO decisions (id, organization_id, decision_number, status, created_by, created_at)
                        VALUES (:id, :org_id, :num, 'draft', :user_id, NOW())
                    """), {"id": decision_id, "org_id": org_id, "num": decision_number, "user_id": user_id})

                    # Create version
                    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
                    conn.execute(text("""
                        INSERT INTO decision_versions
                        (id, decision_id, version_number, title, impact_level, content, tags, created_by, created_at, change_summary, content_hash)
                        VALUES (:id, :did, 1, :title, :impact, :content, :tags, :user_id, NOW(), 'Initial version', :hash)
                    """), {
                        "id": version_id, "did": decision_id, "title": title,
                        "impact": impact_level, "content": json.dumps(content),
                        "tags": tags, "user_id": user_id, "hash": content_hash
                    })

                    # Update decision with current version
                    conn.execute(text("""
                        UPDATE decisions SET current_version_id = :vid WHERE id = :did
                    """), {"vid": version_id, "did": decision_id})

                    conn.commit()

                    self._send(201, {
                        "id": decision_id,
                        "organization_id": org_id,
                        "decision_number": decision_number,
                        "status": "draft",
                        "created_by": {
                            "id": str(user_id),
                            "name": user_name,
                            "email": user_email
                        },
                        "created_at": datetime.utcnow().isoformat(),
                        "version": {
                            "id": version_id,
                            "version_number": 1,
                            "title": title,
                            "impact_level": impact_level,
                            "content": content,
                            "tags": tags,
                            "content_hash": content_hash,
                            "created_by": {"id": str(user_id), "name": user_name},
                            "created_at": datetime.utcnow().isoformat(),
                            "change_summary": "Initial version",
                            "is_current": True
                        },
                        "version_count": 1
                    })
                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

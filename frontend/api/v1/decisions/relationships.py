"""Decision Relationships API - GET, POST, DELETE for mind map visualization.

Endpoints:
- GET /api/v1/decisions/relationships - Get all relationships for mind map
- POST /api/v1/decisions/relationships - Create a new relationship
- POST /api/v1/decisions/relationships/generate - AI-generate relationships
- DELETE /api/v1/decisions/relationships/[id] - Delete a relationship
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from datetime import datetime
import urllib.request

# Gemini API for AI relationship detection
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"

AI_RELATIONSHIP_PROMPT = """You are an AI assistant that analyzes engineering decisions to find relationships between them.

Given a list of decisions with their titles, context, choices, and dates, identify meaningful relationships.

RELATIONSHIP TYPES (you MUST only use these exact values):
- "supersedes": Decision A replaces or overrides Decision B
- "blocked_by": Decision A cannot proceed until Decision B is resolved
- "related_to": Decisions share common themes, technologies, or concerns
- "implements": Decision A is an implementation detail of Decision B
- "conflicts_with": Decisions are in tension or contradict each other

ANALYSIS GUIDELINES:
1. Look for temporal relationships (decisions close in time may be related)
2. Look for content similarity (similar topics, technologies, or domains)
3. Look for causal chains (one decision leading to another)
4. Look for supersession patterns (newer decisions replacing older ones)
5. Consider impact levels - high impact decisions often influence others
6. Be selective - only identify strong, meaningful relationships
7. Maximum 15 relationships total to keep the mind map readable

OUTPUT FORMAT (JSON array):
[
    {
        "source_id": "uuid-of-source-decision",
        "target_id": "uuid-of-target-decision",
        "relationship_type": "one_of_the_types_above",
        "description": "Brief explanation of why these decisions are related",
        "confidence": 0.0-1.0
    }
]

Only include relationships with confidence >= 0.6. Return empty array if no strong relationships found."""


def analyze_relationships_with_gemini(decisions: list) -> list:
    """Use Gemini AI to analyze decisions and find relationships."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        print("[RELATIONSHIPS] No GEMINI_API_KEY configured")
        return []

    print(f"[RELATIONSHIPS] Analyzing {len(decisions)} decisions with Gemini")

    # Format decisions for analysis
    decision_summaries = []
    for d in decisions:
        content = d.get("content", {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except:
                content = {"context": content}

        summary = f"""
DECISION ID: {d['id']}
Number: DECISION-{d['decision_number']}
Title: {d['title']}
Status: {d['status']}
Impact: {d.get('impact_level', 'medium')}
Created: {d.get('created_at', 'Unknown')}
Context: {content.get('context', 'N/A')[:500]}
Choice: {content.get('choice', 'N/A')[:500]}
Tags: {', '.join(d.get('tags', []))}
"""
        decision_summaries.append(summary)

    decisions_text = "\n---\n".join(decision_summaries)

    analysis_prompt = f"""Analyze these engineering decisions and identify relationships between them:

{decisions_text}

Return a JSON array of relationships. Focus on the most meaningful connections."""

    url = f"{GEMINI_API_URL}?key={gemini_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [
                {"text": AI_RELATIONSHIP_PROMPT},
                {"text": analysis_prompt}
            ]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "topP": 0.8,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json"
        }
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        response = urllib.request.urlopen(req, timeout=30)
        data = json.loads(response.read().decode())

        candidates = data.get("candidates", [])
        if not candidates:
            print("[RELATIONSHIPS] No candidates in Gemini response")
            return []

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        print(f"[RELATIONSHIPS] Gemini raw response: {text[:500]}")

        # Parse JSON from response
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())
        print(f"[RELATIONSHIPS] Parsed {len(result) if isinstance(result, list) else 0} relationships from AI")

        if not isinstance(result, list):
            return []

        # Filter by confidence
        filtered = [r for r in result if r.get("confidence", 0) >= 0.6]
        print(f"[RELATIONSHIPS] {len(filtered)} relationships passed confidence threshold")
        return filtered

    except Exception as e:
        import traceback
        print(f"[RELATIONSHIPS] Gemini API error: {e}")
        traceback.print_exc()
        return []


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
        self.end_headers()
        if body:
            self.wfile.write(json.dumps(body).encode() if isinstance(body, (dict, list)) else body.encode())

    def do_OPTIONS(self):
        self._send(204, None)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

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
                if not firebase_uid:
                    self._send(401, {"error": "Invalid token"})
                    return
            except Exception as e:
                self._send(401, {"error": "Invalid token"})
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

                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                # Check if decision_relationships table exists
                try:
                    table_check = conn.execute(text("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_name = 'decision_relationships'
                        )
                    """))
                    table_exists = table_check.fetchone()[0]
                except:
                    table_exists = False

                if not table_exists:
                    # Table doesn't exist - return empty for GET, error for POST
                    if method == "GET":
                        self._send(200, {"relationships": []})
                        return
                    else:
                        self._send(500, {"error": "Relationships table not yet created. Please run the migration."})
                        return

                # GET /api/v1/decisions/relationships - List all relationships
                if method == "GET":
                    # Get optional decision_ids filter (for showing subset in mind map)
                    decision_ids = params.get("decision_ids", [None])[0]

                    if decision_ids:
                        # Filter by specific decisions - join with decisions to filter by org
                        ids_list = decision_ids.split(",")
                        src_placeholders = ",".join([f":src_id{i}" for i in range(len(ids_list))])
                        tgt_placeholders = ",".join([f":tgt_id{i}" for i in range(len(ids_list))])
                        id_params = {}
                        for i, id in enumerate(ids_list):
                            id_params[f"src_id{i}"] = id
                            id_params[f"tgt_id{i}"] = id

                        result = conn.execute(text(f"""
                            SELECT
                                dr.id,
                                dr.source_decision_id,
                                dr.target_decision_id,
                                dr.relationship_type::text,
                                dr.description,
                                dr.confidence_score,
                                dr.created_at,
                                sd.decision_number as source_number,
                                sd.status::text as source_status,
                                sdv.title as source_title,
                                sdv.impact_level::text as source_impact,
                                td.decision_number as target_number,
                                td.status::text as target_status,
                                tdv.title as target_title,
                                tdv.impact_level::text as target_impact
                            FROM decision_relationships dr
                            JOIN decisions sd ON dr.source_decision_id = sd.id
                            JOIN decision_versions sdv ON sd.current_version_id = sdv.id
                            JOIN decisions td ON dr.target_decision_id = td.id
                            JOIN decision_versions tdv ON td.current_version_id = tdv.id
                            WHERE sd.organization_id = :org_id
                              AND td.organization_id = :org_id
                              AND (dr.source_decision_id IN ({src_placeholders})
                                   OR dr.target_decision_id IN ({tgt_placeholders}))
                            ORDER BY dr.created_at DESC
                        """), {"org_id": org_id, **id_params})
                    else:
                        # Get all relationships for org - filter by decisions belonging to org
                        result = conn.execute(text("""
                            SELECT
                                dr.id,
                                dr.source_decision_id,
                                dr.target_decision_id,
                                dr.relationship_type::text,
                                dr.description,
                                dr.confidence_score,
                                dr.created_at,
                                sd.decision_number as source_number,
                                sd.status::text as source_status,
                                sdv.title as source_title,
                                sdv.impact_level::text as source_impact,
                                td.decision_number as target_number,
                                td.status::text as target_status,
                                tdv.title as target_title,
                                tdv.impact_level::text as target_impact
                            FROM decision_relationships dr
                            JOIN decisions sd ON dr.source_decision_id = sd.id
                            JOIN decision_versions sdv ON sd.current_version_id = sdv.id
                            JOIN decisions td ON dr.target_decision_id = td.id
                            JOIN decision_versions tdv ON td.current_version_id = tdv.id
                            WHERE sd.organization_id = :org_id
                              AND td.organization_id = :org_id
                            ORDER BY dr.created_at DESC
                        """), {"org_id": org_id})

                    relationships = []
                    for row in result.fetchall():
                        relationships.append({
                            "id": str(row[0]),
                            "source_decision_id": str(row[1]),
                            "target_decision_id": str(row[2]),
                            "relationship_type": row[3],
                            "description": row[4],
                            "confidence_score": row[5],
                            "created_at": row[6].isoformat() if row[6] else None,
                            "source_decision": {
                                "id": str(row[1]),
                                "decision_number": row[7],
                                "status": row[8],
                                "title": row[9],
                                "impact_level": row[10]
                            },
                            "target_decision": {
                                "id": str(row[2]),
                                "decision_number": row[11],
                                "status": row[12],
                                "title": row[13],
                                "impact_level": row[14]
                            }
                        })

                    self._send(200, {"relationships": relationships})

                # POST /api/v1/decisions/relationships - Create relationship or generate with AI
                elif method == "POST":
                    content_len = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}

                    action = body.get("action", "create")

                    if action == "generate":
                        # AI-generate relationships for given decisions
                        decision_ids = body.get("decision_ids", [])

                        if not decision_ids:
                            # Get recent decisions (up to 8)
                            result = conn.execute(text("""
                                SELECT d.id, d.decision_number, d.status, d.created_at,
                                       dv.title, dv.impact_level, dv.content, dv.tags
                                FROM decisions d
                                JOIN decision_versions dv ON d.current_version_id = dv.id
                                WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
                                ORDER BY d.created_at DESC
                                LIMIT 8
                            """), {"org_id": org_id})
                        else:
                            placeholders = ",".join([f":id{i}" for i in range(len(decision_ids))])
                            id_params = {f"id{i}": id for i, id in enumerate(decision_ids)}
                            result = conn.execute(text(f"""
                                SELECT d.id, d.decision_number, d.status, d.created_at,
                                       dv.title, dv.impact_level, dv.content, dv.tags
                                FROM decisions d
                                JOIN decision_versions dv ON d.current_version_id = dv.id
                                WHERE d.organization_id = :org_id
                                  AND d.id IN ({placeholders})
                                  AND d.deleted_at IS NULL
                            """), {"org_id": org_id, **id_params})

                        decisions = []
                        for row in result.fetchall():
                            decisions.append({
                                "id": str(row[0]),
                                "decision_number": row[1],
                                "status": row[2],
                                "created_at": row[3].isoformat() if row[3] else None,
                                "title": row[4],
                                "impact_level": row[5],
                                "content": row[6] if isinstance(row[6], dict) else {},
                                "tags": row[7] or []
                            })

                        if len(decisions) < 2:
                            self._send(200, {"relationships": [], "message": "Need at least 2 decisions to analyze"})
                            return

                        print(f"[RELATIONSHIPS] Sending {len(decisions)} decisions to AI for analysis")

                        # Get AI analysis
                        ai_relationships = analyze_relationships_with_gemini(decisions)
                        print(f"[RELATIONSHIPS] AI returned {len(ai_relationships)} relationships")

                        # Get existing relationships to avoid duplicates
                        existing = set()
                        result = conn.execute(text("""
                            SELECT dr.source_decision_id, dr.target_decision_id, dr.relationship_type::text
                            FROM decision_relationships dr
                            JOIN decisions sd ON dr.source_decision_id = sd.id
                            WHERE sd.organization_id = :org_id
                        """), {"org_id": org_id})
                        for row in result.fetchall():
                            existing.add((str(row[0]), str(row[1]), row[2]))

                        # Insert new relationships
                        created = []
                        for rel in ai_relationships:
                            key = (rel["source_id"], rel["target_id"], rel["relationship_type"])
                            if key in existing:
                                continue

                            # Verify both decisions exist and belong to org
                            check = conn.execute(text("""
                                SELECT COUNT(*) FROM decisions
                                WHERE id IN (:src, :tgt) AND organization_id = :org_id AND deleted_at IS NULL
                            """), {"src": rel["source_id"], "tgt": rel["target_id"], "org_id": org_id})
                            if check.fetchone()[0] != 2:
                                continue

                            rel_id = str(uuid4())
                            conn.execute(text("""
                                INSERT INTO decision_relationships
                                (id, source_decision_id, target_decision_id,
                                 relationship_type, description, confidence_score, created_by, created_at)
                                VALUES (:id, :src, :tgt, CAST(:type AS relationship_type), :desc, :conf, :user_id, NOW())
                            """), {
                                "id": rel_id,
                                "src": rel["source_id"],
                                "tgt": rel["target_id"],
                                "type": rel["relationship_type"],
                                "desc": rel.get("description", ""),
                                "conf": rel.get("confidence", 0.7),
                                "user_id": user_id
                            })
                            created.append({
                                "id": rel_id,
                                "source_decision_id": rel["source_id"],
                                "target_decision_id": rel["target_id"],
                                "relationship_type": rel["relationship_type"],
                                "description": rel.get("description", ""),
                                "confidence_score": rel.get("confidence", 0.7)
                            })
                            existing.add(key)

                        conn.commit()
                        self._send(200, {"relationships": created, "analyzed_count": len(decisions)})

                    else:
                        # Create single relationship manually
                        source_id = body.get("source_decision_id")
                        target_id = body.get("target_decision_id")
                        rel_type = body.get("relationship_type")
                        description = body.get("description", "")

                        if not all([source_id, target_id, rel_type]):
                            self._send(400, {"error": "source_decision_id, target_decision_id, and relationship_type required"})
                            return

                        valid_types = ["supersedes", "blocked_by", "related_to", "implements", "conflicts_with"]
                        if rel_type not in valid_types:
                            self._send(400, {"error": f"Invalid relationship_type. Must be one of: {valid_types}"})
                            return

                        if source_id == target_id:
                            self._send(400, {"error": "Cannot create self-referencing relationship"})
                            return

                        # Verify decisions exist and belong to org
                        check = conn.execute(text("""
                            SELECT COUNT(*) FROM decisions
                            WHERE id IN (:src, :tgt) AND organization_id = :org_id AND deleted_at IS NULL
                        """), {"src": source_id, "tgt": target_id, "org_id": org_id})
                        if check.fetchone()[0] != 2:
                            self._send(404, {"error": "One or both decisions not found"})
                            return

                        # Check for duplicate
                        existing = conn.execute(text("""
                            SELECT id FROM decision_relationships
                            WHERE source_decision_id = :src AND target_decision_id = :tgt
                              AND relationship_type = CAST(:type AS relationship_type)
                        """), {"src": source_id, "tgt": target_id, "type": rel_type})
                        if existing.fetchone():
                            self._send(409, {"error": "Relationship already exists"})
                            return

                        rel_id = str(uuid4())
                        conn.execute(text("""
                            INSERT INTO decision_relationships
                            (id, source_decision_id, target_decision_id,
                             relationship_type, description, created_by, created_at)
                            VALUES (:id, :src, :tgt, CAST(:type AS relationship_type), :desc, :user_id, NOW())
                        """), {
                            "id": rel_id,
                            "src": source_id,
                            "tgt": target_id,
                            "type": rel_type,
                            "desc": description,
                            "user_id": user_id
                        })
                        conn.commit()

                        self._send(201, {
                            "id": rel_id,
                            "source_decision_id": source_id,
                            "target_decision_id": target_id,
                            "relationship_type": rel_type,
                            "description": description
                        })

                # DELETE - handled by [id].py in the same folder
                else:
                    self._send(405, {"error": "Method not allowed"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

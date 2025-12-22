"""Risk Dashboard Stats API - GET /api/v1/risk-dashboard/stats"""

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

                # Get decision stats
                result = conn.execute(text("""
                    SELECT
                        COUNT(*) FILTER (WHERE deleted_at IS NULL) as total,
                        COUNT(*) FILTER (WHERE status = 'draft' AND deleted_at IS NULL) as draft,
                        COUNT(*) FILTER (WHERE status = 'pending_review' AND deleted_at IS NULL) as pending_review,
                        COUNT(*) FILTER (WHERE status = 'approved' AND deleted_at IS NULL) as approved,
                        COUNT(*) FILTER (WHERE status = 'deprecated' AND deleted_at IS NULL) as deprecated,
                        COUNT(*) FILTER (WHERE status = 'superseded' AND deleted_at IS NULL) as superseded
                    FROM decisions
                    WHERE organization_id = :org_id
                """), {"org_id": org_id})
                stats = result.fetchone()

                # Get impact level distribution
                result = conn.execute(text("""
                    SELECT dv.impact_level, COUNT(*) as count
                    FROM decisions d
                    JOIN decision_versions dv ON d.current_version_id = dv.id
                    WHERE d.organization_id = :org_id AND d.deleted_at IS NULL
                    GROUP BY dv.impact_level
                """), {"org_id": org_id})

                impact_levels = {"low": 0, "medium": 0, "high": 0, "critical": 0}
                for row in result.fetchall():
                    if row[0] in impact_levels:
                        impact_levels[row[0]] = row[1]

                # Get recent activity (decisions created in last 30 days)
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM decisions
                    WHERE organization_id = :org_id
                    AND deleted_at IS NULL
                    AND created_at > NOW() - INTERVAL '30 days'
                """), {"org_id": org_id})
                recent_count = result.fetchone()[0]

                # Calculate risk score (simple heuristic)
                # More pending reviews + more high/critical impact = higher risk
                total = stats[0] if stats[0] else 1
                pending = stats[2] if stats[2] else 0
                high_critical = impact_levels["high"] + impact_levels["critical"]

                risk_score = min(100, int(
                    (pending / total * 30) +  # Pending decisions contribute to risk
                    (high_critical / total * 40) +  # High impact decisions
                    (stats[1] / total * 20) if stats[1] else 0  # Draft decisions (undocumented)
                ))

                self._send(200, {
                    "total_decisions": stats[0] or 0,
                    "by_status": {
                        "draft": stats[1] or 0,
                        "pending_review": stats[2] or 0,
                        "approved": stats[3] or 0,
                        "deprecated": stats[4] or 0,
                        "superseded": stats[5] or 0
                    },
                    "by_impact": impact_levels,
                    "recent_activity": recent_count,
                    "risk_score": risk_score,
                    "decisions_only": False
                })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send(500, {"error": str(e)})

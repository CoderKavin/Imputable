"""Decision versions API - GET /api/v1/decisions/[id]/versions"""

import os
import sys
import json
import asyncio
from uuid import UUID
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from sqlalchemy import select, desc
from api.lib.db import get_db_session, User, OrganizationMember, Decision, DecisionVersion
from api.lib.auth import verify_token, get_or_create_user


def cors_response(handler, status=200, body=None):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
    handler.end_headers()
    if body:
        handler.wfile.write(json.dumps(body).encode())


async def get_versions(session, decision_id: UUID):
    decision_result = await session.execute(
        select(Decision).where(Decision.id == decision_id, Decision.deleted_at.is_(None))
    )
    if not decision_result.scalar_one_or_none():
        return {"error": "Decision not found"}, 404

    result = await session.execute(
        select(DecisionVersion, User).join(User, DecisionVersion.created_by == User.id)
        .where(DecisionVersion.decision_id == decision_id)
        .order_by(desc(DecisionVersion.version_number))
    )

    versions = []
    for version, creator in result.all():
        versions.append({
            "id": str(version.id), "version_number": version.version_number,
            "title": version.title,
            "impact_level": version.impact_level.value if hasattr(version.impact_level, 'value') else version.impact_level,
            "content_hash": version.content_hash,
            "created_by": {"id": str(creator.id), "name": creator.name},
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "change_summary": version.change_summary,
        })

    return versions, 200


async def handle_request(headers, decision_id):
    auth_header = headers.get("Authorization", headers.get("authorization", ""))
    if not auth_header.startswith("Bearer "):
        return {"error": "Not authenticated"}, 401

    firebase_user = verify_token(auth_header[7:])
    if not firebase_user:
        return {"error": "Invalid token"}, 401

    org_id = headers.get("X-Organization-ID", headers.get("x-organization-id", ""))
    if not org_id:
        return {"error": "X-Organization-ID header required"}, 400

    try:
        org_uuid = UUID(org_id)
        decision_uuid = UUID(decision_id)
    except ValueError:
        return {"error": "Invalid ID format"}, 400

    async with get_db_session() as session:
        user = await get_or_create_user(session, firebase_user)

        membership = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_uuid,
                OrganizationMember.user_id == user.id,
            )
        )
        if not membership.scalar_one_or_none():
            return {"error": "Not a member of this organization"}, 403

        return await get_versions(session, decision_uuid)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_response(self, 204)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path_parts = parsed.path.strip("/").split("/")
            # Path: /api/v1/decisions/{id}/versions -> extract {id}
            decision_id = path_parts[-2] if len(path_parts) >= 2 else ""

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, status = loop.run_until_complete(handle_request(dict(self.headers), decision_id))
            loop.close()

            cors_response(self, status, result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            cors_response(self, 500, {"error": str(e)})

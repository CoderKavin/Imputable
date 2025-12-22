"""Decision detail API - GET, PUT /api/v1/decisions/[id]"""

import os
import sys
import json
import asyncio
import hashlib
from uuid import UUID, uuid4
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, func
from api.lib.db import get_db_session, User, OrganizationMember, Decision, DecisionVersion, ImpactLevel
from api.lib.auth import verify_token, get_or_create_user


def cors_response(handler, status=200, body=None):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Organization-ID")
    handler.end_headers()
    if body:
        handler.wfile.write(json.dumps(body).encode())


async def get_decision(session, decision_id: UUID, version: int | None = None):
    result = await session.execute(
        select(Decision, User).join(User, Decision.created_by == User.id)
        .where(Decision.id == decision_id, Decision.deleted_at.is_(None))
    )
    row = result.first()
    if not row:
        return {"error": "Decision not found"}, 404

    decision, creator = row

    if version:
        version_result = await session.execute(
            select(DecisionVersion, User).join(User, DecisionVersion.created_by == User.id)
            .where(DecisionVersion.decision_id == decision_id, DecisionVersion.version_number == version)
        )
    else:
        version_result = await session.execute(
            select(DecisionVersion, User).join(User, DecisionVersion.created_by == User.id)
            .where(DecisionVersion.id == decision.current_version_id)
        )

    version_row = version_result.first()
    if not version_row:
        return {"error": "Version not found"}, 404

    dec_version, version_creator = version_row
    version_count = (await session.execute(select(func.count()).where(DecisionVersion.decision_id == decision_id))).scalar() or 1

    return {
        "id": str(decision.id), "organization_id": str(decision.organization_id),
        "decision_number": decision.decision_number,
        "status": decision.status.value if hasattr(decision.status, 'value') else decision.status,
        "created_by": {"id": str(creator.id), "name": creator.name, "email": creator.email},
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
        "version": {
            "id": str(dec_version.id), "version_number": dec_version.version_number,
            "title": dec_version.title,
            "impact_level": dec_version.impact_level.value if hasattr(dec_version.impact_level, 'value') else dec_version.impact_level,
            "content": dec_version.content or {}, "tags": dec_version.tags or [],
            "content_hash": dec_version.content_hash,
            "created_by": {"id": str(version_creator.id), "name": version_creator.name},
            "created_at": dec_version.created_at.isoformat() if dec_version.created_at else None,
            "change_summary": dec_version.change_summary,
            "is_current": decision.current_version_id == dec_version.id,
        },
        "version_count": version_count, "requested_version": version,
    }, 200


async def amend_decision(session, decision_id: UUID, user_id: UUID, data: dict):
    result = await session.execute(select(Decision).where(Decision.id == decision_id, Decision.deleted_at.is_(None)))
    decision = result.scalar_one_or_none()
    if not decision:
        return {"error": "Decision not found"}, 404

    title = data.get("title", "").strip()
    content = data.get("content", {})
    impact_level = data.get("impact_level", "medium")
    tags = data.get("tags", [])
    change_summary = data.get("change_summary", "").strip()

    if not title:
        return {"error": "Title is required"}, 400
    if not change_summary:
        return {"error": "Change summary is required"}, 400

    current_version = (await session.execute(
        select(func.max(DecisionVersion.version_number)).where(DecisionVersion.decision_id == decision_id)
    )).scalar() or 0

    version_id = uuid4()
    version = DecisionVersion(
        id=version_id, decision_id=decision_id, version_number=current_version + 1,
        title=title,
        impact_level=ImpactLevel(impact_level) if impact_level in [e.value for e in ImpactLevel] else ImpactLevel.MEDIUM,
        content=content, tags=tags, created_by=user_id, change_summary=change_summary,
        content_hash=hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
    )
    session.add(version)
    decision.current_version_id = version_id
    await session.commit()

    return await get_decision(session, decision_id)


async def handle_request(method, headers, body, query_params, decision_id):
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

        if method == "GET":
            version = query_params.get("version", [None])[0]
            version = int(version) if version else None
            return await get_decision(session, decision_uuid, version)

        elif method == "PUT":
            data = json.loads(body) if body else {}
            return await amend_decision(session, decision_uuid, user.id, data)

    return {"error": "Method not allowed"}, 405


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_response(self, 204)

    def do_GET(self):
        self._handle("GET")

    def do_PUT(self):
        self._handle("PUT")

    def _handle(self, method):
        try:
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)

            # Extract decision ID from path
            path_parts = parsed.path.strip("/").split("/")
            decision_id = path_parts[-1] if path_parts else ""

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else None

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, status = loop.run_until_complete(handle_request(method, dict(self.headers), body, query_params, decision_id))
            loop.close()

            cors_response(self, status, result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            cors_response(self, 500, {"error": str(e)})

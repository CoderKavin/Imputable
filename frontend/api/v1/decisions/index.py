"""Decisions API - GET (list) and POST (create) /api/v1/decisions"""

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

from sqlalchemy import select, func, desc
from api.lib.db import (
    get_db_session, User, OrganizationMember,
    Decision, DecisionVersion, DecisionStatus, ImpactLevel
)
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


async def get_next_decision_number(session, org_id) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(Decision.decision_number), 0))
        .where(Decision.organization_id == org_id)
    )
    return result.scalar() + 1


async def list_decisions(session, org_id, page: int, page_size: int, status_filter: str | None, search: str | None):
    query = (
        select(Decision, DecisionVersion, User)
        .join(DecisionVersion, Decision.current_version_id == DecisionVersion.id)
        .join(User, Decision.created_by == User.id)
        .where(Decision.organization_id == org_id, Decision.deleted_at.is_(None))
    )

    if status_filter:
        try:
            status = DecisionStatus(status_filter)
            query = query.where(Decision.status == status)
        except ValueError:
            pass

    if search:
        query = query.where(DecisionVersion.title.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    query = query.order_by(desc(Decision.created_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(query)).all()

    items = []
    for decision, version, creator in rows:
        vc = (await session.execute(select(func.count()).where(DecisionVersion.decision_id == decision.id))).scalar() or 1
        items.append({
            "id": str(decision.id),
            "organization_id": str(decision.organization_id),
            "decision_number": decision.decision_number,
            "status": decision.status.value if hasattr(decision.status, 'value') else decision.status,
            "title": version.title,
            "impact_level": version.impact_level.value if hasattr(version.impact_level, 'value') else version.impact_level,
            "tags": version.tags or [],
            "created_by": {"id": str(creator.id), "name": creator.name, "email": creator.email},
            "created_at": decision.created_at.isoformat() if decision.created_at else None,
            "version_count": vc,
        })

    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }


async def create_decision(session, org_id, user_id, data: dict):
    title = data.get("title", "").strip()
    content = data.get("content", {})
    impact_level = data.get("impact_level", "medium")
    tags = data.get("tags", [])

    if not title:
        return {"error": "Title is required"}, 400

    decision_number = await get_next_decision_number(session, org_id)
    decision_id, version_id = uuid4(), uuid4()

    decision = Decision(
        id=decision_id, organization_id=org_id, decision_number=decision_number,
        status=DecisionStatus.DRAFT, created_by=user_id,
    )
    session.add(decision)

    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

    version = DecisionVersion(
        id=version_id, decision_id=decision_id, version_number=1, title=title,
        impact_level=ImpactLevel(impact_level) if impact_level in [e.value for e in ImpactLevel] else ImpactLevel.MEDIUM,
        content=content, tags=tags, created_by=user_id,
        change_summary="Initial version", content_hash=content_hash,
    )
    session.add(version)

    await session.flush()
    decision.current_version_id = version_id
    await session.commit()

    creator = (await session.execute(select(User).where(User.id == user_id))).scalar_one()

    return {
        "id": str(decision.id), "organization_id": str(decision.organization_id),
        "decision_number": decision.decision_number, "status": decision.status.value,
        "created_by": {"id": str(creator.id), "name": creator.name, "email": creator.email},
        "created_at": decision.created_at.isoformat() if decision.created_at else datetime.utcnow().isoformat(),
        "version": {
            "id": str(version.id), "version_number": 1, "title": version.title,
            "impact_level": version.impact_level.value, "content": version.content,
            "tags": version.tags or [], "content_hash": version.content_hash,
            "created_by": {"id": str(creator.id), "name": creator.name},
            "created_at": version.created_at.isoformat() if version.created_at else datetime.utcnow().isoformat(),
            "change_summary": version.change_summary, "is_current": True,
        },
        "version_count": 1,
    }, 201


async def handle_request(method, headers, body, query_params):
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
    except ValueError:
        return {"error": "Invalid organization ID"}, 400

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
            page = int(query_params.get("page", ["1"])[0])
            page_size = int(query_params.get("page_size", ["20"])[0])
            status = query_params.get("status", [None])[0]
            search = query_params.get("search", [None])[0]
            return await list_decisions(session, org_uuid, page, page_size, status, search), 200

        elif method == "POST":
            data = json.loads(body) if body else {}
            return await create_decision(session, org_uuid, user.id, data)

    return {"error": "Method not allowed"}, 405


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_response(self, 204)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def _handle(self, method):
        try:
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else None

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, status = loop.run_until_complete(handle_request(method, dict(self.headers), body, query_params))
            loop.close()

            cors_response(self, status, result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            cors_response(self, 500, {"error": str(e)})

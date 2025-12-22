"""Audit log API - GET /api/v1/audit"""

import os
import sys
import json
import asyncio
from uuid import UUID
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, desc, func
from api.lib.db import get_db_session, User, OrganizationMember, AuditLog
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


async def get_audit_logs(session, org_id: UUID, page: int, page_size: int):
    query = (
        select(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id)
        .where(AuditLog.organization_id == org_id)
    )

    total = (await session.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    query = query.order_by(desc(AuditLog.created_at)).offset((page - 1) * page_size).limit(page_size)

    items = []
    for log, user in (await session.execute(query)).all():
        items.append({
            "id": str(log.id),
            "action": log.action.value if hasattr(log.action, 'value') else log.action,
            "resource_type": log.resource_type, "resource_id": str(log.resource_id),
            "details": log.details or {},
            "user": {"id": str(user.id), "name": user.name, "email": user.email} if user else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
    }, 200


async def handle_request(headers, query_params):
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

        page = int(query_params.get("page", ["1"])[0])
        page_size = int(query_params.get("page_size", ["50"])[0])

        return await get_audit_logs(session, org_uuid, page, page_size)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        cors_response(self, 204)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            query_params = parse_qs(parsed.query)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result, status = loop.run_until_complete(handle_request(dict(self.headers), query_params))
            loop.close()

            cors_response(self, status, result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            cors_response(self, 500, {"error": str(e)})

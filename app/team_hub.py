"""Supabase-backed organization identity; provider tokens stay in the local server."""
from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr

import kit_settings

router = APIRouter(prefix="/api/team", tags=["editing-team"])
_sessions: dict[str, dict[str, Any]] = {}
_session_lock = threading.RLock()
COOKIE = "clipkit_session"


def _config() -> tuple[str, str]:
    cfg = kit_settings._read_config()
    url, key = str(cfg.get("supabase_url", "")).rstrip("/"), str(cfg.get("supabase_anon_key", ""))
    parsed = urllib.parse.urlsplit(url)
    if not key or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise HTTPException(503, "ยังไม่ได้ตั้งค่าระบบบัญชีผู้ใช้และองค์กร")
    return url, key


def _provider(path: str, method: str = "GET", body: dict | None = None, token: str = "") -> Any:
    url, key = _config()
    headers = {"apikey": key, "Authorization": "Bearer " + (token or key), "Content-Type": "application/json"}
    request = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as result:
            data = result.read()
            return json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except ValueError:
            data = {}
        raise HTTPException(exc.code, data.get("msg") or data.get("message") or data.get("error_description") or "ระบบทีมปฏิเสธคำขอ") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(502, "ติดต่อระบบบัญชีผู้ใช้และองค์กรไม่ได้") from exc


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "คำขอต้องมาจากหน้า ClipKit นี้")


def _remember(data: dict, response: Response) -> bool:
    if not data.get("access_token"):
        return False
    session_id = secrets.token_urlsafe(32)
    with _session_lock:
        _sessions[session_id] = {**data, "expires_at": time.time() + data.get("expires_in", 3600)}
    response.set_cookie(COOKIE, session_id, httponly=True, samesite="strict", max_age=86400, path="/")
    return True


def session(request: Request) -> dict[str, Any]:
    session_id = request.cookies.get(COOKIE, "")
    with _session_lock:
        data = _sessions.get(session_id)
        if not data:
            raise HTTPException(401, "เข้าสู่ระบบก่อน")
        if data["expires_at"] <= time.time() + 30:
            renewed = _provider("/auth/v1/token?grant_type=refresh_token", "POST", {"refresh_token": data["refresh_token"]})
            data.update(renewed)
            data["expires_at"] = time.time() + renewed.get("expires_in", 3600)
        return data.copy()


def rpc(request: Request, name: str, body: dict) -> Any:
    _same_origin(request)
    return _provider("/rest/v1/rpc/" + name, "POST", body, session(request)["access_token"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr


class Signup(Credentials):
    display_name: str = Field(min_length=1, max_length=120)


@router.post("/signup")
def signup(body: Signup, request: Request, response: Response) -> dict:
    _same_origin(request)
    password = body.password.get_secret_value()
    if len(password) < 8:
        raise HTTPException(400, "รหัสผ่านต้องยาวอย่างน้อย 8 ตัว")
    data = _provider("/auth/v1/signup", "POST", {"email": body.email.strip(), "password": password,
                    "data": {"display_name": body.display_name.strip()}})
    return {"verification_required": not _remember(data, response)}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response) -> dict:
    _same_origin(request)
    data = _provider("/auth/v1/token?grant_type=password", "POST", {"email": body.email.strip(), "password": body.password.get_secret_value()})
    if not _remember(data, response):
        raise HTTPException(401, "เข้าสู่ระบบไม่ได้")
    return {"signed_in": True}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    _same_origin(request)
    with _session_lock:
        _sessions.pop(request.cookies.get(COOKIE, ""), None)
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}


@router.get("/session")
def identity(request: Request) -> dict:
    try:
        _config()
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        return {"configured": False, "signed_in": False}
    if request.cookies.get(COOKIE, "") not in _sessions:
        return {"configured": True, "signed_in": False}
    data = session(request)
    user = data["user"]
    return {"configured": True, "signed_in": True, "user": {"id": user["id"], "email": user.get("email"),
            "display_name": user.get("user_metadata", {}).get("display_name", "")}}


@router.get("/organizations")
def organizations(request: Request) -> Any:
    return _provider("/rest/v1/clipkit_organizations?select=*,clipkit_members(*)&order=created_at", token=session(request)["access_token"])


class Organization(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@router.post("/organizations")
def create_organization(body: Organization, request: Request) -> dict:
    return {"id": rpc(request, "clipkit_create_organization", {"org_name": body.name.strip()})}


class Member(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["lead", "editor"]


@router.post("/organizations/{org}/members")
def add_member(org: UUID, body: Member, request: Request) -> dict:
    rpc(request, "clipkit_add_member", {"org": str(org), "member_email": body.email.strip(), "member_role": body.role})
    return {"saved": True}


@router.get("/organizations/{org}/assets")
def assets(org: UUID, request: Request) -> Any:
    return _provider("/rest/v1/clipkit_assets?organization_id=eq." + str(org) + "&select=*&order=updated_at.desc", token=session(request)["access_token"])


@router.get("/organizations/{org}/activity")
def activity(org: UUID, request: Request) -> Any:
    return _provider("/rest/v1/clipkit_activity?organization_id=eq." + str(org) + "&select=*&order=created_at.desc&limit=100", token=session(request)["access_token"])


class Asset(BaseModel):
    kind: Literal["footage", "project"]
    name: str = Field(min_length=1, max_length=500)
    source_id: UUID | None = None


@router.post("/organizations/{org}/assets")
def register_asset(org: UUID, body: Asset, request: Request) -> dict:
    return {"id": rpc(request, "clipkit_register_asset", {"org": str(org), "asset_kind": body.kind, "asset_name": body.name.strip(), "source": str(body.source_id) if body.source_id else None})}


class Review(BaseModel):
    asset_ids: list[UUID] = Field(min_length=1, max_length=500)
    status: Literal["editing", "awaiting_lead", "awaiting_review", "changes_requested", "approved"]
    expected_revisions: dict[UUID, int]
    note: str = Field(default="", max_length=5000)


@router.post("/organizations/{org}/review")
def review(org: UUID, body: Review, request: Request) -> dict:
    changed = rpc(request, "clipkit_review_assets", {"org": str(org), "asset_ids": [str(x) for x in body.asset_ids],
                  "next_status": body.status, "expected_revisions": {str(k): v for k, v in body.expected_revisions.items()}, "note": body.note})
    return {"updated": changed}

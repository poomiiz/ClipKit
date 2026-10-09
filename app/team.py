"""Team sign-in against the team hub on Supabase (Auth + the team_members table).

The app carries only the project URL and the public anon key (config.json: team_url, team_key); what a signed-in
person may read or change is decided by row level security in the database, never by this file. The session
(access + refresh token) stays on this machine in team_session.json, which git ignores.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

KIT = Path(__file__).resolve().parents[1]
SESSION = KIT / "team_session.json"


class TeamError(ValueError):
    pass


def _hub() -> tuple[str, str]:
    import kit_settings
    cfg = kit_settings._read_config()
    url, key = str(cfg.get("team_url", "")).strip().rstrip("/"), str(cfg.get("team_key", "")).strip()
    if not url.startswith("https://") or not key:
        raise TeamError("ยังไม่ได้ตั้งค่าที่อยู่ทีม: ใส่ที่อยู่ทีมและรหัสแอปในหน้าตั้งค่า แท็บทีม แล้วกดบันทึก")
    return url, key


def _call(method: str, path: str, body: dict | None = None, token: str | None = None) -> Any:
    url, key = _hub()
    req = urllib.request.Request(url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"apikey": key, "Content-Type": "application/json",
                                          "Authorization": f"Bearer {token or key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        try:
            j = json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            j = {}
        raise TeamError(j.get("msg") or j.get("error_description") or j.get("message") or f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise TeamError(f"ต่อเซิร์ฟเวอร์ทีมไม่ได้: {exc.reason}") from exc
    return json.loads(raw) if raw else None


def _save(s: dict) -> dict:
    keep = {"access_token": s["access_token"], "refresh_token": s["refresh_token"],
            "expires_at": int(s.get("expires_at") or time.time() + int(s.get("expires_in", 3600))),
            "user_id": s["user"]["id"], "email": s["user"].get("email", "")}
    SESSION.write_text(json.dumps(keep, indent=1), encoding="utf-8")
    return keep


def _session() -> dict | None:
    """The saved session, refreshed when it is about to expire; None when signed out."""
    if not SESSION.is_file():
        return None
    s = json.loads(SESSION.read_text(encoding="utf-8"))
    if s["expires_at"] - time.time() < 60:
        s = _save(_call("POST", "/auth/v1/token?grant_type=refresh_token", {"refresh_token": s["refresh_token"]}))
    return s


def _check(email: str, password: str) -> None:
    if "@" not in email:
        raise TeamError("อีเมลไม่ถูกต้อง")
    if len(password) < 8:
        raise TeamError("รหัสผ่านต้องยาวอย่างน้อย 8 ตัว")


def sign_up(email: str, password: str) -> dict[str, Any]:
    _check(email, password)
    r = _call("POST", "/auth/v1/signup", {"email": email, "password": password})
    if r and r.get("access_token"):
        _save(r)
        return status()
    return {"signed_in": False, "confirm_email": True}   # project asks for e-mail confirmation first


def sign_in(email: str, password: str) -> dict[str, Any]:
    _check(email, password)
    _save(_call("POST", "/auth/v1/token?grant_type=password", {"email": email, "password": password}))
    return status()


def sign_out() -> dict[str, Any]:
    if SESSION.is_file():
        s = json.loads(SESSION.read_text(encoding="utf-8"))
        try:   # an expired token can't log out on the server; the local session goes either way
            _call("POST", "/auth/v1/logout", {}, s["access_token"])
        finally:
            SESSION.unlink()
    return {"signed_in": False}


def status() -> dict[str, Any]:
    s = _session()
    if not s:
        return {"signed_in": False}
    rows = _call("GET", "/rest/v1/team_members?select=display_name,role&user_id=eq."
                 + urllib.parse.quote(s["user_id"]), token=s["access_token"])
    member = rows[0] if rows else None
    return {"signed_in": True, "email": s["email"], "user_id": s["user_id"],
            "member": member is not None, "role": member["role"] if member else None,
            "display_name": member["display_name"] if member else None}

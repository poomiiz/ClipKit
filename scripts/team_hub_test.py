"""Check the local auth boundary without calling a live identity provider."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import team_hub as hub


def main():
    app = FastAPI()
    app.include_router(hub.router)
    user = {"id": "00000000-0000-0000-0000-000000000001", "email": "editor@example.test", "user_metadata": {"display_name": "Editor"}}
    session = {"access_token": "provider-access", "refresh_token": "provider-refresh", "expires_in": 3600, "user": user}
    hub._sessions.clear()
    with TestClient(app) as client, patch.object(hub, "_config", return_value=("https://hub.example.test", "public-key")), patch.object(hub, "_provider") as provider:
        assert client.get("/api/team/organizations").status_code == 401
        assert client.post("/api/team/login", json={"email": user["email"], "password": "password"}, headers={"Origin": "https://other.example.test"}).status_code == 403
        provider.assert_not_called()
        provider.return_value = session
        response = client.post("/api/team/login", json={"email": user["email"], "password": "password"})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert "provider-access" not in response.text and "provider-refresh" not in response.text
        assert client.get("/api/team/session").json()["user"] == {"id": user["id"], "email": user["email"], "display_name": "Editor"}
        provider.return_value = "new-org"
        assert client.post("/api/team/organizations", json={"name": "Team"}).json() == {"id": "new-org"}
        provider.assert_called_with("/rest/v1/rpc/clipkit_create_organization", "POST", {"org_name": "Team"}, "provider-access")
        session_id = client.cookies.get(hub.COOKIE)
        hub._sessions[session_id]["expires_at"] = 0
        provider.return_value = {**session, "access_token": "renewed-access"}
        assert client.get("/api/team/session").status_code == 200
        provider.assert_called_with("/auth/v1/token?grant_type=refresh_token", "POST", {"refresh_token": "provider-refresh"})
        assert hub._sessions[session_id]["access_token"] == "renewed-access"
        provider.return_value=[{"id":"00000000-0000-0000-0000-000000000010","clipkit_members":[{"user_id":user["id"],"role":"editor"}]}]
        assert client.post("/api/team/organizations/00000000-0000-0000-0000-000000000010/members",json={"email":"invited@example.test","role":"lead"}).status_code==403
        assert provider.call_args.args[0].startswith("/rest/v1/clipkit_organizations")
        assert client.post("/api/team/logout", json={}).status_code == 200
        assert client.get("/api/team/organizations").status_code == 401
    with TestClient(app) as client, patch.object(hub.kit_settings, "_read_config", return_value={}):
        assert client.get("/api/team/session").json() == {"configured": False, "signed_in": False}
        assert client.post("/api/team/signup", json={"email": user["email"], "password": "password", "display_name": "Editor"}).status_code == 503
    with TestClient(app) as client, patch.object(hub.kit_settings, "_read_config", return_value={"supabase_url": "https://hub.example.test", "supabase_anon_key": "sb_secret_private"}):
        assert client.post("/api/team/login", json={"email": user["email"], "password": "password"}).status_code == 503
        assert client.get("/api/team/setup").json()["supabase_anon_key"] == ""
    with TemporaryDirectory() as folder, TestClient(app) as client, patch.object(hub.kit_settings, "CONFIG", Path(folder)/"config.json"), patch.object(hub.kit_settings, "_read_config", return_value={"work_root":"preserved"}):
        setup={"supabase_url":"https://hub.example.test","supabase_anon_key":"sb_publishable_public"}
        assert client.post("/api/team/setup",json=setup,headers={"Origin":"https://other.example.test"}).status_code == 403
        assert not hub.kit_settings.CONFIG.exists()
        assert client.post("/api/team/setup",json=setup).status_code == 200
        import json
        saved=json.loads(hub.kit_settings.CONFIG.read_text())
        assert saved["work_root"] == "preserved" and saved["supabase_anon_key"]==setup["supabase_anon_key"]
    print("Local team session, cookie, origin and provider-token boundary checks passed")


if __name__ == "__main__":
    main()

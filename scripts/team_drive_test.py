"""Drive transfer boundary checks; never contact Google or upload real footage."""
import hashlib
import io
import json
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import team_drive as drive
import team_hub as hub


class Response(io.BytesIO):
    def __init__(self,data=b"",status=200,headers=None):
        super().__init__(data)
        self.status=status
        self.headers=headers or {}


def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory); file=root/"take.mp4";content=b"test footage";file.write_bytes(content)
        sha=hashlib.sha256(content).hexdigest()
        requests=[]
        def google(req):
            requests.append(req)
            if req.get_method()=="POST":
                return Response(headers={"Location":"https://www.googleapis.com/upload/drive/v3/files?upload_id=sample"})
            return Response(json.dumps({"id":"driveSnapshot123"}).encode())
        with patch.object(drive,"google",side_effect=google):
            assert drive.upload_file({"access_token":"private"},file,"org","asset","folder",sha)=="driveSnapshot123"
        metadata=json.loads(requests[0].data)
        assert metadata["parents"]==["folder"] and metadata["appProperties"]["sha256"]==sha
        assert requests[1].data==content and requests[1].headers["Content-range"]==f"bytes 0-{len(content)-1}/{len(content)}"
        assert "private" not in requests[1].full_url
        parts=[]
        def chunked(req):
            if req.get_method()=="POST":return Response(headers={"Location":"https://www.googleapis.com/upload/drive/v3/files?upload_id=sample"})
            parts.append(req.data)
            if len(parts)==1:return Response(status=308,headers={"Range":"bytes=0-7"})
            return Response(b'{"id":"driveSnapshot456"}')
        with patch.object(drive,"CHUNK",8),patch.object(drive,"google",side_effect=chunked):
            assert drive.upload_file({"access_token":"private"},file,"org","asset","folder",sha)=="driveSnapshot456"
        assert b''.join(parts)==content
        with patch.object(drive,"google",return_value=Response(headers={"Location":"https://attacker.example.test/upload"})):
            try:drive.upload_file({"access_token":"private"},file,"org","asset","folder",sha)
            except drive.HTTPException as e:assert e.status_code==502
            else:raise AssertionError("Untrusted upload URL accepted")

        app=FastAPI();app.include_router(drive.router)
        org="00000000-0000-0000-0000-000000000010";asset_id="00000000-0000-0000-0000-000000000020"
        org_data={"id":org,"drive_folder_id":"organizationFolder123"}
        asset={"id":asset_id,"kind":"footage","revision":2,"checksum":sha,"drive_file_id":"driveSnapshot123"}
        body={"organization_id":org,"asset_id":asset_id,"expected_revision":2}
        meta={"name":"take.mp4","parents":[org_data["drive_folder_id"]],"appProperties":{"clipkit_org":org,"clipkit_asset":asset_id,"sha256":sha}}
        with TestClient(app) as client,patch.object(drive,"organization",return_value=org_data),patch.object(hub,"assets",return_value=[asset]),patch.object(drive,"drive_session",return_value={"access_token":"private"}),patch.object(drive.kit_settings,"_read_config",return_value={"work_root":directory}),patch.object(drive,"drive_json",return_value=meta),patch.object(hub,"rpc") as rpc:
            with patch.object(drive,"google",return_value=Response(content)):
                result=client.post("/api/team/drive/download",json=body)
            assert result.status_code==200,result.text
            path=Path(result.json()["path"]);assert path.is_relative_to(root) and path.read_bytes()==content
            assert rpc.call_args.args[1]=="clipkit_record_received"
            path.write_bytes(b"local edits")
            assert client.post("/api/team/drive/download",json=body).status_code==409
            assert path.read_bytes()==b"local edits"
            assert client.post("/api/team/drive/download",json={**body,"expected_revision":1}).status_code==409
            assert client.post("/api/team/drive/download",json=body,headers={"Origin":"https://other.example.test"}).status_code==403
            path.unlink()
            with patch.object(drive,"google",return_value=Response(b"wrong content")):
                assert client.post("/api/team/drive/download",json=body).status_code==409
            assert not path.exists() and not list(path.parent.glob("*.partial"))
        hub._sessions["test-session"]={"ends_at":time.time()+600,"expires_at":time.time()+600,"user":{"id":"user"}}
        with TestClient(app) as client,patch.object(drive,"client_config",return_value={"client_id":"desktop","client_secret":"secret"}),patch.object(drive,"webbrowser") as browser:
            client.cookies.set(hub.COOKIE,"test-session")
            assert client.post("/api/team/drive/connect",headers={"Origin":"https://other.example.test"}).status_code==403
            browser.open.assert_not_called()
            browser.open.return_value=True
            assert client.post("/api/team/drive/connect").status_code==200
            url=urllib.parse.urlsplit(browser.open.call_args.args[0]);params=urllib.parse.parse_qs(url.query)
            assert url.hostname=="accounts.google.com" and params["code_challenge_method"]==["S256"]
            redirect=params["redirect_uri"][0];assert urllib.parse.urlsplit(redirect).hostname=="127.0.0.1"
            try:urllib.request.urlopen(redirect+"?state=wrong",timeout=2)
            except urllib.error.HTTPError as error:assert error.code==400
            else:raise AssertionError("Invalid OAuth state accepted")
            token={"access_token":"never-send-to-browser","refresh_token":"refresh-private","scope":drive.SCOPE,"expires_at":time.time()+3600}
            with patch.object(drive,"oauth_token",return_value=token) as exchange:
                with urllib.request.urlopen(redirect+"?"+urllib.parse.urlencode({"state":params["state"][0],"code":"test-code"}),timeout=2) as callback:
                    assert "Connected" in callback.read().decode()
                verifier=exchange.call_args.args[0]["code_verifier"]
                import base64
                assert params["code_challenge"][0]==base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            result=client.get("/api/team/drive/connection")
            assert result.json()["connected"] and "never-send-to-browser" not in result.text
        hub._sessions.clear()
    print("Drive immutable upload, URL checks, checksum, local edit protection and origin checks passed (mock provider)")


if __name__=="__main__":main()

"""Desktop OAuth and immutable Drive transfers; organization decisions remain in Supabase."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import threading
import tempfile
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import kit_settings
import team_hub as hub
import team_packet
from team_packet import digest as file_checksum

router = APIRouter(prefix="/api/team/drive", tags=["team-drive"])
SCOPE = "https://www.googleapis.com/auth/drive"
API = "https://www.googleapis.com/drive/v3/"
CHUNK = 8 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code == 308:
            return None
        raise HTTPException(502, "Drive ส่งต่อคำขอไปปลายทางอื่น จึงหยุดส่งข้อมูล")


def google(request: urllib.request.Request):
    try:
        return urllib.request.build_opener(NoRedirect()).open(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code == 308:
            return exc  # Drive resumable upload acknowledges an incomplete chunk with 308.
        raise HTTPException(502, f"Google Drive ปฏิเสธคำขอ ({exc.code})") from exc
    except OSError as exc:
        raise HTTPException(502, "ติดต่อ Google Drive ไม่ได้") from exc


def oauth_token(values: dict) -> dict:
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=urllib.parse.urlencode(values).encode(), method="POST")
    with google(req) as response:
        data = json.load(response)
    if not data.get("access_token"):
        raise HTTPException(502, "Google ไม่ได้ส่งสิทธิ์เชื่อมต่อกลับมา")
    return {**data, "expires_at": time.time() + data.get("expires_in", 3600)}


def client_config() -> dict:
    cfg = kit_settings._read_config()
    if not cfg.get("google_drive_client_id") or not cfg.get("google_drive_client_secret"):
        raise HTTPException(503, "ตั้งค่า OAuth Desktop Client ID และ Client secret ในระบบทีมก่อน")
    return {"client_id": cfg["google_drive_client_id"], "client_secret": cfg["google_drive_client_secret"]}


def drive_session(request: Request) -> dict:
    hub.session(request)
    with hub._session_lock:
        data = hub._sessions[request.cookies[hub.COOKIE]]
        token = data.get("drive")
        if not token:
            raise HTTPException(401, "เชื่อมบัญชี Google Drive ก่อน")
        if token["expires_at"] <= time.time() + 60:
            refreshed = oauth_token({**client_config(), "grant_type": "refresh_token", "refresh_token": token["refresh_token"]})
            token.update(refreshed)
        return token.copy()


@router.get("/connection")
def connection(request: Request) -> dict:
    hub.session(request)
    with hub._session_lock:
        data = hub._sessions[request.cookies[hub.COOKIE]]
        return {"connected": bool(data.get("drive")), "pending": data.get("drive_pending", False), "error": data.get("drive_error", "")}


@router.post("/connect")
def connect(request: Request) -> dict:
    hub._same_origin(request)
    hub.session(request)
    cfg = client_config()
    session_id = request.cookies[hub.COOKIE]
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    with hub._session_lock:
        data = hub._sessions[session_id]
        if data.get("drive_pending"):
            raise HTTPException(409, "กำลังรอการอนุญาต Drive ในเบราว์เซอร์")
        data["drive_pending"], data["drive_error"], data["drive_state"] = True, "", state
    finished = threading.Event()

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # OAuth codes and state must never enter access logs.

        def do_GET(self):
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if not secrets.compare_digest(params.get("state", [""])[0], state):
                self.send_error(400, "Invalid authorization state")
                return
            try:
                if params.get("error") or not params.get("code"):
                    raise HTTPException(400, "ไม่ได้อนุญาตให้เชื่อม Google Drive")
                token = oauth_token({**cfg, "grant_type": "authorization_code", "code": params["code"][0], "redirect_uri": redirect, "code_verifier": verifier})
                if SCOPE not in token.get("scope", "").split() or not token.get("refresh_token"):
                    raise HTTPException(400, "Google ให้สิทธิ์ Drive ไม่ครบ กรุณาเชื่อมใหม่")
                with hub._session_lock:
                    current = hub._sessions.get(session_id)
                    if not current or current["ends_at"] <= time.time() or current.get("drive_state") != state:
                        raise HTTPException(401, "บัญชี ClipKit ออกจากระบบแล้ว กรุณาเชื่อมใหม่")
                    current["drive"] = token
                message = "Connected. Return to ClipKit."
            except (HTTPException, ValueError, KeyError) as exc:
                with hub._session_lock:
                    if session_id in hub._sessions and hub._sessions[session_id].get("drive_state") == state:
                        hub._sessions[session_id]["drive_error"] = exc.detail if isinstance(exc, HTTPException) else "เชื่อม Drive ไม่สำเร็จ"
                message = "Connection failed. Return to ClipKit for details."
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(message.encode())
            finally:
                finished.set()

    try:
        server = HTTPServer(("127.0.0.1", 0), Callback)
    except OSError as exc:
        with hub._session_lock:
            hub._sessions[session_id]["drive_pending"] = False
        raise HTTPException(503, "เปิดช่องรับคำอนุญาต Google ไม่ได้") from exc
    server.timeout = 1
    redirect = f"http://127.0.0.1:{server.server_port}/"

    def listen():
        try:
            deadline = time.time() + 600
            while not finished.is_set() and time.time() < deadline:
                with hub._session_lock:
                    if session_id not in hub._sessions or hub._sessions[session_id].get("drive_state") != state:
                        break
                server.handle_request()
        finally:
            server.server_close()
            with hub._session_lock:
                if session_id in hub._sessions and hub._sessions[session_id].get("drive_state") == state:
                    hub._sessions[session_id]["drive_pending"] = False
                    if not finished.is_set():
                        hub._sessions[session_id]["drive_error"] = "หมดเวลาอนุญาต Drive กรุณาเชื่อมใหม่"

    threading.Thread(target=listen, daemon=True).start()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({"client_id": cfg["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": SCOPE, "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent"})
    if not webbrowser.open(url):
        finished.set()
        raise HTTPException(503, "เปิดเบราว์เซอร์เพื่อเชื่อม Google ไม่ได้")
    return {"pending": True}


@router.post("/disconnect")
def disconnect(request: Request) -> dict:
    hub._same_origin(request)
    hub.session(request)
    with hub._session_lock:
        data=hub._sessions[request.cookies[hub.COOKIE]]
        token=data.get("drive")
        if token:
            req=urllib.request.Request("https://oauth2.googleapis.com/revoke",data=urllib.parse.urlencode({"token":token["refresh_token"]}).encode(),method="POST")
            with google(req):
                pass
        data.pop("drive",None)
        data.pop("drive_state",None)
        data["drive_pending"]=False
    return {"disconnected": True}


def drive_json(token: dict, path: str) -> dict:
    with google(urllib.request.Request(API + path, headers={"Authorization": "Bearer " + token["access_token"]})) as response:
        return json.load(response)


def organization(request: Request, org: UUID) -> dict:
    rows = hub.organizations(request)
    found = next((x for x in rows if x["id"] == str(org)), None)
    if not found:
        raise HTTPException(403, "คุณไม่ได้เป็นสมาชิกองค์กรนี้")
    if not found.get("drive_folder_id"):
        raise HTTPException(409, "เจ้าขององค์กรต้องตั้งโฟลเดอร์ Drive ก่อน")
    return found


def folder_access(token: dict, folder_id: str, writing: bool = False) -> None:
    folder = drive_json(token, "files/" + folder_id + "?supportsAllDrives=true&fields=id,mimeType,trashed,capabilities(canAddChildren)")
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise HTTPException(409, "โฟลเดอร์ Drive นี้ใช้ไม่ได้")
    if writing and not folder.get("capabilities", {}).get("canAddChildren"):
        raise HTTPException(403, "บัญชี Google นี้ไม่มีสิทธิ์ส่งไฟล์เข้าโฟลเดอร์องค์กร")


def upload_file(token: dict, file: Path, org: str, asset: str, folder: str, checksum: str) -> str:
    metadata = {"name": asset + "-" + checksum[:16] + file.suffix, "parents": [folder], "appProperties": {"clipkit_org": org, "clipkit_asset": asset, "sha256": checksum}}
    req = urllib.request.Request("https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true&fields=id", data=json.dumps(metadata).encode(), headers={"Authorization": "Bearer " + token["access_token"], "Content-Type": "application/json", "X-Upload-Content-Length": str(file.stat().st_size)}, method="POST")
    with google(req) as response:
        upload_url = response.headers.get("Location", "")
    parsed = urllib.parse.urlsplit(upload_url)
    if parsed.scheme != "https" or parsed.hostname != "www.googleapis.com" or parsed.username or parsed.port not in (None,443):
        raise HTTPException(502, "Drive ส่งที่อยู่รับไฟล์ไม่ถูกต้อง")
    size, sent, retries = file.stat().st_size, 0, 0
    with file.open("rb") as source:
        while sent < size:
            source.seek(sent)
            chunk = source.read(CHUNK)
            if not chunk:
                raise HTTPException(409, "ไฟล์เปลี่ยนระหว่างส่ง กรุณาส่งใหม่")
            end = sent + len(chunk) - 1
            req = urllib.request.Request(upload_url, data=chunk, method="PUT", headers={"Content-Length":str(len(chunk)), "Content-Range":f"bytes {sent}-{end}/{size}"})
            recovering=False
            try:
                response=google(req)
            except HTTPException as exc:
                if exc.status_code!=502 or retries>=3:
                    raise
                retries+=1
                recovering=True
                response=google(urllib.request.Request(upload_url,data=b"",method="PUT",headers={"Content-Range":f"bytes */{size}"}))
            with response:
                if response.status in (200,201):
                    if end != size-1 and not recovering:
                        raise HTTPException(502, "Drive จบการรับไฟล์ก่อนครบ")
                    return json.load(response)["id"]
                match=re.fullmatch(r"bytes=0-(\d+)",response.headers.get("Range",""))
                offset=int(match[1])+1 if match else 0
                if response.status != 308 or not sent<=offset<=end+1:
                    raise HTTPException(502, "Drive ยืนยันจำนวนข้อมูลไม่ตรง กรุณาส่งใหม่")
                if offset==sent:
                    retries+=1
                    if retries>3:
                        raise HTTPException(502,"Drive ยังไม่รับข้อมูล กรุณาส่งใหม่")
                sent=offset
    raise HTTPException(400, "ส่งไฟล์ว่างไม่ได้")


class Transfer(BaseModel):
    organization_id: UUID
    asset_id: UUID
    expected_revision: int = Field(ge=1)
    path: str = Field(min_length=1, max_length=2000)


@router.post("/upload")
def upload(body: Transfer, request: Request) -> dict:
    hub._same_origin(request)
    org = organization(request, body.organization_id)
    all_assets = hub.assets(body.organization_id, request)
    asset = next((x for x in all_assets if x["id"] == str(body.asset_id)), None)
    if not asset or asset["revision"] != body.expected_revision:
        raise HTTPException(409, "รายการเปลี่ยนหรือไม่อยู่ในองค์กร กรุณาโหลดใหม่")
    if asset["kind"]=="project" and asset["status"] not in ("editing","changes_requested"):
        raise HTTPException(409,"โปรเจกต์อยู่ระหว่างตรวจหรืออนุมัติแล้ว หัวหน้าต้องส่งกลับแก้ก่อนส่งไฟล์ใหม่")
    file = Path(body.path).resolve()
    cfg=kit_settings._read_config()
    if asset["kind"]=="project":
        kind,project=kit_settings._project(str(file))
        if kind!="capcut":raise HTTPException(400,"ขณะนี้ส่งโปรเจกต์ CapCut ได้เท่านั้น")
        if kit_settings._capcut_running():raise HTTPException(409,"ปิด CapCut ก่อนส่งโปรเจกต์")
        base=Path(cfg.get("output_dir") or cfg.get("work_root") or "")
        if not base.is_dir() or str(base)==".":raise HTTPException(400,"ตั้งโฟลเดอร์งานก่อนส่งโปรเจกต์")
        roots=[Path(cfg[k]) for k in kit_settings.FOLDER_KEYS if cfg.get(k) and k!="models_dir"]
        with tempfile.TemporaryDirectory(dir=base,prefix="clipkit-packet-") as directory:
            if not Path(directory).resolve().is_relative_to(base.resolve()):raise HTTPException(400,"โฟลเดอร์แพ็กไม่ถูกต้อง")
            packet=Path(directory)/"snapshot.zip"
            team_packet.pack(project,packet,str(body.organization_id),str(body.asset_id),roots)
            return send_snapshot(packet,org,body,request)
    roots = [Path(value).resolve() for key,value in cfg.items() if key in ("work_root", "output_dir") and value]
    if not file.is_file() or not any(file.is_relative_to(root) for root in roots) or file.suffix.lower() not in (".mp4", ".mov", ".mkv", ".avi", ".wav", ".mp3", ".m4a"):
        raise HTTPException(400, "เลือกฟุตจากโฟลเดอร์งานที่ตั้งค่าไว้")
    return send_snapshot(file,org,body,request)


def send_snapshot(file: Path,org: dict,body: Transfer,request: Request) -> dict:
    before = file.stat()
    checksum = file_checksum(file)
    token = drive_session(request)
    folder_access(token, org["drive_folder_id"], writing=True)
    drive_id = upload_file(token, file, str(body.organization_id), str(body.asset_id), org["drive_folder_id"], checksum)
    after = file.stat()
    if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
        raise HTTPException(409, "ไฟล์เปลี่ยนระหว่างส่ง ยังไม่ผูกไฟล์กับงาน ให้ส่งใหม่")
    try:
        revision = hub.rpc(request, "clipkit_commit_drive_file", {"org":str(body.organization_id),"asset":str(body.asset_id),"expected_revision":body.expected_revision,"file_id":drive_id,"sha256":checksum,"expected_folder":org["drive_folder_id"]})
    except HTTPException as exc:
        raise HTTPException(exc.status_code, "ส่งไฟล์ถึง Drive แล้ว แต่ผูกกับงานไม่ได้: " + str(exc.detail) + " · โหลดใหม่ก่อนส่งอีกครั้ง ไฟล์ที่ส่งยังอยู่ในโฟลเดอร์") from exc
    return {"saved": True, "revision": revision}


class Receive(BaseModel):
    organization_id: UUID
    asset_id: UUID
    expected_revision: int = Field(ge=1)


@router.post("/download")
def download(body: Receive, request: Request) -> dict:
    hub._same_origin(request)
    org = organization(request, body.organization_id)
    asset = next((x for x in hub.assets(body.organization_id,request) if x["id"]==str(body.asset_id)),None)
    if not asset or asset["revision"]!=body.expected_revision or not asset.get("drive_file_id") or not asset.get("checksum"):
        raise HTTPException(409,"ไฟล์เปลี่ยนหรือยังไม่ได้ส่งขึ้น Drive กรุณาโหลดใหม่")
    cfg=kit_settings._read_config()
    if not cfg.get("work_root") or not Path(cfg["work_root"]).is_dir():
        raise HTTPException(400,"ตั้งค่าโฟลเดอร์ฟุตของเครื่องก่อนรับไฟล์")
    token=drive_session(request)
    meta=drive_json(token,"files/"+asset["drive_file_id"]+"?supportsAllDrives=true&fields=id,name,parents,appProperties,trashed")
    props=meta.get("appProperties",{})
    if meta.get("trashed") or org["drive_folder_id"] not in meta.get("parents",[]) or props.get("clipkit_org")!=str(body.organization_id) or props.get("clipkit_asset")!=str(body.asset_id) or props.get("sha256")!=asset["checksum"]:
        raise HTTPException(409,"ไฟล์บน Drive ไม่ตรงกับรายการองค์กร")
    suffix=Path(meta["name"]).suffix.lower()
    if (asset["kind"]=="project" and suffix!=".zip") or (asset["kind"]=="footage" and suffix not in (".mp4",".mov",".mkv",".avi",".wav",".mp3",".m4a")):
        raise HTTPException(400,"ไฟล์ Drive นี้ไม่ใช่ฟุตที่รองรับ")
    root=Path(cfg["work_root"]).resolve()
    destination=root/"clipkit-team"/str(body.organization_id)/str(body.asset_id)
    if not destination.resolve().is_relative_to(root):
        raise HTTPException(400,"โฟลเดอร์รับไฟล์อยู่นอกโฟลเดอร์งาน")
    destination.mkdir(parents=True,exist_ok=True)
    target=destination/(asset["checksum"]+suffix)
    if target.exists():
        if file_checksum(target)!=asset["checksum"]:
            raise HTTPException(409,"ไฟล์ในเครื่องถูกแก้ไข กรุณาเก็บงานนั้นก่อนรับใหม่")
        hub.rpc(request,"clipkit_record_received",{"org":str(body.organization_id),"asset":str(body.asset_id),"expected_revision":body.expected_revision})
        if asset["kind"]=="project":return import_project(target,asset,body,cfg)
        return {"path":str(target),"revision":asset["revision"]}
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=destination,suffix=".partial",delete=False) as output:
            temp=Path(output.name)
            req=urllib.request.Request(API+"files/"+asset["drive_file_id"]+"?alt=media&supportsAllDrives=true",headers={"Authorization":"Bearer "+token["access_token"]})
            checksum=hashlib.sha256()
            with google(req) as response:
                while chunk:=response.read(CHUNK):
                    checksum.update(chunk);output.write(chunk)
        if checksum.hexdigest()!=asset["checksum"]:
            raise HTTPException(409,"ข้อมูลที่รับไม่ตรงกับไฟล์ต้นทาง ยังไม่เปิดใช้ไฟล์")
        temp.rename(target)
        hub.rpc(request,"clipkit_record_received",{"org":str(body.organization_id),"asset":str(body.asset_id),"expected_revision":body.expected_revision})
        if asset["kind"]=="project":return import_project(target,asset,body,cfg)
        return {"path":str(target),"revision":asset["revision"]}
    finally:
        if temp and temp.exists():
            temp.unlink()


def import_project(packet: Path,asset: dict,body: Receive,cfg: dict) -> dict:
    if kit_settings._capcut_running():raise HTTPException(409,"รับแพ็กแล้ว ปิด CapCut ก่อนนำโปรเจกต์เข้า")
    root=Path(cfg.get("capcut_drafts") or "")
    if not root.is_dir() or str(root)==".":raise HTTPException(400,"ตั้งโฟลเดอร์โปรเจกต์ CapCut ก่อนรับงาน")
    root=root.resolve()
    final=root/("CK-"+str(body.asset_id)+"-"+asset["checksum"][:12])
    if final.resolve().parent!=root:raise HTTPException(400,"ตำแหน่งรับโปรเจกต์ไม่ถูกต้อง")
    if final.exists():raise HTTPException(409,"โปรเจกต์รุ่นนี้อยู่ในเครื่องแล้ว: "+str(final)+" · เก็บงานในเครื่องไว้ ไม่เขียนทับ")
    sys.path.insert(0,str(kit_settings.KIT/"scripts"/"capcut"))
    import kitconfig
    registry=Path(kitconfig.ROOT_META)
    if not registry.is_file():raise HTTPException(400,"ไม่พบรายชื่อโปรเจกต์ CapCut เปิด CapCut ครั้งแรกและตั้งโฟลเดอร์ให้ถูกต้องก่อน")
    existing=json.loads(registry.read_text(encoding="utf-8-sig"))
    if not isinstance(existing.get("all_draft_store"),list):raise HTTPException(400,"รายชื่อโปรเจกต์ CapCut อ่านไม่ได้")
    with tempfile.TemporaryDirectory(dir=root,prefix="clipkit-import-") as directory:
        staging=Path(directory)
        if not staging.resolve().is_relative_to(root):raise HTTPException(400,"โฟลเดอร์รับโปรเจกต์ไม่ถูกต้อง")
        team_packet.unpack(packet,staging,final,str(body.organization_id),str(body.asset_id),asset["name"])
    metadata=final/"draft_meta_info.json"
    if not metadata.is_file():raise HTTPException(400,"รับโปรเจกต์แล้ว แต่แพ็กไม่มีข้อมูลรายชื่อ CapCut: "+str(final))
    entry=json.loads(metadata.read_text(encoding="utf-8"))
    entry["draft_cover"]=(final/"draft_cover.jpg").as_posix()
    existing["all_draft_store"].insert(0,entry)
    backup=registry.with_name(registry.name+".bak_team_"+secrets.token_hex(6))
    shutil.copy2(registry,backup)
    temporary=registry.with_name(registry.name+".tmp_"+secrets.token_hex(6))
    try:
        temporary.write_text(json.dumps(existing,ensure_ascii=False),encoding="utf-8")
        temporary.replace(registry)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path":str(final),"revision":asset["revision"],"kind":"capcut"}

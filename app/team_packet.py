"""Portable CapCut snapshots. Originals are read only; imports use a fresh project folder."""
from __future__ import annotations

import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

from fastapi import HTTPException

PREFIX = "clipkit-packet://"


def digest(path: Path) -> str:
    result=hashlib.sha256()
    with path.open("rb") as stream:
        while chunk:=stream.read(8*1024*1024):result.update(chunk)
    return result.hexdigest()


def walk(value, transform, key=""):
    if isinstance(value,dict):return {k:walk(v,transform,k) for k,v in value.items()}
    if isinstance(value,list):return [walk(v,transform,key) for v in value]
    if isinstance(value,str):
        if value.startswith(("{","[")):
            try:nested=json.loads(value)
            except ValueError:pass
            else:return json.dumps(walk(nested,transform,key),ensure_ascii=False)
        return transform(value,key)
    return value


def json_content(data: bytes, name: str):
    try:text=data.decode("utf-8-sig")
    except UnicodeError:return None
    if name.endswith(".json") or text.lstrip().startswith(("{","[")):
        try:return json.loads(text)
        except ValueError:
            if name.endswith(".json"):raise HTTPException(400,"ไฟล์โปรเจกต์อ่านไม่ได้: "+name)
    return None


def pack(project: Path, destination: Path, org: str, asset: str, roots: list[Path]) -> None:
    project=project.resolve(); roots=[p.resolve() for p in roots]
    files={};directories=set();resources={}
    def include(path: Path, member: str):
        if path.is_symlink() or not any(path.resolve().is_relative_to(root) for root in [project,*roots]):
            raise HTTPException(400,"โปรเจกต์อ้างถึงไฟล์นอกโฟลเดอร์งาน: "+path.name)
        if member.startswith("resources/"):resources[path.resolve()]=member
        if path.is_dir():
            directories.add(member)
            for child in path.iterdir():include(child,member+"/"+child.name)
        elif path.is_file():files[member]=path
        else:raise HTTPException(400,"โปรเจกต์มีสื่อที่หาไม่เจอ: "+path.name)

    def portable(value: str,key: str):
        if not value or not (Path(value).is_absolute() or PureWindowsPath(value).is_absolute()):return value
        path=Path(value).resolve()
        if key=="draft_root_path" and path==project.parent:return PREFIX+"parent"
        if path.is_relative_to(project):
            member="project"+("/"+path.relative_to(project).as_posix() if path!=project else "")
            if not path.exists():raise HTTPException(400,"สื่อในโปรเจกต์หาไม่เจอ: "+path.name)
            if path.is_dir():directories.add(member)
            elif member not in files:include(path,member)
            return PREFIX+member
        if path not in resources:
            member="resources/"+hashlib.sha256(str(path).encode()).hexdigest()[:24]+"/"+path.name
            include(path,member);resources[path]=member
        return PREFIX+resources[path]

    for path in project.rglob("*"):
        relative=path.relative_to(project)
        if any(x in ("clipkit_history",".git") for x in relative.parts) or ".bak" in path.name or path.name=="clipkit_seal.json":continue
        if path.is_file():include(path,"project/"+relative.as_posix())
    payloads={};processed=set()
    while pending:=[member for member in files if member not in processed]:
        for member in pending:
            path=files[member];before=path.stat()
            with path.open("rb") as stream:head=stream.read(4)
            parsed=None
            if path.suffix==".json" or head.lstrip().startswith((b"{",b"[")):
                if before.st_size>64*1024*1024:raise HTTPException(400,"ข้อมูลโปรเจกต์ JSON ใหญ่เกินไป")
                parsed=json_content(path.read_bytes(),path.name)
            if parsed is not None:payloads[member]=json.dumps(walk(parsed,portable),ensure_ascii=False).encode()
            if (before.st_size,before.st_mtime_ns)!=(path.stat().st_size,path.stat().st_mtime_ns):raise HTTPException(409,"ไฟล์เปลี่ยนระหว่างแพ็ก ปิด CapCut แล้วส่งใหม่")
            processed.add(member)
    if "project/draft_content.json" not in payloads:raise HTTPException(400,"ไม่ใช่โปรเจกต์ CapCut")
    manifest={"version":1,"organization_id":org,"asset_id":asset,"format":"capcut","files":{member:hashlib.sha256(payloads[member]).hexdigest() if member in payloads else digest(path) for member,path in files.items()}}
    with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json",json.dumps(manifest))
        for directory in sorted(directories):archive.writestr(directory+"/",b"")
        for member,path in files.items():
            if member in payloads:archive.writestr(member,payloads[member]);continue
            before=path.stat();archive.write(path,member,compress_type=zipfile.ZIP_STORED)
            if (before.st_size,before.st_mtime_ns)!=(path.stat().st_size,path.stat().st_mtime_ns):raise HTTPException(409,"สื่อเปลี่ยนระหว่างแพ็ก กรุณาส่งใหม่")


def safe_member(name: str) -> PurePosixPath:
    path=PurePosixPath(name)
    if not name or "\\" in name or ":" in name or "\0" in name or path.is_absolute() or any(x in (".","..","") for x in name.rstrip("/").split("/")):
        raise HTTPException(400,"แพ็กมีตำแหน่งไฟล์ที่ไม่ปลอดภัย")
    reserved={"con","prn","aux","nul",*[f"com{i}" for i in range(1,10)],*[f"lpt{i}" for i in range(1,10)]}
    if any(part.endswith(("."," ")) or part.split(".")[0].lower() in reserved for part in path.parts):raise HTTPException(400,"แพ็กมีชื่อไฟล์ที่ใช้บน Windows ไม่ได้")
    if path.parts[0] not in ("project","resources") and name!="manifest.json":raise HTTPException(400,"แพ็กมีไฟล์ที่ไม่รองรับ")
    return path


def unpack(packet: Path, staging: Path, final: Path, org: str, asset: str, name: str) -> None:
    with zipfile.ZipFile(packet) as archive:
        entries=archive.infolist();seen=set()
        if len(entries)>100000:raise HTTPException(400,"แพ็กมีไฟล์มากเกินไป")
        for entry in entries:
            safe_member(entry.filename)
            folded=entry.filename.rstrip("/").casefold()
            if folded in seen or stat.S_ISLNK(entry.external_attr>>16):raise HTTPException(400,"แพ็กมีชื่อซ้ำหรือลิงก์ไฟล์")
            seen.add(folded)
        if sum(e.file_size for e in entries)>shutil.disk_usage(staging.parent).free:raise HTTPException(400,"พื้นที่ไม่พอรับโปรเจกต์")
        manifest=json.loads(archive.read("manifest.json"))
        if (manifest.get("version"),manifest.get("format"),manifest.get("organization_id"),manifest.get("asset_id"))!=(1,"capcut",org,asset):raise HTTPException(400,"แพ็กไม่ตรงกับโปรเจกต์ขององค์กร")
        expected=manifest.get("files",{})
        actual={e.filename for e in entries if not e.is_dir() and e.filename!="manifest.json"}
        if not isinstance(expected,dict) or actual!=set(expected) or "project/draft_content.json" not in actual:raise HTTPException(400,"แพ็กมีข้อมูลไม่ครบ")
        for entry in entries:
            if entry.filename=="manifest.json":continue
            destination=staging/Path(*safe_member(entry.filename).parts)
            if entry.is_dir():destination.mkdir(parents=True,exist_ok=True);continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            result=hashlib.sha256()
            with archive.open(entry) as source,destination.open("xb") as output:
                while chunk:=source.read(8*1024*1024):result.update(chunk);output.write(chunk)
            if result.hexdigest()!=expected[entry.filename]:raise HTTPException(409,"ไฟล์ในแพ็กไม่ตรงกับต้นทาง")

    def local(value: str,key: str):
        if not value.startswith(PREFIX):return value
        member=value[len(PREFIX):]
        if member=="parent":return final.parent.as_posix()
        relative=safe_member(member)
        if relative.parts[0]=="project":relative=PurePosixPath(*relative.parts[1:])
        else:relative=PurePosixPath("_team_resources",*relative.parts[1:])
        return (final/Path(*relative.parts)).as_posix()

    project=staging/"project"
    project_id=str(uuid4()).upper()
    for path in list(staging.rglob("*")):
        if not path.is_file():continue
        with path.open("rb") as stream:head=stream.read(4)
        if path.suffix!=".json" and not head.lstrip().startswith((b"{",b"[")):continue
        if path.stat().st_size>64*1024*1024:raise HTTPException(400,"ข้อมูลโปรเจกต์ JSON ใหญ่เกินไป")
        parsed=json_content(path.read_bytes(),path.name)
        if parsed is not None:
            if path.name=="draft_content.json":shutil.copy2(path,path.with_name(path.name+".bak_sync"))
            parsed=walk(parsed,local)
            if path==project/"draft_content.json":parsed["id"]=project_id
            if path==project/"draft_meta_info.json":parsed.update(draft_id=project_id,draft_name=name,draft_fold_path=final.as_posix(),draft_root_path=final.parent.as_posix(),draft_json_file=(final/"draft_content.json").as_posix())
            path.write_text(json.dumps(parsed,ensure_ascii=False),encoding="utf-8")
    if (staging/"resources").exists():shutil.move(str(staging/"resources"),str(project/"_team_resources"))
    if final.exists():raise HTTPException(409,"โปรเจกต์รุ่นนี้มีอยู่ในเครื่องแล้ว ไม่เขียนทับ")
    if not project.resolve().is_relative_to(staging.resolve()) or final.resolve().parent!=final.parent.resolve():raise HTTPException(400,"ตำแหน่งรับโปรเจกต์ไม่ถูกต้อง")
    project.rename(final)

"""Disposable two-workspace CapCut roundtrip and hostile packet checks."""
import json
import sys
import tempfile
import zipfile
import types
from uuid import uuid4
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
import team_packet as packet
import team_drive as drive
from fastapi import HTTPException


def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);first=root/"editor";second=root/"lead";first.mkdir();second.mkdir()
        footage=first/"take.mp4";footage.write_bytes(b"sample-footage")
        project=first/"project";project.mkdir();(project/"draft_cover.jpg").write_bytes(b"cover")
        document={"id":"original","materials":{"videos":[{"path":str(footage),"id":"media"}]},"cover":str(project/"draft_cover.jpg"),"content":json.dumps({"path":str(footage)})}
        original=json.dumps(document).encode();(project/"draft_content.json").write_bytes(original)
        (project/"draft_meta_info.json").write_text(json.dumps({"draft_id":"original","draft_root_path":str(first),"draft_fold_path":str(project)}))
        archive=root/"snapshot.zip";packet.pack(project,archive,"org","asset",[first])
        assert (project/"draft_content.json").read_bytes()==original
        with zipfile.ZipFile(archive) as z:
            assert str(first).encode() not in z.read("project/draft_content.json")
        staging=second/"staging";staging.mkdir();target=second/"shared-project"
        packet.unpack(archive,staging,target,"org","asset","Shared clip")
        imported=json.loads((target/"draft_content.json").read_text())
        assert imported["id"]!="original"
        path=Path(imported["materials"]["videos"][0]["path"])
        assert path.is_relative_to(target) and path.read_bytes()==footage.read_bytes()
        assert Path(imported["cover"]).read_bytes()==b"cover"
        assert json.loads(imported["content"])["path"]==path.as_posix()
        assert (target/"draft_content.json.bak_sync").is_file()
        assert json.loads((target/"draft_meta_info.json").read_text())["draft_id"]==imported["id"]
        org,asset=str(uuid4()),str(uuid4());packet.pack(project,archive,org,asset,[first])
        registry=second/"root_meta_info.json";registry.write_text(json.dumps({"all_draft_store":[],"draft_ids":0}))
        body=drive.Receive(organization_id=org,asset_id=asset,expected_revision=2)
        info={"id":asset,"kind":"project","name":"Team clip","checksum":packet.digest(archive),"revision":2}
        with patch.object(drive.kit_settings,"_capcut_running",return_value=False),patch.dict(sys.modules,{"kitconfig":types.SimpleNamespace(ROOT_META=str(registry))}):
            received=drive.import_project(archive,info,body,{"capcut_drafts":str(second)})
            added=json.loads(registry.read_text())["all_draft_store"][0]
            assert added["draft_fold_path"]==Path(received["path"]).as_posix()
            assert added["draft_id"]==json.loads((Path(received["path"])/"draft_content.json").read_text())["id"]
            assert list(second.glob("root_meta_info.json.bak_team_*"))
            try:drive.import_project(archive,info,body,{"capcut_drafts":str(second)})
            except HTTPException as error:assert error.status_code==409
            else:raise AssertionError("Existing project overwritten")
        for name in ("../outside","project/../../outside","project/C:/outside","project/CON.txt","project/draft_content.json.","project\\outside"):
            try:packet.safe_member(name)
            except HTTPException:pass
            else:raise AssertionError("Unsafe member accepted: "+name)
        poisoned=root/"poisoned.zip"
        with zipfile.ZipFile(poisoned,"w") as z:z.writestr("project/../../outside",b"bad")
        try:packet.unpack(poisoned,staging,second/"bad","org","asset","Bad")
        except HTTPException:pass
        else:raise AssertionError("Traversal archive accepted")
        assert not (root/"outside").exists()
        document["materials"]["videos"][0]["path"]=str(root/"missing.mp4")
        (project/"draft_content.json").write_text(json.dumps(document))
        try:packet.pack(project,root/"bad.zip","org","asset",[first])
        except HTTPException:pass
        else:raise AssertionError("Missing/outside media silently packaged")
    print("Two-workspace CapCut packet relinking, original preservation and unsafe archive checks passed")


if __name__=="__main__":main()

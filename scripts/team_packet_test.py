"""Disposable two-workspace CapCut roundtrip and hostile packet checks."""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
import team_packet as packet
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

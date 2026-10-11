"""Delivery status validation, persistence and rename checks using disposable projects."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import kit_settings as k
from fastapi import FastAPI
from fastapi.testclient import TestClient


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        project = root / "clip"
        project.mkdir()
        (project / "index.html").write_text("preview", encoding="utf-8")
        app = FastAPI()
        app.include_router(k.router)
        with patch.object(k, "DELIVERY_STATUSES", root / "statuses.json"), patch.object(
            k, "_project_roots", return_value={"hyperframes": root}
        ), TestClient(app) as client:
            endpoint = "/api/kit/delivery-status"
            assert client.get(endpoint).json() == {"statuses": {}}
            for status in ("editing", "awaiting_review", "changes_requested", "approved"):
                assert client.post(endpoint, json={"path":str(project),"status":status}).status_code == 410
                assert client.post(endpoint+"/bulk", json={"paths":[str(project)],"status":status}).status_code == 410
            assert client.get(endpoint).json() == {"statuses": {}}
            # Historical statuses remain readable and follow local renames, without granting review decisions.
            k._set_delivery_status([str(project)], "awaiting_review")
            renamed = client.post("/api/kit/draft-rename", json={"path": str(project), "name": "renamed"})
            assert renamed.status_code == 200, renamed.text
            saved = client.get(endpoint).json()["statuses"]
            assert str(project.resolve()).lower() not in saved
            assert saved[str((root / "renamed").resolve()).lower()]["status"] == "awaiting_review"
            assert (root / "renamed" / "index.html").read_text() == "preview"
    print("Historical delivery readback, protected decisions and rename OK")


if __name__ == "__main__":
    main()

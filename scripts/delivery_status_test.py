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
                result = client.post(endpoint, json={"path": str(project), "status": status})
                assert result.status_code == 200, result.text
                saved = client.get(endpoint).json()["statuses"][str(project.resolve()).lower()]
                assert saved["status"] == status and saved["updated_at"].endswith("Z")
            assert client.post(endpoint, json={"path": str(project), "status": "100%"}).status_code == 422
            assert client.post(endpoint, json={"path": str(root.parent), "status": "approved"}).status_code == 400
            assert client.get(endpoint).json()["statuses"][str(project.resolve()).lower()]["status"] == "approved"
            renamed = client.post("/api/kit/draft-rename", json={"path": str(project), "name": "renamed"})
            assert renamed.status_code == 200, renamed.text
            saved = client.get(endpoint).json()["statuses"]
            assert str(project.resolve()).lower() not in saved
            assert saved[str((root / "renamed").resolve()).lower()]["status"] == "approved"
            assert (root / "renamed" / "index.html").read_text() == "preview"
    print("Delivery status validation, persistence and rename OK")


if __name__ == "__main__":
    main()

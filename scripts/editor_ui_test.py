"""Check the unavailable-project screen without opening CapCut or editing any draft."""
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "app" / "static"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page()
                writes = []

                def api(route, request):
                    if request.method == "POST":
                        writes.append(request.url)
                        route.fulfill(json={"opened": "CapCut"})
                    elif "/draft/timeline" in request.url:
                        route.fulfill(status=400, json={"detail": "Unsupported multi-file project <b>detail</b>"})
                    else:
                        route.fulfill(json={})

                page.route("**/api/**", api)
                page.goto(f"http://127.0.0.1:{server.server_port}/editor.html?path=test-project", wait_until="networkidle")
                assert page.locator("#empty").inner_text() != "กำลังเตรียมตัวเล่น…"
                assert page.locator("#side details p").text_content().endswith("<b>detail</b>")
                assert page.locator("#bExport").is_disabled()
                page.locator("#bCapcut").click()
                page.wait_for_function("document.getElementById('busy').textContent === 'เปิด CapCut แล้ว'")
                assert len(writes) == 1 and writes[0].endswith("/api/kit/draft-open"), writes
                assert page.locator("#bExport").is_disabled()
                print("PASS unavailable project and safe CapCut handoff")
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()

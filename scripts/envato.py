"""Standalone Envato search/download with Playwright and this machine's own Chrome profile.

    python envato.py login                       # open Chrome once, sign in to Envato, close the window
    python envato.py search "electrician checking control panel" [--count 4]
    python envato.py download <item url> [--kind video|music] [--quality 1080P]

The profile lives in config "envato_profile" (default %USERPROFILE%/.clip-kit/envato-profile), so it never
touches the team bot's Chrome. Each download registers a licence on the signed-in account: only call
`download` for items a person ticked. Prints JSON on stdout; raises on any failure.
"""
import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent / "capcut"))
from kitconfig import CFG  # noqa: E402

from playwright.sync_api import TimeoutError as PWTimeout  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PROFILE = Path(CFG.get("envato_profile") or Path.home() / ".clip-kit" / "envato-profile")
DEST = {"video": Path(CFG.get("stock_video") or ""), "music": Path(CFG.get("stock_music") or "")}

PICK_JS = """() => {
    const cards = [...document.querySelectorAll('a[data-analytics-item_id]')];
    const curated = new Set(cards.filter(a => a.getAttribute('data-analytics-context-detail') === 'curated-items')
                                 .map(a => a.getAttribute('data-analytics-item_id')));
    const out = [], seen = new Set();
    for (const a of cards) {
        const id = a.getAttribute('data-analytics-item_id');
        if (curated.has(id) || seen.has(id)) continue;
        seen.add(id);
        const img = a.querySelector('img');
        out.push({id, title: a.getAttribute('data-analytics-item_title') || '', url: a.href.split('?')[0],
                  thumb: img ? (img.currentSrc || img.src) : null});
    }
    return out;
}"""


def browser(p, headless=False):
    PROFILE.mkdir(parents=True, exist_ok=True)
    # real Chrome (channel) and a visible window: Envato's sign-in and anti-bot checks reject headless browsers
    ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=headless,
                                               accept_downloads=True, no_viewport=True)  # page follows the window size, never wider than the screen
    return ctx, (ctx.pages[0] if ctx.pages else ctx.new_page())


def logged_out(page):
    u = page.url.lower()
    return "/sign_in" in u or "/signin" in u or "/login" in u or "account.envato.com" in u


def cmd_login(a):
    with sync_playwright() as p:
        ctx, page = browser(p)
        page.goto("https://elements.envato.com/sign-in", wait_until="domcontentloaded")
        print("Sign in to Envato in the Chrome window, then close it.", file=sys.stderr)
        page.wait_for_event("close", timeout=0)
        ctx.close()
    print(json.dumps({"profile": str(PROFILE)}))


def cmd_search(a):
    with sync_playwright() as p:
        ctx, page = browser(p)
        try:
            section = "music" if a.kind == "music" else "stock-video"
            page.goto(f"https://app.envato.com/{section}?term={quote(a.query)}", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            if logged_out(page):
                raise RuntimeError("Envato is not signed in - run: python envato.py login")
            submit = page.locator("form:has(input[name='term']) button[type='submit']").first
            if submit.count() and submit.is_visible():
                submit.click()            # the term lands in the box but the grid shows curated picks until submitted
            found = []
            for _ in range(12):
                page.wait_for_timeout(2000)
                found = page.evaluate(PICK_JS)
                if found:
                    break
            if not found:
                raise RuntimeError(f"no results for '{a.query}' ({page.url})")
            print(json.dumps({"query": a.query, "items": found[:a.count]}, ensure_ascii=False))
        finally:
            ctx.close()


def cmd_download(a):
    if not a.url.startswith(("https://elements.envato.com/", "https://app.envato.com/")):
        raise RuntimeError(f"not an Envato item url: {a.url}")
    dest = DEST[a.kind]
    if not str(dest) or not dest.is_dir():
        raise RuntimeError(f"config stock_{'video' if a.kind == 'video' else 'music'} folder not found: {dest}")
    with sync_playwright() as p:
        ctx, page = browser(p)
        try:
            url = a.url.replace("app.envato.com/search/", "app.envato.com/")   # search links open a modal route
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(7000)       # elements.* forwards to app.envato.com
            if logged_out(page):
                raise RuntimeError("Envato is not signed in - run: python envato.py login")
            # the item panel's own button; the grid behind it has small icon-only Download buttons too
            main = page.locator('[data-cy="idp-download-button"]').first
            try:
                main.wait_for(state="visible", timeout=20000)
            except PWTimeout:
                raise RuntimeError("no Download button - account not signed in or no download rights")
            picked = (main.inner_text() or "").strip()
            with page.expect_download(timeout=90000) as dl:
                if a.kind == "video" and a.quality.lower() not in picked.lower():
                    box = main.bounding_box()   # resolution menu hangs off the chevron right of the button
                    page.mouse.click(box["x"] + box["width"] + 15, box["y"] + box["height"] / 2)
                    page.wait_for_timeout(900)
                    want = int(re.sub(r"\D", "", a.quality) or 1080)
                    offers = []
                    for e in page.get_by_text(re.compile(r"\(\s*\d+\s*x\s*\d+")).all():
                        m = re.search(r"(\d+)\s*x\s*(\d+)", e.inner_text())
                        if m and e.is_visible():
                            offers.append((min(int(m.group(1)), int(m.group(2))), e))
                    if not offers:
                        main.click()            # single-resolution item: no menu
                    else:
                        exact = [o for o in offers if o[0] == want]
                        usable = exact or sorted((o for o in offers if o[0] >= 720), key=lambda o: o[0])
                        option = (usable or sorted(offers, key=lambda o: o[0]))[0][1]
                        picked = option.inner_text().strip()
                        option.click()
                else:
                    main.click()
            download = dl.value
            target = dest / download.suggested_filename
            if not (target.exists() and target.stat().st_size >= 100_000):
                download.save_as(str(target))
            size = target.stat().st_size
            if size < 100_000:
                target.unlink(missing_ok=True)   # never leave a stub a retry mistakes for done
                raise RuntimeError(f"downloaded file is too small ({size} bytes): {target}")
            files = [str(target)]
            if target.suffix.lower() == ".zip":
                files = unzip_audio(target)
            print(json.dumps({"file": files[0], "files": files, "bytes": size, "picked": picked, "url": a.url},
                             ensure_ascii=False))
        finally:
            ctx.close()


def unzip_audio(archive):
    """Envato ships music as a zip; keep only the audio, named after the item."""
    stem = re.sub(r"-\d{4}-\d{2}-\d{2}-.*$", "", archive.stem)
    out = []
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = Path(info.filename).name
            if info.is_dir() or "__MACOSX" in info.filename or name.startswith("._") or re.search(r"stem", name, re.I):
                continue
            if Path(name).suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac"):
                target = archive.parent / f"{stem}__{name}"
                with z.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                out.append(str(target))
    if not out:
        raise RuntimeError(f"zip has no audio: {archive}")
    archive.unlink()
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login").set_defaults(fn=cmd_login)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--count", type=int, default=4)
    s.add_argument("--kind", default="video", choices=["video", "music"])
    s.set_defaults(fn=cmd_search)
    d = sub.add_parser("download")
    d.add_argument("url")
    d.add_argument("--kind", default="video", choices=["video", "music"])
    d.add_argument("--quality", default="1080P")
    d.set_defaults(fn=cmd_download)
    a = ap.parse_args()
    a.fn(a)

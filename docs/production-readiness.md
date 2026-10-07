# ClipKit release readiness

Task: 9160a2ce-9aa8-446d-9b9a-20aa52b24a53

## Verified on 2026-10-07

- Baseline: `python scripts/smoke_test.py` passed all 7 existing checks.
- Machine: `python scripts/doctor.py` passed Python, packages, FFmpeg, Node,
  configured folders, NVIDIA GPU, cached speech model, disk and preview font.
- Settings jobs now reserve their name before starting a worker, preventing
  duplicate setup, update and login workers. Stored log tails are bounded to
  6,000 characters. Worker-start errors leave a visible failed state.
- Regression: `python scripts/smoke_test.py` also checks reservation, log limits
  and worker-start failures without media or network.
- HTTP boundary: only localhost and 127.0.0.1 Host headers are accepted;
  requests with foreign/null Origin or cross-site browser metadata are rejected
  before endpoints execute. Same-origin UI and local script requests remain usable.
  Framing is denied and MIME sniffing disabled. Regression checks cover both
  readable endpoints and a setup command without actually starting setup.
  Host protection uses [Starlette's existing middleware](https://www.starlette.io/middleware/).
- All 10 smoke checks passed locally. A Windows CI workflow now runs the same
  checks with development dependencies and the example config. Hosted CI has
  not run yet; clean-machine installation remains unverified.
- Setup now stops on failed native installer, package, model or doctor commands
  instead of continuing with an incomplete installation.
  A PowerShell regression simulates pip exit 17 and verifies setup stops before
  installing models or creating shortcuts; no installer is executed by this test.

## Remaining acceptance gates

These checks do not establish production editing quality.

- Run one representative Thai source through transcription, story selection,
  subtitles, preview, MP4 export and CapCut import. Record runtime, peak memory,
  duration and audio/subtitle synchronization. Have a person watch the pilot.
- Verify interruption, retry and rerun preserve source footage and existing
  drafts; close CapCut and back up drafts before any draft mutation.
- Audit local HTTP endpoints and external requests before release. A loopback
  address alone does not establish browser-request authorization.
- Choose an explicit project license with the owner; currently no root LICENSE.
  Retain third-party notices and font license. Check bundled runtime notices.
- Add clean-machine installation and CI based on the existing smoke suite.
- Review public files for credentials, personal paths and client material before
  publishing. Keep config.json and media outside version control.

No production deployment or public release has been performed.

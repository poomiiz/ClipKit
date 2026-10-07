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
  External framing is denied, same-origin previews are allowed, and MIME sniffing is disabled. Regression checks cover both
  readable endpoints and a setup command without actually starting setup.
  Host protection uses [Starlette's existing middleware](https://www.starlette.io/middleware/).
- All 20 smoke checks passed locally. A Windows CI workflow now runs the same
  checks with development dependencies and the example config. Hosted CI has
  not run yet. A fresh temporary Python 3.12 virtual environment installed
  requirements-dev.txt successfully and passed all 14 checks with the example
  config. This verifies Python dependency completeness on this host; full OS
  installation, GPU dependencies and installation on a separate machine remain unverified.
- Setup now stops on failed native installer, package, model or doctor commands
  instead of continuing with an incomplete installation.
  A PowerShell regression simulates pip exit 17 and verifies setup stops before
  installing models or creating shortcuts; no installer is executed by this test.
- Declared Pillow and fonttools as direct export dependencies; doctor checks
  them, and smoke verifies the bundled Thai font can actually be measured.
  Font metadata files now close immediately after reading.
- Story input rejects empty lists, wrong types, invalid ranges and non-finite
  timestamps before project creation. Missing agent output still requests input.
- Preview proxies now encode in a temporary directory and publish only after
  success. Cache keys include source identity, size and modification time.
  Existing previews survive failures; old proxies remain available to open
  players (disk cleanup is still an explicit future acceptance item).
- `python scripts/media_test.py` passed with generated H.264/AAC footage:
  two kept pieces produced a 2.0-second video; full decode, cache reuse,
  simulated partial-write failure, real retry and distinct-source caches passed.
  This is transport/render evidence, not Thai editorial or human pilot approval.
- Speech loading now uses the current configured device, model and model folder.
  Explicit model arguments and VIDEO_WHISPER_MODEL override the configured name.
  CPU selection is honored even when CUDA exists; failed CUDA loading raises
  an actionable error rather than silently loading a different CPU model.
  Model loading is serialized and cached by model/device/precision/folder.
  Invalid transcription times and windows are rejected before loading a model.
- `python scripts/doctor.py --asr` passed through the editor's real transcription
  path with configured large-v3/CUDA on a generated 3-second tone. This verifies
  model loading and inference, not speech accuracy. Doctor uses isolated temporary
  files and a bounded subprocess timeout instead of the legacy CLI defaults.
- Settings and workspace config writes now publish a completed temporary file
  atomically. A simulated replacement failure preserves the previous config,
  cleans the temporary file and remains visible; invalid device values are rejected.
- Settings read/modify/write operations are serialized within the app so
  simultaneous changes preserve both fields. A two-worker regression passed.
  This lock does not coordinate separate running ClipKit processes.
- Copied preview media now uses source/version-specific names and publishes
  only complete copies. A regression verified equal-name/equal-size sources,
  cache reuse, interrupted copying, updated sources and retry preservation.
- Real headless Chromium loaded the cover and motion preview iframe bodies
  against an isolated local server. X-Frame-Options SAMEORIGIN and CSP
  frame-ancestors self retain external framing protection without breaking
  ClipKit's nested previews.
- A limited pattern scan of 116 tracked files found no matching credential or
  machine-path patterns. This is not a complete secrets or public-content audit.
- Folder transcription now reserves/checks its process under a lock and closes
  the parent's log handle after launch. Exit status is reported as done/failed,
  with no live handle reported as idle rather than inferred completion.
  The UI labels failed and unknown jobs honestly, enables retry after termination,
  shows status-read errors, and renders generated review text with textContent.
  Process regression and Node execution of the actual status function passed.
- The launcher monitors the server it starts and refuses to open a browser when
  startup fails or readiness times out. Its error points to the existing logs
  and doctor. PowerShell checks cover an already-ready server and failed startup
  using mocked process/browser calls; no user browser is opened by these checks.

## Speech settings

Select CPU explicitly on machines without a supported GPU. GPU load failures
remain visible; no automatic model/device substitution occurs. The GPU uses
int8_float16 and CPU int8. Precision and Thai transcription quality still need
comparison on representative real speech; a tone test cannot establish quality.

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

## Input needed for final acceptance

The antigravity reports were reviewed and a confirmed unused-material builder
defect was fixed. The 20th regression checks transitive references, cycles,
global entries and repeat pruning. See antigravity-bug-review.md; the team's
installed revision and original failing project are still needed for native
CapCut verification. The Markdown reports do not contain those artifacts.

The configured footage folder exists. Its top-level videos and immediate
subfolder candidates include branding, motion and mockup assets; no candidate
has been confirmed as the representative Thai talking-head pilot. Do not use
those files to claim editorial, subtitle-accuracy or native CapCut acceptance.

Awaiting the pilot source path and the owner's choice of project license
(Apache-2.0 or MIT were offered). The owner must watch the first pilot before
batch release. No second machine or fresh Windows environment is available
in this session; the isolated Python installation result is narrower evidence.

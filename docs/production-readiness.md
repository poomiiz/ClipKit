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
- All 13 smoke checks passed locally. A Windows CI workflow now runs the same
  checks with development dependencies and the example config. Hosted CI has
  not run yet; clean-machine installation remains unverified.
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

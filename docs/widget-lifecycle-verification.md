# ClipKit widget verification — 2026-10-07

Task: `2a22b5af-3843-43ef-9a69-6bab236e605e`

The local MoonRacle dashboard could not embed ClipKit because the browser boundary
rejected cross-site iframe navigation and sent SAMEORIGIN framing headers. The
dashboard also treated opaque HTTP failures as readiness successes.

The boundary now permits HTML iframe navigation from the two existing local KB
origins. Only the harmless window health route exposes a readable response to
these origins. Foreign API reads and mutations remain rejected. HTML framing is
restricted with CSP. Malformed referrers return 400.

Observed on the actual local dashboard in the in-app browser:

- CapCut loads 50 projects, including all five newer IMG_6805 projects.
- The animation library loads 249 items.
- Leaving the widget sets its iframe to about:blank. After both agent test windows
  closed, server PID 39768 exited cleanly and port 8770 had no listener.
- Opening the widget again sent the existing worker launch request. Server PID
  56136 started automatically, reported managed=true/windows=1, and loaded all
  50 projects. No manual server launch was used for this reopening.

Checks passed:

```text
python scripts/smoke_test.py                 20 checks passed
python scripts/window_lifecycle_test.py     managed-window checks passed
node scripts/test_video_editor_widget.cjs   passed (run in knowledge_base)
```

Screenshots: `widget-capcut-live.jpg`, `widget-library-live.jpg`.

The Desktop ClipKit shortcut was traced to this checkout's app/start.ps1. Native
Chrome app-window closure has not been directly observed; the browser automation
surface does not expose that window. Do not describe that native acceptance as
verified. The lifecycle protects running jobs and other open windows; crashed
connections expire after 180 seconds. The existing worker may take up to one
minute to start a dashboard widget.

No real CapCut draft content was changed during these checks.

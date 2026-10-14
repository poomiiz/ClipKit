# Approximate duration and fresh semantic pilot — 2026-10-14

Choose the desired length before selecting content: natural length, 30 seconds, 1, 2, 3 or 5 minutes. The saved per-source target goes into the Browser AI attachment and optional local-agent packet. It is an approximate aim; a complete thought can finish slightly earlier or later. Changing it archives earlier selections and pending answers. Resuming retains the choice. Imported AI selections are not subsequently split by a rigid duration rule.

Browser AI can now explicitly group consecutive transcript fragments with `through` before choosing normal text and emphasis. The same validated import and manual merge endpoint preserve the original word clock. Missing word timing cannot be presented as synchronized emphasis. Normal text stays while its emphasis appears, and both hold until the next phrase begins. Existing ratio fitting is shared by MP4, HyperFrames and CapCut.

The real UI trial found a separate failure: Auto edit borrowed a subtitle style with helper IDs belonging to another draft. The structural export gate correctly refused the missing references. The shared style borrower now copies typography without foreign animation/keyframe references; a regression exercises the real subtitle writer. The failed draft was retained and a new project was generated after the fix.

The cut log records letter counts, cut rate and duration as observations rather than demanding arbitrary letter, emphasis or minimum-length quotas. Its machine check is explicitly separate from pending human editorial review.

## Fresh private pilot

| Measurement | Observed result |
| --- | --- |
| Original footage | 54:30.25, Thai speech; low-resolution artwork with embedded text |
| Transcription | Fresh source copy; no transcript cache; large-v3; 374.067 seconds |
| Desired duration | Approximately 3 minutes, chosen before story selection |
| Selected story | Source 166.04–366.14 seconds; 3:20.10, complete job-offer outcome |
| Subtitle decisions | 79 ASR rows → 27 semantic groups; 11 chosen emphasis phrases |
| Export | 1920×1080; 200.12 seconds; libx264; 21.297 seconds encoding |
| Decode | Full FFmpeg decode exit 0; 13,728,813 bytes |
| CapCut | Generated structure passed; opened and played in CapCut 9.5; no missing-media dialog; normal text and emphasis observed together |

Playwright exercised the duration selector before planning, target lock during the active plan, attachment download containing the target before the transcript, JSON story import and retention of the 3:20 selection. It captured desktop 1440×1000 and actual CSS viewport 375×844; mobile document width was 375 and the select was 44px high. The first headed-browser capture had browser zoom (500 CSS pixels) and was replaced by a verified headless 375px capture.

Semantic grouping, the repaired subtitle writer, MP4 export and both builders were subsequently exercised through the application's shared Python functions. The final fresh export is **not** being represented as a successful full Playwright Auto edit rerun. The browser answer was authored by the operator from the exported transcript; no external Browser AI provider was exercised.

## Verification

```powershell
python scripts/story_target_test.py       # 6 tests
python scripts/subtitle_merge_test.py     # 6 tests, including foreign-helper regression
python scripts/subtitle_timing_test.py    # 11 tests
python scripts/draft_quality_test.py      # 12 tests
python scripts/motion_handoff_test.py     # 12 tests
python scripts/render_encoder_test.py     # 5 tests
python scripts/cutlog_quality_test.py     # 1 test
node scripts/web_ai_ui_test.js
python scripts/smoke_test.py
git diff --check
```

All listed checks passed locally. New import fixtures use temporary configuration so clean-checkout CI does not require a user's `config.json`. Numeric and structural evidence is in [duration-pilot-20261014.json](duration-pilot-20261014.json).

Human listening, uncertain names and ASR spelling remain pending. The low-resolution source artwork has baked-in large text, so this is a timing/contract pilot rather than polished visual acceptance. This pilot uses the normal/emphasis subtitle path, with zero standalone full-frame motion overlays. No native CapCut export, external provider acceptance, eight-video benchmark, installer release, Mac hardware acceptance or measured time-saving claim follows. Source media, full transcript, answers, project paths and login state stay private. The changes remain on the draft PR branch until reviewed and merged.

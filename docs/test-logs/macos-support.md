# Mac and Update checks

Checked on 13 October 2026. This records software evidence; it does not certify a CapCut project on a Mac.

## Published version 0.29.0

- [Release](https://github.com/poomiiz/EditorKrab/releases/tag/v0.29.0): commit `aee73656f608ee78d0ef2049529f220f4c50a970`.
- [PR checks](https://github.com/poomiiz/EditorKrab/actions/runs/38377507826) and [main checks](https://github.com/poomiiz/EditorKrab/actions/runs/38378233631): passed at that commit.
- Intel (`macos-15-intel`) and Apple Silicon (`macos-15`) runners installed the tools, configured a temporary workspace, ran CPU transcription on a generated tone, and passed the Python/page checks. The tone checks that the speech engine runs; it cannot establish speech accuracy.
- Native Mac server checks covered start, readiness, reopening without duplication, login-page/CSP transport, restart and graceful shutdown on an isolated port.
- All nine required original security commits in [the inventory](../release-inventory.json) existed and were ancestors of the release commit.
- A disposable Windows clone updated from v0.28.1 to this exact commit using the old updater. Tracked edits were stashed, a local commit remained on a backup branch, dependencies were updated, and a second Update reported the newest version. The benchmark returned `UNKNOWN` with no human trials.

## Patch work

The next patch fixes a missing-font case in CapCut titles as well as subtitles. Six regression checks pass locally, including the public templates, installed fonts, quoted text and missing bundled fonts. The old implementation failed four of those cases.

The promo MP4 and GIF now describe an editable draft, human review and export. They are labelled a workflow illustration, with Mac setup experimental. The voice-over script matches the captions. Rendered scenes were reviewed; the video is silent and is not an editing-speed demonstration.

Native font/render/preview checks and a real release-Update check are being added. Their CI results and the patch's published tag must be recorded before claiming delivery.

## Still needed

The owner has no Mac available for an interactive trial. These checks remain open:

- Select and cancel files/folders in the native dialogs; move a disposable item to Trash and confirm its recovery.
- Use real speech, inspect Thai subtitles and sound, then watch the exported MP4.
- Open a generated project in Mac CapCut, edit it, save it, reopen it and export it. Record the Mac model, macOS and CapCut versions.
- Try Google sign-in and any team workflow with the operator's actual services.

Follow [the Mac guide](../macos.md). A passing CI run cannot close the CapCut or human-review items. Real editing-time savings still need the [paired benchmark](../benchmark.md).

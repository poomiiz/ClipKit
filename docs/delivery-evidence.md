# Local delivery evidence

MP4 exports return `delivery_manifest` alongside `file`. Native builds keep their existing `(path, warnings)` return and store evidence in the same ledger: `<output-parent>/.clipkit-deliveries/<id>.private.json`. These records contain local provenance and must stay private. The repository ignores `*.private.json`; do not attach them directly to public bug reports.

Each immutable record binds the checked source revision, actual dependency fingerprints, backend options and resulting MP4 hash or native file tree. It records the source HEAD as well as actual code hashes, so a dirty development checkout is distinguishable from the committed source. No record is a signature, a human verdict or a replacement for team approval.

Read back one exact delivery:

```powershell
python scripts/quality_gate.py "<source-project>" --delivery "<manifest.private.json>" --output "<exact-output.mp4-or-native-folder>"
```

- Exit0: structural check passes and input/artifact bytes match this record. Human/native checks still remain pending.
- Exit2: inputs or output changed; the record is stale.
- Exit1: invalid structure, missing artifact or invalid/tampered evidence.
- `pending_checks`: recorded machine checks or commit provenance are incomplete.
- `pending_review`: recorded checks are current; human review is still pending.

Creating evidence happens before final publication. Disk/write failure preserves the existing output. If publication itself fails, an orphan manifest may remain; verify its exact artifact and current inputs before treating it as a delivered revision. Repeated exports keep old manifests. Native save/edit/addition changes its file tree and invalidates the prior record.

This is a partial EK08 implementation. Team-review decisions are not yet bound to these manifests, native review-UI discovery remains open, and no local approval mutation is added. CPU full audio/video decode is still explicitly pending; native opening/playback remains pending. Input coverage currently follows the existing export snapshot and does not yet certify every automatic music/SFX/tool/environment dependency. Caption presence and matching hashes do not prove speech timing, translation meaning, complete storytelling, face-safe motion, a watched pilot or time savings.

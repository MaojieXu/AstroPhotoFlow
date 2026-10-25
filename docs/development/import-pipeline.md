# Import pipeline candidate

Base: `3f72b71` on `feature/import-pipeline`. Worktree: `C:/Users/Administrator/.codex/worktrees/apf-import-pipeline/ComfyUI-AstroPhotoFlow`.

## Behavior

Registration enumerates and fixes member order, reads FITS headers, registers each Asset/AssetVersion and immutable intake metadata, then publishes the dataset with its pending members. It does not hash, copy or decode image pixels. A registered version has `availability=unknown`, null hash/size and `content_status=pending`; only a complete, hashed original becomes available. Registration progress is `task.report.registration={total,registered,completed}`. The counter includes completed registration decisions (including skipped/failed sources); cancellation can leave it incomplete.

The service lifespan owns one file executor and one preview executor, configured by the existing Settings.file_workers (default 2) and Settings.preview_workers (default 1). Every HTTP import, resume and retry shares these executors. Direct maintenance callers without executors own a temporary pair. The service drains submitted executor jobs at shutdown. Each task waits for all its content jobs and preview jobs before terminal status; active/interrupted tasks continue to protect pending assets/groups in trash cleanup.

Managed local files hash and copy to a partial file in one pass, then atomically rename. Uploaded files are already staged: the background worker hashes the staged file without a destination writer and atomically relocates it into objects. A crash after rename but before the database update retains the allocated path; resume/retry hashes the completed object and reuses the original asset/version IDs. Partial copies are removed, and external originals remain unchanged.

Automatic classification uses explicit IMAGETYP/IMAGETYPE/OBSTYPE/FRAMETYP/FRAME labels, preserving the raw selected header. Recognized light/bias/dark/flat/dark-flat labels supply the frame use; explicit Master and Frame/Subframe labels supply shape. Unrecognized/missing information remains unknown. Filenames do not classify. Omitting the request classification means automatic file/preset classification. Supplying the classification object means a whole-batch manual override, including explicit null fields. Existing stored task classifications retain their manual meaning. PATCH code was not changed.

Effective parameters/classification use manual values, then observed FITS values, then the frozen task preset snapshot, then unknown. Manual numeric zero wins. The flat capture_snapshot parameter keys remain, with immutable `import_provenance={value_sources,observed_parameters,defaults_snapshot}` added. Background content work does not rewrite asset metadata, so current manual edits and immutable intake facts remain separate. A concrete upload/preset autoflush bug was fixed by freezing the preset before adding queued task items.

FITS homogeneous groups are single preview jobs whose members retain fixed order; the first usable member establishes the persisted stretch. Different groups can use different preview workers, and retries carry the stored profiles. XISF/high-depth image members retain their format order and existing homogeneous stretch keys. Metadata/preview errors remain queryable and retryable. Both existing dataset publication paths retain calibration defaults and retained member overrides (the shared foundation already provided these copies).

The visible progress row ends when registration completes. Polling continues for background completion and preview/error refresh. Interrupted tasks retain resume controls. The actual WorkspaceRecords slot uses registration counts; parent-scoped registration notification dedup prevents repeated refresh when loading temporarily remounts ImportTasks. Upload transport progress remains visible while upload itself is incomplete; copy/hash/preview progress does not delay registration completion.

## Verification

All commands ran from this worktree, with its own `.artifacts/venvs/dev` and own node_modules. Every benchmark asserts `astrophotoflow.__file__` belongs to this worktree. Dependencies: root uv bootstrap with UV_PROJECT_ENVIRONMENT/UV_CACHE_DIR pointing inside this worktree; `uv sync --locked --extra dev --python <root-python>`; `corepack pnpm install --frozen-lockfile`. Local HTTP tests used elevated execution because this host's sandbox loopback hangs.

- `.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend -q --basetemp=.artifacts/pytest-backend`: **136 passed, 1 skipped**,48.50s. One existing SQLAlchemy cyclic-FK comparison warning. This covers the original ingestion/FITS/video/library/trash/R4/source/revision tests plus 15 pipeline cases.
- `.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend/test_import_pipeline.py -q --basetemp=.artifacts/pytest-pipeline-final`: **16 passed**,7.61s. Includes one subsequently added persisted-stretch retry test; no backend implementation changed after the full backend run.
- `corepack pnpm test`: **114 passed**,15 files,12.08s. Includes actual workspace registration progress, hidden background row with continued polling, refresh dedup, automatic/default omission and whole-batch override payloads.
- `corepack pnpm build`: Vue typecheck and production build pass; assets remain in local ignored build/frontend.
- `git diff --check`: clean.

Pipeline tests cover an explicit registration barrier (all pending members visible, zero completed content, task still running), blocked permanent deletion during that barrier, manual null/zero edits before copying completes, exact shared service peak file 2 / preview 1 across simultaneous tasks, configurable preview 2 with out-of-order content completion, first usable stretch, preset mutation after acceptance, upload hash-without-copy, failure after atomic rename, cancelled partial copy, original-byte preservation, same-ID interruption/resume, retry profile persistence, and draining file/preview jobs on service shutdown.

No request/response schema changed: the registration receipt uses the existing report dictionary and omitted classification was already allowed. Existing Zod contracts pass; generated OpenAPI therefore has no contract change to regenerate.

## Reproducible benchmark

Run from the worktree root:

```powershell
.artifacts/venvs/dev/Scripts/python.exe tests/benchmarks/import_pipeline.py
```

The exact script was run before edits at 3f72b71 and after the candidate, on the same machine and same synthetic eight 2048x2048 float32 FITS files (134,254,080 source bytes), three trials each. Inputs are created/reused under ignored `.artifacts/import-benchmark/source`; each trial creates a fresh local database/object directory. The script polls committed registration/dataset visibility every 5 ms and records full task drain, process I/O counters and peak RSS. These are warm local-filesystem measurements, not cold-cache storage benchmarks. The final candidate run had this branch's tests/builds idle. Other chats share the host, so small throughput differences are not attributed to a specific optimization.

| Median | Baseline | Candidate |
|---|---:|---:|
| All asset IDs registered |1.674s|0.063s|
| Dataset visible |1.879s|0.073s|
| Full background completion |1.884s|1.982s|
| Process read bytes |450,969,188|452,382,408|
| Process write bytes |135,257,572|135,372,932|
| Peak RSS |139.72MiB|120.93MiB|

Raw trials and medians: [import-pipeline-benchmark.json](import-pipeline-benchmark.json). Process I/O counters include database and preview work and are not physical-disk measurements. Baseline fixture generation retained its last float array in the process, while the final run reused existing files; peak RSS is recorded as observed and does not establish a comparable memory improvement. The result supports much earlier registration/visibility; it does **not** show a total-throughput improvement. Managed-file write volume stays approximately the source size. The upload regression independently proves no second full-file writer is opened. No real dataset was reimported or changed.

## Integration

- api.py: import asynccontextmanager, add create_app lifespan worker wiring, preserve all middleware/router code. Settings branch's additional router imports/registration can be retained independently.
- imports.py: pass app.state.import_workers through four background entry points; preserve the shared upload snapshot-before-items fix if already present.
- ImportDialog.vue: preserve the Settings branch's CapturePresetPicker import/state/template/capture_preset_id payload. This branch changes blank parameter omission and the manual-classification checkbox/payload only.
- Workspace.vue: only importRegistrationCompleted+dedup, uploadTaskProgress/uploadTaskLabel and context export changed; preserve all Settings sections. WorkspaceRecords only adds the registration event handler.
- No shared models, migrations, config, global MCP registration or default workspace pointer changed. No push or merge performed.

No unfinished implementation issue is known within this scope. User interaction acceptance and integrated multi-branch review remain the root task's responsibility. Background work currently uses explicit content-then-preview phases; the measured total duration is reported above rather than introducing additional scheduling complexity.

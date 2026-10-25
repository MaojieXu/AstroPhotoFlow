# Import pipeline candidate

Base: `3f72b71` on `feature/import-pipeline`. Worktree: `C:/Users/Administrator/.codex/worktrees/apf-import-pipeline/ComfyUI-AstroPhotoFlow`.

## Behavior

Registration enumerates and fixes member order, reads FITS/XISF headers, registers each Asset/AssetVersion and immutable intake metadata, then publishes the dataset with its pending members. It does not hash, copy or decode image pixels. A registered version has `availability=unknown`, null hash/size and `content_status=pending`; only a complete, hashed original becomes available. Registration progress is `task.report.registration={total,registered,completed}`. The counter includes completed registration decisions (including skipped/failed sources); cancellation can leave it incomplete.

The service lifespan owns one file executor and one preview executor, configured by the existing Settings.file_workers (default 2) and Settings.preview_workers (default 1). Every HTTP import, resume and retry shares these executors. Direct maintenance callers without executors own a temporary pair. The service drains submitted executor jobs at shutdown. Each task waits for all its content jobs and preview jobs before terminal status; active/interrupted tasks continue to protect pending assets/groups in trash cleanup.

Managed local files hash and copy to a partial file in one pass, then atomically rename. Uploaded files are already staged: the background worker hashes the staged file without a destination writer and atomically relocates it into objects. A crash after rename but before the database update retains the allocated path; resume/retry hashes the completed object and reuses the original asset/version IDs. Partial copies are removed, and external originals remain unchanged.

Automatic FITS/XISF classification uses explicit IMAGETYP/IMAGETYPE/OBSTYPE/FRAMETYP/FRAME labels, preserving the raw selected header. Recognized light/bias/dark/flat/dark-flat labels supply the frame use; explicit Master and Frame/Subframe labels supply shape. Unrecognized/missing information remains unknown. Filenames do not classify. Omitting the request classification means automatic file/preset classification. Supplying the classification object means a whole-batch manual override, including explicit null fields. Existing stored task classifications retain their manual meaning. PATCH code was not changed.

Effective parameters/classification use manual values, then observed FITS/XISF values, then the frozen task preset snapshot, then unknown. Manual numeric zero wins. The flat capture_snapshot parameter keys remain, with immutable `import_provenance={value_sources,observed_parameters,defaults_snapshot}` added. Background content work does not rewrite asset metadata, so current manual edits and immutable intake facts remain separate. A concrete upload/preset autoflush bug was fixed by freezing the preset before adding queued task items.

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

## Follow-up: phase evidence and measured FITS bottleneck

This follow-up supersedes the initial benchmark comparison for current performance and RSS. The original raw receipt remains unchanged for history. The new benchmark generates fixtures only in its parent process, deletes the final fixture array, and runs every baseline/candidate trial in a fresh child interpreter. Both receive the same pre-created warm source files; neither measured process generates fixtures. Baseline ingestion, FITS preview and upload route source is loaded directly from Git `3f72b71`. Candidate source hashes are recorded because measurement occurred before this follow-up commit. The measurement uses the isolated worktree Python and local databases.

Command (run from the worktree root; omit the two real-source arguments for synthetic-only runs):

```powershell
.artifacts/venvs/dev/Scripts/python.exe tests/benchmarks/import_pipeline.py --trials 3 --output .artifacts/import-phase-benchmark/final.json --real-source "C:/Users/Administrator/Desktop/WorkSpace/ComfyUI-AstroPhotoFlow/tests/data/Astro_Dataset/AstrophotoMarket.com - masterLight_BIN-2_4144x2822_EXPOSURE-300.00s_FILTER-SII_mono.fit" --real-source "C:/Users/Administrator/Desktop/WorkSpace/ComfyUI-AstroPhotoFlow/tests/data/Astro_Dataset/James Glucksman - NGC2070 Oiii.xisf"
```

All 24 trials completed. The synthetic workload is eight 2048x2048 float32 FITS files, 134,254,080 source bytes, using managed-local and upload flows. Only the named 46,823,040-byte FITS and 49,097,280-byte XISF are used for real reference-mode trials; originals are only opened for reading. No whole-corpus import or managed real-source copy is performed; the two named files use reference-mode trials in disposable local databases.

Elapsed wall times below are medians in seconds. Registration/dataset times start at background processing; total includes client/context startup and upload where applicable. Upload wall includes request setup and reading fixture bytes into the in-process client. It is an in-process ASGI upload benchmark, not a network bandwidth measurement.

| Workload | Revision | Registration | Dataset visible | Upload wall | Background drain | Total wall | Peak RSS MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| managed | baseline | 1.5452 | 1.7265 | 0.0000 | 1.7265 | 1.7769 | 136.5547 |
| managed | candidate | 0.0735 | 0.0892 | 0.0000 | 0.2763 | 0.3268 | 127.4648 |
| upload | baseline | 1.5441 | 1.7321 | 0.1404 | 1.7321 | 1.9146 | 186.7227 |
| upload | candidate | 0.0821 | 0.0821 | 0.1440 | 0.2300 | 0.4145 | 199.3711 |

Phase values are aggregate inclusive **wall-time sums / thread-CPU-time sums**, not elapsed duration. Concurrent workers overlap, and nested phases overlap: hash/copy contains copy writes and cancellation DB reads; preview contains decode plus publication/DB; upload request includes its ASGI request while the write runs on its service thread. Do not add these rows to reconstruct wall time or CPU utilization. The Windows thread CPU clock reports approximately 15.625 ms increments; zero and small CPU sums are quantized measurements, not evidence that a phase consumed no CPU. DB read timings also include one final correctness query; monitoring queries are excluded.

| Phase, seconds | Managed baseline | Managed candidate | Upload baseline | Upload candidate |
|---|---:|---:|---:|---:|
| upload_request | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.051617 / 0.015625 | 0.052875 / 0.000000 |
| upload_write | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.025969 / 0.031250 | 0.026133 / 0.046875 |
| hash_copy | 0.122832 / 0.078125 | 0.127450 / 0.093750 | 0.147439 / 0.093750 | 0.063769 / 0.062500 |
| copy_write | 0.023585 / 0.000000 | 0.023926 / 0.046875 | 0.022462 / 0.000000 | 0.000000 / 0.000000 |
| parsing | 0.044738 / 0.000000 | 0.006156 / 0.015625 | 0.037986 / 0.000000 | 0.037732 / 0.000000 |
| database_read | 0.030827 / 0.031250 | 0.047625 / 0.046875 | 0.032014 / 0.031250 | 0.050970 / 0.031250 |
| database_write | 0.076455 / 0.046875 | 0.105876 / 0.078125 | 0.073184 / 0.078125 | 0.125948 / 0.093750 |
| preview | 1.451481 / 1.281250 | 0.076914 / 0.046875 | 1.459001 / 1.437500 | 0.050133 / 0.031250 |
| preview_decode | 1.426571 / 1.265625 | 0.053682 / 0.015625 | 1.435000 / 1.406250 | 0.022348 / 0.015625 |
| atomic_managed_relocation | 0.001829 / 0.015625 | 0.001924 / 0.000000 | 0.002136 / 0.000000 | 0.000000 / 0.000000 |
| atomic_upload_relocation | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.002053 / 0.000000 |

Every upload trial records exactly 134,254,080 bytes written to upload-staging. Baseline then writes the same 134,254,080 bytes again through copy_write. Candidate upload has zero copy_write bytes and eight atomic_upload_relocation calls. The atomic rename itself takes about 2 ms in aggregate for eight files; hashing still reads every uploaded byte. Process I/O includes DB/preview traffic and is not physical-disk I/O. The fresh-process managed/upload comparisons now show a measured total-duration reduction on this fixture, driven primarily by the profiled FITS sampling fix; they do not promise improvement for all formats or storage systems.

### Actual format profiles and narrow fix

Isolated cProfile decode diagnostics run **after** the measured pipeline, with the monitor and executors stopped. Their profiler overhead and allocations are excluded from pipeline phases and RSS. Raw profiler tables are embedded in [import-pipeline-phases.json](import-pipeline-phases.json).

| Read-only real sample | Revision | Parsing sum | Preview sum | FITS decode sum | Background drain |
|---|---|---:|---:|---:|---:|
| .fit | baseline | 0.008215 | 0.136340 | 0.127437 | 0.197339 |
| .fit | candidate | 0.008383 | 0.013468 | 0.004166 | 0.079874 |
| .xisf | baseline | 0.016718 | 0.152746 | 0.000000 | 0.216126 |
| .xisf | candidate | 0.022456 | 0.150524 | 0.000000 | 0.226982 |

The real FITS profile identified 6,732 scalar scaled-data/readarray/fromfile calls for one 100px mono preview. Reading selected rows contiguously and then slicing the same columns in NumPy reduces those calls to 68. The sample coordinates, percentiles, Bayer offsets/demosaic, output pixels and display parameters remain unchanged. The helper signature and preview algorithm version remain unchanged. Regression coverage compares the previous Section expression against the new output for float, unsigned/scaled FITS, Bayer offsets, planar/interleaved RGB and tile-compressed FITS; a separate synthetic read-count regression proves 600 calls become 20.

The real XISF still spends most preview time computing full-frame 1/99 percentiles and mapping the full frame before shrinking. Its library decoder reads the full image. That behavior and its stretch remain unchanged; the follow-up does not introduce approximate percentiles, a new preview algorithm or scheduling framework. XISF total background time remains approximately unchanged, and its approximately 265 MiB peak RSS is a remaining format cost for this roughly 49 MB source.

### XISF header correctness

XISF registration now reads get_images_metadata()[0].FITSKeywords without calling read_image. It feeds explicit keyword values through the same parsed-parameter/classification rules as FITS and retains the raw keyword lists, values and comments in observed_parameters.xisf_fits_keywords and immutable import provenance. Thus Master Light and EXPTIME=300 win over preset defaults; explicit whole-batch/manual values still win, and absent fields remain unknown. Metadata errors retain XISF_PARSE_FAILED even when preview succeeds and can be retried without changing asset/version identity.

Affected checks: `.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend/test_fits_preview.py tests/backend/test_import_pipeline.py tests/backend/test_ingestion.py -q --basetemp=.artifacts/pytest-import-phase`: **76 passed in 22.21s**. The benchmark completed all baseline/candidate synthetic and real trials. Written-byte receipt assertions verified one upload write and no candidate second copy. `python -m py_compile tests/benchmarks/import_pipeline.py` and `git diff --check` pass. No frontend, shared models/config, API contracts, preview signatures or global workspace settings changed in the follow-up.

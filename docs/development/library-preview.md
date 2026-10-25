# Library display preview candidate

Base: `d46dc5a4c79ac6bacdc5bfd1d70af5c2ee1a4513`. Branch: `feature/library-preview`.
Worktree: `C:/Users/Administrator/.codex/worktrees/apf-library-preview/ComfyUI-AstroPhotoFlow`.

## Delivered behavior

Every photo thumbnail in the shared library, an open group, project photo references and project fixed-group member browsing opens a lightweight ComfyUI-styled dialog. List images stay 100 px. Display JPEGs are generated only on request, have maximum edge 1080 px and never upscale smaller images. The dialog shows loading/error/not-ready states, retries explicitly, closes by button/backdrop/Escape and releases blob URLs/timers; late responses after close cannot reopen it. Failed inline-save guards still protect drafts before opening a preview.

The redundant member-manager buttons are removed from records, the active-group toolbar and settings details. Direct library openDataset browsing and inline parameter/name edits, numeric sorting, paging, draft/revision errors and deletion remain. The dead Workspace DatasetEditor import/template/state/callbacks are removed, as approved after confirming no production conflict flow used them. Standalone DatasetEditor source/tests and membership/version HTTP APIs remain.

Project dataset references have a small read-only member browser using exactly row.version.members, paged ten at a time. It never substitutes dataset.current_version_id or asset.current_version for a pinned member version. Tests cover project reference A while the current dataset and photo are B.

## HTTP and frontend contract

Shared scope:

- `POST /api/v1/library/assets/{asset_id}/versions/{version_id}/previews/display` schedules/retries one derived cache job. It returns HTTP 202 for generating, otherwise 200 with the typed state.
- `GET .../previews/display/status` returns state without starting work.
- Existing `GET .../previews/display` returns only the cached JPEG; absent/nonavailable cache returns 404 and does not decode.

Project scope uses matching POST/status routes at `/api/v1/projects/{project_id}/asset-references/{reference_id}/previews/display`. Existing project cached GET remains. It resolves the reference's pinned version and enforces project ownership/scope; private assets remain unavailable through shared-library URLs. Thumbnail GET semantics are unchanged; unsupported `detail` remains unsupported.

Pydantic DisplayPreviewState and frontend displayPreviewSchema have this shape:

```json
{
  "asset_version_id": "fixed UUID",
  "size": "display",
  "status": "not_ready | generating | available | failed | unsupported",
  "width": null,
  "height": null,
  "error": null
}
```

Available states supply integer width/height. Other states use null dimensions. A problem supplies `error:{code,message}`. Explicit not-ready codes include SOURCE_NOT_READY, SOURCE_CLEANUP_ACTIVE, METADATA_NOT_READY, RECIPE_NOT_READY and STRETCH_NOT_READY. Unsupported layouts return PREVIEW_UNSUPPORTED; decode/publication failures remain queryable as PREVIEW_FAILED and POST retries them.

OpenAPI and Zod are synchronized. Four exact same-origin proxy entries were added: POST/status for shared and project scopes. The prior versions-path write prohibition has one narrowly documented POST exception for this derived display cache; business version writes remain prohibited. Actual proxy forwarding/auth/origin tests cover both route families.

## Cache, recipes and lifecycle

Cache identity is the existing Preview unique key: fixed asset version, selected HDU, size=display and preview algorithm version. New requests for an existing available file return without decoding; concurrent requests observe one generating ownership row and deduplicate under BEGIN IMMEDIATE. A missing derived cache can be regenerated. The same service preview executor from import_workers is used, respecting Settings.preview_workers; no request-owned executor or rendering wait is introduced. Cached JPEG retrieval is separate from small schedule/status requests and therefore does not hold the ComfyUI ten-second proxy request open during decoding.

Display generation requires an available original and an available 100 px recipe. Linear FITS/XISF/high-depth display reuses saved stretch bounds and reference; it never chooses the clicked member as a new reference. Pending/missing group reference or failed scientific metadata returns not_ready. Unknown metadata values are supported normally when parsing succeeded. FITS create_preview signature and algorithm version remain unchanged.

The concrete metadata-retry window is protected: _refresh_fits_metadata sets the retry item's existing preview_status=pending and invalidates existing thumbnail Preview rows to status=pending atomically with updated observations/HDU selection. Cache misses use the actual available thumbnail recipe, not historical task outcomes. This covers the period after metadata becomes available but before thumbnail regeneration, as well as cancellation/interruption/failure in that period. Successful regeneration or backfill marks the actual cache available. The retry endpoint accepts pending preview-only work; a barrier/cancel/retry test proves the old recipe stays uncached and the refreshed recipe becomes usable. No recipe-hash, history migration or general invalidation framework was added.

XISF and ordinary/high-depth images reuse current decoders with stored stretch; their full-frame decode costs remain. RAW embedded thumbnails must meet the requested threshold; a tiny embedded 100 px image cannot stand in for a 1080 px request. RAW falls back to half-size processing when that can meet the request, otherwise full processing; smaller sources are not enlarged. SER now stores its first-frame stretch bounds and accepts optional replay bounds. Existing SER thumbnails without those bounds reproduce the fixed 100 px first-frame recipe before larger sampling. FFmpeg videos keep their current first-frame/no-upscale behavior. `_save_preview` now includes size in its filename, preventing display writes from overwriting thumbnail files.

The service lifespan resets orphan generating display records to failed with a retry message. Shutdown drains queued/running display jobs through the shared executor. Tests verify one configured preview worker processes two owned jobs without creating extra decoder threads and that shutdown waits for both.

## Cleanup protection

`assert_no_preview_jobs(session, version_ids)` is a temporary PREVIEW_ACTIVE blocker. Trash calls it in `_trash_scope` immediately after collecting version IDs, and inside each per-asset write transaction immediately after rechecking version identities, before any unlink/calibration deferral. It does not count a running preview as successfully cleaned or dependency-retained.

Display scheduling rejects real cleanup intent/progress (`cleanup_status != trash`), while ordinary library removal still permits a valid fixed-project/shared view. The cleanup manifest's partial marker prevents new jobs after cleanup starts. Publication holds the DB write transaction while rechecking the Preview owner, AssetVersion and generating status, writing/renaming the JPEG and marking it available. A version deleted during decoding cannot receive a file or row afterward.

Temporary display files use the owner's deterministic `<storage_path>.tmp` name and are removed on normal completion/failure. `owned_preview_locations` adds an existing interrupted companion to the confirmed finite cleanup path list. Startup can clear orphan generating ownership without leaving an untracked temporary file when its source is later deleted. Existing shared-path exclusions protect both final and temporary companions; external originals are unchanged. Tests cover locked publication/retry, active-generation deletion rejection, deletion during decode, interrupted temporary cleanup and shared cache/temporary retention.

## Verification and isolation

Own dependencies were installed with root uv bootstrap while UV_PROJECT_ENVIRONMENT and UV_CACHE_DIR pointed inside this worktree, then `uv sync --locked --extra dev --python <root-python>` and `corepack pnpm install --frozen-lockfile`. Imported astrophotoflow.__file__ was verified inside this worktree. Config/data/reports are local: `.artifacts/preview-workspace/config.toml` and `.artifacts/reports/library-preview-validation.json`. Tests use synthetic sources and disposable local databases. No computer use, real dataset import, global MCP change or default workspace activation occurred. Localhost tests used elevated execution because this host's sandbox loopback hangs.

- `.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend tests/comfyui/test_proxy.py -q --basetemp=.artifacts/pytest-preview-candidate`: **180 passed, 1 skipped**, 61.05s; one existing SQLAlchemy cyclic-FK comparison warning. This broad run includes original ingestion, video, library, trash/R4/source/reference protection and contract/proxy tests.
- `.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend/test_display_previews.py tests/backend/test_import_pipeline.py tests/backend/test_ingestion.py -q --basetemp=.artifacts/pytest-preview-barrier`: **76 passed**, 33.37s, on the final metadata-ready/old-thumbnail barrier and pending-preview cancellation/retry implementation. This also includes the subsequently added shared temporary protection.
- `corepack pnpm test`: **121 passed**, 17 files, 10.94s. Standalone DatasetEditor coverage remains. Six obsolete manager-entry callback scenarios were removed; required direct group edit/sort/paging/error tests remain, obsolete no-click-preview assertions now test lazy display, and manager-only name/error tests were rewritten against direct group row editing.
- `corepack pnpm build`: Vue typecheck and production build passed, 160 modules; outputs remain local ignored build/frontend.
- OpenAPI export: `.artifacts/venvs/dev/Scripts/python.exe scripts/export_openapi.py`; running snapshot and proxy allowlist regression passed.
- `git diff --check`: clean.

RAW sizing is tested with a controlled LibRaw fixture. FFmpeg remains an optional local decoder and its environment-dependent existing test can skip. Unsupported scientific cubes/X-Trans/Quad Bayer remain explicit unsupported states. No unsupported format fallback or upscaling was introduced. User visual acceptance and integrated multi-branch checks remain for the root task, as computer use was excluded.

## Integration notes

- Preserve root's newer import classification/source-stamp changes. This branch's ingestion hunks are only size-specific preview filename, RAW requested-size selection and `_refresh_fits_metadata` pending preview marker. imports.py changes only pending preview retry eligibility.
- api.py adds previews router and creates DisplayPreviews in the existing lifespan with workers[1]. Keep root/calibration router registrations.
- Calibration trash guards remain independent. Keep this branch's PREVIEW_ACTIVE checks before calibration deferral and its finite owned-preview/temporary path collection plus shared-path protection.
- New reusable PhotoPreviewDialog prop is `photo?: {assetId,versionId,title,basePath?}` and event `close`. Default base path uses shared-library fixed IDs; project references supply their scoped `/projects/.../asset-references/.../previews` base. It owns schedule/poll/blob/error/retry lifecycle.
- FixedDatasetMembers accepts fixed `members:{id,asset:{id,name},version:{id}}[]` and owns read-only paging/thumbnails/dialog. Main calibration/library/project lists already share WorkspaceRecords/openPhotoPreview, so no extra calibration thumbnail hook is needed.
- New library-group UI mocks use the existing configureLibrary helper in Workspace.dataset-groups.test.ts. Root should retain/add calibration matching_member_count fields when merging its newer library-item contract. The actual project fixed-group mock is a DatasetReference, not a library item.
- Standalone DatasetEditor and all membership/version backend APIs are unchanged. No shared models/config/migration/dependency changes, push or merge were performed in this branch.

## Runtime acceptance correction: actual cache authority

Accepted PixInsight backfill can provide an available, correct 100 px cache while intentionally retaining terminal unsupported/failed AssetTaskItem history. The latest-task outcome gate incorrectly blocked those baseline photos. Display scheduling now treats the actual available thumbnail plus source/metadata/fixed stretch recipe as authority and never rewrites historical task outcomes.

The stale-recipe barrier now lives in the actual cache state: metadata refresh invalidates existing thumbnail Preview rows in the same write transaction that installs new observations and selected HDUs. An old JPEG can remain on disk, but status=pending makes it nonavailable until successful regeneration/backfill; cancellation or regeneration failure leaves it nonavailable. No fallback to stale JPEGs, recipe hashes, new tables, reimports or historical-task migration is used.

Synthetic regressions reproduce the accepted legacy PixInsight unsupported path and a failed-preview history, then backfill a valid RGB thumbnail. Display generation preserves saved bounds/reference, correct color, source bytes, thumbnail bytes and the entire recorded task response. The refreshed-metadata barrier now asserts actual thumbnail.pending, no display job, cancellation and successful preview-only retry. A failed refresh-preview test proves backfill can restore the actual cache without rewriting the failed task, after which display works.

Before the fix the two backfilled-history cases failed with not_ready. Final affected command:

```powershell
.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend/test_display_previews.py tests/backend/test_import_pipeline.py tests/backend/test_ingestion.py -q --basetemp=.artifacts/pytest-cache-authority-final
```

Result: **79 passed in 34.77s**, including existing stale-recipe/group and owned-cleanup cases. `git diff --check` passes. This was scoped source/test work in the existing preview worktree; no actual dev database/original files, root/import checkout, Node dependencies, schemas or API contract changed. The metadata-refresh hunk is beside the pending marker only and leaves root's earlier CFA priority/source-stamp/classification corrections to be preserved on integration.

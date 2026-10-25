# Library agent tools

The Python `AssetClient`, `apf` CLI and `apf mcp` stdio server share explicit domain operations over the authenticated local HTTP service. They use the same workspace config/token and business rules as the UI. They do not open SQLite or change workspace activation/MCP registration. Existing `client.py` imports, transport/context manager, `ServiceApiError`, `apf`/`apf-service` entrypoints, workbench flags and five original MCP names remain compatible.

## Structure and request contracts

- `client.py` owns config, authentication, HTTP transport, request serialization and service errors.
- `client_domains/imports.py`, `library.py`, and `organization.py` own named business methods and endpoint paths.
- `cli_commands.py` maps named CLI commands to those methods; `agent_tools/` contains explicit typed MCP functions over the same methods.
- Backend Pydantic request models from `import_schemas.py`, `schemas.py`, and `setup_schemas.py` are reused directly. `PhotoImportOptions` describes upload metadata only; file names and sizes are built from supplied local paths and validated by `UploadImportCreate`.

Complex CLI requests use `--data '<JSON>'` or `--data '@request.json'` for UTF-8 JSON. MCP requests use a typed `body` object, except `import_photo`/`import_photos` use optional `options`, and the original `update_asset_parameters` retains `asset_id`, `base_revision`, `parameters`. Published MCP schemas contain the full nested backend contracts, including equipment discriminators and revision fields. Unknown fields fail validation before HTTP.

Serialization uses `model_dump(mode="json", exclude_unset=True)` recursively. Omitted fields remain omitted; explicit null and numeric zero survive. A stale revision fails with the backend's `REVISION_CONFLICT`, HTTP status, field details and request ID. The CLI prints a failure to stderr and exits 1; MCP returns a tool error preserving that information. No blind conflict retries or fallback values are introduced.

Use `ASTROPHOTOFLOW_CONFIG` to select an already configured workspace:

```powershell
$env:ASTROPHOTOFLOW_CONFIG='C:/APF/workspace/config.toml'
apf imports roots
apf imports browse science --path '2026-10-25' --limit 50 --offset 0
```

There is no arbitrary-HTTP MCP tool. Legacy capture-profile endpoints, FITS HDU/header inspection, every numeric library filter and service-admin endpoints are not separately exposed as new tools in this change. Existing service administration commands remain available.

## Command and tool inventory

List commands accept `--limit/--offset`. Searchable registries accept `--q/--status/--sort-by/--order`; asset lists additionally accept `--frame-type/--role`; equipment accepts `--kind`; presets accept `--equipment-setup-id`. `apf <group> <command> --help` lists the actual supported flags. `tasks get` has `--items-limit/--items-offset` for member paging. `library list` offers `--frame-class` in addition to frame type/role/name/order. Reference lists, version lists, calibration targets and trash retain their own paging scope.

| CLI commands | MCP tools |
|---|---|
| `import-photo`, `import-photos` | `import_photo`, `import_photos` |
| `imports roots/browse/local` | `list_import_roots`, `browse_import_root`, `import_local` |
| `task`, `tasks list/get/cancel/resume/retry` | `get_import_task`, `list_import_tasks`, `cancel_import_task`, `resume_import_task`, `retry_import_items` |
| `assets list/get/parameters/patch/versions/version` | `list_assets`, `get_asset`, `update_asset_parameters`, `update_asset`, `list_asset_versions`, `get_asset_version` |
| `library list/remove` | `list_library_items`, `remove_library_items` |
| `datasets create/list/get/patch/archive/versions/version/publish/member-parameters` | `create_dataset`, `list_datasets`, `get_dataset`, `update_dataset`, `list_dataset_versions`, `get_dataset_version`, `publish_dataset_version`, `update_dataset_members` |
| `projects create/list/get/patch/archive` | `create_project`, `list_projects`, `get_project`, `update_project` |
| `projects assets/asset/add-asset/remove-asset` | `list_project_assets`, `get_project_asset`, `add_project_asset`, `remove_project_asset` |
| `projects datasets/dataset/add-dataset/remove-dataset` | `list_project_datasets`, `get_project_dataset`, `add_project_dataset`, `remove_project_dataset` |
| `equipment create/list/get/patch/archive` | `create_equipment`, `list_equipment`, `get_equipment`, `update_equipment` |
| `setups create/list/get/patch/archive` | `create_equipment_setup`, `list_equipment_setups`, `get_equipment_setup`, `update_equipment_setup` |
| `presets create/list/get/patch/archive` | `create_capture_preset`, `list_capture_presets`, `get_capture_preset`, `update_capture_preset` |
| `calibration targets` | `list_calibration_targets` |
| `previews schedule/status/export` | `schedule_display_preview`, `get_display_preview_status`, `read_display_preview` |
| `trash list/restore/delete-preview/delete` | `list_trash`, `restore_trash`, `preview_trash_delete`, `delete_trash` |

There are 58 tools. All five original names remain: `import_photo`, `get_import_task`, `list_assets`, `get_asset`, `update_asset_parameters`. `read_display_preview` is an explicit native MCP `ImageContent` response; ordinary import/task/asset responses contain metadata without embedded base64 JPEGs. The CLI export exclusively creates the requested local output file and returns its absolute path and byte count. An existing destination fails clearly without changing its bytes; choose a new output path on collision.

## Night import and automatic/manual classification

```powershell
apf import-photo 'C:/Photos/one.fits'
apf import-photos 'C:/Photos/one.fits' 'C:/Photos/two.fits' --data '@upload.json'
apf imports local --data '@night.json'
apf tasks list --status all --limit 20
apf tasks get TASK_ID --items-limit 50 --items-offset 0
apf tasks cancel TASK_ID
apf tasks resume INTERRUPTED_TASK_ID
apf tasks retry FAILED_TASK_ID --data '@retry.json'
```

`upload.json` contains optional metadata, for example:

```json
{"dataset_name":"M31 L night","capture_preset_id":"PRESET_UUID"}
```

`night.json` selects one or more configured-root files/folders:

```json
{"sources":[{"root_id":"science","path":"2026-10-25/M31"}],"storage_mode":"reference","dataset_name":"M31 night"}
```

`retry.json` selects original task-item IDs: `{"item_ids":["FAILED_ITEM_UUID"]}`. Resume applies to service-interrupted tasks; selected retry applies to eligible failed or cancelled tasks/items. Task `report.registration.completed` is distinct from `content_status`, `metadata_status`, `preview_status` and asset-version `availability`. Registration alone does not mean managed originals or previews are ready. A `SOURCE_CHANGED` item error / `availability:changed` means the source changed between registration and reading/copying: confirm the intended current source and create a new import rather than blindly retrying or altering timestamps.

The old single-photo client no longer hardcodes Light/subframe. Omitted classification keys use file facts/preset defaults. Supplied keys override the batch, including explicit null; supply both keys to classify the whole batch manually:

```json
{"classification":{"frame_class":"subframe","frame_type":"light"},"parameters":{"gain":0,"exposure_seconds":120},"dataset_name":"Manually classified night"}
```

Unknown stays unknown; filenames are not classification evidence. Parameter priority is manual non-null, observed file, frozen preset, unknown. The service freezes preset/setup facts when accepting the task and retries retain that snapshot. The client does not resolve mutable live presets. Multiple uploads create a logical dataset according to the existing backend rule, even when `create_dataset` is omitted.

## Revision edits, groups and project references

```powershell
apf assets get ASSET_UUID
apf assets parameters ASSET_UUID --base-revision 3 --gain 0 --clear exposure_seconds
apf assets patch ASSET_UUID --data '@asset-patch.json'
apf datasets create --data '@group.json'
apf datasets version DATASET_UUID VERSION_UUID
apf datasets publish DATASET_UUID --data '@publish.json'
apf datasets member-parameters DATASET_UUID --data '@members.json'
apf projects create --data '{"name":"M31 processing","target_name":"M31"}'
apf projects add-asset PROJECT_UUID --data '@asset-reference.json'
apf projects add-dataset PROJECT_UUID --data '@dataset-reference.json'
apf projects remove-asset PROJECT_UUID REFERENCE_UUID --data '{"base_revision":4}'
```

Representative bodies (replace UUID placeholders with actual returned IDs):

```json
{
  "asset-patch.json": {"base_revision":3,"notes":null,"classification":{"frame_type":"light"}},
  "group.json": {"name":"M31 L","asset_version_ids":["ASSET_VERSION_UUID"]},
  "asset-reference.json": {"base_revision":1,"asset_version_id":"ASSET_VERSION_UUID"},
  "dataset-reference.json": {"base_revision":2,"dataset_id":"DATASET_UUID","dataset_version_id":"DATASET_VERSION_UUID"},
  "members.json": {"base_revision":2,"base_version_id":"DATASET_VERSION_UUID","members":[{"asset_id":"ASSET_UUID","revision":3}],"parameters":{"gain":0}}
}
```

Read the current project revision between dependent reference writes. References pin versions; membership and project reference operations do not physically copy originals. Removing project references preserves the library object. Group publication takes the complete membership list; retained members keep their existing relative order and new members append. Batch member editing requires `base_version_id` and revisions for ALL current canonical group assets.

## Equipment, setups and owned presets

```powershell
apf equipment create --data '{"kind":"camera","name":"Main camera","specs":{"sensor_mode":"mono"}}'
apf equipment list --kind telescope
apf setups create --data '@setup.json'
apf presets create SETUP_UUID --data '@preset.json'
apf presets list --equipment-setup-id SETUP_UUID
apf presets patch PRESET_UUID --data '{"base_revision":1,"parameters":{"gain":0,"offset":null}}'
apf equipment archive EQUIPMENT_UUID --kind camera --base-revision 2
apf setups archive SETUP_UUID --base-revision 2
apf presets archive PRESET_UUID --base-revision 2
apf projects archive PROJECT_UUID --base-revision 5
```

```json
{
  "setup.json": {"name":"Travel rig","components":[{"source":"registered","equipment_id":"EQUIPMENT_UUID"},{"source":"inline","equipment":{"kind":"accessory","name":"Adapter"}}]},
  "preset.json": {"name":"L 120s","classification":{"frame_class":"subframe","frame_type":"light"},"parameters":{"gain":0,"exposure_seconds":120}}
}
```

Equipment kinds are camera, telescope, filter, mount, accessory and the preserved optical_system. Inline components are snapshots and do not auto-register equipment. Setup edits do not modify registered equipment. Configuration deletion means archive; no physical table deletion command is offered.

## Fixed calibration bindings

```powershell
apf calibration targets --frame-type dark --limit 50 --offset 0
apf datasets publish DATASET_UUID --data '@publish.json'
```

```json
{"base_revision":2,"asset_version_ids":["MEMBER_VERSION_UUID"],"calibration_defaults":{"dark":{"kind":"asset_version","id":"MASTER_DARK_VERSION_UUID"}},"member_calibration_overrides":{"MEMBER_VERSION_UUID":{"dark":null}}}
```

Targets are fixed asset_version or dataset_version IDs. Supplying defaults replaces the map, `{}` clears it, omission retains it. Each supplied member map replaces that member's map; omitted members retain theirs. Missing slots inherit and null explicitly disables use. `{}` restores member inheritance. The service validates target kind/use. It records calibration relationships without calibration computation. Historical bindings still protect targets after current bindings change.

## Display preview and guarded cleanup

```powershell
apf previews schedule ASSET_UUID VERSION_UUID
apf previews status ASSET_UUID VERSION_UUID
apf previews export ASSET_UUID VERSION_UUID preview.jpg
apf library remove --data '@remove.json'
apf trash list --limit 50
apf trash restore --data '@selection.json'
apf trash delete-preview --data '@selection.json'
apf trash delete --data '@confirmed-delete.json'
```

Preview state is `not_ready|generating|available|failed|unsupported`. Poll while generating. On `not_ready`, inspect original availability and the import-task outcome; wait only for a live running import/retry. Otherwise report the concrete unavailable/failed/interrupted cause or perform an already-authorized resume/retry. Cached failed/unsupported outcomes are terminal; inspect the error and explicitly schedule to retry a failed preview. Read/export the cached display JPEG after availability. No implicit scheduling is hidden in the image read.

Removal items require `entry_type`, `id`, `revision`, `current_version_id`. Trash selection items require `entry_type`, `id`, `removed_at`, `revision`, `current_version_id`, optional `source_dataset_id`. Use only these request fields from the current trash DTO. A permanent deletion body is that exact current selection plus `preview_fingerprint` from its fresh deletion preview. Review references, tasks and managed-file scope, and act only inside the user's explicitly authorized permanent cleanup task.

Backend fingerprints, reference checks, active-task protection, partial cleanup and external-source rules remain authoritative. Calibration consumers/targets selected together can leave a retained target as an independent trash record. Re-read trash and preview before retrying; do not clear maps or remove managed files directly. Unknown or stale state fails clearly.

## Project Skill and verification

[The project Skill](../../.agents/skills/astrophotoflow-library/SKILL.md) is versioned in this repository and included in the source distribution with this reference. It uses normal implicit discovery and needs no global installation, profile update or installer framework.

Tests use the tools worktree's private Python environment, synthetic PNG/FITS originals, temporary config/token/SQLite and the real `apf-service` + SDK stdio process. No CUA or full real import is required. See the acceptance evidence below for actual commands and outcomes.


### Acceptance evidence

Implementation base: `bda6047a89da55f50f28cc70db0d366f9bf553e6`; synchronized the exact integrated preview source `b6370979669ceb3bc15d2b58272c33753bb5ed2c` before final protocol verification. Worktree: `C:/Users/Administrator/.codex/worktrees/apf-library-agent-tools/ComfyUI-AstroPhotoFlow`; all generated environments, configs, databases, reports, dependencies and assets remained private to it. The source identity check resolves `astrophotoflow.__file__` inside this worktree. No global profile, active-workspace pointer or MCP registration was changed.

```powershell
.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/backend tests/comfyui/test_proxy.py tests/integration/test_client_operations.py tests/integration/test_cli_mcp_protocol.py tests/workbench tests/packaging -q --basetemp=.artifacts/pytest-tools-full --junitxml=.artifacts/reports/tools-full.xml
.artifacts/venvs/dev/Scripts/python.exe -m pytest tests/integration/test_client_operations.py tests/integration/test_cli_mcp_protocol.py -q --basetemp=.artifacts/pytest-tools-preview-integrated --junitxml=.artifacts/reports/tools-preview-integrated.xml
.artifacts/venvs/dev/Scripts/python.exe C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/astrophotoflow-library
corepack pnpm install --frozen-lockfile
corepack pnpm build
.artifacts/venvs/dev/Scripts/python.exe -m build --sdist --wheel --outdir .artifacts/tools-dist
```

| Check | Result |
|---|---|
| Backend/proxy/client/CLI/real stdio/workbench/package regression before preview synchronization | 202 passed, 1 skipped in 98.58s; existing SQLAlchemy cyclic-FK comparison warning |
| Final synchronized client/CLI/real stdio regression | 16 passed in 41.85s (11 client checks and 5 real-process workflows), including wrong-MIME rejection with request ID and exclusive export preserving original bytes |
| Real stdio workflow | Six equipment kinds, inline/registered setups, frozen presets, bulk upload, automatic FITS Master Dark, configured-root folder import and selected repaired retry, fixed groups/calibration maps/member edits, project references, trash restore and fresh-fingerprint cleanup; terminal cancel/resume errors preserve request IDs |
| Real display preview protocol | Initial DISPLAY_NOT_GENERATED, explicit schedule/poll, available 1080×540 JPEG from a 1600×800 source, native SDK ImageContent, cached reschedule, CLI export of exact cached bytes, actual source-path collision exits 1 and retains all original bytes |
| New structured CLI workflow | Equipment/setup/preset, multi-upload, paged task items, group versions, fixed project dataset references, archival, invalid-body exit status |
| Skill validator | Passed |
| Private frontend typecheck/production assets | Passed; used only to satisfy the existing wheel builder |
| Wheel/sdist build and archive layout | Passed; domain client/CLI/MCP modules in wheel; Skill and reference in sdist; wheel CLI/MCP import exposes 58 tools |
| Source/diff scope | No backend handler or frontend source changes; no new dependencies; whitespace check passed |

The final real-process preview verification uses the synchronized service implementation. Frontend behavior tests are unchanged by this branch and retain the integrated preview branch evidence. No real photo batch, interactive host, or CUA run was performed.

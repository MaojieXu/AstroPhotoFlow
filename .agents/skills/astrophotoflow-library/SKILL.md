---
name: astrophotoflow-library
description: Manage the local AstroPhotoFlow astronomy library through its HTTP-backed MCP tools or apf CLI, including night imports, fixed-version groups, project references, equipment setups, calibration bindings, previews and trash.
---

# AstroPhotoFlow library

Use the connected AstroPhotoFlow MCP server, or the installed `apf` CLI with `ASTROPHOTOFLOW_CONFIG` pointing to the intended workspace's `config.toml`. Both call the same local service. Keep the user's workspace and configuration; this Skill does not register MCP servers or change the active workspace. Use the API rather than SQL or direct managed-file changes.

Read [the operation reference](../../../docs/development/library-agent-tools.md) when choosing commands, request schemas or a complete multi-step operation. The available MCP input schemas are authoritative for arguments. Complex CLI bodies accept `--data '<JSON>'` or `--data '@request.json'` from a UTF-8 file. IDs in examples are placeholders for IDs returned by the service.

## Import a night

For files on the agent's machine, use `import_photos(paths, options)` or `apf import-photos <paths...> --data '@night.json'`. Local uploads use managed storage and the backend creates a logical dataset for multiple photos. `options` can contain `dataset_name`, `capture_preset_id`, `notes`, `classification`, `parameters`, and `create_dataset`.

For files already under a configured service root, call `list_import_roots`, then `browse_import_root(root_id, path, limit, offset, q)`. Submit files or a folder with `import_local(body)`:

```json
{"sources":[{"root_id":"science","path":"2026-10-25/M31"}],"storage_mode":"reference","dataset_name":"M31 night"}
```

CLI: `apf imports local --data '@night.json'`. Paths inside roots are relative POSIX paths. Use `managed` when the user wants originals copied into managed storage; `reference` retains the external source. Group membership and project references do not copy originals.

Omit `classification` for automatic file/preset classification. Each supplied classification key is an explicit whole-batch override; `null` deliberately keeps that key unknown. To classify the whole batch manually, supply both keys, for example `{"frame_class":"subframe","frame_type":"light"}`. Unknown remains unknown; filenames are not evidence. Master Light belongs with light material.

The service combines manual non-null parameter values, observed file values, the accepted frozen preset snapshot, then unknown. Numeric zero is a real manual value. Supply only `capture_preset_id` to use defaults; copying preset values into manual parameters changes their priority. Retries reuse the accepted snapshot, even after the preset changes.

Use `get_import_task(task_id, items_limit, items_offset)` / `apf tasks get` and paginate all relevant items. `report.registration.completed` means registration finished; inspect `content_status`, `metadata_status`, `preview_status`, and asset-version `availability` separately. Do not describe pending originals as ready. `cancel_import_task` cancels eligible active tasks; `resume_import_task` resumes service-interrupted tasks only. For failed or cancelled tasks, use `retry_import_items(task_id, body={"item_ids":[...]})` on selected failed/pending stages after fixing the cause. Preserve returned asset identities. If an item fails with `SOURCE_CHANGED` / version availability `changed`, the source changed after registration: confirm the intended current source and create a new import. Do not blindly retry that item or alter timestamps to bypass the check.

## Organize and edit

Read current records before edits. Pass their current `base_revision`; on a conflict re-read, reconcile the user's intended change, and submit the new revision. Do not blindly retry stale writes. Omitted PATCH fields stay unchanged, explicit `null` clears supported fields, and `0` stays zero.

- Use `update_asset(asset_id, body)` for name, notes, classification and parameters, or `update_asset_parameters(asset_id, base_revision, parameters)` for the existing parameter tool. CLI example: `apf assets parameters ASSET --base-revision 3 --gain 0 --clear exposure_seconds`.
- Use `create_dataset(body={"name":"M31 L","asset_version_ids":[...]})` for a logical ordered group. Read `get_dataset_version` to inspect fixed membership. `publish_dataset_version(dataset_id, body)` takes the complete ordered member-version list and current dataset revision. `update_dataset_members` additionally requires `base_version_id` and each selected asset's revision.
- Use `create_project`, `add_project_asset(project_id, body)` and `add_project_dataset(project_id, body)` to pin fixed versions across nights/filters. Reference add/remove operations use the project's current revision; re-read it between dependent operations. Removing a reference preserves its library original/group.
- Register equipment using `create_equipment(body)` with `kind` camera, telescope, optical_system, filter, mount, or accessory. `create_equipment_setup(body)` accepts registered equipment references and inline equipment snapshots. Inline equipment is not registered automatically; editing a setup does not edit registered equipment.
- Create owned presets with `create_capture_preset(setup_id, body)`; query with `list_capture_presets(equipment_setup_id=...)`. Delete requests for configuration records mean archival: use the applicable update tool with `status:"archived"` and `base_revision`. CLI has explicit `projects/equipment/setups/presets archive` commands.

Reversible edits already requested by the user do not require an extra approval step.

## Bind calibration versions

Find candidates with paged `list_calibration_targets(limit, offset, frame_type, q)` / `apf calibration targets`. A target is a fixed `{"kind":"asset_version"|"dataset_version","id":"..."}`; standalone asset targets are Master calibration material.

Use `publish_dataset_version` for group defaults and member overrides, along with the current dataset revision and complete ordered member list:

```json
{"base_revision":2,"asset_version_ids":["MEMBER_VERSION"],"calibration_defaults":{"dark":{"kind":"asset_version","id":"MASTER_VERSION"}},"member_calibration_overrides":{"MEMBER_VERSION":{"dark":null}}}
```

Providing `calibration_defaults` replaces that map; `{}` clears it. A submitted member's map replaces its old map; an omitted member retains its map. Absent slots inherit; explicit `null` disables that slot for that member. `{}` restores all inheritance for a submitted member. Bindings belong to that dataset version and do not alter other groups. This records relationships; it does not perform calibration or stacking.

## Read a display preview

Call `schedule_display_preview(asset_id, version_id)`, then `get_display_preview_status` until available or a terminal failed/unsupported outcome. Registration alone does not make a preview available. Failed status carries an error; scheduling explicitly retries. `read_display_preview` returns a native MCP image only when explicitly needed. CLI: `apf previews schedule ASSET VERSION`, `apf previews status ASSET VERSION`, then `apf previews export ASSET VERSION preview.jpg`. Display JPEGs are cached at a longest edge of at most 1080 pixels without enlarging small images.

## Trash and permanent cleanup

`remove_library_items(body)` moves current asset/dataset selections to reversible trash. It takes `items` with `entry_type`, `id`, `revision`, and `current_version_id`. Read `list_trash` for current trash identity and partial/failed outcomes. `restore_trash(body)` restores selected records.

Permanent cleanup is allowed only within the user's explicit destructive task. First call `preview_trash_delete(body)` with the current selection fields: `entry_type`, `id`, `removed_at`, `revision`, `current_version_id`, and optional `source_dataset_id`. Inspect its references, tasks, files and bytes. Then call `delete_trash(body)` with that exact selection and the returned `preview_fingerprint`. Do not invent, reuse stale fingerprints, clear binding maps, or delete files directly.

Historical calibration/project/group references protect originals. Unbinding the current version does not remove historical bindings. Cleanup may leave partial/failed records or retain a target while selected consumer containers are cleaned. Re-read trash and generate a fresh preview before any retry; respect external sources and the backend's protection errors. Stop when the requested selections are removed, or report the concrete remaining blocker.

"""Named CLI business commands; complex bodies use the backend request schemas."""
import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.contracts.datasets import DatasetCreate, DatasetMemberParametersUpdate, DatasetMembersCreate, DatasetPatch
from astrophotoflow.contracts.imports import ImportCreate, RetryCreate
from astrophotoflow.contracts.trash import LibraryEntriesRemove, LibraryTrashDelete, LibraryTrashSelection
from astrophotoflow.contracts.projects import ProjectDatasetReferenceCreate, ProjectReferenceCreate, ProjectReferenceDelete
from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentPatch
from astrophotoflow.contracts.projects import ProjectCreate, ProjectPatch
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetPatch, EquipmentSetupCreate, EquipmentSetupPatch
from astrophotoflow.contracts.imports import PhotoImportOptions
from astrophotoflow.contracts.inputs import CanvasDataRequest
from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasGraphRequest


def read_body(value: str, schema):
    text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    return TypeAdapter(schema).validate_python(json.loads(text))


def _command(commands, name, method, *, ids=(), schema=None, page=False, filters=(), archive=None):
    parser = commands.add_parser(name, help=method.replace("_", " "))
    parser.set_defaults(api_method=method, api_ids=ids, api_schema=schema, api_queries=[], api_archive=archive)
    for field in ids:
        parser.add_argument(field)
    if schema is not None:
        parser.add_argument("--data", required=True, help="Request JSON or @UTF-8-file; omitted fields remain omitted")
    if page:
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--offset", type=int, default=0)
        parser.get_default("api_queries").extend(("limit", "offset"))
    for field in filters:
        parser.add_argument("--" + field.replace("_", "-"), default=argparse.SUPPRESS)
        parser.get_default("api_queries").append(field)
    if archive:
        parser.add_argument("--base-revision", type=int, required=True)
        if archive is EquipmentPatch:
            parser.add_argument("--kind", required=True, choices=("camera", "optical_system", "telescope", "filter", "mount", "accessory"))
    return parser


def _group(commands, name):
    return commands.add_parser(name).add_subparsers(dest=name + "_command", required=True)


def register(commands, assets):
    nodes = _group(commands, "nodes")
    _command(nodes, "list", "list_nodes", filters=("query",))
    _command(nodes, "get", "get_node", ids=("definition_id",))
    canvas = _group(commands, "canvas")
    _command(canvas, "get", "get_canvas", ids=("page_id",))
    _command(canvas, "edit", "edit_canvas", schema=CanvasGraphRequest)
    _command(canvas, "pages", "list_canvas_pages")
    _command(canvas, "add-data", "add_canvas_data", schema=CanvasAddRequest)
    _command(canvas, "result", "get_canvas_request", ids=("operation_id",))

    photo = commands.add_parser("import-photos", help="Upload multiple local photos in supplied order")
    photo.add_argument("paths", nargs="+", type=Path)
    photo.add_argument("--data", help="Optional upload metadata JSON or @file (classification, parameters, preset, dataset)")
    photo.set_defaults(api_method="import_photos", api_ids=("paths",), api_queries=[], api_schema=None, api_archive=None, photo_options=True)

    imports = _group(commands, "imports")
    _command(imports, "roots", "list_import_roots")
    browse = _command(imports, "browse", "browse_import_root", ids=("root_id",), page=True, filters=("q",))
    browse.add_argument("--path", default="")
    browse.get_default("api_queries").append("path")
    _command(imports, "local", "import_local", schema=ImportCreate)

    tasks = _group(commands, "tasks")
    _command(tasks, "list", "list_import_tasks", page=True, filters=("status",))
    get = _command(tasks, "get", "get_import_task", ids=("task_id",))
    get.add_argument("--items-limit", type=int, default=50)
    get.add_argument("--items-offset", type=int, default=0)
    get.get_default("api_queries").extend(("items_limit", "items_offset"))
    _command(tasks, "cancel", "cancel_import_task", ids=("task_id",))
    _command(tasks, "resume", "resume_import_task", ids=("task_id",))
    _command(tasks, "retry", "retry_import_items", ids=("task_id",), schema=RetryCreate)

    _command(assets, "patch", "update_asset", ids=("asset_id",), schema=AssetPatch)
    _command(assets, "versions", "list_asset_versions", ids=("asset_id",), page=True)
    _command(assets, "version", "get_asset_version", ids=("asset_id", "version_id"))
    library = _group(commands, "library")
    _command(library, "canvas-data", "prepare_canvas_data", schema=CanvasDataRequest)
    _command(library, "list", "list_library_items", page=True,
             filters=("q", "frame_type", "frame_class", "role", "sort_by", "order"))
    _command(library, "remove", "remove_library_items", schema=LibraryEntriesRemove)

    datasets = _group(commands, "datasets")
    _command(datasets, "list", "list_datasets", page=True, filters=("q", "status", "sort_by", "order"))
    _command(datasets, "create", "create_dataset", schema=DatasetCreate)
    _command(datasets, "get", "get_dataset", ids=("dataset_id",))
    _command(datasets, "patch", "update_dataset", ids=("dataset_id",), schema=DatasetPatch)
    _command(datasets, "archive", "update_dataset", ids=("dataset_id",), archive=DatasetPatch)
    _command(datasets, "versions", "list_dataset_versions", ids=("dataset_id",), page=True)
    _command(datasets, "version", "get_dataset_version", ids=("dataset_id", "version_id"))
    _command(datasets, "publish", "publish_dataset_version", ids=("dataset_id",), schema=DatasetMembersCreate)
    _command(datasets, "member-parameters", "update_dataset_members", ids=("dataset_id",), schema=DatasetMemberParametersUpdate)

    projects = _group(commands, "projects")
    _command(projects, "list", "list_projects", page=True, filters=("q", "status", "sort_by", "order"))
    _command(projects, "create", "create_project", schema=ProjectCreate)
    _command(projects, "get", "get_project", ids=("project_id",))
    _command(projects, "patch", "update_project", ids=("project_id",), schema=ProjectPatch)
    _command(projects, "archive", "update_project", ids=("project_id",), archive=ProjectPatch)
    _command(projects, "assets", "list_project_assets", ids=("project_id",), page=True)
    _command(projects, "asset", "get_project_asset", ids=("project_id", "reference_id"))
    _command(projects, "add-asset", "add_project_asset", ids=("project_id",), schema=ProjectReferenceCreate)
    _command(projects, "remove-asset", "remove_project_asset", ids=("project_id", "reference_id"), schema=ProjectReferenceDelete)
    _command(projects, "datasets", "list_project_datasets", ids=("project_id",), page=True)
    _command(projects, "dataset", "get_project_dataset", ids=("project_id", "reference_id"))
    _command(projects, "add-dataset", "add_project_dataset", ids=("project_id",), schema=ProjectDatasetReferenceCreate)
    _command(projects, "remove-dataset", "remove_project_dataset", ids=("project_id", "reference_id"), schema=ProjectReferenceDelete)

    equipment = _group(commands, "equipment")
    _command(equipment, "list", "list_equipment", page=True, filters=("q", "status", "kind", "sort_by", "order"))
    _command(equipment, "create", "create_equipment", schema=EquipmentCreate)
    _command(equipment, "get", "get_equipment", ids=("equipment_id",))
    _command(equipment, "patch", "update_equipment", ids=("equipment_id",), schema=EquipmentPatch)
    _command(equipment, "archive", "update_equipment", ids=("equipment_id",), archive=EquipmentPatch)

    setups = _group(commands, "setups")
    _command(setups, "list", "list_equipment_setups", page=True, filters=("q", "status", "sort_by", "order"))
    _command(setups, "create", "create_equipment_setup", schema=EquipmentSetupCreate)
    _command(setups, "get", "get_equipment_setup", ids=("setup_id",))
    _command(setups, "patch", "update_equipment_setup", ids=("setup_id",), schema=EquipmentSetupPatch)
    _command(setups, "archive", "update_equipment_setup", ids=("setup_id",), archive=EquipmentSetupPatch)

    presets = _group(commands, "presets")
    _command(presets, "list", "list_capture_presets", page=True, filters=("q", "status", "equipment_setup_id", "sort_by", "order"))
    _command(presets, "create", "create_capture_preset", ids=("setup_id",), schema=CapturePresetCreate)
    _command(presets, "get", "get_capture_preset", ids=("preset_id",))
    _command(presets, "patch", "update_capture_preset", ids=("preset_id",), schema=CapturePresetPatch)
    _command(presets, "archive", "update_capture_preset", ids=("preset_id",), archive=CapturePresetPatch)

    previews = _group(commands, "previews")
    _command(previews, "schedule", "schedule_display_preview", ids=("asset_id", "version_id"))
    _command(previews, "status", "get_display_preview_status", ids=("asset_id", "version_id"))
    _command(previews, "export", "export_display_preview", ids=("asset_id", "version_id", "output"))

    calibration = _group(commands, "calibration")
    _command(calibration, "targets", "list_calibration_targets", page=True, filters=("q", "frame_type"))
    trash = _group(commands, "trash")
    _command(trash, "list", "list_trash", page=True, filters=("group_id",))
    _command(trash, "restore", "restore_trash", schema=LibraryTrashSelection)
    _command(trash, "delete-preview", "preview_trash_delete", schema=LibraryTrashSelection)
    _command(trash, "delete", "delete_trash", schema=LibraryTrashDelete)


def run(client, args):
    kwargs = {field: getattr(args, field) for field in args.api_ids}
    kwargs.update({field: getattr(args, field) for field in args.api_queries if hasattr(args, field)})
    if args.api_schema is not None:
        kwargs["body"] = read_body(args.data, args.api_schema)
    if args.api_archive:
        body = {"base_revision": args.base_revision, "status": "archived"}
        if args.api_archive is EquipmentPatch:
            body["kind"] = args.kind
        kwargs["body"] = TypeAdapter(args.api_archive).validate_python(body)
    if getattr(args, "photo_options", False) and args.data is not None:
        kwargs["options"] = read_body(args.data, PhotoImportOptions)
    if args.api_method == "export_display_preview":
        kwargs["output"] = Path(kwargs["output"])
    return getattr(client, args.api_method)(**kwargs)

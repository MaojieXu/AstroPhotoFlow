from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.models import Asset, AssetTask, AssetTaskItem, AssetVersion, Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.ingestion import _publish_dataset
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.config import Settings


AUTH = {"Authorization": "Bearer calibration-test"}


@pytest.fixture
def service(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    app = create_app(settings, "calibration-test")
    with TestClient(app) as client:
        yield client, app.state.database, settings
    app.state.database.close()


def photo(service, frame_type, master=False, *, version_type=None, scope="shared", project_id=None):
    _, database, settings = service
    asset_id, version_id = str(uuid4()), str(uuid4())
    path = settings.data_dir / "objects" / version_id / "source.fits"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic calibration input")
    classification = {"frame_class": "masterframe" if master else "subframe", "frame_type": frame_type}
    with database.write_session() as session:
        asset = Asset(id=asset_id, name=f"{frame_type}-{version_id[:4]}", scope=scope, owner_project_id=project_id,
                      role="calibration" if frame_type in {"bias", "dark", "flat", "dark_flat"} else "raw", classification=classification)
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
            storage_location=path.relative_to(settings.data_dir).as_posix(), availability="available",
            frame_type=frame_type if version_type is None else version_type,
            calibration_level="master" if master else "individual", capture_snapshot={"original": True}))
        session.flush()
        asset.current_version_id = version_id
    return asset_id, version_id, path


def group(client, name, ids, notes=None):
    response = client.post("/api/v1/datasets", headers=AUTH, json={"name": name, "asset_version_ids": ids, "notes": notes})
    assert response.status_code == 201, response.text
    return response.json()


def version(client, dataset):
    return client.get(f"/api/v1/datasets/{dataset['id']}/versions/{dataset['current_version_id']}", headers=AUTH).json()


def publish(client, dataset, ids, **changes):
    return client.post(f"/api/v1/datasets/{dataset['id']}/versions", headers=AUTH,
                       json={"base_revision": dataset["revision"], "asset_version_ids": ids, **changes})


def selection(client, entries):
    existing = client.get("/api/v1/library/trash", headers=AUTH).json()["items"]
    keys = {(row["entry_type"], row["id"]) for row in existing}
    missing = [entry for entry in entries if (entry["entry_type"], entry["id"]) not in keys]
    if missing:
        assert client.request("DELETE", "/api/v1/library/items", headers=AUTH, json={"items": missing}).status_code == 200
    rows = client.get("/api/v1/library/trash", headers=AUTH).json()["items"]
    return [{key: next(row for row in rows if row["entry_type"] == entry["entry_type"] and row["id"] == entry["id"])[key]
             for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")} for entry in entries]


def clean(client, items):
    preview = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json={"items": items})
    assert preview.status_code == 200, preview.text
    return preview.json(), client.post("/api/v1/library/trash/delete", headers=AUTH,
        json={"items": items, "preview_fingerprint": preview.json()["preview_fingerprint"]})


def test_explicit_groups_share_versions_and_preserve_mixed_original_and_notes(service):
    client, database, _ = service
    _, light, _ = photo(service, "light", True)
    _, dark, path = photo(service, "dark")
    original = group(client, "mixed import", [light, dark])
    first = group(client, "cold night calibration", [dark], "-10 C / gain 0")
    second = group(client, "another logical scene", [dark])
    assert first["notes"] == "-10 C / gain 0" and first["revision"] == 1
    assert [row["asset_version_id"] for row in version(client, original)["members"]] == [light, dark]
    assert version(client, first)["members"][0]["asset_version_id"] == version(client, second)["members"][0]["asset_version_id"] == dark
    with database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 2
        assert session.scalar(select(func.count()).select_from(AssetVersion)) == 2
    assert path.read_bytes() == b"synthetic calibration input"
    targets = client.get("/api/v1/calibration/targets", headers=AUTH).json()["items"]
    assert {item["name"] for item in targets} == {first["name"], second["name"]}
    light_items = client.get("/api/v1/library/items", headers=AUTH, params={"frame_type": "light"}).json()["items"]
    mixed = next(item for item in light_items if item["dataset"]["id"] == original["id"])
    assert len(mixed["version"]["members"]) == 2
    assert mixed["matching_member_count"] == 1


def test_binding_versions_inherit_none_override_and_cross_group_isolation(service):
    client, _, _ = service
    _, light, _ = photo(service, "light")
    _, light2, _ = photo(service, "light", True)
    _, master, _ = photo(service, "dark", True)
    _, bias, _ = photo(service, "bias")
    bias_group = group(client, "bias inputs", [bias])
    consumer = group(client, "light night", [light, light2])
    other = group(client, "same photos other scene", [light])
    old_version = version(client, consumer)
    project = client.post("/api/v1/projects", headers=AUTH, json={"name": "fixed project"}).json()
    ref = client.post(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH, json={
        "base_revision": 1, "dataset_id": consumer["id"], "dataset_version_id": old_version["id"],
    }).json()
    defaults = {"dark": {"kind": "asset_version", "id": master}, "bias": {"kind": "dataset_version", "id": bias_group["current_version_id"]}}
    overrides = {light: {"dark": None}, light2: {"flat": None, "dark": {"kind": "asset_version", "id": master}}}
    saved = publish(client, consumer, [light, light2], calibration_defaults=defaults, member_calibration_overrides=overrides)
    assert saved.status_code == 201, saved.text
    current = saved.json()
    assert current["id"] != old_version["id"] and current["calibration_defaults"] == defaults
    assert current["members"][0]["calibration_overrides"] == {"dark": None}
    assert "bias" not in current["members"][0]["calibration_overrides"]
    assert version(client, other)["members"][0]["calibration_overrides"] == {}
    pinned = client.get(f"/api/v1/projects/{project['id']}/dataset-references/{ref['id']}", headers=AUTH).json()
    assert pinned["version"]["id"] == old_version["id"] and pinned["version"]["calibration_defaults"] == {}
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    same = publish(client, consumer, [light, light2], calibration_defaults=defaults, member_calibration_overrides=overrides).json()
    assert same["id"] == current["id"]
    inherited = publish(client, consumer, [light, light2], member_calibration_overrides={light: {}}).json()
    assert inherited["members"][0]["calibration_overrides"] == {} and inherited["calibration_defaults"] == defaults
    stale = publish(client, consumer, [light, light2], calibration_defaults={})
    assert stale.status_code == 409


def test_manual_current_correction_is_bindable_and_carried_binding_is_not_revalidated(service):
    client, database, _ = service
    master_id, master_version, _ = photo(service, None)
    _, light, _ = photo(service, "light")
    _, added, _ = photo(service, "light")
    consumer = group(client, "corrected scene", [light])
    corrected = client.patch(f"/api/v1/library/assets/{master_id}", headers=AUTH, json={
        "base_revision": 1, "classification": {"frame_class": "masterframe", "frame_type": "dark"},
    })
    assert corrected.status_code == 200
    assert corrected.json()["current_version_id"] == master_version
    with database.read_session() as session:
        assert session.get(AssetVersion, master_version).frame_type is None
    target = {"kind": "asset_version", "id": master_version}
    assert publish(client, consumer, [light], calibration_defaults={"dark": target}).status_code == 201
    assert client.patch(f"/api/v1/library/assets/{master_id}", headers=AUTH, json={
        "base_revision": 2, "classification": {"frame_type": "light"},
    }).status_code == 200
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    carried = publish(client, consumer, [light, added], calibration_defaults={"dark": target})
    assert carried.status_code == 201 and carried.json()["calibration_defaults"] == {"dark": target}
    other = group(client, "new consumer", [light])
    assert publish(client, other, [light], calibration_defaults={"dark": target}).status_code == 422


def test_target_scope_type_historical_versions_and_sparse_validation(service):
    client, database, _ = service
    asset_id, old, _ = photo(service, "dark", True)
    _, light, _ = photo(service, "light", True)
    consumer = group(client, "light inputs", [light])
    newer = str(uuid4())
    with database.write_session() as session:
        session.add(AssetVersion(id=newer, asset_id=asset_id, version_number=2, storage_mode="reference", storage_location="newer", frame_type="light"))
        session.flush()
        session.get(Asset, asset_id).current_version_id = newer
        session.get(Asset, asset_id).classification = {"frame_class": "masterframe", "frame_type": "light"}
    assert publish(client, consumer, [light], calibration_defaults={"dark": {"kind": "asset_version", "id": old}}).status_code == 201
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    assert publish(client, consumer, [light], calibration_defaults={"dark": {"kind": "asset_version", "id": newer}}).status_code == 422
    assert publish(client, consumer, [light], member_calibration_overrides={str(uuid4()): {"dark": None}}).status_code == 422
    assert publish(client, consumer, [light], calibration_defaults=None).status_code == 422
    project = client.post("/api/v1/projects", headers=AUTH, json={"name": "private"}).json()
    _, private, _ = photo(service, "dark", True, scope="project", project_id=project["id"])
    assert publish(client, consumer, [light], calibration_defaults={"dark": {"kind": "asset_version", "id": private}}).status_code == 422


def test_surviving_default_and_member_bindings_protect_targets_before_unlink(service):
    client, _, _ = service
    _, light, _ = photo(service, "light")
    target_id, target, path = photo(service, "dark", True)
    consumer = group(client, "protected consumer", [light])
    assert publish(client, consumer, [light], member_calibration_overrides={light: {"dark": {"kind": "asset_version", "id": target}}}).status_code == 201
    entry = {"entry_type": "asset", "id": target_id, "revision": 1, "current_version_id": target}
    items = selection(client, [entry])
    preview, deleted = clean(client, items)
    assert any(ref["kind"] == "calibration" for ref in preview["references"])
    assert deleted.status_code == 409 and deleted.json()["error"]["code"] == "CALIBRATION_IN_USE"
    assert path.is_file()
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    # A new version with no override leaves the pinned historical consumer version intact.
    assert publish(client, consumer, [light], member_calibration_overrides={light: {}}).status_code == 201
    next_preview, rejected = clean(client, items)
    assert rejected.status_code == 409 and next_preview["references"] == preview["references"]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("overlap", [False, True])
def test_selected_consumer_and_target_retention_can_complete_on_retry(service, reverse, overlap):
    client, database, _ = service
    _, light, _ = photo(service, "light")
    target_id, target, target_path = photo(service, "dark", True)
    ids = [light, target] if overlap else [light]
    consumer = group(client, "selected consumer", ids)
    bound = publish(client, consumer, ids, calibration_defaults={"dark": {"kind": "asset_version", "id": target}})
    assert bound.status_code == 201
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    entries = [{"entry_type": "dataset", "id": consumer["id"], "revision": consumer["revision"], "current_version_id": consumer["current_version_id"]},
               {"entry_type": "asset", "id": target_id, "revision": 1, "current_version_id": target}]
    if reverse:
        entries.reverse()
    preview, first = clean(client, selection(client, entries))
    assert first.status_code == 200, first.text
    assert not any(ref["kind"] == "calibration" for ref in preview["references"])
    with database.read_session() as session:
        assert session.get(Dataset, consumer["id"]) is None
        assert session.get(AssetVersion, target) is not None
    assert target_path.is_file()
    retry = selection(client, [entries[0] if entries[0]["entry_type"] == "asset" else entries[1]])
    _, second = clean(client, retry)
    assert second.status_code == 200 and second.json()["deleted_count"] == 1
    assert not target_path.exists()


def test_consumer_file_failure_retains_target_until_consumer_can_finish(service, monkeypatch):
    client, database, _ = service
    _, light, light_path = photo(service, "light")
    target_id, target, path = photo(service, "dark", True)
    consumer = group(client, "locked consumer", [light, target])
    assert publish(client, consumer, [light, target], calibration_defaults={"dark": {"kind": "asset_version", "id": target}}).status_code == 201
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    entries = [{"entry_type": "dataset", "id": consumer["id"], "revision": consumer["revision"], "current_version_id": consumer["current_version_id"]},
               {"entry_type": "asset", "id": target_id, "revision": 1, "current_version_id": target}]
    original = Path.unlink
    def locked(selected_path, *args, **kwargs):
        if selected_path == light_path:
            raise PermissionError("controlled consumer file lock")
        return original(selected_path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", locked)
    _, first = clean(client, selection(client, entries))
    assert first.status_code == 200 and first.json()["failed"]
    with database.read_session() as session:
        assert session.get(Dataset, consumer["id"]) is not None
        assert session.get(AssetVersion, target) is not None
    assert path.is_file()
    monkeypatch.setattr(Path, "unlink", original)
    _, resumed = clean(client, selection(client, entries))
    assert resumed.status_code == 200
    with database.read_session() as session:
        assert session.get(Dataset, consumer["id"]) is None
    target_entry = next(entry for entry in entries if entry["entry_type"] == "asset")
    assert clean(client, selection(client, [target_entry]))[1].json()["deleted_count"] == 1


@pytest.mark.parametrize("frame_type", ["bias", "dark", "flat", "dark_flat"])
def test_all_calibration_types_accept_fixed_master_and_group_targets(service, frame_type):
    client, _, _ = service
    _, light, _ = photo(service, "light")
    _, raw, _ = photo(service, frame_type)
    _, master, _ = photo(service, frame_type, True)
    target_group = group(client, frame_type + " raw group", [raw])
    consumer = group(client, "light", [light])
    body = {frame_type: {"kind": "dataset_version", "id": target_group["current_version_id"]}}
    assert publish(client, consumer, [light], calibration_defaults=body,
                   member_calibration_overrides={light: {frame_type: {"kind": "asset_version", "id": master}}}).status_code == 201
    options = client.get("/api/v1/calibration/targets", headers=AUTH, params={"frame_type": frame_type}).json()["items"]
    assert {item["target"]["id"] for item in options} == {master, target_group["current_version_id"]}


@pytest.mark.parametrize("reverse", [False, True])
def test_selected_dataset_target_and_consumer_finish_without_deadlock(service, reverse):
    client, database, _ = service
    _, light, _ = photo(service, "light")
    _, raw, target_path = photo(service, "flat")
    target_group = group(client, "flat inputs", [raw])
    consumer = group(client, "light consumer", [light])
    assert publish(client, consumer, [light], calibration_defaults={"flat": {"kind": "dataset_version", "id": target_group["current_version_id"]}}).status_code == 201
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    target_entry = {"entry_type": "dataset", "id": target_group["id"], "revision": target_group["revision"], "current_version_id": target_group["current_version_id"]}
    target_only = selection(client, [target_entry])
    protected_preview, protected = clean(client, target_only)
    assert protected.status_code == 409 and target_path.is_file()
    assert any(ref["kind"] == "calibration" for ref in protected_preview["references"])
    entries = [target_entry, {"entry_type": "dataset", "id": consumer["id"], "revision": consumer["revision"], "current_version_id": consumer["current_version_id"]}]
    if reverse:
        entries.reverse()
    assert clean(client, selection(client, entries))[1].status_code == 200
    remaining = client.get("/api/v1/library/trash", headers=AUTH).json()["items"]
    retry = [{key: row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")} for row in remaining]
    if retry:
        resumed = clean(client, retry)[1]
        assert resumed.status_code == 200, resumed.text
        # A retained target photo can become independent after its selected container disappears.
        remaining = client.get("/api/v1/library/trash", headers=AUTH).json()["items"]
        if remaining:
            retry = [{key: row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")} for row in remaining]
            assert clean(client, retry)[1].status_code == 200
    with database.read_session() as session:
        assert session.get(Dataset, consumer["id"]) is None
        assert session.get(DatasetVersion, target_group["current_version_id"]) is None
    assert not target_path.exists()


def test_new_calibration_reference_changes_preview_and_blocks_stale_unlink(service):
    client, _, _ = service
    _, light, _ = photo(service, "light")
    asset_id, target, path = photo(service, "dark", True)
    consumer = group(client, "new external consumer", [light])
    items = selection(client, [{"entry_type": "asset", "id": asset_id, "revision": 1, "current_version_id": target}])
    initial = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json={"items": items}).json()
    assert publish(client, consumer, [light], calibration_defaults={"dark": {"kind": "asset_version", "id": target}}).status_code == 201
    current = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json={"items": items}).json()
    assert current["preview_fingerprint"] != initial["preview_fingerprint"]
    stale = client.post("/api/v1/library/trash/delete", headers=AUTH, json={"items": items, "preview_fingerprint": initial["preview_fingerprint"]})
    assert stale.status_code == 409 and path.is_file()


def test_selected_protected_target_retains_shared_managed_path_until_retry(service):
    client, database, settings = service
    _, light, _ = photo(service, "light")
    target_id, target, path = photo(service, "dark", True)
    with database.write_session() as session:
        session.get(AssetVersion, light).storage_location = path.relative_to(settings.data_dir).as_posix()
    consumer = group(client, "shared path consumer", [light, target])
    assert publish(client, consumer, [light, target], calibration_defaults={"dark": {"kind": "asset_version", "id": target}}).status_code == 201
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    entries = [{"entry_type": "dataset", "id": consumer["id"], "revision": consumer["revision"], "current_version_id": consumer["current_version_id"]},
               {"entry_type": "asset", "id": target_id, "revision": 1, "current_version_id": target}]
    first = clean(client, selection(client, entries))[1]
    assert first.status_code == 200 and first.json()["deleted_file_count"] == 0
    assert path.read_bytes() == b"synthetic calibration input"
    with database.read_session() as session:
        assert session.get(Dataset, consumer["id"]) is None
    remaining = client.get("/api/v1/library/trash", headers=AUTH).json()["items"]
    retry = [{key: row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")} for row in remaining]
    resumed = clean(client, retry)[1]
    assert resumed.json()["deleted_file_count"] == 1, resumed.text
    assert not path.exists()


def test_import_append_copies_group_defaults_and_member_override(service):
    client, database, _ = service
    _, light, _ = photo(service, "light")
    added_asset, added, _ = photo(service, "light")
    _, target, _ = photo(service, "dark", True)
    consumer = group(client, "append scene", [light])
    defaults = {"dark": {"kind": "asset_version", "id": target}}
    assert publish(client, consumer, [light], calibration_defaults=defaults, member_calibration_overrides={light: {"dark": None}}).status_code == 201
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    task_id = str(uuid4())
    with database.write_session() as session:
        session.add(AssetTask(id=task_id, status="running", sources=[], storage_mode="reference", classification={}, parameters={},
            target_dataset_id=consumer["id"], dataset_base_revision=consumer["revision"], enumeration_completed=True, report={}))
        session.flush()
        session.add(AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), root_id="test", source_path="added.fit",
            source_identity="append-added", position=0, status="completed", content_status="available", metadata_status="available", preview_status="available",
            asset_id=added_asset, asset_version_id=added))
    assert _publish_dataset(database, {"target_dataset_id": consumer["id"]}, task_id)
    current = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    appended = version(client, current)
    assert appended["calibration_defaults"] == defaults
    assert [member["calibration_overrides"] for member in appended["members"]] == [{"dark": None}, {}]

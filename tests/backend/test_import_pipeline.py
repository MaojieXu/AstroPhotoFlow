from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import Event, Lock, Thread
import time
from uuid import uuid4

import blake3
import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from astrophotoflow.backend import ingestion
from astrophotoflow.backend.api import create_app
from astrophotoflow.backend.models import Asset, AssetTask, AssetTaskItem, AssetVersion, CapturePreset, DatasetVersion, EquipmentSetup, Preview
from astrophotoflow.backend.schema import database_lock, upgrade_database
from astrophotoflow.config import ImportRoot, Settings

AUTH = {"Authorization": "Bearer import-pipeline-test"}


def image(path, label="Light Frame", offset=0, **headers):
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.PrimaryHDU(np.arange(120, dtype=np.float32).reshape(10, 12) + offset)
    if label is not None:
        hdu.header["IMAGETYP"] = label
    for key, value in headers.items():
        hdu.header[key] = value
    hdu.writeto(path)
    return path.read_bytes()


@pytest.fixture
def service(tmp_path, request):
    root = tmp_path / "science"
    root.mkdir()
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", ("http://127.0.0.1:8188",),
                        (ImportRoot("science", root),), **getattr(request, "param", {}))
    with database_lock(settings):
        upgrade_database(settings)
    app = create_app(settings, "import-pipeline-test")
    with TestClient(app) as client:
        yield settings, app, client, root
    assert all(executor._shutdown for executor in app.state.import_workers)
    app.state.database.close()


def enqueue(app, paths=None, **changes):
    task_id = str(uuid4())
    values = dict(id=task_id, status="queued", sources=[
        {"root_id": "science", "path": path, "enumeration_completed": False, "kind": "file"}
        for path in (paths or [""])], storage_mode="managed", classification={}, parameters={},
        notes=None, dataset_name="pending group", target_dataset_id=str(uuid4()), dataset_base_revision=None,
        dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None)
    values.update(changes)
    with app.state.database.write_session() as session:
        session.add(AssetTask(**values))
    return task_id


def run(app, settings, task_id):
    thread = Thread(target=ingestion.process_task, args=(app.state.database, settings, task_id, app.state.import_workers))
    thread.start()
    return thread


def task(client, task_id):
    return client.get(f"/api/v1/asset-tasks/{task_id}", headers=AUTH).json()


def test_registration_publishes_pending_members_and_keeps_trash_protected(service, monkeypatch):
    settings, app, client, root = service
    original_bytes = [image(root / f"{i}.fits", GAIN=9) for i in range(2)]
    entered, release = Event(), Event()
    read = ingestion._read_hash_and_copy
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return read(*args)
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", blocked)
    task_id = enqueue(app)
    thread = run(app, settings, task_id)
    try:
        assert entered.wait(5)
        current = task(client, task_id)
        assert current["report"]["registration"] == {"total": 2, "registered": 2, "completed": True}
        assert current["status"] == "running"
        assert current["items_completed"] == 0
        entry = client.get("/api/v1/library/items", headers=AUTH).json()["items"][0]
        assert entry["entry_type"] == "dataset"
        members = entry["version"]["members"]
        assert len(members) == 2
        assert all(member["version"]["availability"] == "unknown" for member in members)
        assert all(member["version"]["content_hash"] is None for member in members)
        first = members[0]
        assert client.get(f"/api/v1/library/assets/{first['asset']['id']}/versions/{first['version']['id']}/previews/thumbnail", headers=AUTH).status_code == 404
        assert client.patch(f"/api/v1/library/assets/{first['asset']['id']}", headers=AUTH,
                            json={"base_revision": 1, "parameters": {"gain": None, "offset": 0}}).status_code == 200
        dataset = entry["dataset"]
        removed = client.request("DELETE", "/api/v1/library/items", headers=AUTH, json={"items": [{
            "entry_type": "dataset", "id": dataset["id"], "revision": dataset["revision"],
            "current_version_id": dataset["current_version_id"]}]})
        assert removed.status_code == 200
        trash = client.get("/api/v1/library/trash", headers=AUTH).json()["items"][0]
        selection = {"items": [{key: trash[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
        preview = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json=selection).json()
        assert preview["tasks"] == [task_id]
        deletion = client.post("/api/v1/library/trash/delete", headers=AUTH,
                               json={**selection, "preview_fingerprint": preview["preview_fingerprint"]})
        assert deletion.status_code == 409
        assert deletion.json()["error"]["code"] == "IMPORT_ACTIVE"
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert task(client, task_id)["status"] == "completed"
    updated = client.get(f"/api/v1/library/assets/{first['asset']['id']}", headers=AUTH).json()
    assert updated["parameters"]["gain"] is None
    assert updated["parameters"]["offset"] == 0
    assert updated["current_version"]["capture_snapshot"]["gain"] == 9
    assert [path.read_bytes() for path in sorted(root.glob("*.fits"))] == original_bytes
    with app.state.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 1


@pytest.mark.parametrize("label,expected", [
    ("Light Frame", {"frame_class": "subframe", "frame_type": "light"}),
    ("MASTER DARK", {"frame_class": "masterframe", "frame_type": "dark"}),
    ("Dark Flat Frame", {"frame_class": "subframe", "frame_type": "dark_flat"}),
    ("dark", {"frame_class": None, "frame_type": "dark"}),
    (None, {"frame_class": None, "frame_type": None}),
    ("something else", {"frame_class": None, "frame_type": None}),
])
def test_header_classification_and_missing_fields(service, label, expected):
    _, _, client, root = service
    image(root / "Master_Light_filename_is_not_evidence.fits", label)
    accepted = client.post("/api/v1/imports", headers=AUTH, json={"sources": [{"root_id": "science", "path": ""}], "storage_mode": "reference"})
    current = task(client, accepted.json()["task_id"])
    asset = client.get(f"/api/v1/library/assets/{current['items'][0]['asset_id']}", headers=AUTH).json()
    assert asset["classification"] == expected
    for key, value in expected.items():
        assert asset["value_sources"][f"classification.{key}"] == ("unknown" if value is None else "file")
    if expected["frame_class"] is None:
        assert asset["current_version"]["calibration_level"] is None


def test_mixed_batch_manual_override_and_frozen_preset_priority(service):
    settings, app, client, root = service
    image(root / "a.fits", "Light Frame", EXPTIME=11, GAIN=9, BAYERPAT="RGGB")
    image(root / "b.fits", "Master Dark", EXPTIME=12, GAIN=8)
    setup_id, preset_id = str(uuid4()), str(uuid4())
    with app.state.database.write_session() as session:
        session.add(EquipmentSetup(id=setup_id, name="Setup", components=[]))
        session.flush()
        session.add(CapturePreset(id=preset_id, equipment_setup_id=setup_id, name="Preset", parameters={
            "gain": 50, "offset": 7, "exposure_seconds": 30, "cfa_pattern": "MONO"},
            classification={"frame_class": "masterframe", "frame_type": "flat"}))
    # Freeze defaults at acceptance, then edit the live preset before processing.
    import astrophotoflow.backend.imports as routes
    process = routes.process_task
    captured = []
    routes.process_task = lambda *args: captured.append(args)
    try:
        accepted = client.post("/api/v1/imports", headers=AUTH, json={
            "sources": [{"root_id": "science", "path": ""}], "storage_mode": "reference",
            "capture_preset_id": preset_id, "parameters": {"gain": 0}})
    finally:
        routes.process_task = process
    task_id = accepted.json()["task_id"]
    with app.state.database.write_session() as session:
        session.get(CapturePreset, preset_id).parameters = {"offset": 99}
    process(*captured[0])
    current = task(client, task_id)
    assets = [client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json() for item in current["items"]]
    assert [asset["classification"]["frame_type"] for asset in assets] == ["light", "dark"]
    assert assets[0]["parameters"]["gain"] == 0
    assert assets[0]["parameters"]["offset"] == 7
    assert assets[0]["parameters"]["exposure_seconds"] == 11
    assert assets[0]["parameters"]["cfa_pattern"] == "RGGB"
    assert assets[0]["value_sources"]["gain"] == "manual"
    assert assets[0]["value_sources"]["offset"] == "preset"
    assert assets[0]["value_sources"]["exposure_seconds"] == "file"
    assert assets[0]["value_sources"]["iso"] == "unknown"
    provenance = assets[0]["current_version"]["capture_snapshot"]["import_provenance"]
    assert provenance["defaults_snapshot"]["parameters"]["offset"] == 7
    assert provenance["defaults_snapshot"]["equipment_setup"]["id"] == setup_id
    before = deepcopy(assets[0]["current_version"]["capture_snapshot"])
    edited = client.patch(f"/api/v1/library/assets/{assets[0]['id']}", headers=AUTH,
                          json={"base_revision": 1, "parameters": {"gain": None}}).json()
    assert edited["current_version"]["capture_snapshot"] == before
    manual = client.post("/api/v1/imports", headers=AUTH, json={"sources": [{"root_id": "science", "path": ""}],
        "storage_mode": "reference", "capture_preset_id": preset_id,
        "classification": {"frame_class": "masterframe", "frame_type": None}})
    overridden = task(client, manual.json()["task_id"])
    for item in overridden["items"]:
        asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
        assert asset["classification"] == {"frame_class": "masterframe", "frame_type": None}
        assert asset["value_sources"]["classification.frame_type"] == "manual"


def test_service_worker_limits_are_shared_between_tasks(service, monkeypatch):
    settings, app, client, root = service
    for group in ("one", "two"):
        for i in range(3):
            image(root / group / f"{i}.fits")
    counters = {"file": 0, "preview": 0}
    peaks = {"file": 0, "preview": 0}
    lock = Lock()
    def measured(kind, original):
        def wrapped(*args, **kwargs):
            with lock:
                counters[kind] += 1
                peaks[kind] = max(peaks[kind], counters[kind])
            try:
                time.sleep(.03)
                return original(*args, **kwargs)
            finally:
                with lock:
                    counters[kind] -= 1
        return wrapped
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", measured("file", ingestion._read_hash_and_copy))
    monkeypatch.setattr(ingestion, "_fit_preview_rows", measured("preview", ingestion._fit_preview_rows))
    ids = [enqueue(app, [group]) for group in ("one", "two")]
    threads = [run(app, settings, task_id) for task_id in ids]
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert peaks == {"file": 2, "preview": 1}
    assert all(task(client, task_id)["status"] == "completed" for task_id in ids)


@pytest.mark.parametrize("service", [{"preview_workers": 2}], indirect=True)
def test_stretch_uses_position_not_content_completion_and_survives_resume(service, monkeypatch):
    settings, app, client, root = service
    for name, offset, filter_name in (("a", 0, "L"), ("b", 1000, "L"), ("c", 0, "Ha"), ("d", 2000, "Ha")):
        image(root / f"{name}.fits", offset=offset, FILTER=filter_name)
    with fits.open(root / "c.fits", mode="update") as hdus:
        hdus[0].data[:] = np.nan
    completed = []
    read = ingestion._read_hash_and_copy
    def out_of_order(path, *args):
        if path.name == "a.fits":
            time.sleep(.12)
        result = read(path, *args)
        completed.append(path.name)
        return result
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", out_of_order)
    task_id = enqueue(app)
    ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    current = task(client, task_id)
    assert completed.index("b.fits") < completed.index("a.fits")
    items = {Path(row["source_path"]).stem: row for row in current["items"]}
    with app.state.database.read_session() as session:
        displays = {name: session.scalar(select(Preview).where(Preview.asset_version_id == items[name]["asset_version_id"])).display_parameters for name in ("a", "b", "d")}
    assert displays["b"]["stretch_reference_version_id"] == items["a"]["asset_version_id"]
    assert displays["d"]["stretch_reference_version_id"] == items["d"]["asset_version_id"]
    assert items["c"]["preview_status"] == "failed"
    with app.state.database.write_session() as session:
        preview = session.scalar(select(Preview).where(Preview.asset_version_id == items["b"]["asset_version_id"]))
        session.delete(preview)
        session.get(AssetTaskItem, items["b"]["id"]).status = "running"
        session.get(AssetTask, task_id).status = "running"
    ingestion.mark_interrupted_tasks(app.state.database)
    assert client.post(f"/api/v1/asset-tasks/{task_id}/resume", headers=AUTH, json={}).status_code == 202
    with app.state.database.read_session() as session:
        regenerated = session.scalar(select(Preview).where(Preview.asset_version_id == items["b"]["asset_version_id"]))
        assert regenerated.display_parameters == displays["b"]
        assert session.scalar(select(func.count()).select_from(Asset)) == 4
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 1


def test_upload_renames_without_second_write_and_recovers_identity_after_rename_failure(service, monkeypatch):
    settings, app, client, root = service
    data = image(root / "upload.fits")
    created = client.post("/api/v1/uploads", headers=AUTH, json={"files": [{"name": "upload.fits", "size": len(data)}]})
    task_id = created.json()["task_id"]
    assert client.put(f"/api/v1/uploads/{task_id}/0", headers=AUTH, content=data).status_code == 200
    read, replace = ingestion._read_hash_and_copy, ingestion.os.replace
    reads = []
    def hash_only(path, stage, cancelled):
        assert stage is None
        reads.append(path)
        return read(path, stage, cancelled)
    def crash_after_rename(source, destination):
        replace(source, destination)
        if Path(destination).parent.parent.name == "objects":
            raise RuntimeError("interrupted after object rename")
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", hash_only)
    monkeypatch.setattr(ingestion.os, "replace", crash_after_rename)
    client.post(f"/api/v1/uploads/{task_id}/start", headers=AUTH, json={})
    failed = task(client, task_id)
    item = failed["items"][0]
    assert item["content_status"] == "failed"
    with app.state.database.read_session() as session:
        version = session.get(AssetVersion, item["asset_version_id"])
        path = settings.data_dir / version.storage_location
        assert version.availability == "unknown"
    assert path.read_bytes() == data
    monkeypatch.setattr(ingestion.os, "replace", replace)
    retried = client.post(f"/api/v1/asset-tasks/{task_id}/retry", headers=AUTH, json={"item_ids": [item["id"]]})
    recovered = task(client, retried.json()["task_id"])
    assert recovered["status"] == "completed"
    assert recovered["items"][0]["asset_id"] == item["asset_id"]
    assert recovered["items"][0]["asset_version_id"] == item["asset_version_id"]
    assert reads[-1] == path
    assert not (settings.data_dir / "upload-staging" / task_id / "0.fits").exists()
    with app.state.database.read_session() as session:
        version = session.get(AssetVersion, item["asset_version_id"])
        assert version.content_hash == "blake3:" + blake3.blake3(data).hexdigest()
        assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_cancelled_managed_copy_retries_registered_identity_and_preserves_source(service, monkeypatch):
    settings, app, client, root = service
    data = image(root / "original.fits")
    task_id = enqueue(app)
    read = ingestion._read_hash_and_copy
    def cancel_copy(path, stage, cancelled):
        stage.write_bytes(b"partial")
        with app.state.database.write_session() as session:
            session.get(AssetTask, task_id).status = "cancelling"
        raise ingestion.IngestionError("CANCELLED", "cancel injected")
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", cancel_copy)
    ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    cancelled = task(client, task_id)
    assert cancelled["status"] == "cancelled"
    item = cancelled["items"][0]
    assert item["asset_id"] and item["content_status"] == "pending"
    assert not list((settings.data_dir / "staging").rglob("*.part"))
    assert (root / "original.fits").read_bytes() == data
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", read)
    retried = client.post(f"/api/v1/asset-tasks/{task_id}/retry", headers=AUTH, json={"item_ids": [item["id"]]})
    recovered = task(client, retried.json()["task_id"])
    assert recovered["status"] == "completed"
    assert recovered["items"][0]["asset_version_id"] == item["asset_version_id"]
    assert (root / "original.fits").read_bytes() == data
    with app.state.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
        assert session.scalar(select(func.count()).select_from(DatasetVersion)) == 1


def test_upload_accepts_preset_snapshot_before_task_items_are_flushed(service):
    _, app, client, _ = service
    setup_id, preset_id = str(uuid4()), str(uuid4())
    with app.state.database.write_session() as session:
        session.add(EquipmentSetup(id=setup_id, name="Setup", components=[]))
        session.flush()
        session.add(CapturePreset(id=preset_id, equipment_setup_id=setup_id, name="Preset",
                                  parameters={"gain": 19}, classification={}))
    accepted = client.post("/api/v1/uploads", headers=AUTH, json={
        "files": [{"name": "one.fits", "size": 100}, {"name": "two.fits", "size": 100}],
        "capture_preset_id": preset_id})
    assert accepted.status_code == 202, accepted.text
    with app.state.database.read_session() as session:
        row = session.get(AssetTask, accepted.json()["task_id"])
        assert row.import_defaults_snapshot["parameters"]["gain"] == 19
        assert session.scalar(select(func.count()).select_from(AssetTaskItem)) == 2


def test_resume_after_registration_keeps_identity_snapshot_and_input_bytes(service):
    settings, app, client, root = service
    data = image(root / "resume.fits", GAIN=4)
    task_id = enqueue(app)
    with app.state.database.write_session() as session:
        session.get(AssetTask, task_id).status = "running"
    task_data = dict(id=task_id, sources=[{"root_id": "science", "path": "", "enumeration_completed": False}],
                     storage_mode="managed", classification={}, parameters={}, notes=None,
                     target_dataset_id=task(client, task_id)["target_dataset_id"],
                     import_defaults_snapshot={"parameters": {"offset": 8}})
    ingestion._enumerate_task(app.state.database, settings, task_id, task_data)
    current = task(client, task_id)
    item_id = current["items"][0]["id"]
    ingestion._register_asset(app.state.database, settings, task_data, item_id)
    before = task(client, task_id)["items"][0]
    with app.state.database.read_session() as session:
        snapshot = deepcopy(session.get(AssetVersion, before["asset_version_id"]).capture_snapshot)
    assert ingestion.mark_interrupted_tasks(app.state.database) == 1
    response = client.post(f"/api/v1/asset-tasks/{task_id}/resume", headers=AUTH, json={})
    assert response.status_code == 202
    recovered = task(client, task_id)
    assert recovered["status"] == "completed"
    assert recovered["items"][0]["asset_version_id"] == before["asset_version_id"]
    assert recovered["items"][0]["asset_id"] == before["asset_id"]
    assert (root / "resume.fits").read_bytes() == data
    with app.state.database.read_session() as session:
        assert session.get(AssetVersion, before["asset_version_id"]).capture_snapshot == snapshot
        assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_service_shutdown_drains_submitted_file_and_preview_jobs(service):
    settings, _, _, _ = service
    app = create_app(settings, "import-pipeline-test")
    client = TestClient(app)
    client.__enter__()
    entered = [Event(), Event()]
    release, exited = Event(), Event()
    def blocked(index):
        entered[index].set()
        assert release.wait(5)
        return index
    futures = [executor.submit(blocked, index) for index, executor in enumerate(app.state.import_workers)]
    assert all(event.wait(5) for event in entered)
    def close():
        client.__exit__(None, None, None)
        exited.set()
    thread = Thread(target=close)
    thread.start()
    try:
        assert not exited.wait(.05)
    finally:
        release.set()
        thread.join(5)
    assert exited.is_set()
    assert [future.result() for future in futures] == [0, 1]
    assert all(executor._shutdown for executor in app.state.import_workers)
    app.state.database.close()


def test_preview_retry_reuses_persisted_group_stretch(service, monkeypatch):
    settings, app, client, root = service
    image(root / "a.fits")
    image(root / "b.fits", offset=1000)
    create = ingestion.create_preview
    def fail_first(path, *args, **kwargs):
        if path.name == "a.fits":
            raise ValueError("injected first preview failure")
        return create(path, *args, **kwargs)
    monkeypatch.setattr(ingestion, "create_preview", fail_first)
    task_id = enqueue(app, storage_mode="reference")
    ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    original = task(client, task_id)
    first, second = original["items"]
    assert first["preview_status"] == "failed"
    monkeypatch.setattr(ingestion, "create_preview", create)
    retried = client.post(f"/api/v1/asset-tasks/{task_id}/retry", headers=AUTH, json={"item_ids": [first["id"]]})
    recovered = task(client, retried.json()["task_id"])
    assert recovered["status"] == "completed"
    assert recovered["items"][0]["asset_version_id"] == first["asset_version_id"]
    with app.state.database.read_session() as session:
        preview = session.scalar(select(Preview).where(Preview.asset_version_id == first["asset_version_id"]))
        assert preview.display_parameters["stretch_reference_version_id"] == second["asset_version_id"]
        assert recovered["report"]["preview_stretch_groups"] == original["report"]["preview_stretch_groups"]


def test_xisf_headers_register_without_pixels_and_override_preset_defaults(service, monkeypatch):
    from xisf import XISF
    settings, app, client, root = service
    keywords = {
        "IMAGETYP": [{"value": "Master Light", "comment": "Type of image"}],
        "EXPTIME": [{"value": "300.000", "comment": "Exposure seconds"}],
        "GAIN": [{"value": "9", "comment": "Observed gain"}],
        "FILTER": [{"value": "O", "comment": "Observed filter"}],
    }
    path = root / "observed.xisf"
    XISF.write(str(path), np.arange(120, dtype=np.float32).reshape(10, 12, 1), image_metadata={"FITSKeywords": keywords})
    defaults = {"parameters": {"exposure_seconds": 60, "gain": 50, "offset": 7},
                "classification": {"frame_class": "subframe", "frame_type": "dark"}}
    task_id = enqueue(app, import_defaults_snapshot=defaults, parameters={"gain": 0})
    entered, release = Event(), Event()
    read = ingestion._read_hash_and_copy
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return read(*args)
    original_pixels = XISF.read_image
    pixel_calls = []
    def pixels(*args, **kwargs):
        pixel_calls.append(1)
        return original_pixels(*args, **kwargs)
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", blocked)
    monkeypatch.setattr(XISF, "read_image", pixels)
    thread = run(app, settings, task_id)
    try:
        assert entered.wait(5)
        assert pixel_calls == []
        item = task(client, task_id)["items"][0]
        asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
        assert asset["classification"] == {"frame_class": "masterframe", "frame_type": "light"}
        assert asset["parameters"]["exposure_seconds"] == 300
        assert asset["parameters"]["gain"] == 0
        assert asset["parameters"]["offset"] == 7
        assert asset["parameters"]["iso"] is None
        assert asset["value_sources"]["exposure_seconds"] == "file"
        observed = asset["current_version"]["scientific_metadata"]["observed_parameters"]
        assert observed["xisf_fits_keywords"] == keywords
        assert observed["filter_name"] == "O"
        assert asset["current_version"]["capture_snapshot"]["import_provenance"]["observed_parameters"] == observed
        assert item["metadata_status"] == "available"
    finally:
        release.set()
        thread.join(5)
    assert task(client, task_id)["status"] == "completed"
    monkeypatch.setattr(ingestion, "_read_hash_and_copy", read)
    manual_id = enqueue(app, import_defaults_snapshot=defaults,
                        classification={"frame_class": "subframe", "frame_type": None}, parameters={"exposure_seconds": 0})
    ingestion.process_task(app.state.database, settings, manual_id, app.state.import_workers)
    item = task(client, manual_id)["items"][0]
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    assert asset["classification"] == {"frame_class": "subframe", "frame_type": None}
    assert asset["parameters"]["exposure_seconds"] == 0
    assert asset["value_sources"]["classification.frame_type"] == "manual"


def test_xisf_missing_headers_remain_unknown_and_metadata_failure_retries(service, monkeypatch):
    from xisf import XISF
    settings, app, client, root = service
    XISF.write(str(root / "unknown.xisf"), np.ones((10, 12, 1), dtype=np.float32))
    task_id = enqueue(app)
    ingestion.process_task(app.state.database, settings, task_id, app.state.import_workers)
    item = task(client, task_id)["items"][0]
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    assert asset["classification"] == {"frame_class": None, "frame_type": None}
    assert asset["parameters"]["exposure_seconds"] is None
    inspect = ingestion._inspect_xisf
    def failed(_path):
        raise ValueError("injected XISF metadata failure")
    monkeypatch.setattr(ingestion, "_inspect_xisf", failed)
    failed_id = enqueue(app)
    ingestion.process_task(app.state.database, settings, failed_id, app.state.import_workers)
    item = task(client, failed_id)["items"][0]
    assert item["metadata_status"] == "failed"
    assert item["preview_status"] == "available"
    assert item["error"]["code"] == "XISF_PARSE_FAILED"
    monkeypatch.setattr(ingestion, "_inspect_xisf", inspect)
    retried = client.post(f"/api/v1/asset-tasks/{failed_id}/retry", headers=AUTH, json={"item_ids": [item["id"]]})
    recovered = task(client, retried.json()["task_id"])
    assert recovered["status"] == "completed"
    assert recovered["items"][0]["asset_version_id"] == item["asset_version_id"]
    assert recovered["items"][0]["metadata_status"] == "available"

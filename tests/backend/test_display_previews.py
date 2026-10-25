from __future__ import annotations

from io import BytesIO
from pathlib import Path
import struct
from threading import Event, Thread
import time
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
from astropy.io import fits
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import delete, select, update
from xisf import XISF

from astrophotoflow.backend import ingestion, previews
from astrophotoflow.backend.api import create_app
from astrophotoflow.backend.models import Asset, AssetTaskItem, AssetVersion, Preview
from astrophotoflow.backend.schema import database_lock, upgrade_database
from astrophotoflow.config import ImportRoot, Settings

AUTH = {"Authorization": "Bearer display-preview-test"}


@pytest.fixture
def service(tmp_path):
    root = tmp_path / "science"
    root.mkdir()
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", ("http://127.0.0.1:8188",), (ImportRoot("science", root),))
    with database_lock(settings):
        upgrade_database(settings)
    app = create_app(settings, "display-preview-test")
    with TestClient(app) as client:
        yield settings, app, client, root
    app.state.database.close()


def imported(client, name):
    response = client.post("/api/v1/imports", headers=AUTH, json={
        "sources": [{"root_id": "science", "path": name}], "storage_mode": "managed"})
    assert response.status_code == 202, response.text
    task = client.get("/api/v1/asset-tasks/" + response.json()["task_id"], headers=AUTH).json()
    assert task["status"] == "completed", task
    return task["items"][0]


def base(item):
    return f"/api/v1/library/assets/{item['asset_id']}/versions/{item['asset_version_id']}/previews"


def finished(client, path):
    for _ in range(300):
        response = client.get(path + "/display/status", headers=AUTH)
        assert response.status_code == 200, response.text
        state = response.json()
        if state["status"] != "generating":
            return state
        time.sleep(.01)
    raise AssertionError("preview did not finish")


def picture(path, width=1600, height=1200):
    Image.new("RGB", (width, height), (20, 80, 160)).save(path)


@pytest.mark.parametrize("kind", ["image", "small", "depth", "xisf", "mono", "bayer", "planar", "interleaved", "video"])
def test_display_is_lazy_sized_cached_and_keeps_thumbnail(service, monkeypatch, kind):
    settings, app, client, root = service
    values = np.arange(1200 * 1600, dtype=np.float32).reshape(1200, 1600)
    if kind in {"image", "small"}:
        path = root / "photo.png"
        picture(path, 12 if kind == "small" else 1600, 8 if kind == "small" else 1200)
    elif kind == "depth":
        path = root / "photo.tif"
        Image.fromarray((values % 65535).astype(np.uint16)).save(path)
    elif kind == "xisf":
        path = root / "photo.xisf"
        XISF.write(str(path), values[..., None])
    elif kind == "video":
        path = root / "photo.ser"
        header = b"LUCAM-RECORDER" + struct.pack("<7I", 0, 0, 1, 1600, 1200, 16, 1) + bytes(136)
        path.write_bytes(header + values.astype("<u2").tobytes())
    else:
        path = root / "photo.fits"
        hdu = fits.PrimaryHDU(np.stack([values, values + 10, values + 20], axis=-1 if kind == "interleaved" else 0) if kind in {"planar", "interleaved"} else values)
        if kind == "bayer": hdu.header["BAYERPAT"] = "RGGB"
        if kind == "planar": hdu.header["CTYPE3"] = "RGB"
        if kind == "interleaved": hdu.header["CTYPE1"] = "RGB"
        hdu.writeto(path)
    original = path.read_bytes()
    item = imported(client, path.name)
    with app.state.database.read_session() as session:
        assert not session.scalar(select(Preview).where(Preview.size == "display"))
    thumbnail = client.get(base(item) + "/thumbnail", headers=AUTH).content
    with Image.open(BytesIO(thumbnail)) as image:
        assert max(image.size) <= 100
    assert client.get(base(item) + "/display", headers=AUTH).status_code == 404
    calls = []
    decoder_name = "create_preview" if kind in {"mono", "bayer", "planar", "interleaved"} else "_xisf_image" if kind == "xisf" else "first_video_frame" if kind == "video" else "_ordinary_image"
    decoder = getattr(previews, decoder_name)
    def counted(*args, **kwargs):
        calls.append(1)
        return decoder(*args, **kwargs)
    monkeypatch.setattr(previews, decoder_name, counted)
    response = client.post(base(item) + "/display", headers=AUTH, json={})
    assert response.status_code in {200, 202}
    assert finished(client, base(item))["status"] == "available"
    display = client.get(base(item) + "/display", headers=AUTH)
    assert display.status_code == 200
    with Image.open(BytesIO(display.content)) as image:
        assert max(image.size) <= 1080
        assert image.size == (12, 8) if kind == "small" else max(image.size) > 100
    assert len(calls) == 1
    for _ in range(2):
        assert client.post(base(item) + "/display", headers=AUTH, json={}).json()["status"] == "available"
    assert len(calls) == 1
    assert client.get(base(item) + "/thumbnail", headers=AUTH).content == thumbnail
    assert path.read_bytes() == original
    with app.state.database.read_session() as session:
        rows = session.scalars(select(Preview).where(Preview.asset_version_id == item["asset_version_id"])).all()
        assert len({row.storage_path for row in rows}) == 2


def test_second_group_member_uses_saved_first_reference_and_not_ready_never_decodes(service, monkeypatch):
    _, app, client, root = service
    for name, offset in (("a", 0), ("b", 1000)):
        fits.PrimaryHDU(np.arange(200 * 300, dtype=np.float32).reshape(200, 300) + offset).writeto(root / f"{name}.fits")
    accepted = client.post("/api/v1/imports", headers=AUTH, json={"sources": [{"root_id": "science", "path": ""}], "storage_mode": "managed"})
    task = client.get("/api/v1/asset-tasks/" + accepted.json()["task_id"], headers=AUTH).json()
    first, second = task["items"]
    with app.state.database.read_session() as session:
        recipe = dict(session.scalar(select(Preview).where(Preview.asset_version_id == second["asset_version_id"])).display_parameters)
    assert recipe["stretch_reference_version_id"] == first["asset_version_id"]
    client.post(base(second) + "/display", headers=AUTH, json={})
    assert finished(client, base(second))["status"] == "available"
    with app.state.database.read_session() as session:
        display = session.scalar(select(Preview).where(Preview.asset_version_id == second["asset_version_id"], Preview.size == "display"))
        assert display.display_parameters["stretch_reference_version_id"] == first["asset_version_id"]
        assert display.display_parameters["stretch_low"] == recipe["stretch_low"]
        assert display.display_parameters["stretch_high"] == recipe["stretch_high"]
        assert not session.scalar(select(Preview).where(Preview.asset_version_id == first["asset_version_id"], Preview.size == "display"))
    with app.state.database.write_session() as session:
        session.execute(delete(Preview).where(Preview.size == "display"))
        session.get(AssetVersion, first["asset_version_id"]).availability = "unknown"
    def forbidden(*_args, **_kwargs):
        raise AssertionError("unready recipe must not decode")
    monkeypatch.setattr(previews, "create_preview", forbidden)
    state = client.post(base(second) + "/display", headers=AUTH, json={}).json()
    assert state["status"] == "not_ready" and state["error"]["code"] == "STRETCH_NOT_READY"
    state = client.post(base(first) + "/display", headers=AUTH, json={}).json()
    assert state["status"] == "not_ready" and state["error"]["code"] == "SOURCE_NOT_READY"
    with app.state.database.write_session() as session:
        session.get(AssetVersion, first["asset_version_id"]).availability = "available"
        row = session.scalar(select(Preview).where(Preview.asset_version_id == second["asset_version_id"], Preview.size == "thumbnail"))
        row.display_parameters = {}
    assert client.post(base(second) + "/display", headers=AUTH, json={}).json()["error"]["code"] == "STRETCH_NOT_READY"


def test_failure_retry_dedup_and_trash_block_active_job(service, monkeypatch):
    settings, app, client, root = service
    picture(root / "photo.png")
    item = imported(client, "photo.png")
    entered, release = Event(), Event()
    decode = previews._ordinary_image
    calls = []
    def blocked(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return decode(*args, **kwargs)
    monkeypatch.setattr(previews, "_ordinary_image", blocked)
    started = time.perf_counter()
    assert client.post(base(item) + "/display", headers=AUTH, json={}).json()["status"] == "generating"
    assert time.perf_counter() - started < 1
    assert entered.wait(5)
    for _ in range(3):
        assert client.post(base(item) + "/display", headers=AUTH, json={}).json()["status"] == "generating"
    assert len(calls) == 1
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    client.request("DELETE", "/api/v1/library/items", headers=AUTH, json={"items": [{"entry_type": "asset", "id": asset["id"], "revision": asset["revision"], "current_version_id": asset["current_version_id"]}]})
    row = client.get("/api/v1/library/trash", headers=AUTH).json()["items"][0]
    selection = {"items": [{key: row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    try:
        blocked_delete = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json=selection)
        assert blocked_delete.status_code == 409
        assert blocked_delete.json()["error"]["code"] == "PREVIEW_ACTIVE"
        with app.state.database.read_session() as session:
            location = session.get(AssetVersion, item["asset_version_id"]).storage_location
            assert (settings.data_dir / location).is_file()
    finally:
        release.set()
    assert finished(client, base(item))["status"] == "available"
    preview = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json=selection).json()
    result = client.post("/api/v1/library/trash/delete", headers=AUTH, json={**selection, "preview_fingerprint": preview["preview_fingerprint"]})
    assert result.status_code == 200, result.text
    assert not (settings.data_dir / location).exists()
    assert not list((settings.data_dir / "previews" / item["asset_version_id"]).glob("*.jpg"))


def test_failed_display_can_retry_same_cache_and_deleted_version_cannot_publish(service, monkeypatch):
    settings, app, client, root = service
    picture(root / "photo.png")
    item = imported(client, "photo.png")
    decode = previews._ordinary_image
    def failed(*_args):
        raise ValueError("decoder failure")
    monkeypatch.setattr(previews, "_ordinary_image", failed)
    client.post(base(item) + "/display", headers=AUTH, json={})
    state = finished(client, base(item))
    assert state["status"] == "failed" and "decoder failure" in state["error"]["message"]
    with app.state.database.read_session() as session:
        preview_id = session.scalar(select(Preview.id).where(Preview.size == "display"))
    monkeypatch.setattr(previews, "_ordinary_image", decode)
    client.post(base(item) + "/display", headers=AUTH, json={})
    assert finished(client, base(item))["status"] == "available"
    with app.state.database.write_session() as session:
        row = session.get(Preview, preview_id)
        Path(settings.data_dir / row.storage_path).unlink()
    entered, release, decoded = Event(), Event(), Event()
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        result = decode(*args)
        decoded.set()
        return result
    monkeypatch.setattr(previews, "_ordinary_image", blocked)
    client.post(base(item) + "/display", headers=AUTH, json={})
    assert entered.wait(5)
    with app.state.database.write_session() as session:
        session.execute(delete(Preview).where(Preview.asset_version_id == item["asset_version_id"]))
        session.execute(update(Asset).where(Asset.id == item["asset_id"]).values(current_version_id=None))
        session.execute(update(AssetTaskItem).where(AssetTaskItem.asset_version_id == item["asset_version_id"]).values(asset_version_id=None))
        session.execute(delete(AssetVersion).where(AssetVersion.id == item["asset_version_id"]))
    release.set()
    assert decoded.wait(5)
    # Queue a barrier after the job in the same single-worker preview executor.
    app.state.import_workers[1].submit(lambda: None).result(5)
    assert not list((settings.data_dir / "previews" / item["asset_version_id"]).glob("*display.jpg"))
    with app.state.database.read_session() as session:
        assert session.get(Preview, preview_id) is None


def test_project_reference_uses_pinned_private_version_and_rejects_wrong_scope(service):
    _, app, client, root = service
    picture(root / "old.png", 240, 160)
    old = imported(client, "old.png")
    picture(root / "new.png", 600, 400)
    newer = imported(client, "new.png")
    project = client.post("/api/v1/projects", headers=AUTH, json={"name": "Project"}).json()
    reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH,
                            json={"base_revision": 1, "asset_version_id": old["asset_version_id"]}).json()
    with app.state.database.write_session() as session:
        asset = session.get(Asset, old["asset_id"])
        current = session.get(AssetVersion, newer["asset_version_id"])
        current_id = str(uuid4())
        session.add(AssetVersion(id=current_id, asset_id=asset.id, version_number=2,
            storage_mode=current.storage_mode, storage_location=current.storage_location,
            availability="available", scientific_metadata={"format": "image"}))
        session.flush()
        asset.scope, asset.owner_project_id, asset.current_version_id = "project", project["id"], current_id
    project_base = f"/api/v1/projects/{project['id']}/asset-references/{reference['id']}/previews"
    assert client.post(base(old) + "/display", headers=AUTH, json={}).status_code == 404
    assert client.post(project_base + "/display", headers=AUTH, json={}).status_code in {200, 202}
    state = finished(client, project_base)
    assert state["asset_version_id"] == old["asset_version_id"]
    with Image.open(BytesIO(client.get(project_base + "/display", headers=AUTH).content)) as image:
        assert image.size == (240, 160)
    wrong = str(uuid4())
    assert client.get(project_base.replace(project["id"], wrong) + "/display/status", headers=AUTH).status_code == 404


def test_orphan_generating_record_is_failed_on_restart_and_does_not_block_cleanup(service):
    settings, app, client, root = service
    picture(root / "photo.png")
    item = imported(client, "photo.png")
    with app.state.database.write_session() as session:
        session.add(Preview(id=str(uuid4()), asset_version_id=item["asset_version_id"], hdu_index=0, size="display", width=0, height=0,
            storage_path=f"previews/{item['asset_version_id']}/interrupted-display.jpg", display_parameters={}, algorithm_version=previews.PREVIEW_ALGORITHM_VERSION,
            status="generating", error=None, mime_type="image/jpeg"))
    temporary_path = settings.data_dir / "previews" / item["asset_version_id"] / "interrupted-display.jpg.tmp"
    temporary_path.write_bytes(b"interrupted JPEG")
    restarted = create_app(settings, "display-preview-test")
    try:
        with TestClient(restarted) as other:
            state = other.get(base(item) + "/display/status", headers=AUTH).json()
            assert state["status"] == "failed" and "服务中断" in state["error"]["message"]
            asset = other.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
            other.request("DELETE", "/api/v1/library/items", headers=AUTH, json={"items": [{
                "entry_type": "asset", "id": asset["id"], "revision": asset["revision"], "current_version_id": asset["current_version_id"]}]})
            removal = other.get("/api/v1/library/trash", headers=AUTH).json()["items"][0]
            selection = {"items": [{key: removal[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
            cleanup = other.post("/api/v1/library/trash/delete-preview", headers=AUTH, json=selection)
            assert cleanup.status_code == 200
            result = other.post("/api/v1/library/trash/delete", headers=AUTH, json={**selection, "preview_fingerprint": cleanup.json()["preview_fingerprint"]})
            assert result.status_code == 200, result.text
            assert not temporary_path.exists()
    finally:
        restarted.state.database.close()


def test_raw_display_ignores_tiny_embedded_preview_and_selects_decode_size(service, monkeypatch):
    _, _, client, root = service
    import rawpy
    encoded = BytesIO()
    Image.new("RGB", (100, 60)).save(encoded, format="JPEG")
    calls = []
    class FakeRaw:
        sizes = SimpleNamespace(width=4000, height=3000)
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def extract_thumb(self): return SimpleNamespace(format=rawpy.ThumbFormat.JPEG, data=encoded.getvalue())
        def postprocess(self, **kwargs):
            calls.append(kwargs)
            return np.zeros((1500, 2000, 3), dtype=np.uint8)
    monkeypatch.setattr(rawpy, "imread", lambda _path: FakeRaw())
    assert ingestion._raw_image(root / "photo.raw").size == (100, 60)
    assert calls == []
    assert ingestion._raw_image(root / "photo.raw", 1080).size == (2000, 1500)
    assert calls[-1]["half_size"] is True
    FakeRaw.sizes = SimpleNamespace(width=1500, height=1000)
    ingestion._raw_image(root / "photo.raw", 1080)
    assert calls[-1]["half_size"] is False
    (root / "photo.dng").write_bytes(b"synthetic RAW decoder fixture")
    item = imported(client, "photo.dng")
    before = len(calls)
    client.post(base(item) + "/display", headers=AUTH, json={})
    assert finished(client, base(item))["status"] == "available"
    with Image.open(BytesIO(client.get(base(item) + "/display", headers=AUTH).content)) as image:
        assert max(image.size) == 1080
    assert len(calls) == before + 1


def test_shutdown_drains_display_jobs_and_shared_executor_limits_generation(tmp_path, monkeypatch):
    root = tmp_path / "science"
    root.mkdir()
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", ("http://127.0.0.1:8188",), (ImportRoot("science", root),))
    with database_lock(settings):
        upgrade_database(settings)
    app = create_app(settings, "display-preview-test")
    client = TestClient(app)
    client.__enter__()
    for name in ("one", "two"):
        picture(root / f"{name}.png")
    items = [imported(client, f"{name}.png") for name in ("one", "two")]
    decode = previews._ordinary_image
    entered, release, closed = Event(), Event(), Event()
    calls = []
    def blocked(*args):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return decode(*args)
    monkeypatch.setattr(previews, "_ordinary_image", blocked)
    assert app.state.display_previews.executor is app.state.import_workers[1]
    client.post(base(items[0]) + "/display", headers=AUTH, json={})
    assert entered.wait(5)
    client.post(base(items[1]) + "/display", headers=AUTH, json={})
    assert len(calls) == 1  # second version owns a queued row, no extra decoder thread
    def close():
        client.__exit__(None, None, None)
        closed.set()
    thread = Thread(target=close)
    thread.start()
    try:
        assert not closed.wait(.05)
        with app.state.database.read_session() as session:
            assert len(session.scalars(select(Preview).where(Preview.size == "display", Preview.status == "generating")).all()) == 2
    finally:
        release.set()
        thread.join(5)
    assert closed.is_set() and len(calls) == 2
    with app.state.database.read_session() as session:
        assert len(session.scalars(select(Preview).where(Preview.size == "display", Preview.status == "available")).all()) == 2
    assert all(executor._shutdown for executor in app.state.import_workers)
    app.state.database.close()


def test_save_preview_uses_size_specific_path(service):
    settings, app, client, root = service
    picture(root / "small.png", 80, 60)
    item = imported(client, "small.png")
    before = client.get(base(item) + "/thumbnail", headers=AUTH).content
    ingestion._save_preview(app.state.database, settings, item["asset_version_id"], 0, "display", 1080, Image.new("RGB", (200, 150)))
    assert client.get(base(item) + "/thumbnail", headers=AUTH).content == before
    with app.state.database.read_session() as session:
        rows = session.scalars(select(Preview).where(Preview.asset_version_id == item["asset_version_id"])).all()
        assert {Path(row.storage_path).name for row in rows} == {
            f"{previews.PREVIEW_ALGORITHM_VERSION}-0-thumbnail.jpg", f"{previews.PREVIEW_ALGORITHM_VERSION}-0-display.jpg"}


def test_project_reference_can_preview_removed_library_asset_until_cleanup_starts(service):
    from astrophotoflow.backend.models import LibraryEntryRemoval
    settings, app, client, root = service
    picture(root / "shared.png")
    item = imported(client, "shared.png")
    project = client.post("/api/v1/projects", headers=AUTH, json={"name": "Pinned source"}).json()
    reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH,
        json={"base_revision": 1, "asset_version_id": item["asset_version_id"]}).json()
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    client.request("DELETE", "/api/v1/library/items", headers=AUTH, json={"items": [{"entry_type": "asset", "id": asset["id"],
        "revision": asset["revision"], "current_version_id": asset["current_version_id"]}]})
    project_base = f"/api/v1/projects/{project['id']}/asset-references/{reference['id']}/previews"
    assert client.post(project_base + "/display", headers=AUTH, json={}).status_code in {200, 202}
    assert finished(client, project_base)["status"] == "available"
    with app.state.database.write_session() as session:
        session.execute(delete(Preview).where(Preview.size == "display"))
        session.get(LibraryEntryRemoval, ("asset", asset["id"])).cleanup_status = "partial"
    state = client.post(project_base + "/display", headers=AUTH, json={}).json()
    assert state["status"] == "not_ready"
    assert state["error"]["code"] == "SOURCE_CLEANUP_ACTIVE"
    with app.state.database.read_session() as session:
        assert session.get(AssetVersion, item["asset_version_id"]) is not None
        assert not session.scalar(select(Preview).where(Preview.size == "display"))


def test_locked_cache_publication_is_failed_and_retryable(service, monkeypatch):
    settings, app, client, root = service
    picture(root / "locked.png")
    item = imported(client, "locked.png")
    original = previews.os.replace
    def locked(source, destination):
        if str(destination).endswith("-display.jpg"):
            raise PermissionError("locked display cache")
        return original(source, destination)
    monkeypatch.setattr(previews.os, "replace", locked)
    client.post(base(item) + "/display", headers=AUTH, json={})
    state = finished(client, base(item))
    assert state["status"] == "failed" and "locked display cache" in state["error"]["message"]
    with app.state.database.read_session() as session:
        previews.assert_no_preview_jobs(session, [item["asset_version_id"]])
    monkeypatch.setattr(previews.os, "replace", original)
    client.post(base(item) + "/display", headers=AUTH, json={})
    assert finished(client, base(item))["status"] == "available"
    assert (root / "locked.png").is_file()


def test_shared_display_file_and_interrupted_temporary_are_preserved(service):
    settings, app, client, root = service
    for name in ("one", "two"):
        picture(root / f"{name}.png", 80, 60)
    first, second = [imported(client, f"{name}.png") for name in ("one", "two")]
    shared = f"previews/{first['asset_version_id']}/shared-display.jpg"
    final, temporary = settings.data_dir / shared, settings.data_dir / (shared + ".tmp")
    final.write_bytes(b"shared JPEG")
    temporary.write_bytes(b"owned interrupted JPEG")
    with app.state.database.write_session() as session:
        for item in (first, second):
            session.add(Preview(id=str(uuid4()), asset_version_id=item["asset_version_id"], hdu_index=0, size="display", width=0, height=0,
                storage_path=shared, display_parameters={}, algorithm_version=previews.PREVIEW_ALGORITHM_VERSION,
                status="failed", error="interrupted", mime_type="image/jpeg"))
    asset = client.get(f"/api/v1/library/assets/{first['asset_id']}", headers=AUTH).json()
    client.request("DELETE", "/api/v1/library/items", headers=AUTH, json={"items": [{"entry_type": "asset", "id": asset["id"],
        "revision": asset["revision"], "current_version_id": asset["current_version_id"]}]})
    row = client.get("/api/v1/library/trash", headers=AUTH).json()["items"][0]
    selection = {"items": [{key: row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=AUTH, json=selection).json()
    deleted = client.post("/api/v1/library/trash/delete", headers=AUTH, json={**selection, "preview_fingerprint": preview["preview_fingerprint"]})
    assert deleted.status_code == 200, deleted.text
    assert final.read_bytes() == b"shared JPEG"
    assert temporary.read_bytes() == b"owned interrupted JPEG"
    with app.state.database.read_session() as session:
        assert session.get(AssetVersion, second["asset_version_id"]) is not None


def test_failed_header_metadata_waits_for_import_retry_before_caching_display(service, monkeypatch):
    _, app, client, root = service
    XISF.write(str(root / "metadata.xisf"), np.arange(600, dtype=np.float32).reshape(20, 30, 1))
    inspect = ingestion._inspect_xisf
    def failed(_path):
        raise ValueError("injected header failure")
    monkeypatch.setattr(ingestion, "_inspect_xisf", failed)
    accepted = client.post("/api/v1/imports", headers=AUTH, json={
        "sources": [{"root_id": "science", "path": "metadata.xisf"}], "storage_mode": "managed"})
    task_id = accepted.json()["task_id"]
    task = client.get("/api/v1/asset-tasks/" + task_id, headers=AUTH).json()
    item = task["items"][0]
    assert item["metadata_status"] == "failed" and item["preview_status"] == "available"
    state = client.post(base(item) + "/display", headers=AUTH, json={}).json()
    assert state["status"] == "not_ready" and state["error"]["code"] == "METADATA_NOT_READY"
    with app.state.database.read_session() as session:
        assert not session.scalar(select(Preview).where(Preview.size == "display"))
    monkeypatch.setattr(ingestion, "_inspect_xisf", inspect)
    retry = client.post(f"/api/v1/asset-tasks/{task_id}/retry", headers=AUTH, json={"item_ids": [item["id"]]})
    assert client.get("/api/v1/asset-tasks/" + retry.json()["task_id"], headers=AUTH).json()["status"] == "completed"
    client.post(base(item) + "/display", headers=AUTH, json={})
    assert finished(client, base(item))["status"] == "available"


def test_metadata_retry_barrier_and_cancelled_preview_stage_stay_uncached_until_retry(service, monkeypatch):
    from astrophotoflow.backend.models import AssetTask
    _, app, client, root = service
    XISF.write(str(root / "recipe.xisf"), np.arange(600, dtype=np.float32).reshape(20, 30, 1), image_metadata={
        "FITSKeywords": {"EXPTIME": [{"value": "300.000", "comment": "Exposure"}],
                         "IMAGETYP": [{"value": "Master Light", "comment": "Type"}]}})
    inspect = ingestion._inspect_xisf
    def failed(_path):
        raise ValueError("injected header failure")
    monkeypatch.setattr(ingestion, "_inspect_xisf", failed)
    accepted = client.post("/api/v1/imports", headers=AUTH, json={
        "sources": [{"root_id": "science", "path": "recipe.xisf"}], "storage_mode": "managed"})
    original_task = client.get("/api/v1/asset-tasks/" + accepted.json()["task_id"], headers=AUTH).json()
    item = original_task["items"][0]
    with app.state.database.read_session() as session:
        old_recipe = dict(session.scalar(select(Preview).where(Preview.size == "thumbnail")).display_parameters)
    monkeypatch.setattr(ingestion, "_inspect_xisf", inspect)
    process = ingestion._process_preview
    entered, release = Event(), Event()
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return process(*args)
    monkeypatch.setattr(ingestion, "_process_preview", blocked)
    response = {}
    def retry():
        response["retry"] = client.post(f"/api/v1/asset-tasks/{original_task['id']}/retry", headers=AUTH,
            json={"item_ids": [item["id"]]})
    thread = Thread(target=retry)
    thread.start()
    try:
        assert entered.wait(5)
        with app.state.database.read_session() as session:
            version = session.get(AssetVersion, item["asset_version_id"])
            assert version.scientific_metadata["metadata_status"] == "available"
            thumbnail = session.scalar(select(Preview).where(Preview.size == "thumbnail"))
            assert thumbnail.status == "available" and thumbnail.display_parameters == old_recipe
            latest = session.scalar(select(AssetTaskItem).where(AssetTaskItem.asset_version_id == version.id)
                .order_by(AssetTaskItem.created_at.desc(), AssetTaskItem.id.desc()).limit(1))
            assert latest.preview_status == "pending"
            retry_id, retry_item_id = latest.task_id, latest.id
        state = client.post(base(item) + "/display", headers=AUTH, json={}).json()
        assert state["status"] == "not_ready" and state["error"]["code"] == "RECIPE_NOT_READY"
        assert client.post(f"/api/v1/asset-tasks/{retry_id}/cancel", headers=AUTH, json={}).status_code == 202
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert response["retry"].status_code == 202
    assert client.get(f"/api/v1/asset-tasks/{retry_id}", headers=AUTH).json()["status"] == "cancelled"
    assert client.post(base(item) + "/display", headers=AUTH, json={}).json()["error"]["code"] == "RECIPE_NOT_READY"
    monkeypatch.setattr(ingestion, "_process_preview", process)
    recovered = client.post(f"/api/v1/asset-tasks/{retry_id}/retry", headers=AUTH, json={"item_ids": [retry_item_id]})
    assert recovered.status_code == 202, recovered.text
    assert client.get("/api/v1/asset-tasks/" + recovered.json()["task_id"], headers=AUTH).json()["status"] == "completed"
    with app.state.database.read_session() as session:
        thumbnail = session.scalar(select(Preview).where(Preview.size == "thumbnail"))
        assert thumbnail.display_parameters["stretch_group"] != old_recipe["stretch_group"]
        assert not session.scalar(select(Preview).where(Preview.size == "display"))
    client.post(base(item) + "/display", headers=AUTH, json={})
    assert finished(client, base(item))["status"] == "available"

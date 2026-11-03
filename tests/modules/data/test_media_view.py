from astrophotoflow.modules.data.formats import pixels as codec_formats_pixels
from io import BytesIO
from pathlib import Path
from threading import Event
import time
import json

from astropy.io import fits
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest
from sqlalchemy import select

from astrophotoflow.core.config import ImportRoot, Settings
from astrophotoflow.core.database.schema import database_lock, upgrade_database
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.public import check_output
from astrophotoflow.modules.data.media.ownership import owned_preview_locations


AUTH = {"Authorization": "Bearer media-view-test"}


def test_available_view_prepare_is_read_only_and_does_not_replay_import_history(media_service, monkeypatch):
    _, app, client, source = media_service
    app.state.thumbnails.pause()
    fits.PrimaryHDU(np.arange(64 * 64, dtype=np.float32).reshape(64, 64)).writeto(source / 'cached.fits')
    base, item = add(client, 'cached.fits')
    state = prepare(client, base)
    assert state['status'] == 'available'
    monkeypatch.setattr(app.state.database, 'write_session', lambda: pytest.fail('cache hit took a write transaction'))
    monkeypatch.setattr('astrophotoflow.modules.data.media.recipes.backfill_context',
        lambda *args: pytest.fail('viewer replayed import history'))
    cached = app.state.media_views.prepare(item['asset_version_id'], MediaSelection())
    assert cached.status == 'available' and cached.key == state['key']


def test_group_view_uses_strict_fixed_first_member_stretch(media_service):
    _, app, client, source = media_service
    app.state.thumbnails.pause()
    first = np.random.default_rng(7).normal(.01, .001, (64, 64)).astype(np.float32)
    second = first * 15
    fits.PrimaryHDU(first).writeto(source / 'first.fits')
    fits.PrimaryHDU(second).writeto(source / 'second.fits')
    first_base, one = add(client, 'first.fits')
    second_base, two = add(client, 'second.fits')
    group = client.post('/api/v1/datasets', headers=AUTH, json={
        'name': 'fixed reference', 'asset_version_ids': [one['asset_version_id'], two['asset_version_id']]}).json()
    standalone = prepare(client, first_base)
    grouped = prepare(client, second_base, {'dataset_version_id': group['current_version_id']})
    assert standalone['status'] == grouped['status'] == 'available'
    assert grouped['display_recipe']['auto_stretch'] == standalone['display_recipe']['auto_stretch']
    assert grouped['selection']['dataset_version_id'] == group['current_version_id']


@pytest.fixture
def media_service(tmp_path):
    source = tmp_path / "sources"
    source.mkdir()
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", ("http://127.0.0.1:8188",), (ImportRoot("source", source),), workspace=tmp_path)
    with database_lock(settings):
        upgrade_database(settings)
    app = create_app(settings, "media-view-test")
    with TestClient(app) as client:
        yield settings, app, client, source


def add(client, name):
    response = client.post("/api/v1/imports", headers=AUTH, json={"sources": [{"root_id": "source", "path": name}], "storage_mode": "managed"})
    assert response.status_code == 202, response.text
    for _ in range(400):
        task = client.get("/api/v1/asset-tasks/" + response.json()["task_id"], headers=AUTH).json()
        if task["status"] not in {"running", "queued"}:
            item = task["items"][0]
            return f"/api/v1/library/assets/{item['asset_id']}/versions/{item['asset_version_id']}/previews", item
        time.sleep(.01)
    pytest.fail("small fixture import did not settle")


def prepare(client, base, body=None):
    response = client.post(base + "/viewer", headers=AUTH, json=body or {})
    assert response.status_code in (200, 202), response.text
    key = response.json()["key"]
    for _ in range(400):
        state = client.get(base + "/viewer/" + key + "/status", headers=AUTH).json()
        if state["status"] != "generating":
            return state
        time.sleep(.01)
    pytest.fail("small fixture viewer did not settle")


def native_url(url):
    return url.removeprefix("/astrophotoflow")


@pytest.mark.parametrize('edge', [512, 1024, 2048, None])
def test_legacy_rgb_preview_rebalances_and_resolution_is_display_only(media_service, edge):
    settings, app, client, source = media_service
    mono = np.random.default_rng(12).normal(.01, .0005, (320, 2100)).astype(np.float32)
    pixels = np.stack([mono, mono * 2, mono], axis=0)
    hdu = fits.PrimaryHDU(pixels)
    hdu.header['CTYPE3'] = 'RGB'
    path = source / 'cast.fit'
    hdu.writeto(path)
    original = path.read_bytes()
    base, item = add(client, 'cast.fit')
    with app.state.database.write_session() as session:
        row = session.scalar(select(Preview).where(Preview.asset_version_id == item['asset_version_id'], Preview.size == 'thumbnail'))
        row.display_parameters = {'stretch_low': .005, 'stretch_high': .025}
    state = prepare(client, base, {'preview_max_edge': edge})
    assert state['status'] == 'available'
    overview = np.asarray(Image.open(BytesIO(client.get(native_url(state['overview_url']), headers=AUTH).content)))
    assert overview.shape[1] == (min(2100, edge) if edge else 2100)
    medians = np.median(overview, axis=(0, 1))
    assert medians.max() - medians.min() <= 2
    preserve = prepare(client, base, {'preview_max_edge': edge, 'display_balance': 'preserve'})
    assert preserve['key'] != state['key']
    cast = np.asarray(Image.open(BytesIO(client.get(native_url(preserve['overview_url']), headers=AUTH).content)))
    medians = np.median(cast, axis=(0, 1))
    assert medians[1] > medians[0]
    restored = prepare(client, base, {'preview_max_edge': edge})
    assert restored['key'] == state['key']
    manifest = settings.data_dir / 'previews' / item['asset_version_id'] / 'media' / state['key'] / 'manifest.json'
    assert len(json.loads(manifest.read_text())['recipe']['auto_stretch']['white_balance']) == 3
    assert path.read_bytes() == original


def test_checked_output_view_uses_thresholds_and_hdu_without_registering_assets(media_service, tmp_path):
    settings, app, _, _ = media_service
    source = tmp_path / 'output.fit'
    pixels = np.array([[0, .5, 1], [1, .5, 0]], dtype=np.float32)
    fits.HDUList([fits.PrimaryHDU(np.zeros((4, 5), dtype=np.float32)),
                  fits.ImageHDU(pixels, name='SCI')]).writeto(source)
    original = source.read_bytes()
    checked = check_output(settings, run_directory=tmp_path, path=source, expected_format='fits', expected_frames=2)
    with app.state.database.read_session() as session:
        before = session.scalars(select(Asset.id)).all()
    views = app.state.media_views
    prepared = views.prepare_output(checked, MediaSelection(hdu_index=1, display_range=(0, 1)), direct=False)
    future = views.preparing.get(prepared.key)
    if future is not None:
        future.result(timeout=30)
    state = views.output_status(checked, prepared.key)
    assert state.status == 'available'
    assert (state.width, state.height) == (3, 2)
    assert [(hdu.index, hdu.name) for hdu in state.hdus] == [(0, None), (1, 'SCI')]
    job, release = views.acquire_output(checked, state.key)
    try:
        tile = np.asarray(Image.open(BytesIO(views.tiles.tile(job, state.max_level, 0, 0))))
        assert np.all(tile[0, 0] == 0) and np.all(tile[0, 2] == 255)
        assert np.all(np.abs(tile[0, 1].astype(int) - 127) <= 1)
    finally:
        release()
    for balance in ('auto', 'preserve'):
        prepared = views.prepare_output(checked, MediaSelection(hdu_index=1, display_balance=balance), direct=True)
        future = views.preparing.get(prepared.key)
        if future is not None:
            future.result(timeout=30)
        balanced_state = views.output_status(checked, prepared.key)
        assert balanced_state.status == 'available'
        job, release = views.acquire_output(checked, balanced_state.key)
        try:
            displayed = np.asarray(Image.open(BytesIO(views.tiles.tile(job, balanced_state.max_level, 0, 0))))
            np.testing.assert_array_equal(displayed, tile)
        finally:
            release()
    with app.state.database.read_session() as session:
        assert session.scalars(select(Asset.id)).all() == before
        assert session.scalars(select(Preview)).all() == []
    assert source.read_bytes() == original


def test_http_original_resolution_tiles_auth_scope_and_cleanup_ownership(media_service):
    settings, app, client, source = media_service
    pixels = np.random.default_rng(7).integers(0, 255, (541, 1033, 3), dtype=np.uint8)
    Image.fromarray(pixels).save(source / "frame.png")
    original = (source / "frame.png").read_bytes()
    base, item = add(client, "frame.png")
    state = prepare(client, base)
    assert (state["width"], state["height"]) == (1033, 541)
    assert state["tile_size"] == 512
    tile_url = native_url(state["tile_url"]).format(level=state["max_level"], x=2, y=1)
    assert client.get(tile_url).status_code == 401
    response = client.get(tile_url, headers=AUTH)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    np.testing.assert_array_equal(np.asarray(Image.open(BytesIO(response.content))), pixels[512:, 1024:])
    assert client.get(tile_url.replace("/2/1", "/3/1"), headers=AUTH).status_code == 422
    assert client.get(tile_url.replace(item["asset_id"], "00000000-0000-4000-8000-000000000000"), headers=AUTH).status_code == 404
    with app.state.database.read_session() as session:
        row = session.scalar(select(Preview).where(Preview.asset_version_id == item["asset_version_id"], Preview.size == "viewer"))
        locations = owned_preview_locations(row, settings)
    assert any(path.endswith("pixels.npy") for path in locations)
    assert any(path.endswith("tile-11-2-1.png") for path in locations)
    assert all(Path(path).parts[0] == "previews" for path in locations)
    assert (source / "frame.png").read_bytes() == original


def test_numpy_array_selection_is_display_only_and_non_numeric_is_explicit(media_service):
    _, app, client, source = media_service
    values = np.arange(2 * 6 * 9, dtype=np.float32).reshape(2, 6, 9)
    np.savez_compressed(source / "planes.npz", science=values, labels=np.array(["name"]))
    base, item = add(client, "planes.npz")
    state = prepare(client, base)
    assert state["needs_selection"] is True and state["width"] == 0
    selected = prepare(client, base, {"array_key": "science", "x_axis": 2, "y_axis": 1, "slices": {"0": 0}})
    assert selected["status"] == "available"
    assert (selected["width"], selected["height"]) == (9, 6)
    failed = prepare(client, base, {"array_key": "labels"})
    assert failed["status"] == "failed" and "不是数值" in failed["error"]["message"]
    current = client.get(f"/api/v1/library/assets/{item['asset_id']}/versions/{item['asset_version_id']}", headers=AUTH).json()
    assert "slices" not in str(current.get("capture_snapshot"))


def test_failed_acquisition_transaction_does_not_leak_file_lease(media_service, monkeypatch):
    from contextlib import contextmanager

    _, app, client, source = media_service
    fits.PrimaryHDU(np.ones((32, 48), dtype=np.float32)).writeto(source / "source.fits")
    base, item = add(client, "source.fits")
    state = prepare(client, base)
    views = app.state.media_views
    original = views.database.write_session
    fail = True

    @contextmanager
    def failed_commit():
        nonlocal fail
        with original() as session:
            yield session
            if fail:
                fail = False
                raise RuntimeError("acquisition transaction failed")

    monkeypatch.setattr(views.database, "write_session", failed_commit)
    with pytest.raises(RuntimeError, match="acquisition transaction failed"):
        views.acquire(item["asset_version_id"], state["key"])
    assert views.leases.active == views.cache.active == {}


def test_source_change_after_prepare_refuses_cached_tile(media_service):
    settings, app, client, source = media_service
    fits.PrimaryHDU(np.ones((32, 48), dtype=np.float32)).writeto(source / "source.fits")
    base, item = add(client, "source.fits")
    state = prepare(client, base)
    job, release = app.state.media_views.acquire(item["asset_version_id"], state["key"])
    managed = job["path"]
    release()
    with managed.open("ab") as stream:
        stream.write(b"changed")
    url = native_url(state["tile_url"]).format(level=state["max_level"], x=0, y=0)
    response = client.get(url, headers=AUTH)
    assert response.status_code == 409 and response.json()["error"]["code"] == "SOURCE_CHANGED"


def test_superseded_queued_view_does_not_decode_original(media_service, monkeypatch):
    _, app, client, source = media_service
    Image.new("RGB", (64, 64), "red").save(source / "first.png")
    Image.new("RGB", (64, 64), "blue").save(source / "second.png")
    first, first_item = add(client, "first.png")
    second, _ = add(client, "second.png")
    from uuid import uuid4
    consumer = str(uuid4())
    gate = Event()
    running = app.state.media_views.executor.submit(lambda: gate.wait(5))
    one = client.post(first + "/viewer", headers=AUTH, json={"consumer_id": consumer, "generation": 1}).json()
    two = client.post(second + "/viewer", headers=AUTH, json={"consumer_id": consumer, "generation": 2}).json()
    gate.set()
    running.result()
    for _ in range(300):
        state = client.get(first + "/viewer/" + one["key"] + "/status", headers=AUTH).json()
        if state["status"] != "generating":
            break
        time.sleep(.01)
    assert state["status"] == "failed" and "cancelled" in state["error"]["message"]
    assert not list((app.state.settings.data_dir / "previews" / first_item["asset_version_id"] / "media" / one["key"]).glob("pixels.npy"))


def test_video_stream_supports_ranges_without_buffering_entire_original(media_service, monkeypatch):
    _, app, client, source = media_service
    from astrophotoflow.modules.data.media import views as media_view
    payload = b"0123456789" * 1000
    (source / "clip.mp4").write_bytes(payload)
    base, _ = add(client, "clip.mp4")
    monkeypatch.setattr(media_view, "video_info", lambda path: (1920, 1080, 1.0))
    state = prepare(client, base)
    url = native_url(state["video_url"])
    response = client.get(url, headers={**AUTH, "Range": "bytes=7-29"})
    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 7-29/{len(payload)}"
    assert response.content == payload[7:30]
    assert client.get(url, headers={**AUTH, "Range": "bytes=20000-"}).status_code == 416


def test_project_viewer_uses_fixed_reference_and_a_live_read_blocks_cleanup(media_service):
    _, app, client, source = media_service
    Image.new("RGB", (93, 61), "green").save(source / "project.png")
    base, item = add(client, "project.png")
    project = client.post("/api/v1/projects", headers=AUTH, json={"name": "Viewer project"}).json()
    reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH,
        json={"base_revision": 1, "asset_version_id": item["asset_version_id"]}).json()
    project_base = f"/api/v1/projects/{project['id']}/asset-references/{reference['id']}/previews"
    state = prepare(client, project_base)
    assert (state["width"], state["height"]) == (93, 61)
    wrong = project_base.replace(project["id"], "00000000-0000-4000-8000-000000000000")
    assert client.post(wrong + "/viewer", headers=AUTH, json={}).status_code == 404
    _, release = app.state.media_views.acquire(item["asset_version_id"], state["key"])
    from astrophotoflow.modules.data.public import data_busy
    from astrophotoflow.modules.data.media.ownership import assert_no_preview_jobs
    from astrophotoflow.core.errors import ApiError
    try:
        assert data_busy(app.state.database).busy
        with app.state.database.read_session() as session:
            with pytest.raises(ApiError, match="大图预览"):
                assert_no_preview_jobs(session, [item["asset_version_id"]])
    finally:
        release()
    assert not data_busy(app.state.database).busy


@pytest.mark.parametrize("keep_second", [True, False])
def test_running_preparation_tracks_all_consumers_and_retries_after_cancel(media_service, monkeypatch, keep_second):
    from uuid import uuid4
    from astrophotoflow.modules.data.formats.source import PixelSource
    _, app, client, source = media_service
    fits.PrimaryHDU(np.arange(64 * 80, dtype=np.float32).reshape(64, 80)).writeto(source / "shared.fits")
    base, item = add(client, "shared.fits")
    first, second = str(uuid4()), str(uuid4())
    entered, proceed = Event(), Event()
    original = PixelSource.read_fits_region
    def blocked(self, *args):
        entered.set()
        assert proceed.wait(5)
        return original(self, *args)
    monkeypatch.setattr(PixelSource, "read_fits_region", blocked)
    service = app.state.media_views
    one = client.post(base + "/viewer", headers=AUTH, json={"consumer_id": first}).json()
    try:
        assert entered.wait(5)
        state = client.get(base + "/viewer/" + one["key"] + "/status", headers=AUTH).json()
        assert state["phase"] == "preparing"
        two = client.post(base + "/viewer", headers=AUTH, json={"consumer_id": second}).json()
        assert two["key"] == one["key"] and two["phase"] == "preparing"
        future = service.preparing[one["key"]]
        client.delete(base + "/viewer/consumer/" + first, headers=AUTH)
        if not keep_second:
            client.delete(base + "/viewer/consumer/" + second, headers=AUTH)
    finally:
        proceed.set()
    future.result(timeout=5)
    state = service.status(item["asset_version_id"], one["key"])
    assert state.phase is None
    assert state.status == ("available" if keep_second else "failed")
    if keep_second:
        monkeypatch.setattr(PixelSource, "read_fits_region", lambda *args: pytest.fail("valid cache was regenerated"))
    retried = prepare(client, base, {"consumer_id": str(uuid4())})
    assert retried["status"] == "available"
    assert retried["key"] == one["key"]


def test_queued_shared_preparation_survives_one_consumer_closing(media_service):
    from uuid import uuid4
    _, app, client, source = media_service
    Image.new("RGB", (64, 64), "green").save(source / "queued.png")
    base, item = add(client, "queued.png")
    first, second = str(uuid4()), str(uuid4())
    gate, entered = Event(), Event()
    def block():
        entered.set()
        assert gate.wait(5)
    service = app.state.media_views
    running = service.executor.submit(block)
    try:
        assert entered.wait(5)
        one = client.post(base + "/viewer", headers=AUTH, json={"consumer_id": first}).json()
        client.post(base + "/viewer", headers=AUTH, json={"consumer_id": second})
        assert one["phase"] == "queued"
        future = service.preparing[one["key"]]
        client.delete(base + "/viewer/consumer/" + first, headers=AUTH)
        assert not future.cancelled()
        client.delete(base + "/viewer/consumer/" + second, headers=AUTH)
        assert future.cancelled()
        state = service.status(item["asset_version_id"], one["key"])
        assert state.status == "failed" and state.phase is None
    finally:
        gate.set()
        running.result(timeout=5)

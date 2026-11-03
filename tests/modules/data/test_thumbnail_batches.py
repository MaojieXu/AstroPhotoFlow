from time import monotonic, sleep
from uuid import uuid4

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from astrophotoflow.contracts.thumbnails import ThumbnailBatchCreate
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.media.executor import PreviewExecutor
from astrophotoflow.modules.data.media.models import Preview, ThumbnailBatch, ThumbnailBatchItem
from astrophotoflow.modules.data.media.thumbnail_batches import create_thumbnail_batch, retry_thumbnail_items, thumbnail_batch_status
from astrophotoflow.modules.data.media.thumbnail_service import ThumbnailService


@pytest.fixture
def library(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    originals = []
    with database.write_session() as session:
        for position in range(3):
            asset_id, version_id = str(uuid4()), str(uuid4())
            relative = f"objects/{version_id}.fits"
            path = settings.data_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            fits.PrimaryHDU(np.random.default_rng(position).normal(100 + 20 * position, 8, (120, 180)).astype(np.float32)).writeto(path)
            originals.append((asset_id, version_id, path, path.read_bytes()))
            asset = Asset(id=asset_id, name=f"image {position}", scope="shared", role="raw", status="active", revision=1)
            session.add(asset)
            session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
                storage_location=relative, availability="available", capture_snapshot={"parameters": {}},
                scientific_metadata={"format": "fits"}))
            session.flush()
            asset.current_version_id = version_id
            session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=version_id, hdu_index=0,
                hdu_type="PrimaryHDU", header_cards=[], parser_version="test", supported_kind="mono", is_selected=True))
    yield settings, database, originals
    database.close()


def _group(database, name, members):
    dataset_id, version_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        dataset = Dataset(id=dataset_id, name=name, status="active", revision=1)
        session.add(dataset)
        session.flush()
        session.add(DatasetVersion(id=version_id, dataset_id=dataset_id, version_number=1))
        session.flush()
        dataset.current_version_id = version_id
        for position, version in enumerate(members):
            session.add(DatasetMember(id=str(uuid4()), dataset_version_id=version_id,
                asset_version_id=version, position=position))
    return dataset_id, version_id


def _request(target, request_id=None):
    return ThumbnailBatchCreate.model_validate({"request_id": str(request_id or uuid4()), "target": target}, strict=False)


def _preview_ids(database, batch_id):
    with database.read_session() as session:
        return session.scalars(select(ThumbnailBatchItem.preview_id).where(
            ThumbnailBatchItem.batch_id == batch_id).order_by(ThumbnailBatchItem.position)).all()


def test_group_uses_fixed_first_recipe_and_distinct_contexts(library):
    settings, database, images = library
    first_group = _group(database, "first", [images[0][1], images[1][1]])
    second_group = _group(database, "second", [images[2][1], images[1][1]])
    targets = [{"kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1]}
               for group in (first_group, second_group)]
    requests = [_request(target) for target in targets]
    ids = [create_thumbnail_batch(database, request) for request in requests]
    assert create_thumbnail_batch(database, requests[0]) == ids[0]
    with pytest.raises(ApiError) as conflict:
        create_thumbnail_batch(database, _request(targets[1], requests[0].request_id))
    assert conflict.value.code == "REQUEST_ID_CONFLICT"
    entries = [_preview_ids(database, identity) for identity in ids]
    assert entries[0][1] != entries[1][1]
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        for reference, member in entries:
            service._generate(reference)
            service._generate(member)
    with database.read_session() as session:
        first_ref, first_member = [session.get(Preview, value) for value in entries[0]]
        second_ref, second_member = [session.get(Preview, value) for value in entries[1]]
        assert all(row.status == "available" for row in (first_ref, first_member, second_ref, second_member))
        assert first_member.display_parameters["auto_stretch"] == first_ref.display_parameters["auto_stretch"]
        assert second_member.display_parameters["auto_stretch"] == second_ref.display_parameters["auto_stretch"]
        assert first_member.display_parameters["auto_stretch"] != second_member.display_parameters["auto_stretch"]
        for row in (first_ref, first_member, second_ref, second_member):
            with Image.open(settings.data_dir / row.storage_path) as image:
                assert max(image.size) == 100
    assert thumbnail_batch_status(database, ids[0]).state == "completed"
    assert thumbnail_batch_status(database, ids[0]).group_failures == []
    assert all(path.read_bytes() == original for _, _, path, original in images)


def test_unavailable_first_does_not_fall_back_to_second(library):
    settings, database, images = library
    group = _group(database, "group", [images[0][1], images[1][1]])
    request = _request({"kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1]})
    batch = create_thumbnail_batch(database, request)
    first, second = _preview_ids(database, batch)
    images[0][2].unlink()
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service._generate(first)
        service._dispatch()
    status = thumbnail_batch_status(database, batch)
    assert status.state == "needs_attention"
    assert status.failed == 2
    failure, = status.group_failures
    assert str(failure.dataset_version_id) == group[1]
    assert str(failure.reference_asset_version_id) == images[0][1]
    assert failure.code == "FIRST_FRAME_UNAVAILABLE"
    with database.read_session() as session:
        assert failure.error == session.get(Preview, first).error
    paged = thumbnail_batch_status(database, batch, limit=1, offset=1)
    assert len(paged.items) == 1
    assert paged.group_failures == status.group_failures
    with database.read_session() as session:
        assert session.get(Preview, second).error == "First group member has no usable stretch."


def test_append_reuses_first_context_and_changed_first_keeps_historical_cache(library):
    settings, database, images = library
    group_id, initial_id = _group(database, "group", [images[0][1], images[1][1]])
    appended_id, changed_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        session.add_all([DatasetVersion(id=appended_id, dataset_id=group_id, version_number=2),
                         DatasetVersion(id=changed_id, dataset_id=group_id, version_number=3)])
        session.flush()
        for version_id, members in ((appended_id, [images[0][1], images[1][1], images[2][1]]),
                                    (changed_id, [images[2][1], images[1][1]])):
            for position, member in enumerate(members):
                session.add(DatasetMember(id=str(uuid4()), dataset_version_id=version_id,
                    asset_version_id=member, position=position))
    def create(version):
        request = _request({"kind": "dataset", "dataset_id": group_id, "dataset_version_id": version})
        return _preview_ids(database, create_thumbnail_batch(database, request))
    initial, appended, changed = create(initial_id), create(appended_id), create(changed_id)
    assert appended[:2] == initial
    assert changed[1] != initial[1]
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        for item in [*initial, appended[2], *changed]:
            service._generate(item)
    with database.read_session() as session:
        assert all(session.get(Preview, item).status == "available" for item in [*initial, *appended, *changed])
        assert session.get(Preview, initial[1]).display_parameters["reference_version_id"] == images[0][1]
        assert session.get(Preview, changed[1]).display_parameters["reference_version_id"] == images[2][1]


def test_background_http_batch_and_contextual_read(library):
    settings, database, images = library
    group = _group(database, "group", [images[0][1], images[1][1]])
    request = _request({"kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1]})
    headers = {"Authorization": "Bearer thumbnail-test"}
    app = create_app(settings, "thumbnail-test")
    with TestClient(app) as client:
        response = client.post("/api/v1/thumbnail-batches", headers=headers, json=request.model_dump(mode="json"))
        assert response.status_code == 200, response.text
        deadline = monotonic() + 15
        while True:
            status = client.get(f"/api/v1/thumbnail-batches/{request.request_id}", headers=headers).json()
            if status["state"] != "running":
                break
            assert monotonic() < deadline, status
            sleep(.05)
        assert status["state"] == "completed", status
        assert status["available"] == 2
        image = client.get(f"/api/v1/datasets/{group[0]}/versions/{group[1]}/members/{images[1][1]}/thumbnail", headers=headers)
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/jpeg"
        library_page = client.get("/api/v1/library/items", headers=headers).json()
        group_row = next(item for item in library_page["items"] if item["id"] == group[0])
        assert group_row["thumbnail"]["asset_version_id"] == images[0][1]
        assert client.get(f"/api/v1/datasets/{group[0]}/versions/{group[1]}/members/{images[2][1]}/thumbnail", headers=headers).status_code == 404


def test_interrupted_work_recovers_and_failed_group_retries(library):
    settings, database, images = library
    group = _group(database, "group", [images[0][1], images[1][1]])
    request = _request({"kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1]})
    batch = create_thumbnail_batch(database, request)
    first, _ = _preview_ids(database, batch)
    with database.write_session() as session:
        session.get(Preview, first).status = "generating"
    images[0][2].unlink()
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service.start()
        try:
            deadline = monotonic() + 15
            while True:
                status = thumbnail_batch_status(database, batch)
                if status.state != "running":
                    break
                assert monotonic() < deadline
                sleep(.05)
            assert status.failed == 2
            images[0][2].write_bytes(images[0][3])
            retry_thumbnail_items(database, batch, [str(item.id) for item in status.items])
            service._wake.set()
            deadline = monotonic() + 15
            while True:
                status = thumbnail_batch_status(database, batch)
                if status.state != "running":
                    break
                assert monotonic() < deadline
                sleep(.05)
            assert status.state == "completed" and status.available == 2
        finally:
            service.close()


def test_retry_member_recovers_failed_first_without_retrying_other_members(library):
    settings, database, images = library
    group = _group(database, "group", [image[1] for image in images])
    batch = create_thumbnail_batch(database, _request({
        "kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1],
    }))
    first, second, third = _preview_ids(database, batch)
    images[0][2].unlink()
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service._generate(first)
        service._dispatch()
        failed = thumbnail_batch_status(database, batch)
        assert failed.failed == 3
        images[0][2].write_bytes(images[0][3])
        retry_thumbnail_items(database, batch, [str(failed.items[1].id)])
        queued = thumbnail_batch_status(database, batch)
        assert queued.queued == 2 and queued.failed == 1
        assert queued.group_failures == []
        with database.read_session() as session:
            assert session.get(Preview, first).status == "queued"
            assert session.get(Preview, second).status == "queued"
            assert session.get(Preview, third).status == "failed"
        service._generate(first)
        service._generate(second)
    result = thumbnail_batch_status(database, batch)
    assert result.available == 2 and result.failed == 1
    assert result.group_failures == []
    assert all(path.read_bytes() == original for _, _, path, original in images)


def test_invalid_retry_does_not_queue_first_dependency(library):
    settings, database, images = library
    group = _group(database, "group", [images[0][1], images[1][1]])
    batch = create_thumbnail_batch(database, _request({
        "kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1],
    }))
    first, second = _preview_ids(database, batch)
    images[0][2].unlink()
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service._generate(first)
        service._dispatch()
    failed = thumbnail_batch_status(database, batch)
    with pytest.raises(ApiError) as error:
        retry_thumbnail_items(database, batch, [str(failed.items[1].id), str(uuid4())])
    assert error.value.code == "THUMBNAIL_NOT_RETRYABLE"
    with database.read_session() as session:
        assert session.get(Preview, first).status == "failed"
        assert session.get(Preview, second).status == "failed"


def test_retry_reports_missing_first_cache_record_without_partial_update(library):
    _, database, images = library
    group = _group(database, "group", [images[0][1], images[1][1]])
    batch = create_thumbnail_batch(database, _request({
        "kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1],
    }))
    first, second = _preview_ids(database, batch)
    with database.write_session() as session:
        session.delete(session.get(Preview, first))
        session.get(Preview, second).status = "failed"
    status = thumbnail_batch_status(database, batch)
    assert status.group_failures[0].code == "FIRST_FRAME_UNAVAILABLE"
    with pytest.raises(ApiError) as error:
        retry_thumbnail_items(database, batch, [str(status.items[1].id)])
    assert error.value.code == "THUMBNAIL_REFERENCE_MISSING"
    with database.read_session() as session:
        assert session.get(Preview, second).status == "failed"


@pytest.mark.parametrize("grouped", [False, True])
def test_missing_cache_is_repaired_with_existing_batch_and_frozen_stretch(library, grouped):
    settings, database, images = library
    if grouped:
        group = _group(database, "group", [images[0][1], images[1][1]])
        target = {"kind": "dataset", "dataset_id": group[0], "dataset_version_id": group[1]}
    else:
        target = {"kind": "asset", "asset_id": images[0][0], "asset_version_id": images[0][1]}
    batch = create_thumbnail_batch(database, _request(target))
    identities = _preview_ids(database, batch)
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service._ensure_auto(target)
        for identity in identities:
            service._generate(identity)
        with database.read_session() as session:
            rows = [session.get(Preview, identity) for identity in identities]
            frozen = [row.display_parameters for row in rows]
            paths = [settings.data_dir / row.storage_path for row in rows]
            batches_before = session.scalar(select(func.count()).select_from(ThumbnailBatch))
        for path in paths:
            path.unlink()
        service._ensure_auto(target)
        service._reconcile_cache()
        service._reconcile_cache()
        assert thumbnail_batch_status(database, batch).queued == len(identities)
        with database.read_session() as session:
            assert session.scalar(select(func.count()).select_from(ThumbnailBatch)) == batches_before
            assert [session.get(Preview, identity).display_parameters for identity in identities] == frozen
        for identity in identities:
            service._generate(identity)
    assert thumbnail_batch_status(database, batch).state == "completed"
    assert _preview_ids(database, batch) == identities
    assert all(path.is_file() for path in paths)
    with database.read_session() as session:
        assert [session.get(Preview, identity).display_parameters for identity in identities] == frozen
    assert all(path.read_bytes() == original for _, _, path, original in images)


def test_cache_reconciliation_respects_maintenance_pause(library):
    settings, database, images = library
    batch = create_thumbnail_batch(database, _request({
        "kind": "asset", "asset_id": images[0][0], "asset_version_id": images[0][1],
    }))
    identity, = _preview_ids(database, batch)
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service._generate(identity)
        with database.read_session() as session:
            path = settings.data_dir / session.get(Preview, identity).storage_path
        path.unlink()
        service.pause()
        service._reconcile_cache()
        assert thumbnail_batch_status(database, batch).available == 1
        service.resume()
        service._reconcile_cache()
        assert thumbnail_batch_status(database, batch).queued == 1


def test_cache_reconciliation_keeps_different_historical_group_contexts(library):
    settings, database, images = library
    dataset_id, initial_id = _group(database, "group", [images[0][1], images[1][1]])
    changed_id = str(uuid4())
    with database.write_session() as session:
        session.add(DatasetVersion(id=changed_id, dataset_id=dataset_id, version_number=2))
        session.flush()
        session.get(Dataset, dataset_id).current_version_id = changed_id
        for position, version_id in enumerate([images[2][1], images[1][1]]):
            session.add(DatasetMember(id=str(uuid4()), dataset_version_id=changed_id,
                asset_version_id=version_id, position=position))
    batches = [create_thumbnail_batch(database, _request({
        "kind": "dataset", "dataset_id": dataset_id, "dataset_version_id": version_id,
    })) for version_id in [initial_id, changed_id]]
    contexts = [_preview_ids(database, batch) for batch in batches]
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        for identities in contexts:
            for identity in identities:
                service._generate(identity)
        old_member, current_member = contexts[0][1], contexts[1][1]
        with database.read_session() as session:
            historical = session.get(Preview, old_member)
            old_recipe = historical.display_parameters
            new_recipe = session.get(Preview, current_member).display_parameters
            (settings.data_dir / historical.storage_path).unlink()
        service._reconcile_cache()
        with database.read_session() as session:
            assert session.get(Preview, old_member).status == "queued"
            assert session.get(Preview, current_member).status == "available"
        service._generate(old_member)
    with database.read_session() as session:
        assert session.get(Preview, old_member).display_parameters == old_recipe
        assert session.get(Preview, current_member).display_parameters == new_recipe
        assert old_recipe["reference_version_id"] != new_recipe["reference_version_id"]


def test_thumbnail_rejects_original_changed_before_generation(library):
    settings, database, images = library
    asset_id, version_id, original, data = images[0]
    with database.write_session() as session:
        session.get(AssetVersion, version_id).byte_size = len(data)
    original.write_bytes(data + b'changed')
    batch = create_thumbnail_batch(database, _request({"kind": "asset", "asset_id": asset_id, "asset_version_id": version_id}))
    preview_id = _preview_ids(database, batch)[0]
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        service._generate(preview_id)
    with database.read_session() as session:
        assert session.get(Preview, preview_id).status == 'failed'


def test_thumbnail_rejects_same_size_original_replacement(library):
    from astrophotoflow.modules.data.science.files import hash_file

    settings, database, images = library
    asset_id, version_id, original, data = images[0]
    original_hash, _, _ = hash_file(original)
    with database.write_session() as session:
        version = session.get(AssetVersion, version_id)
        version.byte_size = len(data)
        version.content_hash = original_hash
    original.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    batch = create_thumbnail_batch(database, _request({"kind": "asset", "asset_id": asset_id, "asset_version_id": version_id}))
    preview_id = _preview_ids(database, batch)[0]
    with PreviewExecutor(1) as executor:
        ThumbnailService(database, settings, executor)._generate(preview_id)
    with database.read_session() as session:
        assert session.get(Preview, preview_id).status == 'failed'


def test_thumbnail_shutdown_during_hash_requeues(library, monkeypatch):
    from astrophotoflow.modules.data.media import thumbnail_service
    from astrophotoflow.modules.data.science.files import hash_file

    settings, database, images = library
    asset_id, version_id, original, data = images[0]
    expected_hash, _, _ = hash_file(original)
    with database.write_session() as session:
        version = session.get(AssetVersion, version_id)
        version.byte_size = len(data)
        version.content_hash = expected_hash
    batch = create_thumbnail_batch(database, _request({"kind": "asset", "asset_id": asset_id, "asset_version_id": version_id}))
    preview_id = _preview_ids(database, batch)[0]
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        def interrupted(_path, _destination, cancelled):
            service._stop.set()
            assert cancelled()
            raise ApiError(409, 'CANCELLED', 'cancelled')
        monkeypatch.setattr(thumbnail_service, 'read_hash_and_copy', interrupted)
        service._generate(preview_id)
    with database.read_session() as session:
        preview = session.get(Preview, preview_id)
        assert preview.status == 'queued' and preview.error is None

def test_thumbnail_shutdown_during_render_does_not_publish(library, monkeypatch):
    from astrophotoflow.modules.data.media import thumbnail_service
    settings, database, images = library
    asset_id, version_id, _original, _data = images[0]
    batch = create_thumbnail_batch(database, _request({"kind": "asset", "asset_id": asset_id, "asset_version_id": version_id}))
    preview_id = _preview_ids(database, batch)[0]
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        def stopped_render(*_args, **_kwargs):
            service._stop.set()
            return Image.new('RGB', (1, 1)), {}
        monkeypatch.setattr(thumbnail_service, 'render_thumbnail', stopped_render)
        service._generate(preview_id)
    with database.read_session() as session:
        preview = session.get(Preview, preview_id)
        assert preview.status == 'queued' and not preview.storage_path

def test_thumbnail_stop_serializes_with_final_publication(library, monkeypatch):
    from threading import Event, Thread
    from astrophotoflow.modules.data.media import thumbnail_service
    settings, database, images = library
    asset_id, version_id, _original, _data = images[0]
    batch = create_thumbnail_batch(database, _request({"kind": "asset", "asset_id": asset_id, "asset_version_id": version_id}))
    preview_id = _preview_ids(database, batch)[0]
    entered, release, stopped = Event(), Event(), Event()
    original_replace = thumbnail_service.os.replace
    def delayed_replace(source, destination):
        entered.set()
        assert release.wait(10)
        original_replace(source, destination)
    monkeypatch.setattr(thumbnail_service.os, 'replace', delayed_replace)
    with PreviewExecutor(1) as executor:
        service = ThumbnailService(database, settings, executor)
        generator = Thread(target=service._generate, args=(preview_id,))
        generator.start()
        try:
            assert entered.wait(10)
            stopper = Thread(target=lambda: (service.close(), stopped.set()))
            stopper.start()
            assert not stopped.wait(0.2)
            assert not service._stop.is_set()
        finally:
            release.set()
            generator.join(timeout=10)
        stopper.join(timeout=10)
        assert not generator.is_alive() and not stopper.is_alive() and stopped.is_set()
    with database.read_session() as session:
        assert session.get(Preview, preview_id).status == 'available'
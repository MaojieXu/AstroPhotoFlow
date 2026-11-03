from astrophotoflow.modules.data.assets.metadata import parameter_columns, set_asset_parameters
import json
from uuid import uuid4

import pytest
import blake3
import numpy as np
from astropy.io import fits
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from astrophotoflow.contracts.inputs import CanvasDataRequest
from astrophotoflow.contracts.inputs import DatasetInputReference, ScienceSelection
from astrophotoflow.modules.data.public import resolve_canvas_inputs
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.database.db import Database
from astrophotoflow.contracts.data_nodes import ScienceReference
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval


@pytest.fixture
def canvas_library(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    database = Database(settings.database_path)
    Base.metadata.create_all(database.engine)
    asset_ids, version_ids = [], []
    group_id, group_version_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        for index in range(3):
            asset_id, version_id = str(uuid4()), str(uuid4())
            asset_ids.append(asset_id)
            version_ids.append(version_id)
            session.add(Asset(id=asset_id, name=f"frame-{index}.fits", scope="shared", role="raw", **parameter_columns({"gain": 0})))
            session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed", storage_location=f"objects/{index}.fits", byte_size=100, content_hash="b3:" + "a" * 64, availability="available"))
        session.flush()
        session.add(Dataset(id=group_id, name="Night", status="active"))
        session.flush()
        session.add(DatasetVersion(id=group_version_id, dataset_id=group_id, version_number=1))
        session.flush()
        for position, version_id in enumerate(version_ids):
            session.add(DatasetMember(id=str(uuid4()), dataset_version_id=group_version_id, asset_version_id=version_id, position=position))
    app = create_app(settings, "canvas-test")
    with TestClient(app, headers={"Authorization": "Bearer canvas-test"}) as client:
        yield client, database, asset_ids, version_ids, group_id, group_version_id
    database.close()


def test_asset_canvas_reference_is_fixed_and_contains_no_preview_or_path(canvas_library):
    client, _, assets, versions, _, _ = canvas_library
    response = client.post("/api/v1/library/canvas-data", json={"entry_type": "asset", "id": assets[0], "version_id": versions[0]})
    assert response.status_code == 200
    value = response.json()
    assert value == {"native_type": "APF_DATA_REFERENCE", "title": "frame-0.fits", "reference": {
        "kind": "asset_version", "asset_version_id": versions[0], "binding_version_id": None,
        "selection": {"kind": "whole_file", "hdu_index": None},
    }}
    assert TypeAdapter(ScienceReference).validate_json(json.dumps(value["reference"])).model_dump(mode="json") == value["reference"]


@pytest.mark.parametrize("indexes", [None, [0, 2]])
def test_dataset_canvas_reference_preserves_fixed_members_and_order(canvas_library, indexes):
    client, _, _, versions, group, fixed = canvas_library
    body = {"entry_type": "dataset", "id": group, "version_id": fixed}
    if indexes is not None:
        body["member_indexes"] = indexes
    response = client.post("/api/v1/library/canvas-data", json=body)
    assert response.status_code == 200
    reference = response.json()["reference"]
    assert reference["dataset_version_id"] == fixed
    positions = list(range(3)) if indexes is None else indexes
    assert [member["member_index"] for member in reference["members"]] == positions
    assert [member["asset_version_id"] for member in reference["members"]] == [versions[index] for index in positions]


@pytest.mark.parametrize("availability", ["unknown", "changed", "missing"])
def test_unready_member_does_not_silently_shrink_group(canvas_library, availability):
    client, database, _, versions, group, fixed = canvas_library
    with database.write_session() as session:
        session.get(AssetVersion, versions[1]).availability = availability
    response = client.post("/api/v1/library/canvas-data", json={"entry_type": "dataset", "id": group, "version_id": fixed})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_UNAVAILABLE"


def test_version_owner_and_member_range_are_checked(canvas_library):
    client, _, assets, versions, group, fixed = canvas_library
    assert client.post("/api/v1/library/canvas-data", json={"entry_type": "asset", "id": assets[0], "version_id": versions[1]}).status_code == 404
    assert client.post("/api/v1/library/canvas-data", json={"entry_type": "dataset", "id": group, "version_id": fixed, "member_indexes": [9]}).status_code == 422
    assert client.post("/api/v1/library/canvas-data", json={"entry_type": "asset", "id": assets[0], "version_id": versions[0]}, headers={"Authorization": "Bearer wrong"}).status_code == 401


@pytest.mark.parametrize("entry_type,indexes", [("asset", [0]), ("dataset", []), ("dataset", [-1]), ("dataset", [1, 0]), ("dataset", [0, 0])])
def test_member_selection_rejects_ambiguous_ranges(entry_type, indexes):
    with pytest.raises(ValidationError):
        CanvasDataRequest(entry_type=entry_type, id=uuid4(), version_id=uuid4(), member_indexes=indexes)


def test_science_reference_contract_rejects_preview_payload():
    with pytest.raises(ValidationError):
        TypeAdapter(ScienceReference).validate_json(json.dumps({"kind": "preview", "url": "thumbnail.jpg"}))


def test_native_siril_inputs_resolve_complete_fixed_members_and_preserve_gain_zero(canvas_library, tmp_path):
    client, database, _, versions, _, fixed = canvas_library
    settings = client.app.state.settings
    with database.write_session() as session:
        for index, version_id in enumerate(versions):
            path = settings.data_dir / f"objects/{index}.fits"
            path.parent.mkdir(parents=True, exist_ok=True)
            fits.writeto(path, np.arange(48, dtype=np.float32).reshape(6, 8) + index)
            version = session.get(AssetVersion, version_id)
            version.byte_size = path.stat().st_size
            version.content_hash = "blake3:" + blake3.blake3(path.read_bytes()).hexdigest()
            version.scientific_metadata = {"format": "fits", "selected_hdu": 0}
    reference = DatasetInputReference(kind="dataset_version", dataset_version_id=fixed, members=[
        {"member_index": index, "asset_version_id": versions[index], "selection": ScienceSelection(kind="whole_file")}
        for index in [0, 2]
    ])
    resolved = resolve_canvas_inputs(database, settings, reference, run_directory=tmp_path / "run-inputs")
    assert [str(item.asset_version_id) for item in resolved.items] == [versions[0], versions[2]]
    assert all(item.parameters["gain"] == 0 and item.format == "fits" for item in resolved.items)
    assert all(item.read_path.name.endswith(".fits") and item.byte_size > 0 for item in resolved.items)
    reference.members.reverse()
    with pytest.raises(ApiError, match="顺序"):
        resolve_canvas_inputs(database, settings, reference, run_directory=tmp_path / "other-inputs")


def test_live_siril_sample_reuses_linear_data_and_participates_in_cleanup_protection(canvas_library):
    from astrophotoflow.contracts.software import BundlePreviewRequest
    from astrophotoflow.modules.data.public import prepare_bundle_sample
    from astrophotoflow.modules.data.media.ownership import assert_no_preview_jobs, owned_preview_locations

    client, database, _, versions, _, _ = canvas_library
    settings = client.app.state.settings
    source = settings.data_dir / "objects/0.fits"
    source.parent.mkdir(parents=True, exist_ok=True)
    pixels = np.linspace(0, 0.1, 48, dtype=np.float32).reshape(6, 8)
    fits.writeto(source, pixels)
    before = source.read_bytes()
    with database.write_session() as session:
        version = session.get(AssetVersion, versions[0])
        version.byte_size = source.stat().st_size
        version.content_hash = "blake3:" + blake3.blake3(before).hexdigest()
        version.scientific_metadata = {"format": "fits", "selected_hdu": 0}
    body = BundlePreviewRequest(reference={"kind": "asset_version", "asset_version_id": versions[0], "selection": {"kind": "whole_file"}},
                              member_index=0, consumer_id=uuid4(), generation=1, package_id="siril", operation_id="autostretch", parameters={"targetbg":0})
    cache = client.app.state.media_views.cache
    sample = prepare_bundle_sample(database, settings, cache, body, lambda: None)
    try:
        np.testing.assert_array_equal(fits.getdata(sample.path), pixels)
        with database.read_session() as session:
            with pytest.raises(ApiError) as active:
                assert_no_preview_jobs(session, [versions[0]])
            assert active.value.code == "PREVIEW_ACTIVE"
            row = session.get(Preview, sample.row_id)
            assert any(path.endswith("sample.fit") for path in owned_preview_locations(row, settings))
        stamp = sample.path.stat().st_mtime_ns
    finally:
        sample.close()
    second = prepare_bundle_sample(database, settings, cache, body.model_copy(update={"generation": 2, "targetbg": 0.4}), lambda: None)
    try:
        assert second.path.stat().st_mtime_ns == stamp
        assert second.row_id == sample.row_id
        assert source.read_bytes() == before
    finally:
        second.close()


def test_later_group_publication_does_not_expand_the_requested_version(canvas_library):
    client, database, _, versions, group, fixed = canvas_library
    with database.write_session() as session:
        later = DatasetVersion(id=str(uuid4()), dataset_id=group, version_number=2)
        session.add(later)
        session.flush()
        session.get(Dataset, group).current_version_id = later.id
    response = client.post("/api/v1/library/canvas-data", json={"entry_type": "dataset", "id": group, "version_id": fixed})
    assert response.status_code == 200
    assert [member["asset_version_id"] for member in response.json()["reference"]["members"]] == versions


def test_removed_library_entry_cannot_be_added_from_a_stale_row(canvas_library):
    client, database, assets, versions, _, _ = canvas_library
    with database.write_session() as session:
        session.add(LibraryEntryRemoval(entry_type="asset", entry_id=assets[0]))
    assert client.post("/api/v1/library/canvas-data", json={"entry_type": "asset", "id": assets[0], "version_id": versions[0]}).status_code == 404


def test_parsing_or_preview_problem_does_not_substitute_the_scientific_original(canvas_library):
    client, database, assets, versions, _, _ = canvas_library
    with database.write_session() as session:
        session.get(AssetVersion, versions[0]).scientific_metadata = {"parse_error": "Unsupported header"}
    response = client.post("/api/v1/library/canvas-data", json={"entry_type": "asset", "id": assets[0], "version_id": versions[0]})
    assert response.status_code == 200
    assert response.json()["reference"]["asset_version_id"] == versions[0]


def test_inspect_uses_original_dimensions_and_current_parameters_without_reading_files(canvas_library):
    client, database, assets, versions, _, _ = canvas_library
    camera_id = str(uuid4())
    with database.write_session() as session:
        session.add(Equipment(id=camera_id, kind="camera", name="Camera", specs={}))
        session.flush()
        set_asset_parameters(session.get(Asset, assets[0]), {"camera_id": camera_id, "gain": 0, "offset": 0, "exposure_seconds": 0, "sensor_temperature_c": 0})
        version = session.get(AssetVersion, versions[0])
        version.capture_snapshot = {"parameters": {"gain": 100}}
        session.get(Asset, assets[0]).current_version_id = versions[0]
        version.scientific_metadata = {"format": "fits"}
        session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=versions[0], hdu_index=0, hdu_type="PRIMARY", shape=[4000, 6000], bitpix=-32, pixel_type="float32", header_cards=[], parser_version="test", supported_kind="mono", is_selected=True))
        session.add(Preview(id=str(uuid4()), asset_version_id=versions[0], hdu_index=0, size="thumbnail", width=60, height=40, storage_path="previews/missing-test.jpg", display_parameters={}, algorithm_version="test", status="available"))
    reference = {"kind": "asset_version", "asset_version_id": versions[0], "selection": {"kind": "whole_file"}}
    response = client.post("/api/v1/library/canvas-data/inspect", json={"reference": reference})
    assert response.status_code == 200
    value = response.json()
    assert (value["width"], value["height"], value["bitpix"]) == (6000, 4000, -32)
    assert value["parameters"]["gain"] == value["parameters"]["offset"] == 0
    assert value["equipment"]["camera"] == "Camera"
    assert value["preview_status"] == "available"
    assert value["view_base"] == f"/astrophotoflow/api/v1/library/assets/{assets[0]}/versions/{versions[0]}/previews"
    assert versions[0] in value["preview_url"]
    listing = client.get("/api/v1/library/items?limit=50&offset=0")
    assert listing.status_code == 200, listing.text
    thumbnails = [item["thumbnail"] for item in listing.json()["items"] if item["thumbnail"]]
    assert thumbnails
    assert thumbnails[0]["asset_version_id"] == versions[0]
    assert thumbnails[0]["view_base"] == value["view_base"]
    assert not (database.path.parent / "objects/0.fits").exists()


def test_inspect_group_index_selects_within_the_fixed_subset(canvas_library):
    client, _, assets, versions, group, fixed = canvas_library
    reference = client.post("/api/v1/library/canvas-data", json={"entry_type": "dataset", "id": group, "version_id": fixed, "member_indexes": [0, 2]}).json()["reference"]
    response = client.post("/api/v1/library/canvas-data/inspect", json={"reference": reference, "member_index": 1})
    assert response.status_code == 200
    value = response.json()
    assert (value["total"], value["member_index"], value["asset_id"], value["asset_version_id"]) == (2, 1, assets[2], versions[2])
    assert value["width"] is None
    assert value["preview_status"] == "not_ready"
    assert value["view_base"] == f"/astrophotoflow/api/v1/library/assets/{assets[2]}/versions/{versions[2]}/previews"
    assert client.post("/api/v1/library/canvas-data/inspect", json={"reference": reference, "member_index": 2}).status_code == 422
    reference["members"][1]["asset_version_id"] = versions[1]
    assert client.post("/api/v1/library/canvas-data/inspect", json={"reference": reference}).status_code == 422


def test_inspect_preserves_reference_when_original_is_missing(canvas_library):
    client, database, _, versions, _, _ = canvas_library
    with database.write_session() as session:
        session.get(AssetVersion, versions[0]).availability = "missing"
    response = client.post("/api/v1/library/canvas-data/inspect", json={"reference": {"kind": "asset_version", "asset_version_id": versions[0], "selection": {"kind": "whole_file"}}})
    assert response.status_code == 200
    assert response.json()["availability"] == "missing"
    assert response.json()["preview_status"] == "not_ready"
    assert response.json()["asset_version_id"] == versions[0]


@pytest.mark.parametrize("shape,cards,expected", [
    ([3, 4000, 6000], [{"keyword": "NAXIS3", "value": 3}, {"keyword": "CTYPE3", "value": "RGB"}], (6000, 4000)),
    ([4000, 6000, 3], [{"keyword": "NAXIS1", "value": 3}, {"keyword": "CTYPE1", "value": "RGB"}], (6000, 4000)),
])
def test_inspect_rgb_dimensions_follow_the_existing_fits_axis_rules(canvas_library, shape, cards, expected):
    client, database, _, versions, _, _ = canvas_library
    with database.write_session() as session:
        session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=versions[0], hdu_index=0, hdu_type="PRIMARY", shape=shape, header_cards=cards, parser_version="test", supported_kind="rgb", is_selected=True))
    response = client.post("/api/v1/library/canvas-data/inspect", json={"reference": {"kind": "asset_version", "asset_version_id": versions[0], "selection": {"kind": "whole_file"}}})
    assert response.status_code == 200
    assert (response.json()["width"], response.json()["height"]) == expected

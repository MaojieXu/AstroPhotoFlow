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
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.core.database.base import Base
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

@pytest.fixture
def canvas_library(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path, ('http://127.0.0.1:8188',), workspace=tmp_path)
    database = Database(settings.database_path)
    Base.metadata.create_all(database.engine)
    asset_ids = []
    group_id, = (str(uuid4()),)
    with database.write_session() as session:
        for index in range(3):
            asset_id, = (str(uuid4()),)
            asset_ids.append(asset_id)
            session.add(Asset(id=asset_id, name=f'frame-{index}.fits', scope='shared', role='raw', frame_class='subframe', frame_type='light', **parameter_columns({'gain': 0}), storage_mode='managed', storage_location=f'objects/{index}.fits', byte_size=100, content_hash='b3:' + 'a' * 64, availability='available'))
            session.flush()
        session.flush()
        session.add(Dataset(id=group_id, name='Night', status='active'))
        session.flush()
        session.flush()
        for position, asset_id in enumerate(asset_ids):
            session.add(DatasetMember(id=str(uuid4()), dataset_id=group_id, asset_id=asset_id, position=position))
    app = create_app(settings, 'canvas-test')
    with TestClient(app, headers={'Authorization': 'Bearer canvas-test'}) as client:
        yield (client, database, asset_ids, group_id)
    database.close()

def test_asset_canvas_reference_is_fixed_and_contains_no_preview_or_path(canvas_library):
    client, _, assets, _ = canvas_library
    response = client.post('/api/v1/library/canvas-data', json={'entry_type': 'asset', 'id': assets[0]})
    assert response.status_code == 200
    value = response.json()
    assert value == {'native_type': 'APF_DATA_REFERENCE', 'title': 'frame-0.fits', 'reference': {'kind': 'asset', 'asset_id': assets[0], 'selection': {'kind': 'whole_file', 'hdu_index': None}}}
    assert TypeAdapter(ScienceReference).validate_json(json.dumps(value['reference'])).model_dump(mode='json') == value['reference']

@pytest.mark.parametrize('indexes', [None, [0, 2], [2, 0]])
def test_dataset_canvas_reference_preserves_fixed_members_and_order(canvas_library, indexes):
    client, _, versions, group = canvas_library
    body = {'entry_type': 'dataset', 'id': group}
    if indexes is not None:
        body['asset_ids'] = [versions[index] for index in indexes]
    response = client.post('/api/v1/library/canvas-data', json=body)
    assert response.status_code == 200
    reference = response.json()['reference']
    assert reference['dataset_id'] == group
    positions = list(range(3)) if indexes is None else sorted(indexes)
    assert reference['asset_ids'] == (None if indexes is None else [versions[index] for index in positions])

@pytest.mark.parametrize('availability', ['unknown', 'changed', 'missing'])
def test_unready_member_does_not_silently_shrink_group(canvas_library, availability):
    client, database, versions, group = canvas_library
    with database.write_session() as session:
        session.get(Asset, versions[1]).availability = availability
    response = client.post('/api/v1/library/canvas-data', json={'entry_type': 'dataset', 'id': group})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'SOURCE_UNAVAILABLE'

def test_missing_asset_and_member_range_are_checked(canvas_library):
    client, _, assets, group = canvas_library
    assert client.post('/api/v1/library/canvas-data', json={'entry_type': 'asset', 'id': str(uuid4())}).status_code == 404
    assert client.post('/api/v1/library/canvas-data', json={'entry_type': 'dataset', 'id': group, 'asset_ids': [str(uuid4())]}).status_code == 422
    assert client.post('/api/v1/library/canvas-data', json={'entry_type': 'asset', 'id': assets[0]}, headers={'Authorization': 'Bearer wrong'}).status_code == 401

@pytest.mark.parametrize('entry_type,indexes', [('asset', [uuid4()]), ('dataset', []), ('dataset', ['invalid-id']), ('dataset', ['00000000-0000-4000-8000-000000000001'] * 2)])
def test_member_selection_rejects_ambiguous_ranges(entry_type, indexes):
    with pytest.raises(ValidationError):
        CanvasDataRequest(entry_type=entry_type, id=uuid4(), asset_ids=indexes)

def test_science_reference_contract_rejects_preview_payload():
    with pytest.raises(ValidationError):
        TypeAdapter(ScienceReference).validate_json(json.dumps({'kind': 'preview', 'url': 'thumbnail.jpg'}))

def test_native_siril_inputs_resolve_complete_fixed_members_and_preserve_gain_zero(canvas_library, tmp_path):
    client, database, versions, fixed = canvas_library
    settings = client.app.state.settings
    with database.write_session() as session:
        for index, version_id in enumerate(versions):
            path = settings.data_dir / f'objects/{index}.fits'
            path.parent.mkdir(parents=True, exist_ok=True)
            fits.writeto(path, np.arange(48, dtype=np.float32).reshape(6, 8) + index)
            version = session.get(Asset, version_id)
            version.byte_size = path.stat().st_size
            version.content_hash = 'blake3:' + blake3.blake3(path.read_bytes()).hexdigest()
            version.scientific_metadata = {'format': 'fits', 'selected_hdu': 0}
    reference = DatasetInputReference(kind='dataset', dataset_id=fixed, asset_ids=[versions[index] for index in [0, 2]])
    resolved = resolve_canvas_inputs(database, settings, reference, run_directory=tmp_path / 'run-inputs')
    assert [str(item.asset_id) for item in resolved.items] == [versions[0], versions[2]]
    assert all((item.parameters['gain'] == 0 and item.format == 'fits' for item in resolved.items))
    assert all((item.read_path.name.endswith('.fits') and item.byte_size > 0 for item in resolved.items))
    reference.asset_ids.reverse()
    reordered = resolve_canvas_inputs(database, settings, reference, run_directory=tmp_path / 'other-inputs')
    assert [item.asset_id for item in reordered.items] == [item.asset_id for item in resolved.items]

def test_live_siril_sample_reuses_linear_data_and_participates_in_cleanup_protection(canvas_library):
    from astrophotoflow.contracts.software import BundlePreviewRequest
    from astrophotoflow.modules.data.public import prepare_bundle_sample
    from astrophotoflow.modules.data.media.ownership import assert_no_preview_jobs, owned_preview_locations
    client, database, versions, _ = canvas_library
    settings = client.app.state.settings
    source = settings.data_dir / 'objects/0.fits'
    source.parent.mkdir(parents=True, exist_ok=True)
    pixels = np.linspace(0, 0.1, 48, dtype=np.float32).reshape(6, 8)
    fits.writeto(source, pixels)
    before = source.read_bytes()
    with database.write_session() as session:
        version = session.get(Asset, versions[0])
        version.byte_size = source.stat().st_size
        version.content_hash = 'blake3:' + blake3.blake3(before).hexdigest()
        version.scientific_metadata = {'format': 'fits', 'selected_hdu': 0}
    body = BundlePreviewRequest(reference={'kind': 'asset', 'asset_id': versions[0], 'selection': {'kind': 'whole_file'}}, member_index=0, consumer_id=uuid4(), generation=1, package_id='siril', operation_id='autostretch', parameters={'targetbg': 0})
    cache = client.app.state.media_views.cache
    sample = prepare_bundle_sample(database, settings, cache, body, lambda: None)
    try:
        np.testing.assert_array_equal(fits.getdata(sample.path), pixels)
        with database.read_session() as session:
            with pytest.raises(ApiError) as active:
                assert_no_preview_jobs(session, [versions[0]])
            assert active.value.code == 'PREVIEW_ACTIVE'
            row = session.get(Preview, sample.row_id)
            assert any((path.endswith('sample.fit') for path in owned_preview_locations(row, settings)))
        stamp = sample.path.stat().st_mtime_ns
    finally:
        sample.close()
    second = prepare_bundle_sample(database, settings, cache, body.model_copy(update={'generation': 2, 'targetbg': 0.4}), lambda: None)
    try:
        assert second.path.stat().st_mtime_ns == stamp
        assert second.row_id == sample.row_id
        assert source.read_bytes() == before
    finally:
        second.close()

def test_removed_library_entry_cannot_be_added_from_a_stale_row(canvas_library):
    client, database, assets, _ = canvas_library
    with database.write_session() as session:
        session.add(LibraryEntryRemoval(entry_type='asset', entry_id=assets[0]))
    assert client.post('/api/v1/library/canvas-data', json={'entry_type': 'asset', 'id': str(uuid4())}).status_code == 404

def test_parsing_or_preview_problem_does_not_substitute_the_scientific_original(canvas_library):
    client, database, assets, _ = canvas_library
    with database.write_session() as session:
        session.get(Asset, assets[0]).scientific_metadata = {'parse_error': 'Unsupported header'}
    response = client.post('/api/v1/library/canvas-data', json={'entry_type': 'asset', 'id': assets[0]})
    assert response.status_code == 200
    assert response.json()['reference']['asset_id'] == assets[0]

def test_inspect_uses_original_dimensions_and_current_parameters_without_reading_files(canvas_library):
    client, database, assets, _ = canvas_library
    camera_id = str(uuid4())
    with database.write_session() as session:
        session.add(Equipment(id=camera_id, kind='camera', name='Camera', specs={}))
        session.flush()
        set_asset_parameters(session.get(Asset, assets[0]), {'camera_id': camera_id, 'gain': 0, 'offset': 0, 'exposure_seconds': 0, 'sensor_temperature_c': 0})
        version = session.get(Asset, assets[0])
        version.capture_snapshot = {'parameters': {'gain': 100}}
        version.scientific_metadata = {'format': 'fits'}
        session.add(FitsHduMetadata(id=str(uuid4()), asset_id=assets[0], hdu_index=0, hdu_type='PRIMARY', shape=[4000, 6000], bitpix=-32, pixel_type='float32', header_cards=[], parser_version='test', supported_kind='mono', is_selected=True))
        session.add(Preview(id=str(uuid4()), asset_id=assets[0], hdu_index=0, size='thumbnail', width=60, height=40, storage_path='previews/missing-test.jpg', display_parameters={}, algorithm_version='test', status='available'))
    reference = {'kind': 'asset', 'asset_id': assets[0], 'selection': {'kind': 'whole_file'}}
    response = client.post('/api/v1/library/canvas-data/inspect', json={'reference': reference})
    assert response.status_code == 200
    value = response.json()
    assert (value['width'], value['height'], value['bitpix']) == (6000, 4000, -32)
    assert value['parameters']['gain'] == value['parameters']['offset'] == 0
    assert value['equipment']['camera'] == 'Camera'
    assert value['preview_status'] == 'available'
    assert value['view_base'] == f'/astrophotoflow/api/v1/library/assets/{assets[0]}/previews'
    assert assets[0] in value['preview_url']
    listing = client.get('/api/v1/library/items?limit=50&offset=0')
    assert listing.status_code == 200, listing.text
    thumbnails = [item['thumbnail'] for item in listing.json()['items'] if item['thumbnail']]
    assert thumbnails
    assert thumbnails[0]['asset_id'] == assets[0]
    assert thumbnails[0]['view_base'] == value['view_base']
    assert not (database.path.parent / 'objects/0.fits').exists()

def test_inspect_group_index_selects_within_the_fixed_subset(canvas_library):
    client, _, assets, group = canvas_library
    reference = client.post('/api/v1/library/canvas-data', json={'entry_type': 'dataset', 'id': group, 'asset_ids': [assets[0], assets[2]]}).json()['reference']
    response = client.post('/api/v1/library/canvas-data/inspect', json={'reference': reference, 'member_index': 1})
    assert response.status_code == 200
    value = response.json()
    assert (value['member_count'], value['member_index'], value['asset_id']) == (2, 1, assets[2])
    assert value['width'] is None
    assert value['preview_status'] == 'not_ready'
    assert value['view_base'] == f'/astrophotoflow/api/v1/library/assets/{assets[2]}/previews'
    assert client.post('/api/v1/library/canvas-data/inspect', json={'reference': reference, 'member_index': 2}).status_code == 422
    reference['asset_ids'][1] = str(uuid4())
    assert client.post('/api/v1/library/canvas-data/inspect', json={'reference': reference}).status_code == 422

def test_inspect_preserves_reference_when_original_is_missing(canvas_library):
    client, database, versions, _ = canvas_library
    with database.write_session() as session:
        session.get(Asset, versions[0]).availability = 'missing'
    response = client.post('/api/v1/library/canvas-data/inspect', json={'reference': {'kind': 'asset', 'asset_id': versions[0], 'selection': {'kind': 'whole_file'}}})
    assert response.status_code == 200
    assert response.json()['availability'] == 'missing'
    assert response.json()['preview_status'] == 'not_ready'
    assert response.json()['asset_id'] == versions[0]

@pytest.mark.parametrize('shape,cards,expected', [([3, 4000, 6000], [{'keyword': 'NAXIS3', 'value': 3}, {'keyword': 'CTYPE3', 'value': 'RGB'}], (6000, 4000)), ([4000, 6000, 3], [{'keyword': 'NAXIS1', 'value': 3}, {'keyword': 'CTYPE1', 'value': 'RGB'}], (6000, 4000))])
def test_inspect_rgb_dimensions_follow_the_existing_fits_axis_rules(canvas_library, shape, cards, expected):
    client, database, versions, _ = canvas_library
    with database.write_session() as session:
        session.add(FitsHduMetadata(id=str(uuid4()), asset_id=versions[0], hdu_index=0, hdu_type='PRIMARY', shape=shape, header_cards=cards, parser_version='test', supported_kind='rgb', is_selected=True))
    response = client.post('/api/v1/library/canvas-data/inspect', json={'reference': {'kind': 'asset', 'asset_id': versions[0], 'selection': {'kind': 'whole_file'}}})
    assert response.status_code == 200
    assert (response.json()['width'], response.json()['height']) == expected

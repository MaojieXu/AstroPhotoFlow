from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import time

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from astrophotoflow.contracts.data_nodes import ExportSettings, NativeDataExecute
from astrophotoflow.contracts.inputs import OutputLocator
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import database_lock, upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.image_formats import convert_pixels, read_image, read_raster, verify_image, write_image
from astrophotoflow.modules.data.models import Asset
from astrophotoflow.modules.workflows.data_nodes import execute_data, result_directory
from astrophotoflow.modules.workflows.software_calls import _resolve_previous

PRECISIONS = {
    'fits': ['uint8','uint16','uint32','int16','int32','float32','float64'],
    'xisf': ['uint8','uint16','uint32','float32','float64'],
    'tiff': ['uint8','uint16','uint32','int16','int32','float32','float64'],
    'png': ['uint8','uint16'], 'jpeg': ['uint8'],
}
AUTH = {'Authorization': 'Bearer test'}


@pytest.mark.parametrize('format,precision', [(format, precision) for format, values in PRECISIONS.items() for precision in values])
@pytest.mark.parametrize('rgb', [False, True])
def test_every_format_and_precision_roundtrips_full_dimensions(tmp_path, format, precision, rgb):
    shape = (5, 7, 3) if rgb else (5, 7)
    values = np.arange(np.prod(shape)).reshape(shape).astype(precision)
    if values.dtype.kind == 'f': values = values / 4 - 2
    expected = values.copy()
    settings = ExportSettings(format=format, precision=precision)
    converted = convert_pixels(values, settings, tmp_path / 'converted.npy')
    path = tmp_path / ('image.' + format)
    write_image(path, converted, fits.Header({'EXPTIME': 0}), settings)
    assert verify_image(path, expected, settings)['shape'] == list(shape)
    np.testing.assert_array_equal(converted, expected)


def test_full_resolution_16bit_rgb_png_and_float_tiff_are_not_decoded_as_eight_bits(tmp_path):
    values = np.arange(72, dtype=np.uint16).reshape(4, 6, 3) * 700
    settings = ExportSettings(format='png', precision='uint16')
    write_image(tmp_path / 'image.png', values, None, settings)
    restored = read_raster(tmp_path / 'image.png')
    assert restored.dtype == np.uint16
    np.testing.assert_array_equal(restored, values)
    floats = values.astype('float64') / 7
    write_image(tmp_path / 'image.tif', floats, None, ExportSettings(format='tiff', precision='float64'))
    np.testing.assert_array_equal(read_raster(tmp_path / 'image.tif'), floats)


def test_integer_conversion_requires_an_explicit_decision_and_preserves_zero(tmp_path):
    pixels = np.array([[-1.0, 0.0, 0.5, 65536]], dtype=np.float64)
    with pytest.raises(ApiError, match='integer range'):
        convert_pixels(pixels, ExportSettings(format='png', precision='uint16'), tmp_path / 'bad.npy')
    with pytest.raises(ApiError, match='Fractional'):
        convert_pixels(np.array([[0.0, 0.5]]), ExportSettings(format='fits', precision='int16'), tmp_path / 'fraction.npy')
    rounded = convert_pixels(np.array([[-1.5, 0, 0.5, 1.5]]), ExportSettings(format='fits', precision='int16', conversion='round'), tmp_path / 'round.npy')
    np.testing.assert_array_equal(rounded, [[-2, 0, 0, 2]])
    normalized = convert_pixels(np.array([[0., 0.5, 1.]]), ExportSettings(format='png', precision='uint16', conversion='normalize', value_range=(0., 1.)), tmp_path / 'normalized.npy')
    np.testing.assert_array_equal(normalized, [[0, 32768, 65535]])


def test_nan_inf_stay_scientific_float_and_need_explicit_display_for_integer(tmp_path):
    values = np.array([[0, np.nan, np.inf, -np.inf]], dtype=np.float64)
    floats = convert_pixels(values, ExportSettings(format='fits', precision='float64'), tmp_path / 'float.npy')
    np.testing.assert_array_equal(floats, values)
    with pytest.raises(ApiError):
        convert_pixels(values, ExportSettings(format='png', precision='uint8'), tmp_path / 'integer.npy')
    rendered = convert_pixels(values, ExportSettings(format='png', precision='uint8', conversion='display', display_range=(0., 1.)), tmp_path / 'display.npy')
    np.testing.assert_array_equal(rendered, [[0, 0, 0, 0]])


def test_precision_combinations_and_multi_hdu_conversion_are_explicit(tmp_path):
    with pytest.raises(ValidationError): ExportSettings(format='jpeg', precision='float32')
    with pytest.raises(ValidationError): ExportSettings(format='xisf', precision='int16')
    with pytest.raises(ValidationError): ExportSettings(format='png', precision='uint16', conversion='normalize')
    path = tmp_path / 'multi.fits'
    fits.HDUList([fits.PrimaryHDU(np.ones((4, 5))), fits.ImageHDU(np.ones((6, 7)) * 9)]).writeto(path)
    from astrophotoflow.contracts.media import MediaSelection
    with pytest.raises(ApiError, match='explicit image HDU'):
        read_image(path, 'fits', MediaSelection(), tmp_path)
    plane, _ = read_image(path, 'fits', MediaSelection(hdu_index=1), tmp_path)
    np.testing.assert_array_equal(plane, np.ones((6, 7)) * 9)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / 'workspace'
    settings = Settings('127.0.0.1', 8190, root / 'data', (), workspace=root)
    with database_lock(settings): upgrade_database(settings)
    app = create_app(settings, 'test')
    with TestClient(app) as client: yield settings, client, app.state.database
    app.state.database.close()


def image_result(settings, database, *, dtype='float32', count=2, rgb=True):
    run, execution = uuid4(), uuid4()
    directory = result_directory(settings, run, execution)
    directory.mkdir(parents=True)
    for index in range(count):
        values = np.full((4, 5, 3) if rgb else (4, 5), index / 2, dtype=dtype)
        np.save(directory / f'input-{index:06}.npy', values, allow_pickle=False)
    body = NativeDataExecute(run_id=run, execution_id=execution, node_id='7', workflow_id=uuid4(), image_count=count, input_dtype=dtype)
    result = execute_data(database, settings, body)
    return body, result


def wait_export(client, identity):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        response = client.get(f'/api/v1/exports/{identity}', headers=AUTH)
        assert response.status_code == 200, response.text
        result = response.json()
        if result['state'] not in {'queued', 'running', 'cancelling'}: return result
        time.sleep(0.05)
    pytest.fail('Export did not reach a terminal state.')


@pytest.mark.parametrize('dtype', ['float16', 'float32', 'float64'])
def test_native_image_materialization_does_not_register_assets_and_feeds_science(workspace, dtype):
    settings, _, database = workspace
    body, result = image_result(settings, database, dtype=dtype)
    assert result['state'] == 'completed' and len(result['members']) == 2
    assert result['reference']['kind'] == 'run_output'
    inputs, supporting = _resolve_previous(settings, SimpleNamespace(prompt_id=body.run_id),
        OutputLocator.model_validate(result['reference']), SimpleNamespace(type='APF_SCIENCE'))
    assert len(inputs) == 2 and supporting == []
    with fits.open(inputs[1].read_path) as hdus:
        assert hdus[0].header['BITPIX'] == (-64 if dtype == 'float64' else -32)
        assert 'EXPTIME' not in hdus[0].header and 'CTYPE1' not in hdus[0].header
        np.testing.assert_array_equal(hdus[0].data, np.full((3, 4, 5), 0.5))
    with database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 0
    repeated = execute_data(database, settings, body)
    assert repeated['reference'] == result['reference']


def test_export_original_is_idempotent_and_never_overwrites(workspace, tmp_path):
    settings, client, database = workspace
    body, result = image_result(settings, database, count=1)
    destination = tmp_path / 'complete.fits'
    request = {'request_id': str(uuid4()), 'source': {'run_id': str(body.run_id), 'execution_id': str(body.execution_id)},
               'target': 'local', 'destination': str(destination), 'member_indexes': [0]}
    accepted = client.post('/api/v1/exports', headers=AUTH, json=request)
    assert accepted.status_code == 202, accepted.text
    receipt = wait_export(client, request['request_id'])
    assert receipt['state'] == 'completed', receipt
    original = destination.read_bytes()
    assert client.post('/api/v1/exports', headers=AUTH, json=request).status_code == 202
    assert destination.read_bytes() == original
    changed = {**request, 'destination': str(tmp_path / 'other.fits')}
    assert client.post('/api/v1/exports', headers=AUTH, json=changed).status_code == 409
    another = {**request, 'request_id': str(uuid4())}
    client.post('/api/v1/exports', headers=AUTH, json=another)
    assert wait_export(client, another['request_id'])['state'] == 'completed_with_errors'
    assert destination.read_bytes() == original
    with database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 0


def test_library_save_is_explicit_and_records_conversion_provenance(workspace):
    settings, client, database = workspace
    body, _ = image_result(settings, database, count=1, rgb=False)
    request = {'request_id': str(uuid4()), 'source': {'run_id': str(body.run_id), 'execution_id': str(body.execution_id)},
               'target': 'library', 'member_indexes': [0], 'name': 'Chosen result', 'settings': {'format': 'tiff', 'precision': 'float64'}}
    response = client.post('/api/v1/exports', headers=AUTH, json=request)
    assert response.status_code == 202, response.text
    receipt = wait_export(client, request['request_id'])
    assert receipt['state'] == 'completed', receipt
    registered = receipt['results'][0]['registration']
    asset = client.get(f"/api/v1/library/assets/{registered['asset_id']}", headers=AUTH).json()
    assert asset['name'] == 'Chosen result'
    version = client.get(f"/api/v1/library/assets/{registered['asset_id']}/versions/{registered['asset_version_id']}", headers=AUTH).json()
    assert version['scientific_metadata']['export_provenance']['settings']['precision'] == 'float64'
    assert client.post('/api/v1/exports', headers=AUTH, json=request).status_code == 202
    with database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_member_partial_failure_keeps_order_and_does_not_rerun_native_data(workspace, tmp_path):
    settings, client, database = workspace
    body, _ = image_result(settings, database)
    destination = tmp_path / 'group'
    destination.mkdir()
    request = {'request_id': str(uuid4()), 'source': {'run_id': str(body.run_id), 'execution_id': str(body.execution_id)},
               'target': 'local', 'destination': str(destination), 'member_indexes': [0, 1],
               'settings': {'format': 'png', 'precision': 'uint16'}}
    client.post('/api/v1/exports', headers=AUTH, json=request)
    receipt = wait_export(client, request['request_id'])
    assert [item['member_index'] for item in receipt['results']] == [0, 1]
    assert [item['state'] for item in receipt['results']] == ['completed', 'failed']
    assert receipt['results'][1]['error']['code'] == 'CONVERSION_REQUIRES_DECISION'
    assert len(list(destination.glob('*.png'))) == 1

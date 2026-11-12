"""Read-only source fixtures and isolated current-library imports."""

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.image_imports import ExplicitImportRequest, ImageInspectionRequest
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.public import (
    configure_library,
    get_image_import_task,
    import_workers,
    inspect_image_files,
    list_image_inspection_files,
    run_import_task,
    submit_image_import,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / 'fixtures/real-data-catalog.json'
AUTHORED_CATALOG = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))


@pytest.fixture(params=AUTHORED_CATALOG['groups'], ids=lambda group: group['name'])
def authored_group(request):
    return request.param


@pytest.fixture(scope='session')
def real_data_catalog():
    return AUTHORED_CATALOG


@pytest.fixture(scope='session')
def real_data_root(pytestconfig, real_data_catalog):
    supplied = pytestconfig.getoption('--real-data-root')
    if supplied is None:
        pytest.skip('Supply --real-data-root to run read-only real-material acceptance.')
    root = supplied.resolve()
    if not root.is_dir():
        pytest.fail(f'The explicitly supplied material root is missing: {root}')
    authored = [member for group in real_data_catalog['groups'] for member in group['members']] + real_data_catalog['masters']
    for folder, count in real_data_catalog['source_folders'].items():
        directory = root / folder
        actual = list(directory.glob('*.fit*')) if directory.is_dir() else []
        if len(actual) != count:
            pytest.fail(f'{directory} has {len(actual)} FITS files; authored baseline requires {count}.')
    for member in authored:
        path = (root / member['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size != member['byte_size']:
            pytest.fail(f'The authored source baseline changed: {member["path"]}')
    return root


@dataclass
class RealLibrary:
    root: Path
    settings: Settings
    database: Database
    workers: tuple
    node: object

    def import_files(self, paths, *, name=None, frame_type='light', frame_class='subframe', status='Unknown'):
        paths = [Path(path).resolve() for path in paths]
        scan = inspect_image_files(self.settings, ImageInspectionRequest(paths=[str(path) for path in paths]))
        entries = list_image_inspection_files(self.settings, scan['scan_id'], query={'limit': 200})['items']
        by_path = {str(Path(entry['path']).resolve()): entry['file_id'] for entry in entries}
        body = ExplicitImportRequest.model_validate_json(json.dumps({
            'request_id': str(uuid4()), 'scan_id': scan['scan_id'],
            'files': [{'file_id': by_path[str(path)]} for path in paths],
            'destination': {'mode': 'new_dataset', 'name': name} if name else {'mode': 'standalone'},
            'defaults': {
                'calibration_status': status,
                'calibration_reason': 'Explicit acceptance fixture declaration.',
                'metadata': {'classification': {'frame_class': frame_class, 'frame_type': frame_type}},
            },
            'accept_unknown': True,
        }))
        with self.database.write_session() as session:
            accepted = submit_image_import(session, self.settings, body)
        if accepted.scheduled:
            run_import_task(self.database, self.settings, accepted.receipt['task_id'], self.workers)
        with self.database.read_session() as session:
            receipt = get_image_import_task(session, accepted.receipt['task_id'], items_limit=200)
        self.node.user_properties.append((f'import_{body.request_id}', {
            'task_id': receipt['task_id'], 'sources': [str(path) for path in paths],
            'stages': receipt['stages'], 'errors': [item.get('error') for item in receipt['items'] if item.get('error')],
        }))
        return receipt

    def import_group(self, group, *, count=2, status='Unknown'):
        return self.import_files([self.root / member['path'] for member in group['members'][:count]], name=group['name'], status=status)

    def assets(self, receipt):
        ids = [str(item['asset_id']) for item in receipt['items'] if item.get('asset_id')]
        with self.database.read_session() as session:
            by_id = {asset.id: asset for asset in session.scalars(select(Asset).where(Asset.id.in_(ids)))}
        return [by_id[identity] for identity in ids]


@pytest.fixture
def real_library(real_data_root, tmp_path, request):
    workspace = tmp_path / 'workspace'
    settings = Settings('127.0.0.1', 8190, workspace / 'data', (), workspace=workspace)
    initialize_database(settings)
    database = Database(settings.database_path)
    configure_library(database, settings)
    try:
        with import_workers(settings) as workers:
            yield RealLibrary(real_data_root, settings, database, workers, request.node)
    finally:
        database.close()


@pytest.fixture
def green_group(real_data_catalog):
    return next(group for group in real_data_catalog['groups'] if group['source_folder'] == 'IC443_RGB_P0' and group['header']['FILTER'] == 'Green')


@pytest.fixture
def imported_group(real_library, green_group):
    receipt = real_library.import_group(green_group)
    assert receipt['stages']['publication']['state'] == 'published', receipt
    return receipt


@pytest.fixture
def master_dark(real_library, real_data_catalog):
    master = next(item for item in real_data_catalog['masters'] if item['frame_type'] == 'dark' and item['header']['EXPTIME'] == 120)
    receipt = real_library.import_files([real_library.root / master['path']], frame_class='masterframe', frame_type='dark')
    return real_library.assets(receipt)[0]


@pytest.fixture
def real_http(real_library, synthetic_bundle_catalog):
    app = create_app(real_library.settings, 'real-data-test-token')
    with TestClient(app, headers={'Authorization': 'Bearer real-data-test-token'}) as client:
        yield client


@pytest.fixture
def real_client_factory(real_http):
    def make_client():
        def handle(request):
            response = real_http.request(request.method, request.url.path, params=request.url.params,
                                         content=request.content, headers=dict(request.headers))
            return httpx.Response(response.status_code, headers=dict(response.headers), content=response.content)
        client = AssetClient.__new__(AssetClient)
        client.base_url = 'http://testserver/api/v1'
        client.client = httpx.Client(base_url=client.base_url, transport=httpx.MockTransport(handle),
                                    headers={'Authorization': 'Bearer real-data-test-token'})
        return client
    return make_client

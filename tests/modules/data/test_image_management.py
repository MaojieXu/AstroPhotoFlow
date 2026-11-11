"""Image metadata, explicit equipment application and declared Master sources."""
import json
from copy import deepcopy
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError
from sqlalchemy import event, select
from astrophotoflow.contracts.datasets import DatasetCreate
from astrophotoflow.contracts.equipment import CameraCreate, TelescopeCreate
from astrophotoflow.contracts.image_management import AssetMetadataChange, AssetRevisionRef, DatasetImageMemberPage, DatasetImagePage, DatasetMemberSearch, DatasetSearch, EquipmentApplication, ImageBatchResult, ImageChanges, ImageDetail, ImageHeaderPage, ImagePage, ImageSearch, MasterProvenanceChanges, MasterProvenanceOut
from astrophotoflow.contracts.setups import EquipmentSetupCreate
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.image_management import apply_image_equipment, get_image, read_image_header, search_images, update_image, update_image_metadata_batch
from astrophotoflow.modules.data.assets.image_metadata import freeze_import_equipment, record_import_image_metadata
from astrophotoflow.modules.data.assets.image_provenance import get_master_provenance, master_provenance_references, update_master_provenance
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.datasets.image_queries import list_image_dataset_members, search_image_datasets
from astrophotoflow.modules.data.datasets.service import create_dataset
from astrophotoflow.modules.data.equipment.service import create_equipment
from astrophotoflow.modules.data.equipment.setups import create_setup
from astrophotoflow.modules.data.persistence import schema_metadata
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

def parsed(model, value):
    return model.model_validate_json(json.dumps(value))

def typed_service(function, model):
    """Also verify that service JSON conforms to the public response contract."""

    def checked(*args, **kwargs):
        return parsed(model, function(*args, **kwargs))
    return checked
get_image = typed_service(get_image, ImageDetail)
search_images = typed_service(search_images, ImagePage)
update_image = typed_service(update_image, ImageDetail)
update_image_metadata_batch = typed_service(update_image_metadata_batch, ImageBatchResult)
apply_image_equipment = typed_service(apply_image_equipment, ImageBatchResult)
read_image_header = typed_service(read_image_header, ImageHeaderPage)
get_master_provenance = typed_service(get_master_provenance, MasterProvenanceOut)
update_master_provenance = typed_service(update_master_provenance, MasterProvenanceOut)
search_image_datasets = typed_service(search_image_datasets, DatasetImagePage)
list_image_dataset_members = typed_service(list_image_dataset_members, DatasetImageMemberPage)

@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / 'images.sqlite3')
    schema_metadata().create_all(database.engine)
    yield database
    database.close()

def image(session, name='light', *, master=False, frame_type='light', status='active', **parameters):
    asset = Asset(id=str(uuid4()), name=name, scope='shared', role='calibration' if frame_type != 'light' else 'raw', frame_class='masterframe' if master else 'subframe', frame_type=frame_type, status=status, revision=1, **parameters, storage_mode='managed', storage_location=f'objects/{str(uuid4())}/source.fits', availability='available', byte_size=5, content_hash='blake3:' + '0' * 64, calibration_level='master' if master else 'individual', capture_snapshot={'parameters': {'gain': 20}, 'classification': {'frame_class': 'masterframe' if master else 'subframe', 'frame_type': frame_type}}, scientific_metadata={'format': 'fits', 'export_provenance': {'actual_call': 'preserved'}})
    session.add(asset)
    session.flush()
    session.flush()
    session.flush()
    return asset

def test_times_keep_raw_unknown_and_query_utc_with_null_last(db):
    with db.write_session() as session:
        late = image(session, 'late')
        early = image(session, 'early')
        unknown = image(session, 'unknown')
        for asset, start in ((early, {'utc': '2026-11-01T01:00:00Z'}), (late, {'utc': '2026-11-02T01:00:00Z'}), (unknown, {'raw_value': '2026-11-01 01:00:00', 'time_system': 'unknown'})):
            record_import_image_metadata(session, asset.id, {'target_name': 'M31', 'times': {'capture_start': start}})
        result = search_images(session, parsed(ImageSearch, {'target_name': 'm31', 'sort_by': 'capture_start'}))
        assert [item.asset.name for item in result.items] == ['late', 'early', 'unknown']
        selected = search_images(session, parsed(ImageSearch, {'captured_from': '2026-11-02T00:00:00Z'}))
        assert selected.total == 1 and selected.items[0].asset.id == UUID(late.id)
        assert get_image(session, unknown.id).metadata.times.capture_start.utc is None

def test_image_search_batches_details_for_each_page(db):
    with db.write_session() as session:
        first = image(session, 'page-a')
        second = image(session, 'page-b')
        third = image(session, 'page-c')
        image(session, 'page-archived', status='archived')
        removed = image(session, 'page-removed')
        session.add(LibraryEntryRemoval(entry_type='asset', entry_id=removed.id))
        record_import_image_metadata(session, first.id, {'target_name': 'M31'})
    with db.read_session() as session:
        expected = [get_image(session, asset.id) for asset in (first, second, third)]
    assert expected[1].metadata.model_dump(exclude_unset=True) == {}
    statements = []

    def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    event.listen(db.engine, 'before_cursor_execute', count_selects)
    try:
        for limit, offset, max_selects in [(1, 0, 4), (3, 0, 4), (2, 1, 4), (2, 3, 2)]:
            statements.clear()
            with db.read_session() as session:
                page = search_images(session, ImageSearch(text='page-', sort_by='name', order='asc', limit=limit, offset=offset))
            assert page.items == expected[offset:offset + limit]
            assert page.total == 3 and page.limit == limit and (page.offset == offset)
            assert len(statements) <= max_selects
    finally:
        event.remove(db.engine, 'before_cursor_execute', count_selects)

def test_metadata_updates_preserve_zero_null_omission_and_old_content_snapshot(db):
    with db.write_session() as session:
        asset = image(session, gain=22, offset=8, exposure_seconds=100)
        old_snapshot = deepcopy(asset.capture_snapshot)
        first = update_image(session, asset.id, 1, parsed(ImageChanges, {'target_name': 'M31', 'parameters': {'gain': 0, 'offset': None, 'readout_mode': 'Mode 0'}, 'times': {'capture_start': {'utc': '2026-11-01T01:00:00Z'}, 'capture_end': {'utc': '2026-11-01T02:00:00Z'}}}))
        assert first.asset.parameters.gain == 0 and first.asset.parameters.offset is None
        assert first.asset.parameters.exposure_seconds == 100 and first.asset.parameters.readout_mode == 'Mode 0'
        second = update_image(session, asset.id, 2, parsed(ImageChanges, {'target_name': None}))
        assert second.metadata.target_name is None and second.metadata.times.capture_end.utc is not None
        assert session.get(Asset, asset.id).capture_snapshot == old_snapshot

def test_new_import_freezes_metadata_and_sources_but_corrections_only_change_current(db):
    with db.write_session() as session:
        asset = image(session)
        record_import_image_metadata(session, asset.id, {'target_name': 'M31', 'times': {'capture_start': {'raw_value': '2026-11-01T01:00:00', 'time_system': 'UTC', 'utc': '2026-11-01T01:00:00Z'}}}, value_sources={'target_name': 'file', 'times.capture_start': 'file'}, freeze_capture=True)
        fixed = deepcopy(asset.capture_snapshot)
        assert fixed['image_metadata']['target_name'] == 'M31'
        assert asset.value_sources['target_name'] == 'file'
        result = update_image(session, asset.id, 1, parsed(ImageChanges, {'target_name': 'M42', 'times': {'capture_start': {'utc': '2026-11-02T01:00:00Z'}}}))
        assert result.metadata.target_name == 'M42' and result.asset.value_sources['target_name'] == 'manual'
        assert result.asset.value_sources['times.capture_start'] == 'manual'
        assert session.get(Asset, asset.id).capture_snapshot == fixed

def test_batch_rejects_entire_changes_on_stale_or_invalid_late_item(db):
    with db.write_session() as session:
        first = image(session, 'first')
        second = image(session, 'second')
        record_import_image_metadata(session, second.id, {'times': {'capture_start': {'utc': '2026-11-02T00:00:00Z'}}})
        items = [parsed(AssetMetadataChange, {'asset_id': first.id, 'expected_revision': 1, 'changes': {'name': 'changed'}}), parsed(AssetMetadataChange, {'asset_id': second.id, 'expected_revision': 1, 'changes': {'times': {'capture_end': {'utc': '2026-11-01T00:00:00Z'}}}})]
        with pytest.raises(ValidationError):
            update_image_metadata_batch(session, items)
        assert session.get(Asset, first.id).name == 'first' and session.get(Asset, first.id).revision == 1
        stale = [parsed(AssetMetadataChange, {'asset_id': first.id, 'expected_revision': 1, 'changes': {'name': 'changed'}}), parsed(AssetMetadataChange, {'asset_id': second.id, 'expected_revision': 2, 'changes': {'name': 'no'}})]
        with pytest.raises(ApiError, match='current revision'):
            update_image_metadata_batch(session, stale)
        assert session.get(Asset, first.id).name == 'first'

def equipment_setup(session):
    camera = create_equipment(session, CameraCreate(kind='camera', name='Camera', specs={'pixel_size_um': 2.9}))
    telescope = create_equipment(session, TelescopeCreate(kind='telescope', name='Scope', specs={'native_focal_length_mm': 1000}))
    setup = create_setup(session, EquipmentSetupCreate(name='Set', components=[{'source': 'registered', 'equipment_id': camera.id}, {'source': 'registered', 'equipment_id': telescope.id}]))
    return (camera, telescope, setup)

def test_equipment_applies_only_requested_fields_without_capture_overrides(db):
    with db.write_session() as session:
        camera, _telescope, setup = equipment_setup(session)
        asset = image(session, gain=22, exposure_seconds=60)
        frozen = deepcopy(asset.capture_snapshot)
        application = parsed(EquipmentApplication, {'choice': {'source': 'setup', 'setup_id': str(setup.id), 'expected_revision': setup.revision}, 'fields': ['camera']})
        ref = AssetRevisionRef(asset_id=UUID(asset.id), expected_revision=1)
        result = apply_image_equipment(session, [ref], application).items[0]
        assert result.asset.parameters.camera_id == camera.id
        assert result.asset.parameters.optical_system_id is None
        assert result.asset.parameters.gain == 22 and result.asset.parameters.exposure_seconds == 60
        assert session.get(Asset, asset.id).capture_snapshot == frozen
        imported = freeze_import_equipment(session, application, {'gain': 10})
        assert imported['parameters'] == {'camera_id': str(camera.id), 'gain': 10}
        assert 'optical_system_id' not in imported['parameters']

def test_equipment_revision_or_wrong_device_type_never_partially_updates(db):
    with db.write_session() as session:
        camera, telescope, _ = equipment_setup(session)
        asset = image(session)
        ref = AssetRevisionRef(asset_id=UUID(asset.id), expected_revision=1)
        for selection in ({'equipment_id': str(camera.id), 'expected_revision': 3}, {'equipment_id': str(telescope.id), 'expected_revision': 1}):
            app = parsed(EquipmentApplication, {'choice': {'source': 'devices', 'camera': selection}, 'fields': ['camera']})
            with pytest.raises(ApiError):
                apply_image_equipment(session, [ref], app)
        assert session.get(Asset, asset.id).revision == 1

def test_accessory_application_changes_only_requested_selection(db):
    with db.write_session() as session:
        accessory_id = str(uuid4())
        scope = create_equipment(session, parsed(TelescopeCreate, {'kind': 'telescope', 'name': 'Scope', 'specs': {'native_focal_length_mm': 1000, 'optical_accessories': [{'id': accessory_id, 'name': 'Reducer', 'factor': 0.7}]}}))
        asset = image(session)
        selection = {'source': 'devices', 'telescope': {'equipment_id': str(scope.id), 'expected_revision': 1}, 'optical_accessory_id': accessory_id}
        app = parsed(EquipmentApplication, {'choice': selection, 'fields': ['telescope', 'optical_accessory']})
        native_only = parsed(EquipmentApplication, {'choice': selection, 'fields': ['telescope']})
        native_import = freeze_import_equipment(session, native_only, {})
        assert native_import['selected_equipment']['optical_system_id']['optical_accessory'] is None
        result = apply_image_equipment(session, [AssetRevisionRef(asset_id=UUID(asset.id), expected_revision=1)], app).items[0]
        assert result.asset.equipment_snapshot.optical_system_id.effective_focal_length_mm == 700
        app = parsed(EquipmentApplication, {'choice': {key: value for key, value in selection.items() if key != 'optical_accessory_id'}, 'fields': ['telescope']})
        result = apply_image_equipment(session, [AssetRevisionRef(asset_id=UUID(asset.id), expected_revision=2)], app).items[0]
        assert result.asset.equipment_snapshot.optical_system_id.optical_accessory.id == UUID(accessory_id)
        clear = parsed(EquipmentApplication, {'choice': {**selection, 'optical_accessory_id': None}, 'fields': ['optical_accessory']})
        with pytest.raises(ApiError, match='new image requires'):
            freeze_import_equipment(session, clear, {})
        result = apply_image_equipment(session, [AssetRevisionRef(asset_id=UUID(asset.id), expected_revision=3)], clear).items[0]
        assert result.asset.parameters.optical_system_id == scope.id
        assert result.asset.equipment_snapshot.optical_system_id.optical_accessory is None
        assert result.asset.equipment_snapshot.optical_system_id.effective_focal_length_mm == 1000

def test_dataset_filters_require_same_member_and_default_members_include_archived(db):
    with db.write_session() as session:
        first = image(session, 'one', gain=0, exposure_seconds=100)
        second = image(session, 'two', gain=10, exposure_seconds=200, status='archived')
        record_import_image_metadata(session, first.id, {'target_name': 'M31'})
        record_import_image_metadata(session, second.id, {'target_name': 'M42'})
        group = create_dataset(session, DatasetCreate(name='Mixed', asset_ids=[UUID(first.id), UUID(second.id)]))
        assert search_image_datasets(session, DatasetSearch(target_name='M31', gain_min=10)).total == 0
        matched = search_image_datasets(session, DatasetSearch(target_name='M31'))
        assert matched.total == 1 and matched.items[0].member_count == 2 and (matched.items[0].matching_member_count == 1)
        assert search_image_datasets(session, DatasetSearch(target_name='M31', match='all')).total == 0
        members = list_image_dataset_members(session, group.id, DatasetMemberSearch())
        assert [row.member.asset.name for row in members.items] == ['one', 'two']
        filtered = list_image_dataset_members(session, group.id, DatasetMemberSearch(status='active'))
        assert filtered.total == 1

def test_master_declaration_updates_current_state_and_keeps_actual_platform_provenance(db):
    with db.write_session() as session:
        source = image(session, 'dark', frame_type='dark')
        master = image(session, 'master', frame_type='dark', master=True)
        record_import_image_metadata(session, source.id, {'times': {'capture_start': {'utc': '2026-11-01T00:00:00Z'}, 'capture_end': {'utc': '2026-11-01T01:00:00Z'}}}, value_sources={'times.capture_start': 'file', 'times.capture_end': 'file'}, freeze_capture=True)
        update_master_provenance(session, master.id, 1, parsed(MasterProvenanceChanges, {'sources': [{'kind': 'asset', 'asset_id': source.id}], 'bias_state': 'removed', 'processing': {'software_name': 'External'}}))
        record_import_image_metadata(session, source.id, {'times': {'capture_start': {'utc': '2026-10-01T00:00:00Z'}}})
        current = update_master_provenance(session, master.id, 2, MasterProvenanceChanges(notes='corrected'))
        saved = get_master_provenance(session, master.id)
        assert saved.declaration.notes == 'corrected'
        assert current.source_time_range.start.utc.month == 11
        assert current.platform_provenance == {'actual_call': 'preserved'}
        assert current.revision == 3 and current.asset_revision == 3
        assert len(master_provenance_references(session, {source.id}, set())) == 1
        respecified = update_master_provenance(session, master.id, 3, parsed(MasterProvenanceChanges, {'sources': [{'kind': 'asset', 'asset_id': source.id}]}))
        assert respecified.source_time_range.start.utc.month == 11 and respecified.source_time_range.complete

def test_master_source_dataset_subset_protects_fixed_selection_and_marks_unknown_time(db):
    with db.write_session() as session:
        first = image(session, 'first', frame_type='dark')
        b = image(session, 'second', frame_type='dark')
        record_import_image_metadata(session, first.id, {'times': {'capture_start': {'utc': '2026-11-01T00:00:00Z'}}})
        group = create_dataset(session, DatasetCreate(name='Darks', asset_ids=[UUID(first.id), UUID(b.id)]))
        master = image(session, 'master', master=True, frame_type='dark')
        result = update_master_provenance(session, master.id, 1, parsed(MasterProvenanceChanges, {'sources': [{'kind': 'dataset', 'dataset_id': str(group.id), 'member_asset_ids': [first.id]}]}))
        assert not result.source_time_range.complete and result.source_time_range.start is None
        assert master_provenance_references(session, {first.id}, set())
        assert not master_provenance_references(session, {b.id}, set())
        assert master_provenance_references(session, set(), {str(group.id)})

def test_invalid_master_source_is_rejected_without_revision_change(db):
    with db.write_session() as session:
        master = image(session, 'master', frame_type='flat', master=True)
        with pytest.raises(ApiError):
            update_master_provenance(session, master.id, 1, parsed(MasterProvenanceChanges, {'sources': [{'kind': 'asset', 'asset_id': master.id}]}))
        assert session.get(Asset, master.id).revision == 1

def test_header_keyword_selection_preserves_cards_and_pages(db):
    with db.write_session() as session:
        asset = image(session)
        session.add(FitsHduMetadata(id=str(uuid4()), asset_id=asset.id, hdu_index=0, hdu_type='PRIMARY', header_cards=[{'keyword': 'COMMENT', 'value': 'A'}, {'keyword': 'GAIN', 'value': 0}, {'keyword': 'COMMENT', 'value': 'B'}], parser_version='test', is_selected=True))
        session.flush()
        page = read_image_header(session, asset.id, 0, keywords=['comment'], limit=1, offset=1)
        assert page.total == 2 and page.cards == [{'keyword': 'COMMENT', 'value': 'B'}]

def test_retired_preset_inputs_are_rejected_and_ambiguous_filter_is_not_guessed(db):
    from astrophotoflow.contracts.equipment import FilterCreate
    from astrophotoflow.contracts.image_management import ImageEquipmentApply
    with pytest.raises(ValidationError):
        parsed(EquipmentApplication, {'choice': {'source': 'preset', 'preset_id': str(uuid4()), 'expected_revision': 1}, 'fields': ['camera']})
    with pytest.raises(ValidationError):
        parsed(ImageEquipmentApply, {'assets': [{'asset_id': str(uuid4()), 'expected_revision': 1}], 'equipment': {'choice': {'source': 'devices', 'camera': None}, 'fields': ['camera']}, 'preset_parameter_fields': ['gain']})
    with db.write_session() as session:
        filters = [create_equipment(session, FilterCreate(kind='filter', name=name)) for name in ('Ha', 'OIII')]
        setup = create_setup(session, EquipmentSetupCreate(name='multi', components=[{'source': 'registered', 'equipment_id': item.id} for item in filters]))
        app = parsed(EquipmentApplication, {'choice': {'source': 'setup', 'setup_id': str(setup.id), 'expected_revision': 1}, 'fields': ['filter']})
        with pytest.raises(ApiError, match='multiple filters'):
            freeze_import_equipment(session, app, {})
        app = parsed(EquipmentApplication, {'choice': {'source': 'setup', 'setup_id': str(setup.id), 'expected_revision': 1}, 'fields': ['camera']})
        assert freeze_import_equipment(session, app, {})['parameters'] == {'camera_id': None}

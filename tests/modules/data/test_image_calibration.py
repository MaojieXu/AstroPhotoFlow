from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from astrophotoflow.contracts.image_calibration import (
    CalibrationCheckPage,
    DatasetCalibrationPage,
    DatasetCalibrationUpdate,
    DatasetMemberCalibrationUpdate,
    ImageCalibrationOut,
    ImageCalibrationUpdate,
    ImageDatasetCreate,
    ImageDatasetEditMembers,
    ImageOperationOut,
)
from astrophotoflow.contracts.inputs import AssetInputReference, DatasetInputMember, DatasetInputReference, ScienceSelection
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.calibration.checks import validate_calibration_bindings
from astrophotoflow.modules.data.calibration.choices import UNCONFIGURED, incoming_bindings, patch_bindings
from astrophotoflow.modules.data.calibration.models import ImageCalibrationConfiguration
from astrophotoflow.modules.data.calibration.service import (
    apply_import_calibration,
    calibration_references,
    check_calibration,
    create_image_dataset,
    edit_image_dataset_members,
    get_image_calibration,
    get_image_calibration_operation,
    get_image_dataset_calibration,
    search_calibrations,
    update_image_calibration,
    update_image_dataset_calibration_defaults,
    update_image_dataset_calibration_members,
)
from astrophotoflow.modules.data.science.files import hash_file
from astrophotoflow.modules.data.science.inputs import resolve_canvas_inputs


@pytest.fixture
def library(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    yield database, settings
    database.close()


CAMERA = str(uuid4())
OPTICS = str(uuid4())
FILTER = str(uuid4())


def image(session, settings, frame_type="light", master=False, camera=CAMERA, exposure=60):
    identity, version_id = str(uuid4()), str(uuid4())
    path = settings.data_dir / "objects" / version_id / "source.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic scientific source")
    content_hash, size, _ = hash_file(path)
    parameters = {"camera_id": camera, "optical_system_id": OPTICS, "filter_id": FILTER,
                  "parameter_mode": "gain", "gain": 0, "offset": 0, "exposure_seconds": exposure,
                  "sensor_temperature_c": -10, "binning_x": 1, "binning_y": 1,
                  "cfa_pattern": "MONO", "readout_mode": "test-mode"}
    asset = Asset(id=identity, name=f"{frame_type}-{version_id[:8]}", scope="shared", role="raw" if frame_type == "light" else "calibration",
                  frame_class="masterframe" if master else "subframe", frame_type=frame_type, **parameters)
    session.add(asset)
    session.flush()
    version = AssetVersion(id=version_id, asset_id=identity, version_number=1, storage_mode="managed",
                           storage_location=path.relative_to(settings.data_dir).as_posix(), availability="available",
                           content_hash=content_hash, byte_size=size, frame_type=frame_type,
                           calibration_level="master" if master else "individual", capture_snapshot={"parameters": parameters},
                           scientific_metadata={"format": "other", "width": 8, "height": 6, "supported_kind": "mono"})
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    return asset, version


def target(version):
    return {"kind": "asset_version", "id": version.id}


def choice(version):
    return {"mode": "target", "target": target(version)}


def create_group(session, name, versions, **extra):
    body = ImageDatasetCreate.model_validate({"request_id": uuid4(), "name": name,
                                             "members": [{"asset_version_id": version.id} for version in versions], **extra})
    return create_image_dataset(session, body)["result"]


def test_visible_effective_targets_and_whole_group_combinations_do_not_check_science(library, monkeypatch):
    database, settings = library
    with database.write_session() as session:
        _, first = image(session, settings)
        _, second = image(session, settings)
        _, flat_a = image(session, settings, 'flat', master=True)
        _, flat_b = image(session, settings, 'flat', master=True)
        body = ImageDatasetCreate.model_validate({'request_id': uuid4(), 'name': 'Across nights',
            'members': [{'asset_version_id': first.id}, {'asset_version_id': second.id, 'calibration': {'flat': choice(flat_b)}}],
            'calibration_defaults': {'flat': choice(flat_a)}, 'accept_unknown': True})
        group = create_image_dataset(session, body)['result']
        other = create_group(session, 'Independent context', [first], calibration_defaults={'flat': choice(flat_b)}, accept_unknown=True)
        monkeypatch.setattr('astrophotoflow.modules.data.calibration.service.inspect_calibration_bindings',
                            lambda *args, **kwargs: pytest.fail('Browsing must not run scientific checks'))
        page = get_image_dataset_calibration(session, group['dataset_id'], group['dataset_version_id'], limit=1)
        DatasetCalibrationPage.model_validate(page)
        assert page['total'] == 2 and len(page['items']) == 1
        assert sorted(row['member_count'] for row in page['combinations']) == [1, 1]
        first_slots = page['items'][0]['slots']
        assert first_slots['flat']['target_detail']['asset_id'] == flat_a.asset_id
        assert first_slots['flat']['target_detail']['target']['id'] == flat_a.id
        assert first_slots['flat']['source'] == 'dataset_default'
        assert first_slots['flat']['check_state'] == 'not_checked'
        assert first_slots['dark_flat']['status'] == 'not_applicable'
        combo = next(row for row in page['combinations'] if row['effective']['flat']['target']['id'] == flat_b.id)
        filtered = get_image_dataset_calibration(session, group['dataset_id'], group['dataset_version_id'], combination_key=combo['key'])
        assert filtered['total'] == 1 and filtered['items'][0]['asset_version_id'] == second.id
        assert filtered['items'][0]['slots']['flat']['source'] == 'member_override'
        assert len(filtered['combinations']) == 2
        unrelated = get_image_dataset_calibration(session, other['dataset_id'], other['dataset_version_id'])
        assert unrelated['items'][0]['slots']['flat']['target_detail']['target']['id'] == flat_b.id
        standalone = get_image_calibration(session, first.asset_id, first.id)
        assert standalone['slots']['flat']['status'] == 'unconfigured'
        assert standalone['slots']['flat']['source'] == 'standalone'
        with pytest.raises(ApiError) as invalid:
            get_image_dataset_calibration(session, group['dataset_id'], group['dataset_version_id'], combination_key='wrong-version')
        assert invalid.value.code == 'INVALID_REFERENCE'


def test_calibration_browsing_uses_database_pagination_and_batched_queries(library):
    from sqlalchemy import event

    from astrophotoflow.modules.data.datasets.models import DatasetMember

    database, settings = library
    with database.write_session() as session:
        versions = [image(session, settings)[1] for _ in range(30)]
        group = create_group(session, 'Large group', versions)
    counts = []
    for size in (1, 25):
        with database.read_session() as session:
            statements = []
            connection = session.connection()
            listener = lambda *args, captured=statements: captured.append(args[2])
            event.listen(connection, 'before_cursor_execute', listener)
            try:
                page = get_image_dataset_calibration(session, group['dataset_id'], group['dataset_version_id'], limit=size)
                assert page['total'] == 30 and len(page['items']) == size
                assert page['combinations'][0]['member_count'] == 30
                assert sum(isinstance(row, DatasetMember) for row in session.identity_map.values()) <= size
                counts.append(len(statements))
            finally:
                event.remove(connection, 'before_cursor_execute', listener)
    assert counts[1] <= counts[0] + 1


def test_scanned_calibration_check_is_read_only_and_reuses_actual_file_facts(library):
    import numpy as np
    from astropy.io import fits

    from astrophotoflow.contracts.image_imports import ImageInspectionRequest, ScannedCalibrationCheckPage, ScannedCalibrationCheckRequest
    from astrophotoflow.modules.data.calibration.import_checks import check_import_calibration
    from astrophotoflow.modules.data.imports.explicit import inspect_image_files, list_image_inspection_files
    from astrophotoflow.modules.data.imports.models import AssetTask

    database, settings = library
    path = settings.workspace / 'external' / 'light.fits'
    path.parent.mkdir(parents=True)
    hdu = fits.PrimaryHDU(np.zeros((6, 8), dtype=np.uint16))
    hdu.header['IMAGETYP'] = 'Light Frame'
    hdu.header['EXPTIME'] = 20
    hdu.header['GAIN'] = 0
    hdu.header['OFFSET'] = 0
    hdu.header['CCD-TEMP'] = -10
    hdu.header['XBINNING'] = 1
    hdu.header['YBINNING'] = 1
    hdu.writeto(path)
    scan = inspect_image_files(settings, ImageInspectionRequest(paths=[str(path)]))
    entries = list_image_inspection_files(settings, scan['scan_id'])
    file_id = entries['items'][0]['file_id']
    with database.write_session() as session:
        _, dark = image(session, settings, 'dark', master=True)
        request = {'scan_id': scan['scan_id'], 'files': [{'file_id': file_id}],
                   'defaults': {'metadata': {'parameters': {'parameter_mode': 'gain'}}},
                   'calibration_defaults': {'dark': choice(dark)}}
        before = session.scalar(select(func.count()).select_from(Asset))
        result = check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate(request))
        ScannedCalibrationCheckPage.model_validate(result)
        assert result['state'] == 'conflict'
        assert result['items'][0]['file_id'] == file_id
        assert any(row['field'] == 'exposure_seconds' and row['code'] == 'METADATA_MISMATCH' for row in result['items'][0]['diagnostics'])
        request['files'][0]['metadata'] = {'parameters': {'exposure_seconds': 60}}
        unknown = check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate(request))
        assert unknown['state'] == 'unknown' and unknown['conflict_count'] == 0
        assert not any(row['field'] == 'dimensions' for row in unknown['items'][0]['diagnostics'])
        assert session.scalar(select(func.count()).select_from(Asset)) == before
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0
        path.write_bytes(b'changed after inspection')
        with pytest.raises(ApiError) as changed:
            check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate(request))
        assert changed.value.code == 'SOURCE_CHANGED'


@pytest.mark.parametrize(('header_pattern', 'changes'), [
    (None, {'parameters': {'gain': None}}),
    (None, {'classification': {'frame_type': None}}),
    (None, {'parameters': {'cfa_pattern': 'RGGB'}}),
    ('RGGB', {'parameters': {'cfa_pattern': 'MONO'}}),
])
def test_scan_precheck_matches_registered_facts_with_nulls_and_cfa_overrides(library, header_pattern, changes):
    import numpy as np
    from astropy.io import fits

    from astrophotoflow.contracts.image_imports import ExplicitImportRequest, ImageInspectionRequest, ScannedCalibrationCheckRequest
    from astrophotoflow.modules.data.calibration.import_checks import check_import_calibration
    from astrophotoflow.modules.data.imports.explicit import (
        get_image_import,
        inspect_image_files,
        list_image_inspection_files,
        submit_image_import,
    )
    from astrophotoflow.modules.data.imports.runner import run_import_task

    database, settings = library
    path = settings.workspace / 'external' / 'explicit-values.fits'
    path.parent.mkdir(parents=True)
    hdu = fits.PrimaryHDU(np.zeros((6, 8), dtype=np.uint16))
    for key, value in {'IMAGETYP': 'Light Frame', 'GAIN': 0, 'OFFSET': 0, 'EXPTIME': 60,
                       'CCD-TEMP': -10, 'XBINNING': 1, 'YBINNING': 1}.items():
        hdu.header[key] = value
    if header_pattern:
        hdu.header['BAYERPAT'] = header_pattern
    hdu.writeto(path)
    scan = inspect_image_files(settings, ImageInspectionRequest(paths=[str(path)]))
    file_id = list_image_inspection_files(settings, scan['scan_id'])['items'][0]['file_id']
    metadata = {'parameters': {'parameter_mode': 'gain', 'readout_mode': 'test-mode', **changes.get('parameters', {})},
                **{key: value for key, value in changes.items() if key != 'parameters'}}
    selected = {'file_id': file_id, 'metadata': metadata}
    request_id = uuid4()
    with database.write_session() as session:
        _, dark = image(session, settings, 'dark', master=True)
        binding = {'dark': choice(dark)}
        preflight = check_import_calibration(session, settings, ScannedCalibrationCheckRequest.model_validate({
            'scan_id': scan['scan_id'], 'files': [selected], 'calibration_defaults': binding}))
        accepted = submit_image_import(session, settings, ExplicitImportRequest.model_validate({
            'request_id': request_id, 'scan_id': scan['scan_id'], 'files': [selected], 'destination': {'mode': 'standalone'}}))
    run_import_task(database, settings, accepted.receipt['task_id'])
    with database.read_session() as session:
        outcome = get_image_import(session, request_id)['items'][0]
        assert outcome['publication_status'] == 'published'
        registered = check_calibration(session, {'kind': 'asset_version', 'asset_id': outcome['asset_id'],
            'asset_version_id': outcome['asset_version_id']}, {'changes': binding})
        assert registered['state'] == preflight['state']
        diagnostics = lambda result: [(row['code'], row['field'], row['severity'], row.get('source_value'), row.get('target_value'))
            for row in result['items'][0]['diagnostics']]
        assert diagnostics(registered) == diagnostics(preflight)
        if changes.get('parameters', {}).get('gain', 'not-provided') is None:
            assert any(row['field'] == 'gain' and row['severity'] == 'unknown' for row in preflight['items'][0]['diagnostics'])
        if changes.get('parameters', {}).get('cfa_pattern') == 'RGGB':
            assert any(row['field'] == 'pixel_layout' and row['source_value'] == 'bayer' for row in preflight['items'][0]['diagnostics'])


def test_standalone_binding_is_immutable_and_request_replay_precedes_revision_check(library):
    database, settings = library
    with database.write_session() as session:
        light, version = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        request_id = uuid4()
        body = ImageCalibrationUpdate.model_validate({"request_id": request_id, "expected_revision": 1,
            "base_binding_version_id": None, "changes": {"dark": choice(dark)}, "accept_unknown": True})
        receipt = update_image_calibration(session, light.id, version.id, body)
        first = receipt["result"]["binding_version_id"]
        assert update_image_calibration(session, light.id, version.id, body) == receipt
        assert get_image_calibration_operation(session, request_id) == receipt
        assert light.revision == 2
        assert session.scalar(select(func.count()).select_from(AssetVersion).where(AssetVersion.asset_id == light.id)) == 1
        second = update_image_calibration(session, light.id, version.id, ImageCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": 2, "base_binding_version_id": first,
            "changes": {"dark": {"mode": "disabled"}}}))
        assert second["result"]["binding_version_id"] != first
        historical = get_image_calibration(session, light.id, version.id, first)
        assert historical["bindings"]["dark"]["target"] == target(dark)
        ImageCalibrationOut.model_validate(historical)
        ImageOperationOut.model_validate(receipt)
        changed_request = body.model_copy(update={"expected_revision": 99})
        with pytest.raises(ApiError, match="different content") as conflict:
            update_image_calibration(session, light.id, version.id, changed_request)
        assert conflict.value.code == "REQUEST_CONFLICT"


def test_explicit_append_preserves_old_flat_and_new_member_is_unconfigured(library):
    database, settings = library
    with database.write_session() as session:
        _, first = image(session, settings)
        _, second = image(session, settings)
        _, third = image(session, settings)
        _, flat_a = image(session, settings, "flat", master=True)
        _, flat_b = image(session, settings, "flat", master=True)
        group = create_group(session, "M31 across nights", [first], calibration_defaults={"flat": choice(flat_a)}, accept_unknown=True)
        original_id = group["dataset_version_id"]
        edited = edit_image_dataset_members(session, group["dataset_id"], ImageDatasetEditMembers.model_validate({
            "request_id": uuid4(), "expected_revision": 1, "base_version_id": original_id,
            "add": [{"asset_version_id": second.id, "calibration": {"flat": choice(flat_b)}}, {"asset_version_id": third.id}],
            "accept_unknown": True}))["result"]
        current = get_image_dataset_calibration(session, group["dataset_id"], edited["dataset_version_id"])
        assert [row["asset_version_id"] for row in current["items"]] == [first.id, second.id, third.id]
        assert current["items"][0]["effective"]["flat"]["target"] == target(flat_a)
        assert current["items"][1]["effective"]["flat"]["target"] == target(flat_b)
        assert current["items"][2]["effective"]["flat"] == UNCONFIGURED
        assert get_image_dataset_calibration(session, group["dataset_id"], original_id)["total"] == 1
        DatasetCalibrationPage.model_validate(current)


def test_group_member_inherit_disabled_and_unconfigured_are_distinct(library):
    database, settings = library
    with database.write_session() as session:
        _, first = image(session, settings)
        _, second = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        group = create_group(session, "lights", [first, second], calibration_defaults={"dark": choice(dark)}, accept_unknown=True)
        edited = update_image_dataset_calibration_members(session, group["dataset_id"], DatasetMemberCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": 1, "base_version_id": group["dataset_version_id"],
            "members": [{"asset_version_id": first.id, "changes": {"dark": {"mode": "unconfigured"}}},
                        {"asset_version_id": second.id, "changes": {"dark": {"mode": "disabled"}}}]}))["result"]
        page = get_image_dataset_calibration(session, group["dataset_id"], edited["dataset_version_id"])
        assert page["items"][0]["effective"]["dark"] == UNCONFIGURED
        assert page["items"][1]["effective"]["dark"] == {"mode": "disabled"}
        inherited = update_image_dataset_calibration_members(session, group["dataset_id"], DatasetMemberCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": edited["revision"], "base_version_id": edited["dataset_version_id"],
            "members": [{"asset_version_id": first.id, "changes": {"dark": {"mode": "inherit"}}}], "accept_unknown": True}))["result"]
        page = get_image_dataset_calibration(session, group["dataset_id"], inherited["dataset_version_id"])
        assert "dark" not in page["items"][0]["overrides"]
        assert page["items"][0]["effective"]["dark"]["target"] == target(dark)
        assert page["items"][1]["effective"]["dark"] == {"mode": "disabled"}


def test_known_camera_conflict_cannot_be_accepted_as_unknown(library):
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        _, dark = image(session, settings, "dark", master=True, camera=str(uuid4()))
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {"dark": target(dark)}, accept_unknown=True)
        assert error.value.code == "CALIBRATION_CONFLICT"


def test_unknown_master_history_requires_explicit_acceptance(library):
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {"dark": target(dark)})
        assert error.value.code == "CALIBRATION_UNKNOWN"
        assert validate_calibration_bindings(session, [light.id], {"dark": target(dark)}, accept_unknown=True)["unknown_count"] == 1


def test_only_master_targets_are_accepted_and_raw_groups_remain_manageable(library):
    from pydantic import ValidationError

    from astrophotoflow.contracts.calibration import CalibrationTarget
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        _, dark = image(session, settings, "dark")
        _, master = image(session, settings, "dark", master=True)
        raw = create_group(session, "raw darks", [dark])
        for candidate in ({"kind": "dataset_version", "id": raw["dataset_version_id"]}, target(dark)):
            with pytest.raises(ApiError) as error:
                validate_calibration_bindings(session, [light.id], {"dark": candidate}, accept_unknown=True)
            assert error.value.code == "CALIBRATION_CONFLICT"
        with pytest.raises(ValidationError):
            CalibrationTarget.model_validate({"kind": "dataset_version", "id": raw["dataset_version_id"]})
        assert validate_calibration_bindings(session, [light.id], {}, accept_unknown=False)["checked_bindings"] == 0
        assert validate_calibration_bindings(session, [light.id], {"dark": target(master)}, accept_unknown=True)["master_required_count"] == 0
        page = search_calibrations(session, "dark")
        assert [item["target"]["id"] for item in page["items"]] == [master.id]


def test_raw_flat_group_can_consume_master_darkflat_without_becoming_target(library):
    database, settings = library
    with database.write_session() as session:
        _, flat = image(session, settings, "flat", exposure=1)
        _, dark_flat = image(session, settings, "dark_flat", master=True, exposure=1)
        raw = create_group(session, "flats", [flat], calibration_defaults={"dark_flat": choice(dark_flat)}, accept_unknown=True)
        checked = check_calibration(session, {"kind": "dataset_version", "dataset_id": raw["dataset_id"],
            "dataset_version_id": raw["dataset_version_id"]}, limit=1)
        assert checked["total"] == 1
        assert checked["items"][0]["asset_version_id"] == flat.id
        assert checked["items"][0]["slot"] == "dark_flat"
        assert checked["items"][0]["master_required"] is False
        CalibrationCheckPage.model_validate(checked)


def test_science_inputs_pin_standalone_configuration_and_group_does_not_inherit_it(library, tmp_path):
    database, settings = library
    with database.write_session() as session:
        light_asset, light = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        first = apply_import_calibration(session, light.id, {"dark": target(dark)}, accept_unknown=True)
        apply_import_calibration(session, light.id, {"dark": None})
        group = create_group(session, "independent group", [light])
        light_id, asset_id = light.id, light_asset.id
        refs = calibration_references(session, {dark.id}, set())
        assert refs[0]["id"] == first["binding_version_id"]
    standalone = resolve_canvas_inputs(database, settings, AssetInputReference(kind="asset_version", asset_version_id=UUID(light_id),
        binding_version_id=UUID(first["binding_version_id"]), selection=ScienceSelection(kind="whole_file")), run_directory=tmp_path / "standalone")
    assert str(standalone.items[0].binding_version_id) == first["binding_version_id"]
    assert str(standalone.items[0].effective_calibration["dark"].id) == dark.id
    grouped = resolve_canvas_inputs(database, settings, DatasetInputReference(kind="dataset_version", dataset_version_id=UUID(group["dataset_version_id"]),
        members=[DatasetInputMember(member_index=0, asset_version_id=UUID(light_id), selection=ScienceSelection(kind="whole_file"))]), run_directory=tmp_path / "group")
    assert grouped.items[0].binding_version_id is None
    assert grouped.items[0].effective_calibration["dark"] is None
    with database.read_session() as session:
        assert get_image_calibration(session, asset_id, light_id)["bindings"]["dark"] == {"mode": "disabled"}
        assert session.scalar(select(func.count()).select_from(ImageCalibrationConfiguration)) == 2


def test_default_change_affects_only_inheritors_and_keeps_old_fixed_version(library):
    database, settings = library
    with database.write_session() as session:
        _, first = image(session, settings)
        _, second = image(session, settings)
        _, dark_a = image(session, settings, "dark", master=True)
        _, dark_b = image(session, settings, "dark", master=True)
        group = create_image_dataset(session, ImageDatasetCreate.model_validate({"request_id": uuid4(), "name": "lights",
            "members": [{"asset_version_id": first.id}, {"asset_version_id": second.id, "calibration": {"dark": {"mode": "disabled"}}}],
            "calibration_defaults": {"dark": choice(dark_a)}, "accept_unknown": True}))["result"]
        edited = update_image_dataset_calibration_defaults(session, group["dataset_id"], DatasetCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": 1, "base_version_id": group["dataset_version_id"],
            "changes": {"dark": choice(dark_b)}, "accept_unknown": True}))["result"]
        current = get_image_dataset_calibration(session, group["dataset_id"], edited["dataset_version_id"])
        assert current["items"][0]["effective"]["dark"]["target"] == target(dark_b)
        assert current["items"][1]["effective"]["dark"] == {"mode": "disabled"}
        historical = get_image_dataset_calibration(session, group["dataset_id"], group["dataset_version_id"])
        assert historical["items"][0]["effective"]["dark"]["target"] == target(dark_a)


def test_incoming_choice_does_not_silently_inherit_and_standalone_rejects_inherit():
    values = incoming_bindings({"flat": {"mode": "inherit"}})
    assert "flat" not in values
    assert values["dark"] == UNCONFIGURED
    with pytest.raises(ApiError):
        patch_bindings({}, {"flat": {"mode": "inherit"}})


@pytest.mark.parametrize("field,value", [("offset", 1), ("readout_mode", "other-mode"), ("exposure_seconds", 120)])
def test_dark_electronic_and_exposure_mismatches_are_hard_conflicts(library, field, value):
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        dark_asset, dark = image(session, settings, "dark", master=True)
        setattr(dark_asset, field, value)
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {"dark": target(dark)}, accept_unknown=True)
        assert error.value.code == "CALIBRATION_CONFLICT"


def test_dark_temperature_difference_is_diagnostic_not_an_invented_tolerance(library):
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        dark_asset, dark = image(session, settings, "dark", master=True)
        dark_asset.sensor_temperature_c = -8
        checked = validate_calibration_bindings(session, [light.id], {"dark": target(dark)}, accept_unknown=True)
        assert any(issue["code"] == "TEMPERATURE_DIFFERENCE" and issue["severity"] == "warning"
                   for issue in checked["items"][0]["diagnostics"])


def test_flat_exposure_can_differ_but_selected_accessory_must_not(library):
    database, settings = library
    with database.write_session() as session:
        light_asset, light = image(session, settings, exposure=300)
        flat_asset, flat = image(session, settings, "flat", master=True, exposure=1)
        validate_calibration_bindings(session, [light.id], {"flat": target(flat)}, accept_unknown=True)
        light_asset.equipment_snapshot = {"optical_system_id": {"effective_focal_length_mm": 1645,
            "optical_accessory": {"id": str(uuid4()), "name": "first reducer", "factor": 0.7}}}
        flat_asset.equipment_snapshot = {"optical_system_id": {"effective_focal_length_mm": 1645,
            "optical_accessory": {"id": str(uuid4()), "name": "different reducer", "factor": 0.7}}}
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {"flat": target(flat)}, accept_unknown=True)
        assert error.value.code == "CALIBRATION_CONFLICT"


def test_known_gain_conflict_is_not_hidden_by_unknown_parameter_mode(library):
    database, settings = library
    with database.write_session() as session:
        light_asset, light = image(session, settings)
        dark_asset, dark = image(session, settings, "dark", master=True)
        light_asset.parameter_mode = None
        dark_asset.parameter_mode = None
        dark_asset.gain = 99
        with pytest.raises(ApiError) as error:
            validate_calibration_bindings(session, [light.id], {"dark": target(dark)}, accept_unknown=True)
        assert error.value.code == "CALIBRATION_CONFLICT"
        assert "METADATA_MISMATCH" in error.value.fields[0]["message"]


def test_unrelated_default_change_does_not_reject_previously_accepted_unknown_dark(library):
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        group = create_group(session, "lights", [light], calibration_defaults={"dark": choice(dark)}, accept_unknown=True)
        changed = update_image_dataset_calibration_defaults(session, group["dataset_id"], DatasetCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": 1, "base_version_id": group["dataset_version_id"],
            "changes": {"bias": {"mode": "disabled"}}}))["result"]
        assert changed["diagnostics"]["checked_bindings"] == 0
        current = get_image_dataset_calibration(session, group["dataset_id"], changed["dataset_version_id"])
        assert current["items"][0]["effective"]["dark"]["target"] == target(dark)


def test_member_change_does_not_revalidate_unaffected_members(library):
    database, settings = library
    with database.write_session() as session:
        _, first = image(session, settings)
        _, second = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        group = create_group(session, "lights", [first, second], calibration_defaults={"dark": choice(dark)}, accept_unknown=True)
        changed = update_image_dataset_calibration_members(session, group["dataset_id"], DatasetMemberCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": 1, "base_version_id": group["dataset_version_id"],
            "members": [{"asset_version_id": first.id, "changes": {"dark": {"mode": "disabled"}}}]}))["result"]
        current = get_image_dataset_calibration(session, group["dataset_id"], changed["dataset_version_id"])
        assert current["items"][1]["effective"]["dark"]["target"] == target(dark)


def test_standalone_unrelated_change_preserves_accepted_unknown_binding(library):
    database, settings = library
    with database.write_session() as session:
        light_asset, light = image(session, settings)
        _, dark = image(session, settings, "dark", master=True)
        initial = apply_import_calibration(session, light.id, {"dark": target(dark)}, accept_unknown=True)
        receipt = update_image_calibration(session, light_asset.id, light.id, ImageCalibrationUpdate.model_validate({
            "request_id": uuid4(), "expected_revision": light_asset.revision,
            "base_binding_version_id": initial["binding_version_id"], "changes": {"bias": {"mode": "disabled"}}}))
        assert receipt["result"]["bindings"]["dark"]["target"] == target(dark)


def test_master_target_check_explains_fixed_reference_without_reapplying_its_bindings(library):
    database, settings = library
    with database.write_session() as session:
        light_asset, light = image(session, settings)
        _, flat = image(session, settings, "flat", master=True, exposure=1)
        _, dark_flat = image(session, settings, "dark_flat", master=True, exposure=1)
        apply_import_calibration(session, flat.id, {"dark_flat": target(dark_flat)}, accept_unknown=True)
        apply_import_calibration(session, light.id, {"flat": target(flat)}, accept_unknown=True)
        checked = check_calibration(session, {"kind": "asset_version", "asset_id": light_asset.id, "asset_version_id": light.id}, limit=1)
        assert checked["unknown_count"] == 1
        assert checked["checked_bindings"] == checked["total"] == 1
        first = checked["items"][0]
        assert first["binding_source"] == "standalone"
        assert first["source_asset_revision"] == light_asset.revision
        assert first["source_metadata_basis"] == "current_metadata"
        assert first["source_availability"] == first["target_availability"] == "available"
        assert first["master_required"] is False
        assert first["dependency_path"] == [target(flat)]
        assert first["target_asset_revision"] == 1
        CalibrationCheckPage.model_validate(checked)


def test_group_check_distinguishes_default_and_override_and_known_missing_source(library):
    database, settings = library
    with database.write_session() as session:
        _, first = image(session, settings)
        _, second = image(session, settings)
        _, dark_a = image(session, settings, "dark", master=True)
        _, dark_b = image(session, settings, "dark", master=True)
        group = create_image_dataset(session, ImageDatasetCreate.model_validate({"request_id": uuid4(), "name": "lights",
            "members": [{"asset_version_id": first.id}, {"asset_version_id": second.id, "calibration": {"dark": choice(dark_b)}}],
            "calibration_defaults": {"dark": choice(dark_a)}, "accept_unknown": True}))["result"]
        dark_a.availability = "missing"
        checked = check_calibration(session, {"kind": "dataset_version", "dataset_id": group["dataset_id"], "dataset_version_id": group["dataset_version_id"]})
        assert checked["items"][0]["binding_source"] == "dataset_default"
        assert checked["items"][0]["target_availability"] == "missing"
        assert checked["items"][0]["state"] == "conflict" and checked["items"][0]["applicable"] is False
        assert checked["items"][1]["binding_source"] == "member_override"


def test_unused_default_still_rejects_raw_subframe_target(library):
    database, settings = library
    with database.write_session() as session:
        _, light = image(session, settings)
        _, raw_dark = image(session, settings, "dark")
        consumer = create_image_dataset(session, ImageDatasetCreate.model_validate({"request_id": uuid4(), "name": "lights",
            "members": [{"asset_version_id": light.id, "calibration": {"dark": {"mode": "disabled"}}}]}))["result"]
        with pytest.raises(ApiError) as error:
            update_image_dataset_calibration_defaults(session, consumer["dataset_id"], DatasetCalibrationUpdate.model_validate({
                "request_id": uuid4(), "expected_revision": 1, "base_version_id": consumer["dataset_version_id"],
                "changes": {"dark": {"mode": "target", "target": target(raw_dark)}},
                "accept_unknown": True}))
        assert error.value.code == "CALIBRATION_CONFLICT"


@pytest.mark.parametrize("frame_type", ["light", "flat", "dark", "dark_flat"])
def test_bias_is_optional_for_all_supported_consumers_and_not_implicitly_disabled(library, frame_type):
    database, settings = library
    with database.write_session() as session:
        asset, consumer = image(session, settings, frame_type)
        _, bias = image(session, settings, "bias", master=True, exposure=0)
        empty = get_image_calibration(session, asset.id, consumer.id)
        assert empty["bindings"]["bias"] == {"mode": "unconfigured"}
        saved = apply_import_calibration(session, consumer.id, {"bias": target(bias)}, accept_unknown=True)
        assert saved["bindings"]["bias"] == choice(bias)
        assert saved["slots"]["bias"]["status"] == "target"


def test_candidate_search_paginates_before_optional_science_check(library, monkeypatch):
    database, settings = library
    with database.write_session() as session:
        masters = []
        for index in range(8):
            asset, master = image(session, settings, "dark", master=True)
            asset.name = f"Master Dark {index}"
            masters.append(master)
        for _ in range(12):
            image(session, settings, "dark", master=False)
        session.flush()
        checks = []
        def checked(_session, consumer, proposal, limit):
            checks.append(proposal["changes"]["dark"]["target"]["id"])
            return {"state": "unknown"}
        monkeypatch.setattr("astrophotoflow.modules.data.calibration.service.check_calibration", checked)
        page = search_calibrations(session, "dark", consumer={"kind": "asset_version"},
                                   query={"text": "master dark", "limit": 2, "offset": 3})
        assert page["total"] == 8
        assert [item["target"]["id"] for item in page["items"]] == [masters[3].id, masters[4].id]
        assert checks == [masters[3].id, masters[4].id]
        checks.clear()
        no_consumer = search_calibrations(session, "dark", query={"limit": 1, "offset": 7})
        assert no_consumer["total"] == 8 and len(no_consumer["items"]) == 1
        assert checks == []
        assert search_calibrations(session, "dark", query={"text": "%"})["total"] == 0

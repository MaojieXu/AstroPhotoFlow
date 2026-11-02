"""Current device inputs are minimal; previously frozen facts remain readable."""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

_spec = importlib.util.spec_from_file_location(
    "simplify_device_fields", Path(__file__).resolve().parents[3] / "scripts/simplify_device_fields.py")
_cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cleanup)
simplify = _cleanup.simplify

from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentSnapshot


@pytest.mark.parametrize("body", [
    {"kind": "camera", "name": "camera", "serial_number": "removed"},
    {"kind": "camera", "name": "camera", "specs": {"sensor_mode": "mono"}},
    {"kind": "telescope", "name": "scope", "specs": {"aperture_mm": 80}},
    {"kind": "filter", "name": "L", "serial_number": "removed"},
])
def test_retired_registry_fields_are_not_editable(body):
    with pytest.raises(ValidationError):
        TypeAdapter(EquipmentCreate).validate_python(body)


@pytest.mark.parametrize("snapshot", [
    {"kind": "camera", "name": "old camera", "serial_number": "SN-1", "specs": {"sensor_mode": "mono"}},
    {"kind": "telescope", "name": "old scope", "serial_number": "SN-2", "specs": {"aperture_mm": 80}},
])
def test_frozen_retired_facts_are_preserved(snapshot):
    frozen = TypeAdapter(EquipmentSnapshot).validate_python(snapshot)
    assert frozen.model_dump(mode="json") == snapshot


def test_explicit_cleanup_preserves_rows_references_and_historical_json(tmp_path):
    database = tmp_path / "workspace.sqlite3"
    historical = ' {"serial_number":"SN-1", "specs":{"sensor_mode":"mono","aperture_mm":80}} '
    with sqlite3.connect(database) as connection:
        connection.executescript('''
            CREATE TABLE equipment (id TEXT PRIMARY KEY,kind TEXT,name TEXT,specs TEXT,serial_number TEXT,revision INTEGER);
            CREATE TABLE equipment_setup_member (id TEXT PRIMARY KEY,setup_id TEXT,equipment_id TEXT,inline_equipment TEXT,optical_accessory_id TEXT);
            CREATE TABLE capture_preset (id TEXT PRIMARY KEY);
            CREATE TABLE asset_version (id TEXT PRIMARY KEY,equipment_snapshot TEXT);
        ''')
        connection.execute("INSERT INTO equipment VALUES(?,?,?,?,?,?)", (
            "camera", "camera", "Keep name", json.dumps({"sensor_mode": "mono", "pixel_size_um": 3.76}), "SN-1", 7))
        connection.execute("INSERT INTO equipment_setup_member VALUES(?,?,?,?,?)", (
            "member", "setup", None, json.dumps({"kind": "telescope", "name": "inline", "serial_number": "SN-2",
                                                 "specs": {"aperture_mm": 80, "native_focal_length_mm": 480}}), None))
        connection.execute("INSERT INTO asset_version VALUES(?,?)", ("version", historical))
    plan = simplify(database, apply=False)
    assert plan["state"] == "planned"
    result = simplify(database, apply=True)
    assert result["unchanged_data_verified"]
    assert result["mono_modes_consolidated"] == 1
    assert result["before"] == result["after"]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id,name,revision FROM equipment").fetchone() == ("camera", "Keep name", 7)
        assert json.loads(connection.execute("SELECT specs FROM equipment").fetchone()[0]) == {
            "cfa_pattern": "MONO", "pixel_size_um": 3.76}
        assert connection.execute("SELECT equipment_snapshot FROM asset_version").fetchone()[0] == historical
        assert "serial_number" not in {row[1] for row in connection.execute("PRAGMA table_info(equipment)")}
    assert simplify(database, apply=True)["state"] == "already_simplified"


def test_cleanup_never_overrides_an_explicit_cfa_or_guesses_color_pattern():
    assert _cleanup.clean_specs("camera", {"sensor_mode": "mono", "cfa_pattern": "RGGB"}) == ({"cfa_pattern": "RGGB"}, False)
    assert _cleanup.clean_specs("camera", {"sensor_mode": "color"}) == ({}, False)

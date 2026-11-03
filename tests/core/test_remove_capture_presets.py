"""Retired preset tables are removed, with an explicit recoverable backup."""
import sqlite3

from alembic import command

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import SCHEMA_REVISION, _alembic_config, current_revision, upgrade_database
from astrophotoflow.modules.data.persistence import schema_metadata


def test_remove_presets_upgrade_preserves_devices_and_backs_up(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    settings.data_dir.mkdir(parents=True)
    command.upgrade(_alembic_config(settings), "0003_equipment_mount")
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("INSERT INTO equipment (id,kind,name,specs,status,revision,name_search_key) VALUES ('mount','mount','AP1100','{}','active',1,'ap1100')")
        connection.execute("INSERT INTO equipment_setup (id,name,status,revision,name_search_key) VALUES ('rig','rig','active',1,'rig')")
        connection.execute("INSERT INTO capture_preset (id,equipment_setup_id,name,parameters,status,revision,name_search_key) VALUES ('preset','rig','old','{}','active',1,'old')")
        devices = connection.execute("SELECT * FROM equipment").fetchall()
    upgrade_database(settings)
    assert current_revision(settings.database_path) == SCHEMA_REVISION
    backups = list((settings.data_dir / "backups").glob("before-remove-capture-presets-*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT id FROM capture_preset").fetchall() == [("preset",)]
    with sqlite3.connect(settings.database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "capture_preset" not in tables and "capture_preset_selection" not in tables
        assert connection.execute("SELECT * FROM equipment").fetchall() == devices
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert "capture_preset" not in schema_metadata().tables
    upgrade_database(settings)
    assert len(list((settings.data_dir / "backups").glob("*.sqlite3"))) == 1

"""Upgrade the existing image library without rewriting historical snapshots."""

import sqlite3

from alembic import command

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import SCHEMA_REVISION, _alembic_config, current_revision, upgrade_database


def test_mount_upgrade_preserves_referenced_equipment_and_backs_up(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ("http://127.0.0.1:8188",), workspace=tmp_path)
    command.upgrade(_alembic_config(settings), "0002_image_management")
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("INSERT INTO equipment (id,kind,name,specs,status,revision,name_search_key) VALUES ('camera','camera','camera','{}','active',5,'camera')")
        connection.execute("INSERT INTO equipment_setup (id,name,status,revision,name_search_key) VALUES ('rig','rig','active',3,'rig')")
        connection.execute("INSERT INTO equipment_setup_member (id,setup_id,position,equipment_id) VALUES ('member','rig',0,'camera')")
        before = connection.execute("SELECT * FROM equipment").fetchall()
        indexes = connection.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='equipment' ORDER BY name").fetchall()
    upgrade_database(settings)
    assert current_revision(settings.database_path) == SCHEMA_REVISION
    backups = list((tmp_path / "backups").glob("before-equipment-mount-*.sqlite3"))
    assert len(backups) == 1 and current_revision(backups[0]) == "0002_image_management"
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT * FROM equipment").fetchall() == before
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='equipment' ORDER BY name").fetchall() == indexes
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        connection.execute("INSERT INTO equipment (id,kind,name,specs,status,revision,name_search_key) VALUES ('mount','mount','AP1100','{}','active',1,'ap1100')")
    upgrade_database(settings)
    assert len(list((tmp_path / "backups").glob("*.sqlite3"))) == 1

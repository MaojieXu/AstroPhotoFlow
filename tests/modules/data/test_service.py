from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from uuid import uuid4
import json
import sys
from types import SimpleNamespace
import pytest
from alembic.autogenerate import compare_metadata
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
import astrophotoflow.core.database as backend
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.core.database.db import Database
from astrophotoflow.modules.data.models import Asset, AssetTask, AssetTaskItem, AssetVersion, Base, Dataset, DatasetMember, DatasetVersion, Equipment, LibraryEntryRemoval, Preview, Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.core.database.schema import SCHEMA_REVISION, SchemaError, current_revision, database_lock, ensure_schema_for_serve, upgrade_database
from astrophotoflow.contracts.common import ErrorEnvelope
from astrophotoflow.core.config import ConfigurationError, Settings, ensure_data_dir, ensure_service_token, load_settings

from astrophotoflow.comfyui.proxy import ROUTES

TOKEN="test-token"
def auth(): return {"Authorization":f"Bearer {TOKEN}"}


def test_internal_shutdown_requires_token_and_is_not_a_public_api(service):
    _, client, _ = service
    calls = []
    client.app.state.shutdown = lambda: calls.append("stop")
    assert client.post("/internal/shutdown").status_code == 401
    assert calls == []
    assert "/internal/shutdown" not in client.app.openapi()["paths"]
    assert client.post("/internal/shutdown", headers=auth()).json() == {"status": "stopping"}
    assert calls == ["stop"]


@pytest.fixture
def service(tmp_path):
    settings=Settings("127.0.0.1",8190,tmp_path,("http://127.0.0.1:8188",), workspace=tmp_path)
    with database_lock(settings): upgrade_database(settings)
    app=create_app(settings,TOKEN)
    with TestClient(app) as client: yield settings,client,app.state.database
    app.state.database.close()

@pytest.fixture
def managed_service(service):
    settings, client, database = service
    path = settings.workspace / "run/processes.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"workspace": str(settings.workspace), "maintenance_operation_id": None, "processes": []}), encoding="utf-8")
    return settings, client, database, str(uuid4())

def add_equipment(c,kind,name,specs=None):
    d={"kind":kind,"name":name}
    if specs is not None: d["specs"]=specs
    return c.post("/api/v1/equipment",headers=auth(),json=d)


@pytest.mark.parametrize("pattern",["MONO","RGGB","BGGR","GRBG","GBRG","XTRANS","QUAD_BAYER"])
def test_camera_cfa_specs_accept_registered_patterns(service,pattern):
    _,client,_=service
    created=add_equipment(client,"camera","Camera "+pattern,{"cfa_pattern":pattern})
    assert created.status_code==201,created.text
    assert created.json()["specs"]["cfa_pattern"]==pattern


def test_camera_cfa_specs_reject_unregistered_pattern(service):
    _,client,_=service
    rejected=add_equipment(client,"camera","Unknown CFA",{"cfa_pattern":"FUJI_GUESS"})
    assert rejected.status_code==422

def test_init_lock_token_and_unknown_schema(tmp_path):
    s=Settings("127.0.0.1",8190,tmp_path,(), workspace=tmp_path)
    with database_lock(s):
        with pytest.raises(SchemaError): database_lock(s)
        assert upgrade_database(s) is None
    assert current_revision(s.database_path)==SCHEMA_REVISION
    token=ensure_service_token(s)
    token_mode=s.token_path.stat().st_mode&0o777
    assert ensure_service_token(s)==token
    if sys.platform != "win32":
        assert token_mode==0o600
    legacy=tmp_path/"legacy"; legacy.mkdir()
    old=Settings("127.0.0.1",8190,legacy,(), workspace=tmp_path)
    with sqlite3.connect(old.database_path) as db: db.execute("CREATE TABLE keep_me(value TEXT)")
    with pytest.raises(SchemaError): ensure_schema_for_serve(old)
    with pytest.raises(SchemaError): upgrade_database(old)
    with sqlite3.connect(old.database_path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='keep_me'").fetchone()
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone()

def test_alembic_initial_migration_matches_orm_metadata(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    with database_lock(settings):
        upgrade_database(settings)
    engine = create_engine("sqlite:///" + str(settings.database_path))
    with engine.connect() as connection:
        changes = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert changes == []

def test_existing_data_directory_permissions_are_not_changed(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    settings.data_dir.chmod(0o750)
    mode = settings.data_dir.stat().st_mode
    ensure_data_dir(settings)
    assert settings.data_dir.stat().st_mode == mode
    if sys.platform != "win32":
        assert mode & 0o777 == 0o750


def test_import_root_settings_require_unique_ids_and_absolute_paths(tmp_path):
    config = tmp_path / "config.toml"
    prefix = """[server]
host = "127.0.0.1"
port = 8190

[storage]
data_dir = "~/.local/share/astrophotoflow"

[comfyui]
allowed_origins = ["http://127.0.0.1:8188"]
"""
    config.write_text(prefix + """
[[imports.roots]]
id = "astrodata"
path = "~/AstroData"
""")
    settings = load_settings(config)
    assert settings.import_roots[0].id == "astrodata"
    assert settings.import_roots[0].path.is_absolute()

    config.write_text(prefix + """
[[imports.roots]]
id = "bad"
path = "relative/path"
""")
    with pytest.raises(ConfigurationError, match="绝对路径"):
        load_settings(config)

    config.write_text(prefix + "\n".join((
        "[[imports.roots]]", 'id = "duplicate"', f'path = "{(tmp_path / "a").as_posix()}"', "",
        "[[imports.roots]]", 'id = "duplicate"', f'path = "{(tmp_path / "b").as_posix()}"', "",
    )))
    with pytest.raises(ConfigurationError, match="唯一"):
        load_settings(config)

def test_explicit_upgrade_keeps_consistent_backup_on_failure(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    with sqlite3.connect(settings.database_path) as db:
        db.execute("CREATE TABLE alembic_version(version_num VARCHAR(32) NOT NULL)")
        db.execute("INSERT INTO alembic_version VALUES ('0000_unknown')")
        db.execute("CREATE TABLE preserved(value TEXT)")
        db.execute("INSERT INTO preserved VALUES ('same snapshot')")
    with pytest.raises(SchemaError, match="备份均已保留"):
        upgrade_database(settings)
    backups = list((settings.data_dir / "backups").glob("*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("SELECT value FROM preserved").fetchone() == ("same snapshot",)
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0000_unknown",)


def test_stage_two_upgrade_preserves_stage_one_records_and_backs_up(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    config = Config(str(Path(backend.__file__).resolve().parent / "alembic.ini"))
    config.attributes["database_url"] = "sqlite:///" + str(settings.database_path)
    command.upgrade(config, "0001_foundation")

    project_id, equipment_id = str(uuid4()), str(uuid4())
    asset_id, version_id, reference_id = str(uuid4()), str(uuid4()), str(uuid4())
    with sqlite3.connect(settings.database_path) as db:
        db.execute(
            "INSERT INTO project (id,name,status,revision) VALUES (?,?,?,?)",
            (project_id, "pre-stage-two", "active", 3),
        )
        db.execute(
            "INSERT INTO equipment (id,kind,name,specs,status,revision) VALUES (?,?,?,?,?,?)",
            (equipment_id, "camera", "preserved camera", "{}", "active", 2),
        )
        db.execute(
            "INSERT INTO asset (id,name,scope,role) VALUES (?,?,?,?)",
            (asset_id, "existing asset", "shared", "raw"),
        )
        db.execute(
            "INSERT INTO asset_version (id,asset_id,version_number,storage_mode,storage_location,availability) VALUES (?,?,?,?,?,?)",
            (version_id, asset_id, 1, "reference", "roots/raw.fits", "unknown"),
        )
        db.execute("UPDATE asset SET current_version_id=? WHERE id=?", (version_id, asset_id))
        db.execute(
            "INSERT INTO project_asset_reference (id,project_id,asset_version_id) VALUES (?,?,?)",
            (reference_id, project_id, version_id),
        )

    backup = upgrade_database(settings)
    assert backup is not None and backup.is_file()
    assert current_revision(settings.database_path) == SCHEMA_REVISION
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT name,revision FROM project WHERE id=?", (project_id,)).fetchone() == ("pre-stage-two", 3)
        assert db.execute("SELECT name FROM equipment WHERE id=?", (equipment_id,)).fetchone() == ("preserved camera",)
        assert db.execute("SELECT parameters,status,revision FROM asset WHERE id=?", (asset_id,)).fetchone() == ("{}", "active", 1)
        assert db.execute("SELECT COUNT(*) FROM project_asset_reference WHERE id=?", (reference_id,)).fetchone() == (1,)
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001_foundation",)


def test_asset_fact_backfill_uses_current_version_and_preserves_manual_clears(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    config = Config(str(Path(backend.__file__).resolve().parent / "alembic.ini"))
    config.attributes["database_url"] = "sqlite:///" + str(settings.database_path)
    command.upgrade(config, "0001_foundation")
    ids = [str(uuid4()) for _ in range(6)]
    camera_id, old_asset_id, old_version_id, edited_asset_id, edited_version_id, _ = ids
    with sqlite3.connect(settings.database_path) as db:
        db.execute("INSERT INTO equipment (id,kind,name,specs,status,revision) VALUES (?,?,?,?,?,?)",
                   (camera_id, "camera", "legacy camera", "{}", "active", 1))
        db.execute("INSERT INTO asset (id,name,scope,role) VALUES (?,?,?,?)", (old_asset_id, "legacy", "shared", "calibration"))
        db.execute("INSERT INTO asset_version (id,asset_id,version_number,storage_mode,storage_location,availability,camera_id,frame_type,calibration_level,capture_snapshot) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (old_version_id, old_asset_id, 1, "reference", "old.fit", "available", camera_id, "dark", "master", json.dumps({"gain": 100, "exposure_seconds": 60, "sensor_temperature_c": 0})))
        db.execute("UPDATE asset SET current_version_id=? WHERE id=?", (old_version_id, old_asset_id))
    command.upgrade(config, "0003_capture_profile_gain_mode")
    with sqlite3.connect(settings.database_path) as db:
        db.execute("INSERT INTO asset (id,name,scope,role,current_version_id,classification,parameters,value_sources) VALUES (?,?,?,?,?,?,?,?)",
                   (edited_asset_id, "edited", "shared", "raw", edited_version_id, '{"frame_type":null}', '{"gain":77,"camera_id":null}', '{"gain":"manual","classification.frame_type":"manual"}'))
        db.execute("INSERT INTO asset_version (id,asset_id,version_number,storage_mode,storage_location,availability,frame_type,capture_snapshot) VALUES (?,?,?,?,?,?,?,?)",
                   (edited_version_id, edited_asset_id, 1, "reference", "edited.fit", "available", "light", json.dumps({"gain": 12, "exposure_seconds": 30})))

    backup = upgrade_database(settings)
    assert backup is not None and current_revision(settings.database_path) == SCHEMA_REVISION
    with sqlite3.connect(settings.database_path) as db:
        legacy = db.execute("SELECT classification,parameters FROM asset WHERE id=?", (old_asset_id,)).fetchone()
        edited = db.execute("SELECT classification,parameters,value_sources FROM asset WHERE id=?", (edited_asset_id,)).fetchone()
        assert json.loads(legacy[0]) == {"frame_type": "dark", "frame_class": "masterframe"}
        assert json.loads(legacy[1]) == {"camera_id": camera_id, "gain": 100, "exposure_seconds": 60, "sensor_temperature_c": 0}
        assert json.loads(edited[0]) == {"frame_type": None}
        assert json.loads(edited[1]) == {"gain": 77, "camera_id": None, "exposure_seconds": 30}
        assert json.loads(edited[2]) == {"gain": "manual", "classification.frame_type": "manual", "exposure_seconds": "file"}
        before = (legacy, edited)
    assert upgrade_database(settings) is None
    with sqlite3.connect(settings.database_path) as db:
        after_legacy = db.execute("SELECT classification,parameters FROM asset WHERE id=?", (old_asset_id,)).fetchone()
        after_edited = db.execute("SELECT classification,parameters,value_sources FROM asset WHERE id=?", (edited_asset_id,)).fetchone()
    assert (after_legacy, after_edited) == before

def test_config_crud_references_revision_and_persistence(service):
    s,c,database=service
    b={"kind":"camera","name":"相机","model":"same","specs":{"sensor_mode":"mono"}}
    camera=c.post("/api/v1/equipment",headers=auth(),json=b).json()
    duplicate=c.post("/api/v1/equipment",headers=auth(),json=b).json()
    assert camera["id"]!=duplicate["id"]
    optics=add_equipment(c,"optical_system","成像系统",{"native_focal_length_mm":600,"effective_focal_length_mm":400}).json()
    project=c.post("/api/v1/projects",headers=auth(),json={"name":"M31"})
    assert project.status_code==201
    update={"base_revision":1,"kind":"optical_system","specs":{"native_focal_length_mm":800}}
    first=c.patch(f"/api/v1/equipment/{optics['id']}",headers=auth(),json=update)
    stale=c.patch(f"/api/v1/equipment/{optics['id']}",headers=auth(),json={**update,"name":"stale"})
    assert first.status_code==200 and first.json()["specs"]["effective_focal_length_mm"]==400
    assert stale.status_code==409
    assert add_equipment(c,"optical_system","zero focal",{"effective_focal_length_mm":0}).status_code==422
    archived=c.patch(f"/api/v1/equipment/{camera['id']}",headers=auth(),json={"base_revision":1,"kind":"camera","status":"archived"})
    assert archived.status_code==200 and c.get(f"/api/v1/equipment/{camera['id']}",headers=auth()).json()["status"]=="archived"
    restored=c.patch(f"/api/v1/equipment/{camera['id']}",headers=auth(),json={"base_revision":2,"kind":"camera","status":"active"})
    assert restored.status_code==200 and restored.json()["id"]==camera["id"]
    database.close()
    with TestClient(create_app(s,TOKEN)) as restarted:
        out=restarted.get(f"/api/v1/projects/{project.json()['id']}",headers=auth())
        assert out.status_code==200 and out.json()["created_at"].endswith("Z")



def test_shared_and_project_version_scope(service):
    _,c,database=service
    with database.write_session() as s:
        p1,p2=Project(id=str(uuid4()),name="1",status="active",revision=1),Project(id=str(uuid4()),name="2",status="active",revision=1)
        s.add_all([p1,p2]);s.flush()
        shared=Asset(id=str(uuid4()),name="shared",scope="shared",role="raw",created_at=datetime.now(timezone.utc))
        own=Asset(id=str(uuid4()),name="own",scope="project",owner_project_id=p1.id,role="intermediate")
        foreign=Asset(id=str(uuid4()),name="foreign",scope="project",owner_project_id=p2.id,role="intermediate")
        s.add_all([shared,own,foreign]);s.flush()
        v1=AssetVersion(id=str(uuid4()),asset_id=shared.id,version_number=1,storage_mode="reference",storage_location="v1",availability="unknown",frame_type="light",capture_snapshot={"gain":10})
        v2=AssetVersion(id=str(uuid4()),asset_id=shared.id,version_number=2,storage_mode="reference",storage_location="v2",availability="unknown",frame_type="dark")
        ownv=AssetVersion(id=str(uuid4()),asset_id=own.id,version_number=1,storage_mode="managed",storage_location="own",availability="unknown")
        foreignv=AssetVersion(id=str(uuid4()),asset_id=foreign.id,version_number=1,storage_mode="managed",storage_location="foreign",availability="unknown")
        s.add_all([v1,v2,ownv,foreignv]);s.flush();shared.current_version_id=v2.id
        pinned_ref=ProjectAssetReference(id=str(uuid4()),project_id=p1.id,asset_version_id=v1.id)
        own_ref=ProjectAssetReference(id=str(uuid4()),project_id=p1.id,asset_version_id=ownv.id)
        foreign_ref=ProjectAssetReference(id=str(uuid4()),project_id=p1.id,asset_version_id=foreignv.id)
        s.add_all([pinned_ref,own_ref,foreign_ref])
        ids=(p1.id,p2.id,shared.id,foreign.id,v1.id,v2.id,pinned_ref.id,foreign_ref.id)
    assert c.get("/api/v1/library/assets",headers=auth()).json()["total"]==1
    assert c.get(f"/api/v1/library/assets/{ids[2]}",headers=auth()).json()["current_version"]["id"]==ids[5]
    rows=c.get(f"/api/v1/projects/{ids[0]}/assets",headers=auth()).json()["items"]
    assert len(rows)==2 and next(x for x in rows if x["asset"]["scope"]=="shared")["version"]["id"]==ids[4]
    detail=c.get(f"/api/v1/projects/{ids[0]}/asset-references/{ids[6]}",headers=auth())
    assert detail.status_code==200 and detail.json()["version"]["id"]==ids[4]
    assert c.get(f"/api/v1/projects/{ids[0]}/asset-references/{ids[7]}",headers=auth()).status_code==404
    assert c.get(f"/api/v1/library/assets/{ids[3]}",headers=auth()).status_code==404
    assert c.get(f"/api/v1/projects/{ids[1]}/assets",headers=auth()).json()["total"]==0

def test_real_empty_auth_error_and_readonly_routes(service):
    _,c,_=service
    assert c.get("/api/v1/library/assets",headers=auth()).json()["items"]==[]
    denied=c.get("/api/v1/health")
    assert denied.status_code==401 and denied.json()["error"]["code"]=="AUTHENTICATION_REQUIRED"
    assert denied.headers["X-Request-ID"]==denied.json()["request_id"]
    assert c.post("/api/v1/library/assets",headers=auth(),json={}).status_code==405
    assert set(c.get("/openapi.json").json()["paths"]["/api/v1/library/assets"])=={"get"}
    assert c.get("/docs").status_code == 404


def test_library_error_responses_match_openapi_error_envelope(service):
    _, client, _ = service
    openapi = client.get("/openapi.json").json()
    declared = openapi["paths"]["/api/v1/library/items"]["get"]["responses"]
    assert declared["401"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorEnvelope")
    assert declared["422"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorEnvelope")

    denied = client.get("/api/v1/library/items")
    invalid = client.get("/api/v1/library/items", headers=auth(), params={"sort_by": "unknown"})
    assert denied.status_code == 401
    assert invalid.status_code == 422
    for response in (denied, invalid):
        parsed = ErrorEnvelope.model_validate_json(response.text)
        assert str(parsed.request_id) == response.headers["X-Request-ID"]


def test_dataset_library_removal_freezes_current_version_members(service):
    settings, client, database = service
    assets = {}
    with database.write_session() as session:
        for name, gain in (("A.fit", 100), ("B.fit", 10)):
            asset_id, asset_version_id = str(uuid4()), str(uuid4())
            asset = Asset(
                id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                classification={"frame_class": "subframe", "frame_type": "light"},
                parameters={"parameter_mode": "gain", "gain": gain, "offset": None},
            )
            session.add(asset)
            session.flush()
            asset_version = AssetVersion(
                id=asset_version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                storage_location=name, availability="available",
            )
            session.add(asset_version)
            session.flush()
            asset.current_version_id = asset_version_id
            assets[name] = (asset_id, asset_version_id)

        group_id, old_version_id, current_version_id = str(uuid4()), str(uuid4()), str(uuid4())
        group = Dataset(
            id=group_id, name="G", status="active", revision=2,
        )
        session.add(group)
        session.flush()
        old_version = DatasetVersion(id=old_version_id, dataset_id=group_id, version_number=1)
        current_version = DatasetVersion(id=current_version_id, dataset_id=group_id, version_number=2)
        session.add_all((old_version, current_version))
        session.flush()
        group.current_version_id = current_version_id
        session.add_all((
            DatasetMember(id=str(uuid4()), dataset_version_id=old_version_id, asset_version_id=assets["A.fit"][1], position=0),
            DatasetMember(id=str(uuid4()), dataset_version_id=old_version_id, asset_version_id=assets["B.fit"][1], position=1),
            DatasetMember(id=str(uuid4()), dataset_version_id=current_version_id, asset_version_id=assets["A.fit"][1], position=0),
        ))

        other_dataset_id, other_version_id = str(uuid4()), str(uuid4())
        other_dataset = Dataset(
            id=other_dataset_id, name="Other", status="active", revision=1,
        )
        session.add(other_dataset)
        session.flush()
        session.add(DatasetVersion(id=other_version_id, dataset_id=other_dataset_id, version_number=1))
        session.flush()
        other_dataset.current_version_id = other_version_id
        session.add(DatasetMember(
            id=str(uuid4()), dataset_version_id=other_version_id, asset_version_id=assets["A.fit"][1], position=0,
        ))

    project = client.post("/api/v1/projects", headers=auth(), json={"name": "Project"}).json()
    with database.write_session() as session:
        session.add_all(
            ProjectAssetReference(id=str(uuid4()), project_id=project["id"], asset_version_id=version_id)
            for _, version_id in assets.values()
        )

    before = client.get("/api/v1/library/items", headers=auth()).json()
    assert before["total"] == 3
    remove_group = {
        "entry_type": "dataset", "id": group_id, "revision": 2, "current_version_id": current_version_id,
    }
    remove_b = {"entry_type": "asset", "id": assets["B.fit"][0], "revision": 1, "current_version_id": None}

    stale_revision = client.request("DELETE", "/api/v1/library/items", headers=auth(), json={
        "items": [remove_b, {**remove_group, "revision": 1}],
    })
    assert stale_revision.status_code == 409
    stale_version = client.request("DELETE", "/api/v1/library/items", headers=auth(), json={
        "items": [remove_b, {**remove_group, "current_version_id": old_version_id}],
    })
    assert stale_version.status_code == 409
    with database.read_session() as session:
        assert session.query(LibraryEntryRemoval).count() == 0

    removed = client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items": [remove_group]})
    assert removed.status_code == 200 and removed.json() == {"removed_count": 1}
    with database.read_session() as session:
        snapshot = session.get(LibraryEntryRemoval, ("dataset", group_id))
        assert snapshot.dataset_version_id == current_version_id
        assert snapshot.member_asset_ids == [assets["A.fit"][0]]
        original_snapshot = (snapshot.dataset_version_id, snapshot.removed_at)

    repeated = client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items": [remove_group]})
    assert repeated.status_code == 200 and repeated.json() == {"removed_count": 0}
    with database.read_session() as session:
        snapshot = session.get(LibraryEntryRemoval, ("dataset", group_id))
        assert (snapshot.dataset_version_id, snapshot.removed_at) == original_snapshot

    new_asset_id, new_asset_version_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        new_asset = Asset(
            id=new_asset_id, name="C.fit", scope="shared", role="raw", status="active", revision=1,
            classification={"frame_class": "subframe", "frame_type": "light"},
            parameters={"parameter_mode": "gain", "gain": 200, "offset": None},
        )
        session.add(new_asset)
        session.flush()
        session.add(AssetVersion(
            id=new_asset_version_id, asset_id=new_asset_id, version_number=1, storage_mode="reference",
            storage_location="C.fit", availability="available",
        ))
        session.flush()
        new_asset.current_version_id = new_asset_version_id
        next_version = DatasetVersion(id=str(uuid4()), dataset_id=group_id, version_number=3)
        session.add(next_version)
        session.flush()
        session.add(DatasetMember(
            id=str(uuid4()), dataset_version_id=next_version.id, asset_version_id=new_asset_version_id, position=0,
        ))
        group = session.get(Dataset, group_id)
        group.current_version_id = next_version.id
        group.revision = 3
    with database.read_session() as session:
        snapshot = session.get(LibraryEntryRemoval, ("dataset", group_id))
        assert (snapshot.dataset_version_id, snapshot.removed_at) == original_snapshot

    after = client.get("/api/v1/library/items", headers=auth()).json()
    visible = {
        ("dataset", item["dataset"]["id"]) if item["entry_type"] == "dataset"
        else ("asset", item["asset"]["id"])
        for item in after["items"]
    }
    assert after["total"] == 3
    assert visible == {("dataset", other_dataset_id), ("asset", assets["B.fit"][0]), ("asset", new_asset_id)}
    assert client.get("/api/v1/library/items", headers=auth(), params={"gain_min": 10, "gain_max": 10}).json()["total"] == 1
    options = client.get("/api/v1/library/filter-options", headers=auth()).json()
    assert options["numeric_ranges"]["gain"] == {"min": 10, "max": 200}
    project_assets = client.get(f"/api/v1/projects/{project['id']}/assets", headers=auth()).json()
    assert {item["asset"]["id"] for item in project_assets["items"]} == {assets["A.fit"][0], assets["B.fit"][0]}
    assert client.get(f"/api/v1/library/assets/{assets['B.fit'][0]}", headers=auth()).status_code == 200

    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT status FROM asset WHERE id=?", (assets["A.fit"][0],)).fetchone() == ("active",)
        assert db.execute("SELECT status FROM asset WHERE id=?", (assets["B.fit"][0],)).fetchone() == ("active",)
        assert db.execute("SELECT COUNT(*) FROM asset_version WHERE asset_id IN (?,?)", (assets["A.fit"][0], assets["B.fit"][0])).fetchone() == (2,)
        assert db.execute("SELECT COUNT(*) FROM dataset_member WHERE dataset_version_id IN (?,?)", (old_version_id, current_version_id)).fetchone() == (3,)


def test_trash_group_restore_also_restores_individually_removed_members(service):
    settings, client, database = service
    asset_id, asset_version_id = str(uuid4()), str(uuid4())
    dataset_id, dataset_version_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="A.fit", scope="shared", role="raw", status="active", revision=1,
                      parameters={}, classification={})
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=asset_version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                 storage_location="A.fit", availability="available"))
        session.flush()
        asset.current_version_id = asset_version_id
        dataset = Dataset(id=dataset_id, name="Group", status="active", revision=1)
        session.add(dataset)
        session.flush()
        session.add(DatasetVersion(id=dataset_version_id, dataset_id=dataset_id, version_number=1))
        session.flush()
        dataset.current_version_id = dataset_version_id
        session.add(DatasetMember(id=str(uuid4()), dataset_version_id=dataset_version_id,
                                  asset_version_id=asset_version_id, position=0))

    remove_asset = {"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":asset_version_id}
    remove_dataset = {"entry_type":"dataset", "id":dataset_id, "revision":1, "current_version_id":dataset_version_id}
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[remove_asset]}).status_code == 200
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[remove_dataset]}).status_code == 200
    with database.read_session() as session:
        dataset_removal = session.get(LibraryEntryRemoval, ("dataset", dataset_id))
        assert dataset_removal.member_asset_ids == [asset_id]
        assert session.get(Asset, asset_id).current_version_id == asset_version_id

    trash = client.get("/api/v1/library/trash", headers=auth()).json()["items"]
    dataset_item = next(row for row in trash if row["entry_type"] == "dataset")
    assert dataset_item["removed_at"].endswith("Z")
    restore_item = {key: dataset_item[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}
    restored = client.post("/api/v1/library/trash/restore", headers=auth(), json={"items":[restore_item]})
    assert restored.status_code == 200 and restored.json()["restored_count"] == 1
    library = client.get("/api/v1/library/items", headers=auth()).json()
    group = next(row for row in library["items"] if row["entry_type"] == "dataset")
    assert [member["asset"]["id"] for member in group["version"]["members"]] == [asset_id]
    assert client.get("/api/v1/library/trash", headers=auth()).json()["total"] == 0
    with database.read_session() as session:
        assert session.get(Asset, asset_id).current_version_id == asset_version_id
        assert session.get(AssetVersion, asset_version_id) is not None


def test_trash_group_delete_uses_snapshot_including_previously_removed_member_only(service):
    _, client, database = service
    asset_a, version_a, asset_b, version_b, dataset_id, old_id, current_id = (str(uuid4()) for _ in range(7))
    with database.write_session() as session:
        for asset_id, version_id, name in ((asset_a, version_a, "A.fit"), (asset_b, version_b, "B.fit")):
            asset = Asset(id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                          parameters={}, classification={})
            session.add(asset)
            session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                     storage_location=name, availability="available"))
            session.flush()
            asset.current_version_id = version_id
        dataset = Dataset(id=dataset_id, name="Light group", status="active", revision=1)
        session.add(dataset)
        session.flush()
        session.add_all((DatasetVersion(id=old_id, dataset_id=dataset_id, version_number=1),
                         DatasetVersion(id=current_id, dataset_id=dataset_id, version_number=2)))
        session.flush()
        dataset.current_version_id = current_id
        session.add_all((DatasetMember(id=str(uuid4()), dataset_version_id=old_id, asset_version_id=version_a, position=0),
                         DatasetMember(id=str(uuid4()), dataset_version_id=old_id, asset_version_id=version_b, position=1),
                         DatasetMember(id=str(uuid4()), dataset_version_id=current_id, asset_version_id=version_a, position=0)))
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[
        {"entry_type":"asset", "id":asset_a, "revision":1, "current_version_id":version_a}
    ]}).status_code == 200
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[
        {"entry_type":"dataset", "id":dataset_id, "revision":1, "current_version_id":current_id}
    ]}).status_code == 200
    trash = client.get("/api/v1/library/trash", headers=auth()).json()["items"]
    group = next(row for row in trash if row["entry_type"] == "dataset")
    assert group["member_asset_ids"] == [asset_a]
    selection = {"items":[{key:group[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    assert preview["photo_count"] == 1
    deleted = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_count"] == 1 and deleted.json()["deleted_entry_count"] == 2
    with database.read_session() as session:
        assert session.get(Asset, asset_a) is None
        assert session.get(Dataset, dataset_id) is None
        assert session.get(Asset, asset_b) is not None
        assert session.get(AssetVersion, version_b) is not None
        assert session.scalar(select(DatasetMember.id).where(DatasetMember.asset_version_id == version_b)) is None


def test_trash_permanent_delete_removes_only_managed_files_and_reports_preview(service, monkeypatch):
    settings, client, database = service
    asset_ids, version_ids, expected_paths = [], [], []
    with database.write_session() as session:
        for index in range(2):
            asset_id, version_id = str(uuid4()), str(uuid4())
            asset_ids.append(asset_id)
            version_ids.append(version_id)
            content_path = settings.data_dir / "objects" / version_id / "source.fit"
            preview_path = settings.data_dir / "previews" / version_id / f"{version_id}.jpg"
            content_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            content_path.write_bytes(b"managed" + bytes([index]))
            preview_path.write_bytes(b"preview" + bytes([index]))
            expected_paths.extend((content_path, preview_path))
            asset = Asset(id=asset_id, name=f"A{index}.fit", scope="shared", role="raw", status="active",
                          revision=1, parameters={}, classification={})
            session.add(asset)
            session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
                                     storage_location=(Path("objects") / version_id / "source.fit").as_posix(),
                                     availability="available", byte_size=8))
            session.flush()
            asset.current_version_id = version_id
            session.add(Preview(id=str(uuid4()), asset_version_id=version_id, hdu_index=0, size="thumbnail",
                                width=1, height=1, storage_path=(Path("previews") / version_id / f"{version_id}.jpg").as_posix(),
                                mime_type="image/jpeg", display_parameters={}, algorithm_version="test",
                                status="available"))
    remove_items = [{"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":version_id}
                    for asset_id, version_id in zip(asset_ids, version_ids)]
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":remove_items}).status_code == 200
    trash = client.get("/api/v1/library/trash", headers=auth()).json()["items"]
    selection = {"items":[{key:row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")} for row in trash]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection)
    assert preview.status_code == 200, preview.text
    assert (preview.json()["photo_count"], preview.json()["managed_file_count"], preview.json()["managed_bytes"]) == (2, 4, 32)
    original_unlink = Path.unlink
    failing_path = next(path for path in expected_paths if path.name.endswith(".jpg") and path.parent.name == version_ids[0])
    def fail_one(path, *args, **kwargs):
        if path == failing_path:
            raise PermissionError("controlled file lock")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_one)
    result = client.post("/api/v1/library/trash/delete", headers=auth(), json={**selection, "preview_fingerprint":preview.json()["preview_fingerprint"]})
    assert result.status_code == 200, result.text
    assert result.json()["deleted_count"] == 1 and result.json()["deleted_entry_count"] == 1 and len(result.json()["failed"]) == 1, result.json()
    trash = client.get("/api/v1/library/trash", headers=auth()).json()["items"]
    remaining = next(row for row in trash if row["id"] == asset_ids[0])
    assert remaining["cleanup_status"] == "partial" and "controlled file lock" in remaining["cleanup_error"]
    assert not next(path for path in expected_paths if path.name == "source.fit" and path.parent.name == version_ids[0]).exists()
    assert failing_path.exists()
    assert all(not path.exists() for path in expected_paths if path.parent.name == version_ids[1])
    failed_item = {key:remaining[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}
    denied_restore = client.post("/api/v1/library/trash/restore", headers=auth(), json={"items":[failed_item]})
    assert denied_restore.status_code == 409

    monkeypatch.setattr(Path, "unlink", original_unlink)
    retry_selection = {"items":[failed_item]}
    retry_preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=retry_selection)
    assert retry_preview.status_code == 200
    retry = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **retry_selection, "preview_fingerprint":retry_preview.json()["preview_fingerprint"]
    })
    assert retry.status_code == 200 and retry.json()["deleted_count"] == 1 and retry.json()["deleted_entry_count"] == 1 and retry.json()["failed"] == []
    assert retry.json()["missing_file_count"] == 0 and retry.json()["deleted_file_count"] == 1
    assert client.get("/api/v1/library/trash", headers=auth()).json()["total"] == 0
    assert all(not path.exists() for path in expected_paths)


def test_trash_asset_delete_preserves_a_managed_path_used_by_unselected_asset(service):
    settings, client, database = service
    selected_asset_id, selected_version_id = str(uuid4()), str(uuid4())
    other_asset_id, other_version_id = str(uuid4()), str(uuid4())
    path = settings.data_dir / "objects" / "shared" / "source.fit"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"shared managed content")
    with database.write_session() as session:
        for asset_id, version_id, name in ((selected_asset_id, selected_version_id, "Selected.fit"),
                                           (other_asset_id, other_version_id, "Other.fit")):
            asset = Asset(id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                          parameters={}, classification={})
            session.add(asset)
            session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
                                     storage_location="objects/shared/source.fit", availability="available"))
            session.flush()
            asset.current_version_id = version_id
    remove_item = {"entry_type":"asset", "id":selected_asset_id, "revision":1, "current_version_id":selected_version_id}
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[remove_item]}).status_code == 200
    row = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    selection = {"items":[{key:row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    assert (preview["photo_count"], preview["managed_file_count"], preview["managed_bytes"]) == (1, 0, 0)
    deleted = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert deleted.status_code == 200 and deleted.json()["deleted_count"] == 1
    assert deleted.json()["deleted_file_count"] == 0 and path.exists()
    with database.read_session() as session:
        assert session.get(Asset, selected_asset_id) is None
        assert session.get(Asset, other_asset_id) is not None
        assert session.get(AssetVersion, other_version_id) is not None


def test_trash_first_unlink_failure_keeps_photo_recoverable(service, monkeypatch):
    settings, client, database = service
    asset_id, version_id = str(uuid4()), str(uuid4())
    path = settings.data_dir / "objects" / version_id / "source.fit"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"managed")
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="Recoverable.fit", scope="shared", role="raw", status="active",
                      revision=1, parameters={}, classification={})
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
                                 storage_location=(Path("objects") / version_id / "source.fit").as_posix(),
                                 availability="available"))
        session.flush()
        asset.current_version_id = version_id
    remove_item = {"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":version_id}
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[remove_item]}).status_code == 200
    row = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    selection = {"items":[{key:row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    original_unlink = Path.unlink
    def fail_first(path_arg, *args, **kwargs):
        if path_arg == path:
            raise PermissionError("first unlink failed")
        return original_unlink(path_arg, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_first)
    result = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert result.status_code == 200 and result.json()["deleted_count"] == 0 and len(result.json()["failed"]) == 1
    remaining = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    assert remaining["cleanup_status"] == "trash" and path.exists()
    restore = client.post("/api/v1/library/trash/restore", headers=auth(), json={"items":[selection["items"][0]]})
    assert restore.status_code == 200 and client.get("/api/v1/library/assets/"+asset_id, headers=auth()).status_code == 200


def test_trash_recovers_after_progress_write_failure_without_reenabling_restore(service, monkeypatch):
    from sqlalchemy.orm import Session
    settings, client, database = service
    asset_id, version_id = str(uuid4()), str(uuid4())
    path = settings.data_dir / "objects" / version_id / "source.fit"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"managed")
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="Progress.fit", scope="shared", role="raw", status="active",
                      revision=1, parameters={}, classification={})
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
                                 storage_location=(Path("objects") / version_id / "source.fit").as_posix(),
                                 availability="available"))
        session.flush()
        asset.current_version_id = version_id
    remove_item = {"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":version_id}
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[remove_item]}).status_code == 200
    row = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    selection = {"items":[{key:row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    original_flush = Session.flush
    state = {"unlinked":False, "failed":False}
    original_unlink = Path.unlink
    def unlink(path_arg, *args, **kwargs):
        result = original_unlink(path_arg, *args, **kwargs)
        if path_arg == path:
            state["unlinked"] = True
        return result
    def fail_progress(session, *args, **kwargs):
        if state["unlinked"] and not state["failed"]:
            state["failed"] = True
            raise RuntimeError("controlled cleanup progress write failure")
        return original_flush(session, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(Session, "flush", fail_progress)
    result = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert result.status_code == 200 and result.json()["deleted_count"] == 0 and not path.exists()
    remaining = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    assert remaining["cleanup_status"] == "partial"
    assert client.post("/api/v1/library/trash/restore", headers=auth(), json={"items":[selection["items"][0]]}).status_code == 409
    monkeypatch.setattr(Path, "unlink", original_unlink)
    retry_preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    retry = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":retry_preview["preview_fingerprint"]
    })
    assert retry.status_code == 200 and retry.json()["deleted_count"] == 1 and retry.json()["failed"] == []
    assert retry.json()["missing_file_count"] == 0


def test_trash_delete_cleans_confirmed_project_and_membership_references(service):
    _, client, database = service
    asset_id, asset_version_id = str(uuid4()), str(uuid4())
    other_dataset_id, other_version_id = str(uuid4()), str(uuid4())
    trash_dataset_id, trash_dataset_version_id = str(uuid4()), str(uuid4())
    historical_task_id = str(uuid4())
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="Referenced.fit", scope="shared", role="raw", status="active",
                      revision=1, parameters={}, classification={})
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=asset_version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                 storage_location="Referenced.fit", availability="available"))
        session.flush()
        asset.current_version_id = asset_version_id
        other_dataset = Dataset(id=other_dataset_id, name="Other dataset", status="active", revision=1)
        trash_dataset = Dataset(id=trash_dataset_id, name="Trash dataset", status="active", revision=1)
        session.add_all((other_dataset, trash_dataset))
        session.flush()
        session.add_all((
            DatasetVersion(id=other_version_id, dataset_id=other_dataset_id, version_number=1),
            DatasetVersion(id=trash_dataset_version_id, dataset_id=trash_dataset_id, version_number=1),
        ))
        session.flush()
        other_dataset.current_version_id = other_version_id
        trash_dataset.current_version_id = trash_dataset_version_id
        session.add(AssetTask(id=historical_task_id, status="completed", sources=[], storage_mode="managed",
                              classification={}, parameters={}, dataset_base_revision=None,
                              enumeration_completed=True, report={}, error=None, dataset_id=trash_dataset_id))
        session.add(DatasetMember(id=str(uuid4()), dataset_version_id=other_version_id,
                                  asset_version_id=asset_version_id, position=0))

    project = client.post("/api/v1/projects", headers=auth(), json={"name":"External project"}).json()
    project_asset_id, project_dataset_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        session.add_all((
            ProjectAssetReference(id=project_asset_id, project_id=project["id"], asset_version_id=asset_version_id),
            ProjectDatasetReference(id=project_dataset_id, project_id=project["id"], dataset_id=trash_dataset_id,
                                    dataset_version_id=trash_dataset_version_id, base_revision=1),
        ))
    remove_items = [
        {"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":asset_version_id},
        {"entry_type":"dataset", "id":trash_dataset_id, "revision":1, "current_version_id":trash_dataset_version_id},
    ]
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":remove_items}).status_code == 200
    trash = client.get("/api/v1/library/trash", headers=auth()).json()["items"]
    selection = {"items":[{key:row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")} for row in trash]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    assert {ref["kind"] for ref in preview["references"]} == {"project_asset", "project_dataset", "dataset_member"}
    late_project = client.post("/api/v1/projects", headers=auth(), json={"name":"Late project"}).json()
    late_reference_id = str(uuid4())
    with database.write_session() as session:
        session.add(ProjectAssetReference(id=late_reference_id, project_id=late_project["id"], asset_version_id=asset_version_id))
    stale = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert stale.status_code == 409, stale.text
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    deleted = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_count"] == 1 and deleted.json()["deleted_entry_count"] == 2
    with database.read_session() as session:
        assert session.get(Asset, asset_id) is None
        assert session.get(Dataset, trash_dataset_id) is None
        assert session.get(ProjectAssetReference, project_asset_id) is None
        assert session.get(ProjectAssetReference, late_reference_id) is None
        assert session.get(ProjectDatasetReference, project_dataset_id) is None
        assert session.get(Dataset, other_dataset_id).revision == 2
        assert session.get(DatasetVersion, other_version_id) is not None
        assert session.get(AssetTask, historical_task_id).dataset_id is None


def test_trash_rechecks_new_reference_after_confirmation_before_file_io(service, monkeypatch):
    from contextlib import contextmanager
    _, client, database = service
    asset_id, version_id = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="Race.fit", scope="shared", role="raw", status="active",
                      revision=1, parameters={}, classification={})
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                 storage_location="Race.fit", availability="available"))
        session.flush()
        asset.current_version_id = version_id
    project = client.post("/api/v1/projects", headers=auth(), json={"name":"Concurrent project"}).json()
    remove_item = {"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":version_id}
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[remove_item]}).status_code == 200
    row = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    selection = {"items":[{key:row[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    late_reference_id = str(uuid4())
    original_write_session = Database.write_session
    calls = 0
    @contextmanager
    def race_after_manifest(self):
        nonlocal calls
        with original_write_session(self) as write:
            yield write
        calls += 1
        if calls == 1:
            with original_write_session(self) as write:
                write.add(ProjectAssetReference(id=late_reference_id, project_id=project["id"], asset_version_id=version_id))
    monkeypatch.setattr(Database, "write_session", race_after_manifest)
    result = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert result.status_code == 409
    with original_write_session(database) as session:
        assert session.get(Asset, asset_id) is not None
        assert session.get(ProjectAssetReference, late_reference_id) is not None
        assert session.get(LibraryEntryRemoval, ("asset", asset_id)).cleanup_status == "trash"


def test_trash_active_import_blocks_and_terminal_task_pointers_are_cleared(service):
    _, client, database = service
    asset_id, version_id, task_id, item_id, retry_task_id, retry_item_id = (str(uuid4()) for _ in range(6))
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="Tasked.fit", scope="shared", role="raw", status="active",
                      revision=1, parameters={}, classification={})
        session.add(asset)
        session.flush()
        session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                 storage_location="Tasked.fit", availability="available"))
        session.flush()
        asset.current_version_id = version_id
        session.add(AssetTask(id=task_id, status="interrupted", sources=[], storage_mode="managed",
                              classification={}, parameters={}, dataset_base_revision=None, enumeration_completed=True,
                              report={}, error=None))
        session.add(AssetTaskItem(id=item_id, task_id=task_id, root_item_id=item_id, retry_of_item_id=None,
                                  root_id="root", source_path="Tasked.fit", source_identity="identity", position=0,
                                  status="interrupted", content_status="available", metadata_status="available",
                                  preview_status="available", asset_id=asset_id, asset_version_id=version_id, error=None))
        session.add(AssetTask(id=retry_task_id, status="completed_with_errors", sources=[], storage_mode="managed",
                              classification={}, parameters={}, dataset_base_revision=None, enumeration_completed=True,
                              report={}, error=None))
        session.add(AssetTaskItem(id=retry_item_id, task_id=retry_task_id, root_item_id=retry_item_id, retry_of_item_id=None,
                                  root_id="root", source_path="Tasked.fit", source_identity="identity-2", position=0,
                                  status="completed_with_errors", content_status="available", metadata_status="available",
                                  preview_status="failed", asset_id=asset_id, asset_version_id=version_id, error={"code":"PREVIEW_FAILED"}))
    removal = {"entry_type":"asset", "id":asset_id, "revision":1, "current_version_id":version_id}
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[removal]}).status_code == 200
    trash = client.get("/api/v1/library/trash", headers=auth()).json()["items"][0]
    selection = {"items":[{key:trash[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    assert preview["tasks"] == [task_id]
    denied = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert denied.status_code == 409
    cancelled = client.post(f"/api/v1/asset-tasks/{task_id}/cancel", headers=auth())
    assert cancelled.status_code == 202 and cancelled.json()["status"] == "cancelled"
    retry_preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    assert retry_preview["tasks"] == []
    deleted = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":retry_preview["preview_fingerprint"]
    })
    assert deleted.status_code == 200 and deleted.json()["deleted_count"] == 1
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        assert item.asset_id is None and item.asset_version_id is None
        retry_item = session.get(AssetTaskItem, retry_item_id)
        assert retry_item.asset_id is None and retry_item.asset_version_id is None
        assert session.get(AssetTask, task_id) is not None


def test_gain_sort_applies_to_filtered_results_before_pagination(service):
    _, client, database = service
    with database.write_session() as session:
        for name, gain in (("matched-100.fit", 100), ("matched-10.fit", 10), ("matched-50.fit", 50)):
            asset_id, asset_version_id = str(uuid4()), str(uuid4())
            asset = Asset(
                id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                classification={"frame_class": "subframe", "frame_type": "light"},
                parameters={"parameter_mode": "gain", "gain": gain, "offset": None},
            )
            session.add(asset)
            session.flush()
            session.add(AssetVersion(
                id=asset_version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                storage_location=name, availability="available",
            ))
            session.flush()
            asset.current_version_id = asset_version_id

    sorted_page = client.get("/api/v1/library/items", headers=auth(), params={
        "q": "matched", "sort_by": "parameter_mode", "order": "desc", "limit": 1, "offset": 1,
    }).json()
    assert sorted_page["total"] == 3
    assert sorted_page["items"][0]["asset"]["parameters"]["gain"] == 50

    filtered_page = client.get("/api/v1/library/items", headers=auth(), params={
        "q": "matched", "gain_min": 10, "gain_max": 50,
        "sort_by": "parameter_mode", "order": "desc", "limit": 1, "offset": 1,
    }).json()
    assert filtered_page["total"] == 2
    assert filtered_page["items"][0]["asset"]["parameters"]["gain"] == 10


def test_openapi_snapshot_matches_service_and_proxy_allowlist(service):
    _, client, _ = service
    actual = client.get("/openapi.json").json()
    snapshot = json.loads((Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json").read_text())
    assert snapshot == actual
    assert all(
        method.lower() in actual["paths"].get("/api/v1" + path, {})
        for method, path, _ in ROUTES
    )
    assert not any(
        method in {"POST", "PATCH", "PUT", "DELETE"} and "/library/assets/" in path and "/versions" in path
        and not (method == "POST" and path == "/library/assets/{asset_id}/versions/{version_id}/previews/display")
        and not (method == "POST" and path == "/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch")
        for method, path, _ in ROUTES
    )



def test_status_filters_for_projects_and_equipment(service):
    _, c, _ = service

    def assert_filters(path, active_id, archived_id, kind=None):
        body = {"base_revision": 1, "status": "archived"}
        params = {}
        if kind is not None:
            body["kind"] = kind
            params["kind"] = kind
        response = c.patch(f"{path}/{archived_id}", headers=auth(), json=body)
        assert response.status_code == 200
        assert c.get(f"{path}/{archived_id}", headers=auth()).json()["status"] == "archived"

        default = c.get(path, headers=auth(), params=params).json()
        active = c.get(path, headers=auth(), params={**params, "status": "active"}).json()
        archived = c.get(path, headers=auth(), params={**params, "status": "archived"}).json()
        all_records = c.get(path, headers=auth(), params={**params, "status": "all"}).json()
        assert {item["id"] for item in default["items"]} == {active_id}
        assert {item["id"] for item in active["items"]} == {active_id}
        assert {item["id"] for item in archived["items"]} == {archived_id}
        assert {item["id"] for item in all_records["items"]} == {active_id, archived_id}

    projects = [
        c.post("/api/v1/projects", headers=auth(), json={"name": name}).json()
        for name in ("active project", "archived project")
    ]
    assert_filters("/api/v1/projects", projects[0]["id"], projects[1]["id"])

    cameras = [
        c.post("/api/v1/equipment", headers=auth(), json={"kind": "camera", "name": name}).json()
        for name in ("active camera", "archived camera")
    ]
    assert_filters("/api/v1/equipment", cameras[0]["id"], cameras[1]["id"], "camera")


def test_datetime_serialization_preserves_text_and_snapshots(service):
    _, c, database = service
    text = "Observer offset +00:00"
    project = c.post("/api/v1/projects", headers=auth(), json={"name": text, "notes": text}).json()
    assert project["name"] == text
    assert project["notes"] == text
    assert project["created_at"].endswith("Z")

    changed_text = "Updated offset +00:00"
    patched = c.patch(
        f"/api/v1/projects/{project['id']}", headers=auth(),
        json={"base_revision": 1, "notes": changed_text},
    ).json()
    reread = c.get(f"/api/v1/projects/{project['id']}", headers=auth()).json()
    assert patched["notes"] == reread["notes"] == changed_text
    assert reread["updated_at"].endswith("Z")

    asset_id = str(uuid4())
    version_id = str(uuid4())
    snapshot_text = "Header offset +00:00"
    with database.write_session() as session:
        asset = Asset(
            id=asset_id, name="snapshot", scope="shared", role="raw",
            current_version_id=None, created_at=datetime.now(timezone.utc),
        )
        session.add(asset)
        session.flush()
        version = AssetVersion(
            id=version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
            storage_location="snapshot", availability="unknown",
            capture_snapshot={"note": snapshot_text}, scientific_metadata={"note": snapshot_text},
        )
        session.add(version)
        session.flush()
        asset.current_version_id = version_id

    response = c.get("/api/v1/library/assets", headers=auth()).json()["items"][0]
    assert response["name"] == "snapshot"
    assert response["current_version"]["capture_snapshot"]["note"] == snapshot_text
    assert response["current_version"]["scientific_metadata"]["note"] == snapshot_text
    assert response["current_version"]["created_at"].endswith("Z")



def test_trash_group_child_restore_shrinks_scope_and_preserves_dataset_membership(service):
    _, client, database = service
    asset_a, version_a, asset_b, version_b, dataset_id, dataset_version_id = (str(uuid4()) for _ in range(6))
    with database.write_session() as session:
        for asset_id, version_id, name in ((asset_a, version_a, "A.fit"), (asset_b, version_b, "B.fit")):
            asset = Asset(id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                          parameters={}, classification={})
            session.add(asset); session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                     storage_location=name, availability="available")); session.flush()
            asset.current_version_id = version_id
        dataset = Dataset(id=dataset_id, name="Light frames", status="active", revision=1)
        session.add(dataset); session.flush()
        session.add(DatasetVersion(id=dataset_version_id, dataset_id=dataset_id, version_number=1)); session.flush()
        dataset.current_version_id = dataset_version_id
        session.add_all((DatasetMember(id=str(uuid4()), dataset_version_id=dataset_version_id, asset_version_id=version_a, position=0),
                         DatasetMember(id=str(uuid4()), dataset_version_id=dataset_version_id, asset_version_id=version_b, position=1)))
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[
        {"entry_type":"dataset", "id":dataset_id, "revision":1, "current_version_id":dataset_version_id}
    ]}).status_code == 200
    group = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == dataset_id)
    children = client.get(f"/api/v1/library/trash?group_id={dataset_id}&limit=1&offset=0", headers=auth()).json()
    assert children["total"] == 2 and children["items"][0]["source_dataset_id"] == dataset_id
    child = next(item for item in children["items"] if item["id"] == asset_a)
    selection = {"items":[{key:child[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id", "source_dataset_id")}]}
    restored = client.post("/api/v1/library/trash/restore", headers=auth(), json=selection)
    assert restored.status_code == 200, restored.text
    with database.read_session() as session:
        assert session.get(Asset, asset_a) is not None
        assert session.scalar(select(DatasetMember.id).where(DatasetMember.dataset_version_id == dataset_version_id,
                                                              DatasetMember.asset_version_id == version_a)) is not None
    normal_page = client.get("/api/v1/library/items?limit=50&offset=0", headers=auth()).json()
    assert any(item.get("asset", {}).get("id") == asset_a for item in normal_page["items"])
    remaining = client.get(f"/api/v1/library/trash?group_id={dataset_id}", headers=auth()).json()
    assert remaining["total"] == 1 and remaining["items"][0]["id"] == asset_b
    group = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == dataset_id)
    group_selection = {"items":[{key:group[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=group_selection)
    assert preview.status_code == 200 and preview.json()["photo_count"] == 1
    deleted = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **group_selection, "preview_fingerprint":preview.json()["preview_fingerprint"]
    })
    assert deleted.status_code == 200, deleted.text
    with database.read_session() as session:
        assert session.get(Asset, asset_a) is not None and session.get(AssetVersion, version_a) is not None
        assert session.get(Asset, asset_b) is None and session.get(Dataset, dataset_id) is None


@pytest.mark.parametrize("late_dependency", ["project_reference", "group_task"])
def test_trash_group_rechecks_project_dataset_reference_before_member_cleanup(service, monkeypatch, late_dependency):
    from contextlib import contextmanager
    settings, client, database = service
    asset_id, version_id, dataset_id, dataset_version_id = (str(uuid4()) for _ in range(4))
    path = settings.data_dir / "objects" / version_id / "source.fit"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"managed")
    with database.write_session() as session:
        asset = Asset(id=asset_id, name="GroupRace.fit", scope="shared", role="raw", status="active", revision=1,
                      parameters={}, classification={}); session.add(asset); session.flush()
        session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="managed",
            storage_location=(Path("objects") / version_id / "source.fit").as_posix(), availability="available")); session.flush()
        asset.current_version_id = version_id
        dataset = Dataset(id=dataset_id, name="Race group", status="active", revision=1); session.add(dataset); session.flush()
        session.add(DatasetVersion(id=dataset_version_id, dataset_id=dataset_id, version_number=1)); session.flush()
        dataset.current_version_id = dataset_version_id
        session.add(DatasetMember(id=str(uuid4()), dataset_version_id=dataset_version_id, asset_version_id=version_id, position=0))
    project = client.post("/api/v1/projects", headers=auth(), json={"name":"Late group reference"}).json()
    task_id = str(uuid4())
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[
        {"entry_type":"dataset", "id":dataset_id, "revision":1, "current_version_id":dataset_version_id}
    ]}).status_code == 200
    group = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == dataset_id)
    selection = {"items":[{key:group[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    reference_id = str(uuid4())
    original_write_session = Database.write_session
    calls = 0
    @contextmanager
    def add_reference_after_manifest(self):
        nonlocal calls
        with original_write_session(self) as write:
            yield write
        calls += 1
        if calls == 1:
            with original_write_session(self) as write:
                if late_dependency == "project_reference":
                    write.add(ProjectDatasetReference(id=reference_id, project_id=project["id"], dataset_id=dataset_id,
                        dataset_version_id=dataset_version_id, base_revision=1))
                else:
                    write.add(AssetTask(id=task_id, status="queued", sources=[], storage_mode="managed",
                        classification={}, parameters={}, enumeration_completed=False, report={}, error=None,
                        dataset_id=dataset_id))
    monkeypatch.setattr(Database, "write_session", add_reference_after_manifest)
    result = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert result.status_code == 409, result.text
    with original_write_session(database) as session:
        assert session.get(Asset, asset_id) is not None
        assert session.get(DatasetMember, session.scalar(select(DatasetMember.id).where(DatasetMember.dataset_version_id == dataset_version_id))) is not None
        if late_dependency == "project_reference":
            assert session.get(ProjectDatasetReference, reference_id) is not None
        else:
            assert session.get(AssetTask, task_id) is not None
        assert session.get(LibraryEntryRemoval, ("dataset", dataset_id)).cleanup_status == "trash"
    assert path.exists()



def test_trash_group_persists_database_cleanup_progress_and_retries_after_file_failure(service, monkeypatch):
    settings, client, database = service
    asset_a, version_a = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000011"
    asset_b, version_b = "00000000-0000-0000-0000-000000000002", "00000000-0000-0000-0000-000000000012"
    dataset_id, dataset_version_id = "00000000-0000-0000-0000-000000000003", "00000000-0000-0000-0000-000000000013"
    original = settings.data_dir.parent / "external-original.fit"
    original.write_bytes(b"external original")
    path = settings.data_dir / "objects" / version_b / "source.fit"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"managed")
    with database.write_session() as session:
        for asset_id, version_id, name, mode, location in (
            (asset_a, version_a, "A reference.fit", "reference", str(original)),
            (asset_b, version_b, "B managed.fit", "managed", (Path("objects") / version_b / "source.fit").as_posix()),
        ):
            asset = Asset(id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                          parameters={}, classification={}); session.add(asset); session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode=mode,
                storage_location=location, availability="available")); session.flush(); asset.current_version_id = version_id
        dataset = Dataset(id=dataset_id, name="Partial database group", status="active", revision=1)
        session.add(dataset); session.flush()
        session.add(DatasetVersion(id=dataset_version_id, dataset_id=dataset_id, version_number=1)); session.flush()
        dataset.current_version_id = dataset_version_id
        session.add_all((DatasetMember(id=str(uuid4()), dataset_version_id=dataset_version_id, asset_version_id=version_a, position=0),
                         DatasetMember(id=str(uuid4()), dataset_version_id=dataset_version_id, asset_version_id=version_b, position=1)))
    assert client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items":[
        {"entry_type":"dataset", "id":dataset_id, "revision":1, "current_version_id":dataset_version_id}
    ]}).status_code == 200
    group = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == dataset_id)
    selection = {"items":[{key:group[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    original_unlink = Path.unlink
    def fail_b(path_arg, *args, **kwargs):
        if path_arg == path:
            raise PermissionError("controlled B lock")
        return original_unlink(path_arg, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_b)
    result = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint":preview["preview_fingerprint"]
    })
    assert result.status_code == 200 and result.json()["deleted_count"] == 1 and len(result.json()["failed"]) == 1
    remaining = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == dataset_id)
    assert remaining["cleanup_status"] == "partial" and remaining["member_asset_ids"] == [asset_b]
    with database.read_session() as session:
        assert session.get(Asset, asset_a) is None
        assert session.get(LibraryEntryRemoval, ("dataset", dataset_id)).cleaned_asset_ids == [asset_a]
    assert original.read_bytes() == b"external original"
    assert client.post("/api/v1/library/trash/restore", headers=auth(), json=selection).status_code == 409
    monkeypatch.setattr(Path, "unlink", original_unlink)
    latest_group = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == dataset_id)
    retry_selection = {"items":[{key:latest_group[key] for key in ("entry_type", "id", "removed_at", "revision", "current_version_id")}]}
    retry_response = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=retry_selection)
    assert retry_response.status_code == 200, retry_response.text
    retry = retry_response.json()
    finished = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **retry_selection, "preview_fingerprint":retry["preview_fingerprint"]
    })
    assert finished.status_code == 200 and finished.json()["deleted_count"] == 1
    with database.read_session() as session:
        assert session.get(Dataset, dataset_id) is None and session.get(Asset, asset_b) is None
    assert original.read_bytes() == b"external original"



def test_trash_group_child_delete_only_removes_selected_asset_and_group_remains_restorable(service):
    _, client, database = service
    asset_a, version_a, asset_b, version_b, dataset_id, dataset_version_id = (str(uuid4()) for _ in range(6))
    with database.write_session() as session:
        for asset_id, version_id, name in ((asset_a, version_a, "A only.fit"), (asset_b, version_b, "B remains.fit")):
            asset = Asset(id=asset_id, name=name, scope="shared", role="raw", status="active", revision=1,
                          parameters={}, classification={}); session.add(asset); session.flush()
            session.add(AssetVersion(id=version_id, asset_id=asset_id, version_number=1, storage_mode="reference",
                                     storage_location=name, availability="available")); session.flush(); asset.current_version_id=version_id
        dataset=Dataset(id=dataset_id,name="Single member removal",status="active",revision=1);session.add(dataset);session.flush()
        session.add(DatasetVersion(id=dataset_version_id,dataset_id=dataset_id,version_number=1));session.flush()
        dataset.current_version_id=dataset_version_id
        session.add_all((DatasetMember(id=str(uuid4()),dataset_version_id=dataset_version_id,asset_version_id=version_a,position=0),
                         DatasetMember(id=str(uuid4()),dataset_version_id=dataset_version_id,asset_version_id=version_b,position=1)))
    assert client.request("DELETE","/api/v1/library/items",headers=auth(),json={"items":[
        {"entry_type":"dataset","id":dataset_id,"revision":1,"current_version_id":dataset_version_id}
    ]}).status_code==200
    child_page=client.get(f"/api/v1/library/trash?group_id={dataset_id}&limit=1&offset=1",headers=auth()).json()
    assert child_page["total"]==2 and child_page["items"][0]["id"]==asset_b
    child=child_page["items"][0]
    selection={"items":[{key:child[key] for key in ("entry_type","id","removed_at","revision","current_version_id","source_dataset_id")}]}
    preview=client.post("/api/v1/library/trash/delete-preview",headers=auth(),json=selection).json()
    assert preview["photo_count"]==1
    deleted=client.post("/api/v1/library/trash/delete",headers=auth(),json={**selection,"preview_fingerprint":preview["preview_fingerprint"]})
    assert deleted.status_code==200 and deleted.json()["deleted_count"]==1 and deleted.json()["deleted_entry_count"]==1
    with database.read_session() as session:
        group_removal=session.get(LibraryEntryRemoval,("dataset",dataset_id))
        assert group_removal.member_asset_ids==[asset_a] and group_removal.cleaned_asset_ids==[]
        assert group_removal.cleanup_status=="trash"
        assert session.get(Asset,asset_a) is not None and session.get(Asset,asset_b) is None
    group=next(row for row in client.get("/api/v1/library/trash",headers=auth()).json()["items"] if row["id"]==dataset_id)
    restored=client.post("/api/v1/library/trash/restore",headers=auth(),json={"items":[{
        key:group[key] for key in ("entry_type","id","removed_at","revision","current_version_id")
    }]})
    assert restored.status_code==200
    with database.read_session() as session:
        assert session.get(Asset,asset_a) is not None and session.get(Asset,asset_b) is None
        assert session.get(Dataset,dataset_id) is not None



def test_trash_group_deletes_multiple_members_without_self_revision_conflict(service):
    _, client, database = service
    dataset_id, dataset_version_id = str(uuid4()), str(uuid4())
    asset_ids, version_ids = [str(uuid4()), str(uuid4())], [str(uuid4()), str(uuid4())]
    with database.write_session() as session:
        for index, (asset_id, version_id) in enumerate(zip(asset_ids, version_ids)):
            asset=Asset(id=asset_id,name=f"Multi {index}.fit",scope="shared",role="raw",status="active",revision=1,
                        parameters={},classification={});session.add(asset);session.flush()
            session.add(AssetVersion(id=version_id,asset_id=asset_id,version_number=1,storage_mode="reference",
                                     storage_location=f"Multi {index}.fit",availability="available"));session.flush()
            asset.current_version_id=version_id
        dataset=Dataset(id=dataset_id,name="Multi-member group",status="active",revision=1);session.add(dataset);session.flush()
        session.add(DatasetVersion(id=dataset_version_id,dataset_id=dataset_id,version_number=1));session.flush()
        dataset.current_version_id=dataset_version_id
        session.add_all(DatasetMember(id=str(uuid4()),dataset_version_id=dataset_version_id,asset_version_id=version_id,position=index)
                        for index,version_id in enumerate(version_ids))
    assert client.request("DELETE","/api/v1/library/items",headers=auth(),json={"items":[
        {"entry_type":"dataset","id":dataset_id,"revision":1,"current_version_id":dataset_version_id}
    ]}).status_code==200
    group=next(row for row in client.get("/api/v1/library/trash",headers=auth()).json()["items"] if row["id"]==dataset_id)
    selection={"items":[{key:group[key] for key in ("entry_type","id","removed_at","revision","current_version_id")}]}
    preview=client.post("/api/v1/library/trash/delete-preview",headers=auth(),json=selection).json()
    assert preview["photo_count"]==2
    deleted=client.post("/api/v1/library/trash/delete",headers=auth(),json={**selection,"preview_fingerprint":preview["preview_fingerprint"]})
    assert deleted.status_code==200,deleted.text
    assert deleted.json()["deleted_count"]==2 and deleted.json()["deleted_entry_count"]==3 and deleted.json()["failed"]==[]
    with database.read_session() as session:
        assert session.get(Dataset,dataset_id) is None and all(session.get(Asset,asset_id) is None for asset_id in asset_ids)


@pytest.fixture
def trash_recovery_group(service):
    settings, client, database = service
    photos = []
    gid, gvid = str(uuid4()), str(uuid4())
    with database.write_session() as session:
        for index in range(2):
            aid = f"00000000-0000-4000-8000-{201 + index:012d}"
            vid = str(uuid4())
            raw = settings.data_dir / "objects" / vid / "source.fit"
            thumb = settings.data_dir / "previews" / vid / "thumb.jpg"
            raw.parent.mkdir(parents=True); raw.write_bytes(b"source")
            thumb.parent.mkdir(parents=True); thumb.write_bytes(b"thumbnail")
            asset = Asset(id=aid, name=f"{index}.fit", scope="shared", role="raw", status="active",
                          revision=1, parameters={}, classification={})
            session.add(asset); session.flush()
            session.add(AssetVersion(id=vid, asset_id=aid, version_number=1, storage_mode="managed",
                storage_location=raw.relative_to(settings.data_dir).as_posix(), availability="available"))
            session.flush(); asset.current_version_id = vid
            session.add(Preview(id=str(uuid4()), asset_version_id=vid, hdu_index=0, size="thumbnail",
                width=1, height=1, storage_path=thumb.relative_to(settings.data_dir).as_posix(),
                display_parameters={}, algorithm_version="test", status="available"))
            photos.append(SimpleNamespace(id=aid, version_id=vid, raw=raw, thumb=thumb))
        group = Dataset(id=gid, name="Recovery group", status="active", revision=1)
        session.add(group); session.flush()
        session.add(DatasetVersion(id=gvid, dataset_id=gid, version_number=1)); session.flush()
        group.current_version_id = gvid
        for position, photo in enumerate(photos):
            session.add(DatasetMember(id=str(uuid4()), dataset_version_id=gvid,
                                      asset_version_id=photo.version_id, position=position))
    removed = client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items": [
        {"entry_type": "dataset", "id": gid, "revision": 1, "current_version_id": gvid}]})
    assert removed.status_code == 200, removed.text
    return SimpleNamespace(settings=settings, client=client, database=database, photos=photos, id=gid)


def trash_selection(row):
    return {"items": [{key: row[key] for key in
        ("entry_type", "id", "removed_at", "revision", "current_version_id", "source_dataset_id") if key in row}]}


def test_trash_group_restore_ignores_paths_of_restored_and_independently_deleted_photo(trash_recovery_group, monkeypatch):
    group = trash_recovery_group
    client, database = group.client, group.database
    removed, intact = group.photos
    row = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    group_version_id = row["current_version_id"]
    with database.read_session() as session:
        member = session.scalar(select(DatasetMember).where(
            DatasetMember.dataset_version_id == group_version_id, DatasetMember.asset_version_id == intact.version_id))
        member_id, member_position = member.id, member.position
    intact_bytes = (intact.raw.read_bytes(), intact.thumb.read_bytes())
    selection = trash_selection(row)
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection)
    assert preview.status_code == 200, preview.text
    unlink = Path.unlink
    attempted = set()

    def fail_first_file(path, *args, **kwargs):
        if path in (removed.raw, intact.raw):
            attempted.add(path)
            raise PermissionError("controlled first-file lock")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_first_file)
        failed = client.post("/api/v1/library/trash/delete", headers=auth(), json={
            **selection, "preview_fingerprint": preview.json()["preview_fingerprint"]})
    assert failed.status_code == 200, failed.text
    assert failed.json()["deleted_count"] == 0 and failed.json()["deleted_file_count"] == 0
    assert len(failed.json()["failed"]) == 2 and attempted == {removed.raw, intact.raw}
    assert all(photo.raw.exists() and photo.thumb.exists() for photo in group.photos)

    child = next(row for row in client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"]
                 if row["id"] == removed.id)
    restored = client.post("/api/v1/library/trash/restore", headers=auth(), json=trash_selection(child))
    assert restored.status_code == 200, restored.text
    with database.read_session() as session:
        parent = session.get(LibraryEntryRemoval, ("dataset", group.id))
        assert parent.member_asset_ids == [intact.id]
        assert str(removed.raw) in parent.pending_paths
        assert parent.cleaned_paths == [] and parent.cleaned_asset_ids == []

    removed_again = client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items": [{
        "entry_type": "asset", "id": removed.id, "revision": child["revision"], "current_version_id": removed.version_id}]})
    assert removed_again.status_code == 200, removed_again.text
    row = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == removed.id)
    selection = trash_selection(row)
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection)
    assert preview.status_code == 200 and preview.json()["photo_count"] == 1, preview.text
    deleted = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint": preview.json()["preview_fingerprint"]})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_count"] == 1 and deleted.json()["deleted_file_count"] == 2 and not deleted.json()["failed"]
    assert not removed.raw.exists() and not removed.thumb.exists()

    row = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    assert row["member_asset_ids"] == [intact.id] and row["cleanup_status"] == "trash"
    restored = client.post("/api/v1/library/trash/restore", headers=auth(), json=trash_selection(row))
    assert restored.status_code == 200, restored.text
    assert client.get("/api/v1/library/trash", headers=auth()).json()["total"] == 0
    with database.read_session() as session:
        assert session.get(Asset, removed.id) is None
        assert session.get(Asset, intact.id).current_version_id == intact.version_id
        assert session.get(AssetVersion, intact.version_id).asset_id == intact.id
        assert session.get(Dataset, group.id).current_version_id == group_version_id
        member = session.get(DatasetMember, member_id)
        assert (member.dataset_version_id, member.asset_version_id, member.position) == (
            group_version_id, intact.version_id, member_position)
    assert (intact.raw.read_bytes(), intact.thumb.read_bytes()) == intact_bytes


def test_trash_partial_group_blocks_damaged_child_but_restores_intact_sibling(trash_recovery_group, monkeypatch):
    group = trash_recovery_group
    client, database = group.client, group.database
    damaged, intact = group.photos
    row = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    selection = trash_selection(row)
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    unlink = Path.unlink
    def fail(path, *args, **kwargs):
        if path in (damaged.thumb, intact.raw):
            raise PermissionError("controlled file lock")
        return unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail)
        result = client.post("/api/v1/library/trash/delete", headers=auth(), json={
            **selection, "preview_fingerprint": preview["preview_fingerprint"]})
    assert result.status_code == 200 and len(result.json()["failed"]) == 2, result.text
    assert not damaged.raw.exists() and intact.raw.exists() and intact.thumb.exists()
    children = {row["id"]: row for row in client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"]}
    assert children[damaged.id]["cleanup_status"] == "partial"
    assert children[intact.id]["cleanup_status"] == "trash"
    with database.read_session() as session:
        assert session.get(LibraryEntryRemoval, ("asset", damaged.id)).pending_paths
    assert client.post("/api/v1/library/trash/restore", headers=auth(), json=trash_selection(children[damaged.id])).status_code == 409
    assert client.post("/api/v1/library/trash/restore", headers=auth(), json=selection).status_code == 409
    restored = client.post("/api/v1/library/trash/restore", headers=auth(), json=trash_selection(children[intact.id]))
    assert restored.status_code == 200, restored.text
    row = next(row for row in client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    selection = trash_selection(row)
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    finished = client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint": preview["preview_fingerprint"]})
    assert finished.status_code == 200 and not finished.json()["failed"], finished.text
    with database.read_session() as session:
        assert session.get(Asset, damaged.id) is None and session.get(Dataset, group.id) is None
        assert session.get(Asset, intact.id).current_version_id == intact.version_id
    assert intact.raw.exists() and intact.thumb.exists()


@pytest.mark.parametrize("remove_source", [False, True])
def test_trash_child_intent_survives_interruption_and_restart(trash_recovery_group, monkeypatch, remove_source):
    from astrophotoflow.modules.data import trash
    from astrophotoflow.contracts.trash import LibraryTrashDelete
    group = trash_recovery_group
    photo = group.photos[0]
    client, database = group.client, group.database
    child = client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"][0]
    selection = trash_selection(child)
    preview = client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    unlink = Path.unlink
    def interrupt(path, *args, **kwargs):
        if path == photo.raw:
            if remove_source:
                unlink(path, *args, **kwargs)
            raise KeyboardInterrupt("controlled interruption")
        return unlink(path, *args, **kwargs)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database, settings=group.settings)))
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", interrupt)
        with pytest.raises(KeyboardInterrupt), database.read_session() as session:
            trash.library_trash_delete(LibraryTrashDelete.model_validate({
                **selection, "preview_fingerprint": preview["preview_fingerprint"]}), request, session)
    with database.read_session() as session:
        record = session.get(LibraryEntryRemoval, ("asset", photo.id))
        assert set(record.pending_paths) == {str(photo.raw), str(photo.thumb)}
        assert session.get(Asset, photo.id) is not None
    restarted_app = create_app(group.settings, TOKEN)
    try:
        with TestClient(restarted_app) as restarted:
            child = restarted.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"][0]
            assert child["cleanup_status"] == ("partial" if remove_source else "trash")
            selection = trash_selection(child)
            restored = restarted.post("/api/v1/library/trash/restore", headers=auth(), json=selection)
            assert restored.status_code == (409 if remove_source else 200), restored.text
            if remove_source:
                preview = restarted.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
                deleted = restarted.post("/api/v1/library/trash/delete", headers=auth(), json={
                    **selection, "preview_fingerprint": preview["preview_fingerprint"]})
                assert deleted.status_code == 200 and not deleted.json()["failed"], deleted.text
                assert not photo.thumb.exists()
            else:
                assert photo.raw.exists() and photo.thumb.exists()
    finally:
        restarted_app.state.database.close()


def test_trash_child_restore_between_intent_and_cleanup_cancels_deletion(trash_recovery_group, monkeypatch):
    from contextlib import contextmanager
    from astrophotoflow.modules.data import trash
    from astrophotoflow.contracts.trash import LibraryTrashSelection
    group = trash_recovery_group
    photo = group.photos[0]
    child = group.client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"][0]
    selection = trash_selection(child)
    preview = group.client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    write_session = group.database.write_session
    restored = False
    @contextmanager
    def restore_after_intent():
        nonlocal restored
        with write_session() as session:
            yield session
        if not restored:
            restored = True
            with write_session() as session:
                result = trash.restore_library_trash(LibraryTrashSelection.model_validate(selection), session)
                assert result["restored_count"] == 1
    monkeypatch.setattr(group.database, "write_session", restore_after_intent)
    response = group.client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint": preview["preview_fingerprint"]})
    assert response.status_code == 409, response.text
    assert photo.raw.exists() and photo.thumb.exists()
    with group.database.read_session() as session:
        assert session.get(Asset, photo.id).current_version_id == photo.version_id
        assert session.get(LibraryEntryRemoval, ("asset", photo.id)) is None


@pytest.mark.parametrize("remove_again", [False, True])
def test_trash_group_restore_after_delete_intent_invalidates_old_request(trash_recovery_group, monkeypatch, remove_again):
    from contextlib import contextmanager
    from astrophotoflow.modules.data import trash
    from astrophotoflow.contracts.trash import LibraryEntriesRemove, LibraryTrashSelection
    group = trash_recovery_group
    children = group.client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"]
    restored = group.client.post("/api/v1/library/trash/restore", headers=auth(), json={
        "items": [trash_selection(child)["items"][0] for child in children]})
    assert restored.status_code == 200, restored.text
    row = next(row for row in group.client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    assert row["photo_count"] == 0
    selection = trash_selection(row)
    preview = group.client.post("/api/v1/library/trash/delete-preview", headers=auth(), json=selection).json()
    assert preview["photo_count"] == 0
    write_session = group.database.write_session
    restored_after_intent = False

    @contextmanager
    def restore_after_intent():
        nonlocal restored_after_intent
        with write_session() as session:
            yield session
        if not restored_after_intent:
            restored_after_intent = True
            with write_session() as session:
                result = trash.restore_library_trash(LibraryTrashSelection.model_validate(selection), session)
                assert result["restored_count"] == 1
                if remove_again:
                    trash.remove_library_entries(LibraryEntriesRemove.model_validate({"items": [{
                        "entry_type": "dataset", "id": group.id, "revision": row["revision"],
                        "current_version_id": row["current_version_id"]}]}), session)

    monkeypatch.setattr(group.database, "write_session", restore_after_intent)
    response = group.client.post("/api/v1/library/trash/delete", headers=auth(), json={
        **selection, "preview_fingerprint": preview["preview_fingerprint"]})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "TRASH_PREVIEW_STALE"
    with group.database.read_session() as session:
        assert session.get(Dataset, group.id).current_version_id == row["current_version_id"]
        removal = session.get(LibraryEntryRemoval, ("dataset", group.id))
        assert (removal is not None) == remove_again
        assert set(session.scalars(select(DatasetMember.asset_version_id).where(
            DatasetMember.dataset_version_id == row["current_version_id"])).all()) == {photo.version_id for photo in group.photos}
    assert all(photo.raw.exists() and photo.thumb.exists() for photo in group.photos)


@pytest.mark.parametrize("parent_first", [False, True])
@pytest.mark.parametrize("individual_removal", [False, True])
def test_trash_restores_parent_and_selected_child_in_either_order(trash_recovery_group, parent_first, individual_removal):
    group = trash_recovery_group
    photo = group.photos[0]
    if individual_removal:
        response = group.client.request("DELETE", "/api/v1/library/items", headers=auth(), json={"items": [{
            "entry_type": "asset", "id": photo.id, "revision": 1, "current_version_id": photo.version_id}]})
        assert response.status_code == 200, response.text
    row = next(row for row in group.client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    child = next(row for row in group.client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"] if row["id"] == photo.id)
    items = [trash_selection(row)["items"][0], trash_selection(child)["items"][0]]
    response = group.client.post("/api/v1/library/trash/restore", headers=auth(), json={
        "items": items if parent_first else items[::-1]})
    assert response.status_code == 200, response.text
    assert response.json()["restored_count"] == 2
    assert group.client.get("/api/v1/library/trash", headers=auth()).json()["total"] == 0
    with group.database.read_session() as session:
        assert session.get(Dataset, group.id).current_version_id == row["current_version_id"]
        assert set(session.scalars(select(DatasetMember.asset_version_id).where(
            DatasetMember.dataset_version_id == row["current_version_id"])).all()) == {photo.version_id for photo in group.photos}
        assert all(session.get(Asset, photo.id).current_version_id == photo.version_id for photo in group.photos)
    assert all(photo.raw.exists() and photo.thumb.exists() for photo in group.photos)


def test_trash_parent_selection_does_not_bypass_a_stale_child_revision(trash_recovery_group):
    group = trash_recovery_group
    row = next(row for row in group.client.get("/api/v1/library/trash", headers=auth()).json()["items"] if row["id"] == group.id)
    child = group.client.get(f"/api/v1/library/trash?group_id={group.id}", headers=auth()).json()["items"][0]
    stale_child = trash_selection(child)["items"][0]
    stale_child["revision"] += 1
    response = group.client.post("/api/v1/library/trash/restore", headers=auth(), json={
        "items": [trash_selection(row)["items"][0], stale_child]})
    assert response.status_code == 409, response.text
    with group.database.read_session() as session:
        assert set(session.get(LibraryEntryRemoval, ("dataset", group.id)).member_asset_ids) == {photo.id for photo in group.photos}
    assert all(photo.raw.exists() and photo.thumb.exists() for photo in group.photos)



def test_maintenance_auth_busy_and_new_task_admission(managed_service, monkeypatch):
    import httpx
    settings, client, database, operation_id = managed_service
    async def empty_queue(self, url, **kwargs):
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", empty_queue)
    assert client.post("/internal/maintenance", json={"action": "enter", "operation_id": operation_id}).status_code == 401
    assert "/internal/maintenance" not in client.app.openapi()["paths"]
    entered = client.post("/internal/maintenance", headers=auth(), json={"action": "enter", "operation_id": operation_id})
    assert entered.json() == {"busy": False, "unknown": False, "blockers": []}
    body = {"files": [{"name": "night.png", "size": 10}]}
    blocked = client.post("/api/v1/uploads", headers=auth(), json=body)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "WORKBENCH_MAINTENANCE"
    preview = client.post(f"/api/v1/library/assets/{uuid4()}/versions/{uuid4()}/previews/display", headers=auth())
    assert preview.status_code == 409
    client.post("/internal/maintenance", headers=auth(), json={"action": "release", "operation_id": operation_id})
    created = client.post("/api/v1/uploads", headers=auth(), json=body)
    assert created.status_code == 202, created.text
    task = created.json()["task_id"]
    busy = client.post("/internal/maintenance", headers=auth(), json={"action": "enter", "operation_id": operation_id}).json()
    assert busy["busy"] and any(task in reason for reason in busy["blockers"])
    assert not client.app.state.maintenance


def test_maintenance_rejects_unknown_or_nonempty_native_queue(managed_service, monkeypatch):
    import httpx
    _, client, _, operation_id = managed_service
    async def unavailable(self, url, **kwargs):
        raise httpx.ConnectError("test unavailable")
    monkeypatch.setattr(httpx.AsyncClient, "get", unavailable)
    unknown = client.post("/internal/maintenance", headers=auth(), json={"action": "enter", "operation_id": operation_id}).json()
    assert unknown["unknown"] and not client.app.state.maintenance
    async def queued(self, url, **kwargs):
        return httpx.Response(200, json={"queue_running": [], "queue_pending": [[1, "prompt"]]}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", queued)
    busy = client.post("/internal/maintenance", headers=auth(), json={"action": "enter", "operation_id": operation_id}).json()
    assert busy["busy"] and not busy["unknown"] and not client.app.state.maintenance


def test_maintenance_check_and_task_admission_cannot_cross(managed_service, monkeypatch):
    import asyncio
    import httpx
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    _, client, _, operation_id = managed_service
    entered, release = Event(), Event()
    async def paused(self, url, **kwargs):
        entered.set()
        assert await asyncio.to_thread(release.wait, 5)
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", paused)
    with ThreadPoolExecutor(max_workers=2) as workers:
        maintenance = workers.submit(client.post, "/internal/maintenance", headers=auth(), json={"action": "enter", "operation_id": operation_id})
        assert entered.wait(5)
        importing = workers.submit(client.post, "/api/v1/uploads", headers=auth(), json={"files": [{"name": "x.png", "size": 10}]})
        release.set()
        assert not maintenance.result(5).json()["busy"]
        assert importing.result(5).status_code == 409



def test_workbench_configuration_http_is_fixed_to_current_workspace_and_preserves_effective_values(service, monkeypatch):
    from astrophotoflow.core import config
    settings, client, _ = service
    monkeypatch.setattr(config, "CONFIG_PATH", settings.workspace / "user/config.toml")
    path = settings.workspace / "config.toml"
    path.write_text('[server]\nhost="127.0.0.1"\nport=8190\n[storage]\ndata_dir="."\n'
                    '[comfyui]\nallowed_origins=["http://127.0.0.1:8188"]\n', encoding="utf-8")
    initial = config.get_configuration(path)
    run = settings.workspace / "run/processes.json"
    run.parent.mkdir()
    run.write_text(json.dumps({"workspace": str(settings.workspace), "config_path": str(path),
        "effective_settings": initial.saved.model_dump(), "processes": [{"role": "asset-service"}]}), encoding="utf-8")
    assert client.get("/api/v1/settings/workbench").status_code == 401
    current = client.get("/api/v1/settings/workbench", headers=auth())
    assert current.status_code == 200 and TOKEN not in current.text
    body = {"config_token": current.json()["config_token"], "values": current.json()["saved"]}
    body["values"]["file_workers"] = 4
    assert client.patch("/api/v1/settings/workbench", json=body).status_code == 401
    saved = client.patch("/api/v1/settings/workbench", headers=auth(), json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["saved"]["file_workers"] == 4
    assert saved.json()["effective"]["file_workers"] == 2
    assert saved.json()["restart_required"]
    assert settings.file_workers == 2
    stale = client.patch("/api/v1/settings/workbench", headers=auth(), json=body)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "CONFIGURATION_CONFLICT"
    body["config_token"] = saved.json()["config_token"]
    body["values"]["file_workers"] = 0
    invalid = client.patch("/api/v1/settings/workbench", headers=auth(), json=body)
    assert invalid.status_code == 422 and invalid.json()["error"]["fields"][0]["path"] == "values.file_workers"
    body["values"]["file_workers"] = 4
    body["default_workspace"] = None
    assert client.patch("/api/v1/settings/workbench", headers=auth(), json=body).status_code == 422
    assert config.get_configuration(path).saved.file_workers == 4
    assert ("GET", "/settings/workbench", "/settings/workbench") in ROUTES
    assert ("PATCH", "/settings/workbench", "/settings/workbench") in ROUTES



def test_maintenance_release_is_bound_to_its_operation_and_cannot_reopen_shutdown(managed_service, monkeypatch):
    import httpx
    _, client, _, first = managed_service
    second = str(uuid4())
    async def empty_queue(self, url, **kwargs):
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", empty_queue)
    def control(action, operation):
        response = client.post("/internal/maintenance", headers=auth(), json={"action": action, "operation_id": operation})
        assert response.status_code == 200, response.text
        return response.json()
    assert not control("enter", first)["busy"]
    assert control("release", second)["busy"] and client.app.state.maintenance
    assert not control("release", first)["busy"] and not client.app.state.maintenance
    assert not control("enter", second)["busy"]
    assert control("release", first)["busy"] and client.app.state.maintenance
    client.app.state.shutdown = lambda: None
    assert client.post("/internal/shutdown", headers=auth()).status_code == 200
    assert control("release", second)["busy"] and client.app.state.maintenance


def test_restart_lost_enter_reply_releases_the_actual_service_gate(managed_service, monkeypatch):
    import httpx
    from astrophotoflow.core import config, workbench
    from astrophotoflow.contracts.workbench import WorkbenchState, ProcessInfo
    settings, client, _, _ = managed_service
    monkeypatch.setattr(config, "CONFIG_PATH", settings.workspace / "user/config.toml")
    path = settings.workspace / "config.toml"
    path.write_text('[server]\nhost="127.0.0.1"\nport=8190\n[storage]\ndata_dir="."\n'
                    '[comfyui]\nallowed_origins=["http://127.0.0.1:8188"]\n', encoding="utf-8")
    settings.token_path.write_text(TOKEN, encoding="utf-8")
    values = config.get_configuration(path).saved
    raw = {"workspace": str(settings.workspace), "config_path": str(path), "effective_settings": values.model_dump(),
           "maintenance_operation_id": None, "processes": []}
    (settings.workspace / "run/processes.json").write_text(json.dumps(raw), encoding="utf-8")
    info = ProcessInfo(role="asset-service", pid=1, create_time=1.0, executable="python", command=["python"],
                       workspace=str(settings.workspace), started_at=datetime.now(timezone.utc))
    ready = WorkbenchState(workspace=str(settings.workspace), config_path=str(path), state="running", ready=True,
                           web_url=values.allowed_origins[0], service_url=settings.service_url, processes=[info],
                           effective_settings=values, versions={}, reason=None, recent=None)
    monkeypatch.setattr(workbench, "status", lambda target: ready)
    monkeypatch.setattr(workbench, "_stop", lambda target: pytest.fail("lost reply must not stop or restart"))
    async def empty_queue(self, url, **kwargs):
        return httpx.Response(200, json={"queue_running": [], "queue_pending": []}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", empty_queue)
    calls = []
    def forward_and_lose_enter(url, **kwargs):
        calls.append(kwargs["json"])
        response = client.post("/internal/maintenance", headers=auth(), json=kwargs["json"])
        assert response.status_code == 200, response.text
        if kwargs["json"]["action"] == "enter":
            assert client.app.state.maintenance
            raise httpx.ReadTimeout("test accepted enter response lost")
        return httpx.Response(200, json=response.json(), request=httpx.Request("POST", url))
    monkeypatch.setattr(workbench.httpx, "post", forward_and_lose_enter)
    result = workbench.restart(path)
    assert result.state == "rejected"
    assert [body["action"] for body in calls] == ["enter", "release"]
    assert all(body["operation_id"] == str(result.operation_id) for body in calls)
    assert not client.app.state.maintenance
    assert json.loads((settings.workspace / "run/processes.json").read_text(encoding="utf-8"))["maintenance_operation_id"] is None
    assert client.post("/api/v1/uploads", headers=auth(), json={"files": [{"name": "after-release.png", "size": 10}]}).status_code == 202


def test_workbench_restart_requires_auth_and_exposes_correlated_result(service, monkeypatch):
    from astrophotoflow.interfaces.http import system
    from astrophotoflow.contracts.workbench import WorkbenchResult
    from uuid import uuid4
    _, client, _ = service
    result = WorkbenchResult(operation_id=uuid4(), action="restart", state="in_progress",
                             workspace="workspace", config_path="workspace/config.toml", reused=False,
                             web_url=None, service_url=None, detail=None, blockers=[], log_path=None)
    calls = []
    monkeypatch.setattr(system, "request_restart", lambda config, operation_id: calls.append(config) or result)
    monkeypatch.setattr(system, "restart_result", lambda config, operation_id: result if operation_id == result.operation_id else None)
    path = "/api/v1/settings/workbench/restart"
    assert client.post(path, json={}).status_code == 401
    assert not calls
    accepted = client.post(path, headers=auth(), json={"operation_id": str(result.operation_id)})
    assert accepted.status_code == 202 and accepted.json()["operation_id"] == str(result.operation_id)
    assert calls == [client.app.state.settings.workspace / "config.toml"]
    assert client.get(path + "/" + str(result.operation_id), headers=auth()).json()["state"] == "in_progress"
    assert client.get(path + "/" + str(uuid4()), headers=auth()).json() is None


def test_workbench_directory_selection_is_authenticated_and_does_not_save_config(service, monkeypatch):
    from astrophotoflow.interfaces.http import system
    settings, client, database = service
    selected = settings.workspace / "selected"
    initial_paths = []
    def choose(initial_path):
        initial_paths.append(initial_path)
        return selected
    monkeypatch.setattr(system, "select_directory", choose)
    endpoint = "/api/v1/settings/workbench/select-directory"
    assert client.post(endpoint, json={"path": "data"}).status_code == 401
    assert initial_paths == []
    response = client.post(endpoint, headers=auth(), json={"path": "data"})
    assert response.status_code == 200 and response.json() == {"path": str(selected)}
    assert initial_paths == [(settings.workspace / "data").resolve()]
    assert not selected.exists()
    monkeypatch.setattr(system, "select_directory", lambda initial_path: None)
    assert client.post(endpoint, headers=auth(), json={"path": ""}).json() == {"path": None}
    def unavailable(initial_path):
        raise OSError("desktop unavailable")
    monkeypatch.setattr(system, "select_directory", unavailable)
    response = client.post(endpoint, headers=auth(), json={"path": "data"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "DIRECTORY_PICKER_UNAVAILABLE"

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from uuid import uuid4
import json
import sys
import pytest
from alembic.autogenerate import compare_metadata
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from astrophotoflow_service.api import create_app
from astrophotoflow_service.db import Database
from astrophotoflow_service.models import (
    Asset, AssetVersion, Base, CaptureProfile, Dataset, DatasetMember, DatasetVersion, Equipment,
    LibraryEntryRemoval, Project, ProjectAssetReference, ProjectCaptureProfile,
)
from astrophotoflow_service.schema import SchemaError, current_revision, database_lock, ensure_schema_for_serve, upgrade_database
from astrophotoflow_service.schemas import ErrorEnvelope
from astrophotoflow_service.settings import ConfigurationError, Settings, ensure_data_dir, ensure_service_token, load_settings

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.astrophotoflow.proxy import ROUTES

TOKEN="test-token"
def auth(): return {"Authorization":f"Bearer {TOKEN}"}
@pytest.fixture
def service(tmp_path):
    settings=Settings("127.0.0.1",8190,tmp_path,("http://127.0.0.1:8188",))
    with database_lock(settings): upgrade_database(settings)
    app=create_app(settings,TOKEN)
    with TestClient(app) as client: yield settings,client,app.state.database
    app.state.database.close()
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
    s=Settings("127.0.0.1",8190,tmp_path,())
    with database_lock(s):
        with pytest.raises(SchemaError): database_lock(s)
        assert upgrade_database(s) is None
    assert current_revision(s.database_path)=="0005_dataset_removal_version_snapshot"
    token=ensure_service_token(s)
    token_mode=s.token_path.stat().st_mode&0o777
    assert ensure_service_token(s)==token
    if sys.platform != "win32":
        assert token_mode==0o600
    legacy=tmp_path/"legacy"; legacy.mkdir()
    old=Settings("127.0.0.1",8190,legacy,())
    with sqlite3.connect(old.database_path) as db: db.execute("CREATE TABLE keep_me(value TEXT)")
    with pytest.raises(SchemaError): ensure_schema_for_serve(old)
    with pytest.raises(SchemaError): upgrade_database(old)
    with sqlite3.connect(old.database_path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='keep_me'").fetchone()
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='alembic_version'").fetchone()

def test_alembic_initial_migration_matches_orm_metadata(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
    with database_lock(settings):
        upgrade_database(settings)
    engine = create_engine("sqlite:///" + str(settings.database_path))
    with engine.connect() as connection:
        changes = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert changes == []

def test_existing_data_directory_permissions_are_not_changed(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
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
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
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
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
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
    assert current_revision(settings.database_path) == "0005_dataset_removal_version_snapshot"
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT name,revision FROM project WHERE id=?", (project_id,)).fetchone() == ("pre-stage-two", 3)
        assert db.execute("SELECT name FROM equipment WHERE id=?", (equipment_id,)).fetchone() == ("preserved camera",)
        assert db.execute("SELECT parameters,status,revision FROM asset WHERE id=?", (asset_id,)).fetchone() == ("{}", "active", 1)
        assert db.execute("SELECT COUNT(*) FROM project_asset_reference WHERE id=?", (reference_id,)).fetchone() == (1,)
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0001_foundation",)


def test_asset_fact_backfill_uses_current_version_and_preserves_manual_clears(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
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
    assert backup is not None and current_revision(settings.database_path) == "0005_dataset_removal_version_snapshot"
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
    bad=c.post("/api/v1/capture-profiles",headers=auth(),json={"name":"bad","camera_id":camera["id"],"optical_system_id":duplicate["id"],"frame_type":"light"})
    missing=c.post("/api/v1/capture-profiles",headers=auth(),json={"name":"missing","camera_id":camera["id"],"optical_system_id":str(uuid4()),"frame_type":"light"})
    assert bad.status_code==422 and bad.json()["error"]["code"]=="INVALID_REFERENCE"
    assert missing.status_code==422 and missing.json()["error"]["code"]=="INVALID_REFERENCE"
    assert c.get("/api/v1/capture-profiles",headers=auth()).json()["total"]==0
    profile=c.post("/api/v1/capture-profiles",headers=auth(),json={"name":"bias","camera_id":camera["id"],"frame_type":"bias","parameter_mode":"iso","iso":800,"exposure_seconds":0,"gain":0,"offset":0,"sensor_temperature_c":-8,"binning_x":1,"binning_y":2})
    assert profile.status_code==201 and profile.json()["binning_y"]==2 and profile.json()["parameter_mode"]=="iso" and profile.json()["iso"]==800
    changed_profile=c.patch(f"/api/v1/capture-profiles/{profile.json()['id']}",headers=auth(),json={"base_revision":1,"parameter_mode":"gain","gain":24})
    assert changed_profile.status_code==200 and changed_profile.json()["parameter_mode"]=="gain" and changed_profile.json()["iso"]==800
    nan_body=("{\"name\":\"nonfinite\",\"camera_id\":\""+camera["id"]+"\",\"frame_type\":\"light\",\"gain\":NaN}").encode()
    nonfinite=c.post("/api/v1/capture-profiles",headers={**auth(),"Content-Type":"application/json"},content=nan_body)
    assert nonfinite.status_code==422
    project=c.post("/api/v1/projects",headers=auth(),json={"name":"M31","capture_profile_ids":[profile.json()["id"]]})
    assert project.status_code==201
    dup=c.post("/api/v1/projects",headers=auth(),json={"name":"bad","capture_profile_ids":[profile.json()["id"],profile.json()["id"]]})
    assert dup.status_code==422 and [x["id"] for x in c.get("/api/v1/projects",headers=auth()).json()["items"]]==[project.json()["id"]]
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
    assert c.get(f"/api/v1/projects/{project.json()['id']}",headers=auth()).json()["capture_profile_ids"]==[profile.json()["id"]]
    database.close()
    with TestClient(create_app(s,TOKEN)) as restarted:
        out=restarted.get(f"/api/v1/projects/{project.json()['id']}",headers=auth())
        assert out.status_code==200 and out.json()["created_at"].endswith("Z")

def test_project_profile_patch_replaces_and_clears_associations(service):
    _, c, _ = service
    camera = c.post(
        "/api/v1/equipment", headers=auth(),
        json={"kind": "camera", "name": "association camera"},
    ).json()
    profiles = [
        c.post(
            "/api/v1/capture-profiles", headers=auth(),
            json={"name": "profile " + str(index), "camera_id": camera["id"], "frame_type": "light"},
        ).json()
        for index in range(3)
    ]
    project = c.post(
        "/api/v1/projects", headers=auth(),
        json={"name": "association project", "capture_profile_ids": [profiles[0]["id"]]},
    ).json()
    assert project["capture_profile_ids"] == [profiles[0]["id"]]
    assert project["revision"] == 1

    replacement = sorted([profiles[1]["id"], profiles[2]["id"]], reverse=True)
    expected_replacement = sorted(replacement)
    assert replacement != expected_replacement
    updated = c.patch(
        f"/api/v1/projects/{project['id']}", headers=auth(),
        json={"base_revision": 1, "capture_profile_ids": replacement},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["capture_profile_ids"] == expected_replacement
    persisted = c.get(f"/api/v1/projects/{project['id']}", headers=auth()).json()
    assert persisted["revision"] == 2
    assert persisted["capture_profile_ids"] == expected_replacement

    cleared = c.patch(
        f"/api/v1/projects/{project['id']}", headers=auth(),
        json={"base_revision": 2, "capture_profile_ids": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["revision"] == 3
    assert cleared.json()["capture_profile_ids"] == []
    persisted = c.get(f"/api/v1/projects/{project['id']}", headers=auth()).json()
    assert persisted["revision"] == 3
    assert persisted["capture_profile_ids"] == []

    invalid_reference = c.patch(
        f"/api/v1/projects/{project['id']}", headers=auth(),
        json={"base_revision": 3, "name": "must not persist", "capture_profile_ids": [str(uuid4())]},
    )
    assert invalid_reference.status_code == 422
    assert invalid_reference.json()["error"]["code"] == "INVALID_REFERENCE"
    after_invalid_reference = c.get(f"/api/v1/projects/{project['id']}", headers=auth()).json()
    assert after_invalid_reference["name"] == "association project"
    assert after_invalid_reference["revision"] == 3
    assert after_invalid_reference["capture_profile_ids"] == []

    stale_revision = c.patch(
        f"/api/v1/projects/{project['id']}", headers=auth(),
        json={"base_revision": 2, "name": "stale", "capture_profile_ids": [profiles[0]["id"]]},
    )
    assert stale_revision.status_code == 409
    after_stale_revision = c.get(f"/api/v1/projects/{project['id']}", headers=auth()).json()
    assert after_stale_revision["name"] == "association project"
    assert after_stale_revision["revision"] == 3
    assert after_stale_revision["capture_profile_ids"] == []


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
    snapshot = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text())
    assert snapshot == actual
    assert all(
        method.lower() in actual["paths"].get("/api/v1" + path, {})
        for method, path, _ in ROUTES
    )
    assert not any(
        method in {"POST", "PATCH", "PUT", "DELETE"} and "/library/assets/" in path and "/versions" in path
        for method, path, _ in ROUTES
    )



def test_status_filters_for_projects_equipment_and_profiles(service):
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

    profiles = [
        c.post(
            "/api/v1/capture-profiles", headers=auth(),
            json={"name": name, "camera_id": camera["id"], "frame_type": "light"},
        ).json()
        for name, camera in zip(("active profile", "archived profile"), cameras)
    ]
    assert_filters("/api/v1/capture-profiles", profiles[0]["id"], profiles[1]["id"])

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

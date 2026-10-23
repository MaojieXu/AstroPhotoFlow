from datetime import datetime, timezone
import sqlite3
from uuid import uuid4
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from astrophotoflow_service.api import create_app
from astrophotoflow_service.db import Database
from astrophotoflow_service.models import Asset, AssetVersion, Base, CaptureProfile, Equipment, Project, ProjectAssetReference, ProjectCaptureProfile
from astrophotoflow_service.schema import SchemaError, current_revision, database_lock, ensure_schema_for_serve, upgrade_database
from astrophotoflow_service.settings import Settings, ensure_data_dir, ensure_service_token

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

def test_init_lock_token_and_unknown_schema(tmp_path):
    s=Settings("127.0.0.1",8190,tmp_path,())
    with database_lock(s):
        with pytest.raises(SchemaError): database_lock(s)
        assert upgrade_database(s) is None
    assert current_revision(s.database_path)=="0001_foundation"
    token=ensure_service_token(s)
    assert s.token_path.stat().st_mode&0o777==0o600 and ensure_service_token(s)==token
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
    ensure_data_dir(settings)
    assert settings.data_dir.stat().st_mode & 0o777 == 0o750

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
    profile=c.post("/api/v1/capture-profiles",headers=auth(),json={"name":"bias","camera_id":camera["id"],"frame_type":"bias","exposure_seconds":0,"gain":0,"offset":0,"sensor_temperature_c":-8,"binning_x":1,"binning_y":2})
    assert profile.status_code==201 and profile.json()["binning_y"]==2
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

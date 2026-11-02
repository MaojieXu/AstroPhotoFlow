from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, insert, select, update

from astrophotoflow.contracts.datasets import DatasetMemberQuery
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.assets.queries import get_filter_options
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.datasets.queries import list_dataset_members
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval


@pytest.fixture
def member_library(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    dataset_id, version_id, empty_id, empty_version_id = [str(uuid4()) for _ in range(4)]
    asset_ids = [str(uuid4()) for _ in range(1001)]
    version_ids = [str(uuid4()) for _ in asset_ids]
    with database.write_session() as session:
        session.execute(insert(Asset), [{"id": identity, "name": f"frame-{i}.fits", "scope": "shared", "role": "raw", "frame_class": "subframe", "frame_type": "light" if i % 2 == 0 else "dark", "gain": i % 3, "binning_x": 1 if i % 2 == 0 else 2, "binning_y": 1 if i % 2 == 0 else 2, "sensor_temperature_c": -9.5 if i == 0 else None} for i, identity in enumerate(asset_ids)])
        session.execute(insert(AssetVersion), [{"id": identity, "asset_id": asset_ids[i], "version_number": 1,
            "storage_mode": "managed", "storage_location": f"objects/{i}.fits", "byte_size": 100,
            "content_hash": "b3:" + "a" * 64, "availability": "available"} for i, identity in enumerate(version_ids)])
        session.execute(insert(Dataset), [{"id": dataset_id, "name": "Night"}, {"id": empty_id, "name": "Empty"}])
        session.execute(insert(DatasetVersion), [{"id": version_id, "dataset_id": dataset_id, "version_number": 1},
                                               {"id": empty_version_id, "dataset_id": empty_id, "version_number": 1}])
        session.execute(insert(DatasetMember), [{"id": str(uuid4()), "dataset_version_id": version_id,
            "asset_version_id": identity, "position": i} for i, identity in enumerate(version_ids)])
        session.execute(update(Dataset).where(Dataset.id == dataset_id).values(current_version_id=version_id))
        session.execute(update(Dataset).where(Dataset.id == empty_id).values(current_version_id=empty_version_id))
    with TestClient(create_app(settings, "member-test"), headers={"Authorization": "Bearer member-test"}) as client:
        yield client, database, dataset_id, version_id, empty_id, empty_version_id, version_ids
    database.close()


def test_members_are_paged_in_fixed_order_with_exact_versions(member_library):
    client, _, dataset, version, _, _, members = member_library
    response = client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members", params={"limit": 3, "offset": 7})
    assert response.status_code == 200, response.text
    page = response.json()
    assert (page["total"], page["limit"], page["offset"]) == (1001, 3, 7)
    assert [item["position"] for item in page["items"]] == [7, 8, 9]
    assert [item["asset_version_id"] for item in page["items"]] == members[7:10]
    assert all(item["version"]["id"] == item["asset_version_id"] and item["version"]["asset_id"] == item["asset"]["id"] for item in page["items"])


def test_empty_and_out_of_range_pages_keep_real_total(member_library):
    client, _, dataset, version, empty, empty_version, _ = member_library
    for owner, fixed, offset, total in [(dataset, version, 1001, 1001), (empty, empty_version, 0, 0)]:
        response = client.get(f"/api/v1/datasets/{owner}/versions/{fixed}/members", params={"limit": 5, "offset": offset})
        assert response.status_code == 200, response.text
        assert response.json() == {"items": [], "total": total, "limit": 5, "offset": offset}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_member_query_bounds_are_enforced_by_http(member_library, params):
    client, _, dataset, version, _, _, _ = member_library
    assert client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members", params=params).status_code == 422


def test_member_query_rejects_foreign_and_missing_versions(member_library):
    client, _, dataset, _, _, foreign_version, _ = member_library
    for version in (foreign_version, str(uuid4())):
        assert client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members").status_code == 404


def test_member_page_loads_only_page_sized_orm_objects(member_library):
    _, database, dataset, version, _, _, _ = member_library
    loaded = []
    with database.read_session() as session:
        event.listen(session, "loaded_as_persistent", lambda session, instance: loaded.append(type(instance).__name__))
        page = list_dataset_members(session, UUID(dataset), UUID(version), DatasetMemberQuery(limit=5, offset=991))
    assert page.total == 1001 and len(page.items) == 5
    assert loaded.count("DatasetMember") == 5
    assert loaded.count("Asset") == 5
    assert loaded.count("AssetVersion") == 5
    assert len(loaded) <= 4 * 5 + 2


@pytest.mark.parametrize("params, total, positions", [
    ({"frame_type": "light", "gain_max": 0, "offset": 1}, 167, [6, 12, 18]),
    ({"binning": "2"}, 500, [1, 3, 5]),
    ({"temperature_min": -10, "temperature_max": -10}, 1, [0]),
])
def test_member_filters_and_totals_are_applied_before_pagination(member_library, params, total, positions):
    client, _, dataset, version, _, _, _ = member_library
    response = client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members", params={"limit": 3, **params})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == total
    assert [item["position"] for item in response.json()["items"]] == positions


def test_invalid_binning_is_a_field_error(member_library):
    client, _, dataset, version, _, _, _ = member_library
    response = client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members", params={"binning": "2x0"})
    assert response.status_code == 422, response.text


def test_filter_options_use_sql_projections_without_orm_materialization(member_library):
    client, database, _, _, _, _, _ = member_library
    loaded = []
    with database.read_session() as session:
        event.listen(session, "loaded_as_persistent", lambda session, instance: loaded.append(type(instance).__name__))
        options = get_filter_options(session)
    assert loaded == []
    assert options.frame_classes == ["subframe"]
    assert options.frame_types == ["dark", "light"]
    assert options.bin_values == ["1x1", "2x2"]
    assert options.numeric_ranges["gain"].model_dump() == {"min": 0.0, "max": 2.0}
    assert options.numeric_ranges["sensor_temperature_c"].model_dump() == {"min": -10.0, "max": -10.0}
    response = client.get("/api/v1/library/filter-options")
    assert response.status_code == 200, response.text
    assert response.json() == options.model_dump(mode="json")


def test_filter_options_exclude_frozen_trash_group_members(member_library):
    client, database, dataset, version, _, _, versions = member_library
    with database.write_session() as session:
        identities = list(session.scalars(select(AssetVersion.asset_id).where(AssetVersion.id.in_(versions))))
        session.add(LibraryEntryRemoval(entry_type="dataset", entry_id=dataset, dataset_version_id=version, member_asset_ids=identities))
    response = client.get("/api/v1/library/filter-options")
    assert response.status_code == 200, response.text
    assert response.json() == {"frame_classes": [], "frame_types": [], "roles": [], "parameter_modes": [], "bin_values": [],
                               "equipment": {"camera_id": [], "optical_system_id": [], "filter_id": []}, "numeric_ranges": {}}


def test_archived_fixed_member_remains_visible_until_explicitly_removed(member_library):
    client, database, _, _, _, _, versions = member_library
    with database.write_session() as session:
        identity = session.scalar(select(AssetVersion.asset_id).where(AssetVersion.id == versions[0]))
        session.execute(update(Asset).where(Asset.id == identity).values(status="archived"))
    response = client.get("/api/v1/library/filter-options")
    assert response.status_code == 200, response.text
    assert response.json()["numeric_ranges"]["sensor_temperature_c"] == {"min": -10.0, "max": -10.0}
    with database.write_session() as session:
        session.add(LibraryEntryRemoval(entry_type="asset", entry_id=identity))
    response = client.get("/api/v1/library/filter-options")
    assert response.status_code == 200, response.text
    assert "sensor_temperature_c" not in response.json()["numeric_ranges"]


def test_library_summary_does_not_embed_members_and_keeps_mixed_unknown_states(member_library):
    client, _, _, _, _, _, _ = member_library
    response = client.get("/api/v1/library/items")
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    rows = {row["name"]: row for row in response.json()["items"]}
    night, empty = rows["Night"], rows["Empty"]
    assert night["member_count"] == night["matching_member_count"] == 1001
    assert night["input_ready"]
    assert night["summary"]["classification"] == {"frame_class": {"state": "consistent", "value": "subframe"}, "frame_type": {"state": "mixed", "value": None}}
    assert night["summary"]["parameters"]["gain"] == {"state": "mixed", "value": None}
    assert night["summary"]["parameters"]["iso"] == {"state": "unknown", "value": None}
    assert "members" not in night and "version" not in night
    assert empty["member_count"] == 0 and not empty["input_ready"]
    assert empty["summary"]["classification"] == {"frame_class": {"state": "unknown", "value": None}, "frame_type": {"state": "unknown", "value": None}}


def test_library_filters_count_matches_without_shrinking_fixed_group(member_library):
    client, _, _, _, _, _, _ = member_library
    response = client.get("/api/v1/library/items", params={"gain_max": 0, "frame_type": "light", "limit": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    row = response.json()["items"][0]
    assert row["member_count"] == 1001 and row["matching_member_count"] == 167
    assert row["summary"]["parameters"]["gain"]["state"] == "mixed"


def test_library_head_sort_paginates_once_and_preserves_total(member_library):
    client, _, dataset, _, empty, _, _ = member_library
    for offset, expected in [(0, [empty]), (1, [dataset]), (2, [])]:
        response = client.get("/api/v1/library/items", params={"sort_by": "name", "order": "asc", "limit": 1, "offset": offset})
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 2
        assert [row["id"] for row in response.json()["items"]] == expected
        if expected == [dataset]:
            assert response.json()["items"][0]["member_count"] == 1001


def test_member_search_and_sort_are_applied_before_sql_pagination(member_library):
    client, _, dataset, version, _, _, _ = member_library
    response = client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members", params={
        "q": "frame-99", "sort_by": "name", "order": "desc", "limit": 2, "offset": 1,
    })
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 11
    assert [item["asset"]["name"] for item in response.json()["items"]] == ["frame-998.fits", "frame-997.fits"]
    assert [item["position"] for item in response.json()["items"]] == [998, 997]


def test_member_gain_sort_reuses_known_missing_and_offset_rules(member_library):
    client, _, dataset, version, _, _, _ = member_library
    response = client.get(f"/api/v1/datasets/{dataset}/versions/{version}/members", params={
        "sort_by": "parameter_mode", "order": "desc", "gain_min": 0, "gain_max": 0, "limit": 3,
    })
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 334
    assert all(item["asset"]["parameters"]["gain"] == 0 for item in response.json()["items"])


def test_project_reference_summary_stays_fixed_without_loading_member_orm(member_library):
    from astrophotoflow.modules.data.projects.models import Project, ProjectDatasetReference
    from astrophotoflow.modules.data.projects.references import list_project_dataset_references

    client, database, dataset, fixed, _, _, versions = member_library
    project, reference, current = str(uuid4()), str(uuid4()), str(uuid4())
    with database.write_session() as session:
        session.add(Project(id=project, name="Pinned project")); session.flush()
        session.add(DatasetVersion(id=current, dataset_id=dataset, version_number=2)); session.flush()
        session.add(DatasetMember(id=str(uuid4()), dataset_version_id=current, asset_version_id=versions[0], position=0))
        session.execute(update(Dataset).where(Dataset.id == dataset).values(current_version_id=current, revision=2))
        session.add(ProjectDatasetReference(id=reference, project_id=project, dataset_id=dataset,
                                            dataset_version_id=fixed, base_revision=1))
    loaded = []
    with database.read_session() as session:
        event.listen(session, "loaded_as_persistent", lambda session, instance: loaded.append(type(instance).__name__))
        page = list_project_dataset_references(session, UUID(project))
    row = page.items[0]
    assert row.dataset.current_version_id == UUID(current)
    assert row.dataset.member_count == 1
    assert row.version.id == UUID(fixed) and row.member_count == 1001
    assert not any(name in loaded for name in ("DatasetMember", "Asset", "AssetVersion"))
    response = client.get(f"/api/v1/projects/{project}/datasets")
    assert response.status_code == 200, response.text
    assert response.json() == page.model_dump(mode="json")
    assert "members" not in response.json()["items"][0]["version"]
    assert len(response.content) < 10000

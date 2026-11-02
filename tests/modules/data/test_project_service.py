"""The direct service and HTTP adapter must not overwrite each other."""

from uuid import UUID

from fastapi.testclient import TestClient

from astrophotoflow.contracts.projects import ProjectOut
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.public import get_project


def test_project_public_service_and_http_route_return_the_same_project(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    app = create_app(settings, "project-test")
    with TestClient(app, headers={"Authorization": "Bearer project-test"}) as client:
        created = client.post("/api/v1/projects", json={"name": "M31"})
        assert created.status_code == 201, created.text
        project_id = UUID(created.json()["id"])
        with app.state.database.read_session() as session:
            result = get_project(session, project_id)
        assert isinstance(result, ProjectOut)
        observed = client.get(f"/api/v1/projects/{project_id}")
        assert observed.status_code == 200, observed.text
        assert result.model_dump(mode="json") == observed.json()

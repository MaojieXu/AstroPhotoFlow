"""Serving owns resources; inspecting the public schema must remain offline."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.interfaces.http.app import create_app


def test_openapi_does_not_initialize_serving_resources(tmp_path):
    workspace = tmp_path / "absent"
    settings = Settings("127.0.0.1", 8190, workspace, (), workspace=workspace)
    with patch("astrophotoflow.interfaces.http.lifespan.Database", side_effect=AssertionError("database created")), \
         patch("astrophotoflow.interfaces.http.lifespan.httpx.AsyncClient", side_effect=AssertionError("HTTP client created")):
        app = create_app(settings, "schema-only")
        assert app.openapi()["paths"]
    assert not workspace.exists()
    assert not hasattr(app.state, "database")
    assert not hasattr(app.state, "http_client")


@pytest.mark.parametrize("fail_startup", [None, "recover_software_calls", "BundlePreviews"])
def test_serving_closes_resources_even_when_startup_fails(tmp_path, fail_startup):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    initialize_database(settings)
    app = create_app(settings, "lifespan-test")
    real_close = Database.close
    with patch("astrophotoflow.interfaces.http.lifespan.Database.close", autospec=True, side_effect=real_close) as close:
        if fail_startup:
            with patch(f"astrophotoflow.interfaces.http.lifespan.{fail_startup}", side_effect=RuntimeError("recovery failed")), \
                 pytest.raises(RuntimeError, match="recovery failed"), TestClient(app):
                pytest.fail("startup should fail")
        else:
            with TestClient(app) as client:
                assert not app.state.http_client.is_closed
                assert client.get("/missing").status_code == 404
        assert app.state.http_client.is_closed
        close.assert_called_once_with(app.state.database)

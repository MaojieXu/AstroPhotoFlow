import pytest
from fastapi.openapi.utils import get_openapi

from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.http.app import create_app


def test_native_message_contracts_share_openapi_without_adding_http_operations(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "absent", (), workspace=tmp_path / "absent")
    app = create_app(settings, "schema-only")
    baseline = get_openapi(title=app.title, version=app.version, routes=app.routes)
    document = app.openapi()
    assert document["paths"] == baseline["paths"]
    assert app.openapi() is document
    assert not settings.database_path.exists()
    assert not hasattr(app.state, "http_client")

    names = set(document["x-apf-native-messages"])
    assert names == {
        "NativeCanvasCommand", "NativeCanvasGraphCommand", "NativeCanvasMessage",
        "NativeCanvasEvent", "NativePageEvent", "NativePageReply",
    }
    schemas = document["components"]["schemas"]
    assert names <= schemas.keys()
    assert schemas["NativeCanvasEvent"]["discriminator"]["propertyName"] == "action"
    assert schemas["NativePageEvent"]["discriminator"]["propertyName"] == "action"
    assert "content_token" in schemas["CanvasGraphRequest"]["required"]
    assert "workflow_impacts" not in schemas["SoftwarePlanSummary"]["properties"]
    assert "workflow_results" not in schemas["PackageMutationResult"]["properties"]
    assert not {"WorkflowImpact", "WorkflowChangeResult", "NativeWorkflowChangeResult"} & schemas.keys()

    pending = [schemas]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            assert "$defs" not in item
            reference = item.get("$ref")
            if reference is not None:
                assert reference.startswith("#/components/schemas/")
                assert reference.removeprefix("#/components/schemas/") in schemas
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def test_native_schema_conflicts_are_reported_instead_of_overwritten(tmp_path):
    app = create_app(Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path), "schema-only")
    document=app.openapi()
    document.pop("x-apf-native-messages")
    document["components"]["schemas"]["NativeCanvasCommand"]={"type":"integer"}
    with pytest.raises(ValueError, match="Conflicting native message schema: NativeCanvasCommand"):
        app.openapi()

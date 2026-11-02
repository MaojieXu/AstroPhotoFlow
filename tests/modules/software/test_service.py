import astrophotoflow.modules.software.packages.state as software_packages_state
import asyncio
import pytest
from types import SimpleNamespace
from uuid import uuid4
from pydantic import TypeAdapter

from astrophotoflow.interfaces.http.dependencies import authenticate
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.contracts.software import SoftwarePackage, SoftwarePackageState
from astrophotoflow.contracts.software import SoftwareInstallRequest
from astrophotoflow.comfyui.proxy import ROUTES
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.interfaces.http.software import get_software_packages, router as software_router
from astrophotoflow.contracts.native import NativePageConfirmSoftwareEvent, NativePageEvent
from astrophotoflow.modules.software.public import (
    get_bundled_definitions, get_operation, list_packages,
)


TOKEN = "test-token"


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_expired_page_and_missing_handler_return_localized_errors(tmp_path, locale):
    import json
    from astrophotoflow.core.localization import error_message
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    app = create_app(settings, TOKEN)
    route = next(route for route in app.routes if getattr(route, 'path', None) == '/internal/native/page')
    event = TypeAdapter(NativePageEvent).validate_python({
        'action': 'confirm_software', 'event_id': str(uuid4()), 'page_id': str(uuid4()),
        'page_token': 'page-token', 'payload': {'operation_id': str(uuid4())},
    })
    async def scenario():
        expired = await route.endpoint(event)
        assert expired.error.code == 'NATIVE_PAGE_EXPIRED'
        assert expired.error.message == error_message(locale, '', 'confirmation_page_expired')
        app.state.software_page_tokens[event.page_id] = event.page_token
        del app.state.confirm_software_action
        missing = await route.endpoint(event)
        assert missing.error.code == 'SOFTWARE_ACTION_EXPIRED'
        assert missing.error.message == error_message(locale, '', 'no_pending_software_action')
        assert not app.state.software_tasks
    asyncio.run(scenario())


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_changed_package_expires_plan_without_starting_install(tmp_path, monkeypatch, locale):
    import json
    import astrophotoflow.interfaces.application.package_actions as app_module
    from astrophotoflow.core.localization import error_message
    ready = SimpleNamespace(ready=True, web_url='http://127.0.0.1:8188')
    monkeypatch.setattr(app_module, 'workbench_status', lambda _path: ready)
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    app = create_app(settings, TOKEN)
    package = list_packages(settings)[0]
    pending = app.state.request_software_action('siril', SoftwareInstallRequest(version='1.4.4', package_token=package.package_token))
    page = uuid4()
    app.state.software_page_tokens[page] = 'page-token'
    monkeypatch.setattr(app_module, 'get_package', lambda *args: package.model_copy(update={'package_token': 'changed'}))
    with pytest.raises(ApiError):
        app.state.start_software_action(pending, page_id=page, page_token='page-token', workbench=ready)
    expired = app.state.software_actions['siril']
    assert expired.state == 'expired'
    assert expired.error.message == error_message(locale, '', 'action_package_changed')
    assert not app.state.software_tasks


@pytest.mark.parametrize('locale', ['en', 'zh'])
def test_background_install_error_localizes_outer_message_and_nested_reason(tmp_path, monkeypatch, locale):
    import json
    import astrophotoflow.interfaces.application.package_actions as app_module
    from astrophotoflow.core.localization import error_message

    ready = SimpleNamespace(ready=True, web_url='http://127.0.0.1:8188')
    monkeypatch.setattr(app_module, 'workbench_status', lambda _path: ready)
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    path = tmp_path / 'comfyui-user/default/comfy.settings.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'Comfy.Locale': locale}), encoding='utf-8')
    reason = ApiError(409, 'BUNDLE_VERSION_CHANGED', '原始中文错误',
                      message_key='bundle_reference_data_does_not_match_the_confirmed_snapshot_nothing_was_ins')
    failure = ApiError(503, 'SOFTWARE_NOT_READY', 'Bundle 安装失败：原始中文错误',
                       fields=[{'path': 'git', 'message': 'raw diagnostic 原文'}],
                       message_key='bundle_installation_failed_p0', message_params={'p0': reason})
    async def install(*args, **kwargs):
        raise failure
    monkeypatch.setattr(app_module, 'install_package', install)
    app = create_app(settings, TOKEN)
    async def scenario():
        package = list_packages(settings)[0]
        pending = app.state.request_software_action('siril', SoftwareInstallRequest(version='1.4.4', package_token=package.package_token))
        page = uuid4()
        app.state.software_page_tokens[page] = 'page-token'
        app.state.start_software_action(pending, page_id=page, page_token='page-token', workbench=ready)
        await app.state.software_tasks['siril']
        details = app.state.get_software_package_details('siril')
        expected = error_message(locale, failure.code, failure.message_key, failure.message_params)
        assert details.current_action.state == 'failed'
        assert details.current_action.error.message == details.result.error.message == expected
        assert details.result.error.code == failure.code and details.result.error.fields == failure.fields
    asyncio.run(scenario())


def test_siril_package_list_is_read_only_and_reports_platform_state(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    first = list_packages(settings)
    second = list_packages(settings)
    assert len(first) == 1
    assert first == second
    assert first[0].package_id == "siril"
    assert first[0].available_versions == ["1.4.4"]
    assert first[0].availability == "not_installed"
    assert first[0].installed_version is None
    assert first[0].install_path is None
    assert not (tmp_path / "software").exists()


def test_siril_package_reads_current_state_and_uses_version_in_token(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    before = list_packages(settings)[0]
    app_path = tmp_path / "software" / "siril" / "app"
    app_path.mkdir(parents=True)
    node_id = uuid4()
    state = SoftwarePackageState(
        installed_version="1.4.4", install_path=app_path, availability="not_ready", reason="Siril needs user setup.",
        operation="prepare", operation_state="failed", phase="license", progress=None,
        last_error=ErrorDetail(code="SETUP_REQUIRED", message="User setup required.", fields=[]),
        node_definition_ids=[node_id],
    )
    state_path = tmp_path / "software" / "siril" / "state.json"
    state_path.write_text(state.model_dump_json(), encoding="utf-8")
    after = list_packages(settings)[0]
    assert after.installed_version == "1.4.4"
    assert after.install_path == app_path
    assert after.availability == "not_ready"
    assert after.operation == "prepare"
    assert after.operation_state == "failed"
    assert after.phase == "license"
    assert after.last_error == state.last_error
    assert after.node_definition_ids == [node_id]
    assert after.package_token != before.package_token


def test_siril_operation_and_definition_are_version_bound(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    operation = get_operation(settings, "siril", "1.4.4", "autostretch")
    assert operation.syntax == "fixture-operation"
    assert operation.ready is False
    assert operation.cancel_supported is True
    assert operation.inputs[0].supports_hdu is False
    assert operation.inputs[0].supports_slice is False
    assert operation.inputs[0].cardinality == "many"
    assert operation.inputs[0].type == "APF_SCIENCE"
    assert [parameter.name for parameter in operation.parameters] == ["linked", "shadowsclip", "targetbg", "runtime"]
    definition = get_bundled_definitions(settings, "siril", "1.4.4")[0]
    assert definition["execution"]["operation_id"] == operation.operation_id
    assert definition["execution"]["package_id"] == operation.package_id
    assert len(get_bundled_definitions(settings, "siril", "1.4.4")) == 2
    with pytest.raises(ApiError) as missing:
        get_operation(settings, "siril", "1.4.3", "autostretch")
    assert missing.value.status_code == 404


def test_software_package_route_requires_auth_and_returns_real_state(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, TOKEN)
    route = next(route for route in software_router.routes if route.path == "/api/v1/software/packages")
    assert any(dependency.call is authenticate for dependency in route.dependant.dependencies)
    for path in (
        "/api/v1/software/packages/{package_id}/versions/{version}/commands",
        "/api/v1/software/packages/{package_id}",
        "/api/v1/software/packages/{package_id}/install",
        "/api/v1/software/packages/{package_id}/prepare",
    ):
        route = next(route for route in software_router.routes if route.path == path)
        assert any(dependency.call is authenticate for dependency in route.dependant.dependencies)
    internal = next(route for route in app.routes if getattr(route, "path", None) == "/internal/native/page")
    assert any(dependency.call is authenticate for dependency in internal.dependant.dependencies)
    assert ("GET", "/software/packages", "/software/packages") in ROUTES
    body = [SoftwarePackage.model_validate(item) for item in get_software_packages(SimpleNamespace(app=app))]
    assert len(body) == 1
    assert body[0].package_id == "siril"
    assert body[0].availability == "not_installed"
    assert not (tmp_path / "software").exists()
    assert "/api/v1/software/packages/{package_id}/versions/{version}/commands" in app.openapi()["paths"]
    assert ("GET", "/software/packages/{package_id}/versions/{version}/commands",
            "/software/packages/{package_id}/versions/{version}/commands") in ROUTES
    assert "/api/v1/software/packages" in app.openapi()["paths"]


def test_native_page_confirmation_has_no_client_supplied_page_identity():
    event_id = str(uuid4())
    page_id = str(uuid4())
    event = TypeAdapter(NativePageEvent).validate_python({
        "event_id": event_id,
        "page_id": page_id,
        "page_token": "server-issued-token",
        "action": "confirm_software",
        "payload": {"operation_id": str(uuid4())},
    })
    assert isinstance(event, NativePageConfirmSoftwareEvent)
    assert str(event.page_id) == page_id
    assert event.payload.operation_id


def test_install_request_builds_replaceable_plan_without_side_effects(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import astrophotoflow.interfaces.application.package_actions as app_module

    apps = []

    def ready_workbench(_path):
        assert not apps[0].state.software_action_lock.locked()
        return SimpleNamespace(ready=True, web_url="http://127.0.0.1:8188")

    monkeypatch.setattr(app_module, "workbench_status", ready_workbench)
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, TOKEN)
    apps.append(app)
    package = list_packages(settings)[0]
    body = SoftwareInstallRequest(version="1.4.4", package_token=package.package_token)
    first = app.state.request_software_action("siril", body)
    assert first.state == "awaiting_confirmation"
    assert "fixture-bundle.git @ v0.2.0-dev.2" in first.plan.source
    assert first.plan.restart_required is False
    assert first.plan.node_changes[0].action == "create"
    assert "operation_id=" + str(first.operation_id) in first.confirmation_url
    assert not (tmp_path / "software").exists()
    assert not (tmp_path / "nodes").exists()
    assert "/api/v1/software/packages/{package_id}" in app.openapi()["paths"]
    assert "/api/v1/software/packages/{package_id}/install" in app.openapi()["paths"]
    assert "/api/v1/software/packages/{package_id}/prepare" in app.openapi()["paths"]
    assert "/internal/native/page" not in app.openapi()["paths"]
    assert ("GET", "/software/packages/{package_id}", "/software/packages/{package_id}") in ROUTES
    assert ("POST", "/software/packages/{package_id}/install", "/software/packages/{package_id}/install") in ROUTES
    assert ("POST", "/software/packages/{package_id}/prepare", "/software/packages/{package_id}/prepare") in ROUTES

    second = app.state.request_software_action("siril", body)
    assert second.operation_id != first.operation_id
    with pytest.raises(ApiError) as expired:
        app.state.get_software_package_details("siril", operation_id=first.operation_id)
    assert expired.value.code == "SOFTWARE_ACTION_EXPIRED"


def test_bundle_update_plan_is_available_during_active_calls(tmp_path, monkeypatch, bundle_install):
    import astrophotoflow.interfaces.application.package_actions as app_module
    monkeypatch.setattr(app_module, 'workbench_status', lambda _path: SimpleNamespace(ready=True, web_url='http://127.0.0.1:8188'))
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', (), workspace=tmp_path)
    bundle_install(settings)
    from astrophotoflow.modules.software import bundles
    original = bundles.release('siril')
    newer = {**original, 'manifest': {**original['manifest'], 'bundle_version': '0.3.0-dev.1'}}
    monkeypatch.setattr(bundles, 'release', lambda package_id: newer)
    app = create_app(settings, TOKEN)
    package = list_packages(settings)[0]
    assert package.update_available
    app.state.software_calls[uuid4()] = SimpleNamespace(done=lambda: False)
    pending = app.state.request_software_action('siril', SoftwareInstallRequest(version='1.4.4', package_token=package.package_token))
    assert pending.state == 'awaiting_confirmation' and pending.plan.action == 'update'
    assert not pending.plan.restart_required


@pytest.mark.parametrize('native_mode', ['installed', 'development-ready', 'development-failed'])
def test_confirmed_install_reloads_native_nodes_without_scheduling_restart(tmp_path, monkeypatch, bundle_install, native_mode):
    from unittest.mock import Mock
    import httpx
    import astrophotoflow.interfaces.application.package_actions as app_module
    from astrophotoflow.contracts.nodes import NodeDefinition
    from astrophotoflow.core import workbench
    from astrophotoflow.modules.nodes.public import replace_package_definitions
    from astrophotoflow.modules.software import public
    from astrophotoflow.contracts.software import BundleDevelopmentSource

    ready = SimpleNamespace(ready=True, web_url='http://127.0.0.1:8188')
    monkeypatch.setattr(app_module, 'workbench_status', lambda _path: ready)
    restart = Mock()
    monkeypatch.setattr(workbench, 'request_restart', restart)
    settings = Settings('127.0.0.1', 8190, tmp_path/'data', ('http://127.0.0.1:8188',), workspace=tmp_path)
    observed_package = app_module.get_package

    def effective_package(settings, package_id):
        package = observed_package(settings, package_id)
        if native_mode != 'installed' and (package.installed_version or native_mode == 'development-ready'):
            source = BundleDevelopmentSource(root=tmp_path / 'development', head='a' * 40,
                fingerprint='b' * 64, state='ready' if native_mode == 'development-ready' else 'failed',
                software_version='1.4.4', bundle_version='0.2.0-dev.2',
                error=None if native_mode == 'development-ready' else 'Development nodes failed to load.')
            return package.model_copy(update={'availability': 'not_ready', 'reason': 'Published nodes are inactive.', 'development_source': source})
        return package

    monkeypatch.setattr(app_module, 'get_package', effective_package)
    development_definitions = get_bundled_definitions(settings, 'siril', '1.4.4')
    development_definitions[0]['name'] = 'Development stretch name'
    development_definitions[0]['category'] = ['development']
    if native_mode == 'development-ready':
        monkeypatch.setattr(app_module, 'get_bundle_metadata', lambda *_: (None, [], development_definitions))

    async def install(*args):
        bundle_install(settings)
        return public.get_package(settings, 'siril')

    monkeypatch.setattr(app_module, 'install_package', install)
    native_requests = []

    def native(request):
        native_requests.append(request)
        declarations = development_definitions if native_mode == 'development-ready' else get_bundled_definitions(settings, 'siril', '1.4.4')
        definitions = [NodeDefinition.model_validate(value) for value in declarations]
        replace_package_definitions(tmp_path, 'siril', definitions, {})
        return httpx.Response(200, json={'status': 'loaded'})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: client_class(transport=httpx.MockTransport(native), **kwargs))
    from astrophotoflow.core.database.schema import upgrade_database
    upgrade_database(settings)
    app = create_app(settings, TOKEN)

    async def scenario():
        async with app.router.lifespan_context(app):
            package = list_packages(settings)[0]
            pending = app.state.request_software_action('siril', SoftwareInstallRequest(version='1.4.4', package_token=package.package_token))
            page = uuid4()
            app.state.software_page_tokens[page] = 'page-token'
            app.state.start_software_action(pending, page_id=page, page_token='page-token', workbench=ready)
            await app.state.software_tasks['siril']
            result = app.state.get_software_package_details('siril')
            if native_mode == 'development-failed':
                assert result.current_action.state == 'failed'
                assert result.result.error.code == 'BUNDLE_LOAD_FAILED'
                assert result.result.definition_results == []
            else:
                assert result.current_action.state == 'completed' and result.package.effective_availability == 'ready'
                assert result.result.definition_results[0].applied
                if native_mode == 'development-ready':
                    assert result.package.availability == 'not_ready'
                    assert any(item.content.definition.name == 'Development stretch name' for item in result.result.definition_results)
            assert len(native_requests) == 1 and native_requests[0].url.path == '/astrophotoflow/internal/bundles/reload'
            assert native_requests[0].headers['Authorization'] == f'Bearer {TOKEN}'
            restart.assert_not_called()
    asyncio.run(scenario())


def test_confirmation_does_not_start_replaced_plan(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import astrophotoflow.interfaces.application.package_actions as app_module

    monkeypatch.setattr(app_module, "workbench_status", lambda _path: SimpleNamespace(ready=True, web_url="http://127.0.0.1:8188"))
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app = create_app(settings, TOKEN)
    package = list_packages(settings)[0]
    request = SoftwareInstallRequest(version="1.4.4", package_token=package.package_token)
    first = app.state.request_software_action("siril", request)
    page_id = uuid4()
    page_token = "page-token"
    with app.state.software_action_lock:
        app.state.software_page_tokens[page_id] = page_token

    second = app.state.request_software_action("siril", request)
    with pytest.raises(ApiError) as expired:
        app.state.start_software_action(
            first,
            page_id=page_id,
            page_token=page_token,
            workbench=SimpleNamespace(ready=True, web_url="http://127.0.0.1:8188"),
        )
    assert expired.value.code == "SOFTWARE_ACTION_EXPIRED"
    assert app.state.software_actions["siril"].operation_id == second.operation_id
    assert app.state.software_tasks == {}


def test_bundle_plan_includes_description_and_parameter_changes(tmp_path, monkeypatch):
    import json
    import astrophotoflow.interfaces.application.package_actions as app_module
    monkeypatch.setattr(app_module, 'workbench_status', lambda _path: SimpleNamespace(ready=True, web_url='http://127.0.0.1:8188'))
    settings = Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path)
    definition = get_bundled_definitions(settings, 'siril', '1.4.4')[0].copy()
    definition['description'] = 'Previous display description'
    directory = tmp_path/'nodes'
    directory.mkdir()
    path = directory/(definition['definition_id']+'.json')
    path.write_text(json.dumps(definition), encoding='utf-8')
    app = create_app(settings, TOKEN)
    package = list_packages(settings)[0]
    body = SoftwareInstallRequest(version='1.4.4', package_token=package.package_token)
    pending = app.state.request_software_action('siril', body)
    assert next(change for change in pending.plan.node_changes if str(change.definition_id) == definition['definition_id']).action == 'update'
    changed = json.loads(path.read_text(encoding='utf-8'))
    changed['parameters'][0]['default'] = True
    path.write_text(json.dumps(changed), encoding='utf-8')
    updated = app.state.request_software_action('siril', body)
    assert next(change for change in updated.plan.node_changes if str(change.definition_id) == definition['definition_id']).action == 'update'
    assert next(change for change in updated.plan.node_changes if str(change.definition_id) == definition['definition_id']).before_content_token != next(change for change in updated.plan.node_changes if str(change.definition_id) == definition['definition_id']).after_content_token


def test_uninstall_plan_requires_confirmation_and_keeps_actual_definitions(tmp_path, monkeypatch):
    import astrophotoflow.interfaces.application.package_actions as app_module
    from astrophotoflow.contracts.software import SoftwareUninstallRequest
    from astrophotoflow.modules.software import public

    monkeypatch.setattr(app_module, "workbench_status", lambda _path: SimpleNamespace(ready=True, web_url="http://127.0.0.1:8188"))
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    app_path = tmp_path / "software/siril/app"
    (app_path / "bin").mkdir(parents=True)
    (app_path / "bin/siril-cli.exe").write_bytes(b"fixture")
    software_packages_state.write_package_state(settings, "siril", SoftwarePackageState(
        installed_version="1.4.4", install_path=app_path, availability="ready", reason=None,
        operation="install", operation_state="completed", phase=None, progress=None,
        last_error=None, node_definition_ids=[],
    ))
    app = create_app(settings, TOKEN)
    package = public.get_package(settings, "siril")
    request = SoftwareUninstallRequest(package_token=package.package_token)
    pending = app.state.request_software_action("siril", request)
    assert pending.state == "awaiting_confirmation" and pending.plan.action == "uninstall"
    assert pending.plan.target_version is None and pending.plan.source is None
    assert pending.plan.restart_required is False
    assert app_path.exists() and not app.state.software_tasks
    assert "/api/v1/software/packages/{package_id}/uninstall" in app.openapi()["paths"]
    with pytest.raises(ApiError) as conflict:
        app.state.request_software_action("siril", SoftwareUninstallRequest(package_token="obsolete"))
    assert conflict.value.code == "SOFTWARE_CONTENT_CONFLICT"

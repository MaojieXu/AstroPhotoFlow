from astrophotoflow.core.workbench import update_running_state

"""HTTP maintenance admission and draining shutdown."""

from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Request
from sqlalchemy.exc import SQLAlchemyError

from astrophotoflow.contracts.workbench import BusyState, MaintenanceAction
from astrophotoflow.core.config import ConfigurationError, Settings
from astrophotoflow.interfaces.http.dependencies import authenticate
from astrophotoflow.modules.data.public import data_busy
from astrophotoflow.modules.software.public import (
    get_usage,
    list_packages,
)


def register_maintenance(app: FastAPI, settings: Settings) -> None:
    def set_maintenance(owner: UUID | None):
        update_running_state(settings.workspace, {"maintenance_operation_id": str(owner) if owner is not None else None})
        app.state.maintenance_owner = owner
        app.state.maintenance = owner is not None
        if owner is None:
            app.state.thumbnails.resume()
        else:
            app.state.thumbnails.pause()

    @app.post("/internal/maintenance", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def maintenance(body: MaintenanceAction):
        async with app.state.maintenance_lock:
            if app.state.shutdown_started:
                return BusyState(busy=True, unknown=False, blockers=["领域服务正在排空停止"])
            if body.action == "release":
                if app.state.maintenance_owner is None:
                    return BusyState(busy=False, unknown=False, blockers=[])
                if app.state.maintenance_owner != body.operation_id:
                    return BusyState(busy=True, unknown=False, blockers=["维护已归另一控制操作，本次释放未应用"])
                try:
                    set_maintenance(None)
                except (OSError, KeyError, ValueError, ConfigurationError) as exc:
                    return BusyState(busy=True, unknown=True, blockers=[f"维护标记释放失败：{exc}"])
                return BusyState(busy=False, unknown=False, blockers=[])
            if app.state.maintenance_owner not in {None, body.operation_id}:
                return BusyState(busy=True, unknown=False, blockers=["已有其他控制操作正在维护"])
            state = BusyState(busy=False, unknown=False, blockers=[])
            try:
                set_maintenance(body.operation_id)
                state = data_busy(app.state.database, app.state.media_views, app.state.data_exports)
                active_software = [package_id for package_id, task in app.state.software_tasks.items() if not task.done()]
                active_software.extend(f"{package.package_id}调用 {use.call_id}" for package in list_packages(settings) for use in get_usage(package.package_id))
                active_software.extend(f"Siril准备 {call_id}" for call_id, task in app.state.software_calls.items() if not task.done())
                if app.state.bundle_previews is not None:
                    active_software.extend(f"Siril实时预览 {consumer}" for consumer in app.state.bundle_previews.active)
                    if app.state.bundle_previews.requests:
                        active_software.append("Siril 实时预览请求尚未结束")
                if active_software:
                    state.busy = True
                    state.blockers.extend(f"软件包动作 {package_id}" for package_id in active_software)
                elif any(package.operation_state == "unknown" for package in list_packages(settings)):
                    state.unknown = True
                    state.blockers.append("无法确认Siril软件动作是否已停止")
                response = await app.state.http_client.get(settings.allowed_origins[0] + "/queue", timeout=3)
                response.raise_for_status()
                queue = response.json()
                running, pending = queue["queue_running"], queue["queue_pending"]
                if not isinstance(running, list) or not isinstance(pending, list):
                    raise TypeError("原生队列格式无效。")
                if running or pending:
                    state.busy = True
                    state.blockers.append("原生队列仍有执行或排队任务")
            except (OSError, httpx.HTTPError, KeyError, TypeError, ValueError, ConfigurationError, SQLAlchemyError) as exc:
                state.unknown = True
                state.blockers.append(f"无法确认工作台空闲：{exc}")
            if state.busy or state.unknown:
                try:
                    set_maintenance(None)
                except (OSError, KeyError, ValueError, ConfigurationError) as exc:
                    state.unknown = True
                    state.blockers.append(f"维护标记释放失败：{exc}")
            return state

    @app.post("/internal/shutdown", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def shutdown(request: Request):
        async with app.state.maintenance_lock:
            app.state.maintenance = True
            app.state.shutdown_started = True
            app.state.thumbnails.pause()
            request.app.state.shutdown()
        return {"status": "stopping"}

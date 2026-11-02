from astrophotoflow.modules.software.metadata import contained

"""Execute one validated software invocation and observe it."""
import asyncio
import logging
import os
import subprocess
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import psutil

from astrophotoflow.contracts.software import ProducedFile, SoftwareCancelResult, SoftwareInvocation, SoftwareObservation, SoftwareResult
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error, localized_error, workspace_locale
from astrophotoflow.modules.software import bundles, development
from astrophotoflow.modules.software.environment import bundle_environment
from astrophotoflow.modules.software.execution.processes import capture_descendants, runtime_active, stop_call, watch_process
from astrophotoflow.modules.software.execution.state import CALLS, Call, ObservationFailed
from astrophotoflow.modules.software.execution.validation import validate_invocation
from astrophotoflow.modules.software.packages.maintenance import PACKAGE_LOCKS

logger = logging.getLogger(__name__)


async def invoke_operation(settings: Settings, invocation: SoftwareInvocation,
                           observe: Callable[[SoftwareObservation], Awaitable[None]]) -> SoftwareResult:
    _package, work, operation = validate_invocation(settings, invocation)
    lock = PACKAGE_LOCKS.setdefault(invocation.package_id, asyncio.Lock())
    if lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "软件包正在维护。", message_key='the_software_package_is_undergoing_maintenance_da8f9d')
    if invocation.call_id in CALLS:
        raise ApiError(409, "SOFTWARE_BUSY", "该调用已受理，不能重复启动。", message_key='this_invocation_has_already_been_accepted_and_cannot_be_started_again')
    started = datetime.now(UTC)
    log = work / "siril.log"
    observation = SoftwareObservation(
        run_id=invocation.run_id, node_execution_id=invocation.node_execution_id, call_id=invocation.call_id,
        observed_at=started, active=True, runtime_ref=None, state="starting", phase="starting", log_path=log,
    )
    call = Call(invocation, observation)
    CALLS[invocation.call_id] = call
    outputs = {item.name: [] for item in operation.outputs}
    supporting_outputs = {}
    code = None
    error = None
    state = "failed"
    task = None
    try:
        await observe(observation)
        work.mkdir(parents=True, exist_ok=False)
        plan = bundles.adapter_plan(settings.workspace, invocation.package_id, invocation.operation_id,
                                    {name: [item.read_path for item in items] for name, items in invocation.inputs.items()},
                                    invocation.parameters, work,
                                    supporting_sources={name: [item.read_path for item in items] for name, items in invocation.supporting_inputs.items()},
                                    source_groups={name: [[item.read_path for item in items if item.reference_index == index]
                                                        for index in sorted({item.reference_index for item in items})]
                                                   for name, items in invocation.inputs.items()},
                                    supporting_groups={name: [[item.read_path for item in invocation.supporting_inputs.get(name, []) if item.reference_index == index]
                                                             for index in sorted({item.reference_index for item in items})]
                                                       for name, items in invocation.inputs.items()},
                                    source_metadata={name: [item.model_dump(mode='json', include={'reference_index', 'selection', 'scientific_metadata'}) for item in items]
                                                     for name, items in invocation.inputs.items()})
        if set(plan.outputs) != set(outputs):
            raise ValueError("Bundle 输出计划与操作端口不匹配。")
        plan.temporary_directory.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, **plan.environment, **{name: str(plan.temporary_directory) for name in ('TEMP', 'TMP', 'TMPDIR')}}
        if plan.thread_limit is not None:
            environment.update(OPENBLAS_NUM_THREADS=str(plan.thread_limit), OMP_NUM_THREADS=str(plan.thread_limit))
        executable = contained(development.source_root(settings.workspace, invocation.package_id),
                                       bundles.metadata(settings.workspace, invocation.package_id)[0].executable)
        if call.cancelled:
            state = "cancelled"
        else:
            with log.open("wb") as stream:
                call.process = await asyncio.create_subprocess_exec(
                    str(executable), *plan.arguments,
                    cwd=work, stdout=stream, stderr=asyncio.subprocess.STDOUT, env={**bundle_environment(executable), **{key: value for key, value in (environment or {}).items() if key.upper() != "PATH"}},
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    process = psutil.Process(call.process.pid)
                    runtime_ref = {"pid": process.pid, "create_time": process.create_time(),
                                   "executable": str(executable)}
                except psutil.NoSuchProcess:
                    runtime_ref = None
                except psutil.AccessDenied:
                    runtime_ref = None
                    call.inspection_unknown = True
                call.observation = observation.model_copy(update={
                    "observed_at": datetime.now(UTC), "state": "running", "phase": "processing",
                    "runtime_ref": runtime_ref,
                })
                task = asyncio.create_task(call.process.wait())
                try:
                    await observe(call.observation)
                except Exception as exc:
                    logger.exception("Initial software observation failed")
                    error = exception_error(workspace_locale(settings.workspace), exc, code='OBSERVATION_FAILED', message_key='observation_start_failed').model_copy(update={'code': 'OBSERVATION_FAILED'})
                if call.cancelled and call.process.returncode is None:
                    await stop_call(call)
                code = await watch_process(call, task, log, bundles.progress_reader(settings.workspace, invocation.package_id), observe)
            if call.cancelled:
                state = "cancelled"
            elif code != 0:
                detail = bundles.failure_reason(settings.workspace, invocation.package_id, log)
                error = localized_error(workspace_locale(settings.workspace), 'SOFTWARE_EXECUTION_FAILED', 'software_exit_failed', parameters={'exit_code': code}, fields=[{'path': 'software_log', 'message': detail}])
            elif error is None:
                collected = await asyncio.to_thread(bundles.collect_result, settings.workspace, invocation.package_id,
                                                    invocation.operation_id, plan, work, log)
                for definition in operation.outputs:
                    files = collected.outputs[definition.name]
                    if (definition.required and not files) or (definition.cardinality == 'one' and len(files) > 1):
                        raise ValueError('Bundle 输出成员数量不符合定义：' + definition.name)
                    if any(file.format not in definition.formats for file in files):
                        raise ValueError('Bundle 输出格式不符合定义：' + definition.name)
                outputs = {name: [ProducedFile.model_validate(file.model_dump()) for file in files] for name, files in collected.outputs.items()}
                supporting_outputs = {name: [ProducedFile.model_validate(file.model_dump()) for file in files] for name, files in collected.supporting_outputs.items()}
                state = "completed"
            elif error.code == 'OBSERVATION_FAILED':
                state = 'unknown'
    except asyncio.CancelledError:
        call.cancelled = True
        await asyncio.shield(stop_call(call))
        state = "cancelled"
        code = call.process.returncode if call.process else None
    except ObservationFailed as exc:
        if call.process is not None:
            code = call.process.returncode
            if code is None:
                code = await asyncio.shield(call.process.wait())
        state = 'unknown'
        error = exception_error(workspace_locale(settings.workspace), exc.__cause__ if isinstance(exc.__cause__, Exception) else exc, code='OBSERVATION_FAILED', message_key='observation_state_failed').model_copy(update={'code': 'OBSERVATION_FAILED'})
    except Exception as exc:
        logger.exception("Software invocation failed")
        if call.process is not None:
            code = call.process.returncode
            if code is None:
                code = await asyncio.shield(call.process.wait())
        error = exception_error(workspace_locale(settings.workspace), exc, code='SOFTWARE_EXECUTION_FAILED', message_key='software_execution_failed').model_copy(update={'code': 'SOFTWARE_EXECUTION_FAILED'})
    finally:
        if call.process is not None and call.process.returncode is not None and call.observation.runtime_ref:
            deadline = time.monotonic() + 5
            while runtime_active(call.observation.runtime_ref) is True and time.monotonic() < deadline:
                await asyncio.sleep(0.1)
        active = runtime_active(call.observation.runtime_ref) if call.observation.runtime_ref else None if call.inspection_unknown else call.process is not None and call.process.returncode is None
        if active is not False:
            state = 'unknown'
        call.observation = call.observation.model_copy(update={
            "observed_at": datetime.now(UTC), "active": active,
            "state": "unknown" if active else state, "phase": None, "exit_code": code, "error": error,
        })
        if active is False:
            CALLS.pop(invocation.call_id, None)
    try:
        await observe(call.observation)
    except Exception as exc:
        logger.exception("Final software observation failed")
        state = "unknown"
        error = exception_error(workspace_locale(settings.workspace), exc, code='OBSERVATION_FAILED', message_key='observation_result_failed').model_copy(update={'code': 'OBSERVATION_FAILED'})
    return SoftwareResult(
        call_id=invocation.call_id, state=state, started_at=started, ended_at=datetime.now(UTC),
        exit_code=code, outputs=outputs, supporting_outputs=supporting_outputs, log_path=log, error=error,
    )


async def inspect_operation(settings: Settings, invocation: SoftwareInvocation,
                            previous: SoftwareObservation | None) -> SoftwareObservation:
    call = CALLS.get(invocation.call_id)
    if call is not None:
        if call.observation.runtime_ref is not None:
            capture_descendants(call)
            call.observation = call.observation.model_copy(update={"active": runtime_active(call.observation.runtime_ref)})
        return call.observation
    if previous is None or previous.active is False:
        return previous or SoftwareObservation(
            run_id=invocation.run_id, node_execution_id=invocation.node_execution_id, call_id=invocation.call_id,
            observed_at=datetime.now(UTC), active=None, runtime_ref=None, state="unknown",
        )
    runtime = previous.runtime_ref
    active = None
    if runtime is not None:
        active = runtime_active(runtime)
    observation = previous.model_copy(update={"observed_at": datetime.now(UTC), "active": active, "state": "unknown", "phase": None})
    if active is not False:
        CALLS[invocation.call_id] = Call(invocation, observation)
    return observation


async def cancel_operation(call_id: UUID) -> SoftwareCancelResult:
    call = CALLS.get(call_id)
    if call is None:
        return SoftwareCancelResult(call_id=call_id, request_state="unknown", stop_state="unknown",
                                    observed_at=datetime.now(UTC), reason="当前没有可核对的调用句柄，不能据此断言已经停止。")
    if call.process is None and call.observation.state == "unknown":
        return SoftwareCancelResult(call_id=call_id, request_state="unknown", stop_state="unknown",
                                    observed_at=datetime.now(UTC), reason="原调用句柄已丢失，不能代替实际停止证据。")
    call.cancelled = True
    process = call.process
    if process is None:
        if call.observation.runtime_ref is not None:
            return SoftwareCancelResult(call_id=call_id, request_state="unknown", stop_state="unknown",
                                        observed_at=datetime.now(UTC), reason="服务重启后不再持有原调用句柄，需先核对实际进程。")
        return SoftwareCancelResult(call_id=call_id, request_state="sent", stop_state="running",
                                    observed_at=datetime.now(UTC), reason="已请求在实际启动前停止。")
    active = await stop_call(call)
    return SoftwareCancelResult(call_id=call_id, request_state="sent",
                                stop_state='stopped' if active is False else 'running' if active is True else 'unknown',
                                observed_at=datetime.now(UTC),
                                reason=None if active is False else '停止请求已发送，尚未确认整个调用进程树退出。')


"""Publish and resolve checked files without reading software-private call records."""

from uuid import UUID

from astrophotoflow.contracts.inputs import CheckedOutput, OutputLocator, ResolvedOutputInput
from astrophotoflow.contracts.results import CheckedResult, CheckedResultMember, CheckedResultPort
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.results.records import get_checked_result, save_checked_result
from astrophotoflow.modules.data.science.outputs import check_output


def result_member_base(run_id: UUID, execution_id: UUID, port_index: int, member_index: int) -> str:
    return f"/astrophotoflow/api/v1/runs/{run_id}/calls/{execution_id}/outputs/{port_index}/members/{member_index}"


def validate_result_file(settings: Settings, previous: CheckedOutput, *, full: bool) -> CheckedOutput:
    try:
        stamp = previous.path.stat()
        if not previous.path.is_file() or stamp.st_size != previous.byte_size or previous.mtime_ns is not None and stamp.st_mtime_ns != previous.mtime_ns:
            raise ApiError(409, "SOURCE_CHANGED", "Checked result changed after execution.", message_key='result_changed_after_execution')
        if not full and previous.mtime_ns is not None:
            return previous
        current = check_output(settings, run_directory=previous.run_directory, path=previous.path, expected_format=previous.format,
                               allow_empty=previous.format == "other" and previous.byte_size == 0,
                               colour_layout=(previous.scientific_metadata or {}).get("colour_layout"))
        if (current.content_hash, current.byte_size) != (previous.content_hash, previous.byte_size):
            raise ApiError(409, "SOURCE_CHANGED", "Checked result bytes differ from the frozen output.", message_key='result_frozen_bytes_mismatch')
        return current.model_copy(update={"scientific_metadata": previous.scientific_metadata})
    except OSError as exc:
        raise ApiError(410, "OUTPUT_UNAVAILABLE", "The checked file is missing; an old preview cannot replace it.", message_key='result_file_missing') from exc


def validate_member_scope(settings: Settings, result: CheckedResult, member: CheckedResultMember) -> None:
    if result.source_kind == "software":
        work = (settings.workspace / "runs" / str(result.run_id) / "work" / str(result.execution_id)).resolve()
        if member.checked.run_directory.resolve() != work or not member.checked.path.resolve().is_relative_to(work):
            raise ApiError(422, "INVALID_REFERENCE", "Output is outside its software execution directory.", message_key='result_outside_execution_directory')


def publish_checked_result(settings: Settings, result: CheckedResult) -> CheckedResult:
    for port in result.ports:
        for member in [*port.members, *port.supporting]:
            validate_member_scope(settings, result, member)
            validate_result_file(settings, member.checked, full=True)
    return save_checked_result(settings, result)


def get_result_member(settings: Settings, run_id: UUID, execution_id: UUID, output_index: int, member_index: int, *, full: bool = False) -> tuple[CheckedOutput, CheckedResultMember, CheckedResultPort]:
    result = get_checked_result(settings, run_id, execution_id)
    if not 0 <= output_index < len(result.ports):
        raise not_found()
    port = result.ports[output_index]
    if not 0 <= member_index < len(port.members):
        raise not_found()
    member = port.members[member_index]
    validate_member_scope(settings, result, member)
    return validate_result_file(settings, member.checked, full=full), member, port


def resolve_result_inputs(settings: Settings, prompt_id: UUID, locator: OutputLocator, expected_type: str) -> tuple[list[ResolvedOutputInput], list[ResolvedOutputInput]]:
    if locator.run_id != prompt_id:
        raise ApiError(422, "INVALID_REFERENCE", "Only checked outputs from this native prompt may be consumed.", message_key='result_prompt_mismatch')
    result = get_checked_result(settings, locator.run_id, locator.execution_id)
    if not 0 <= locator.output_index < len(result.ports) or result.ports[locator.output_index].type != expected_type:
        raise ApiError(422, "INVALID_REFERENCE", "Output port is missing or has an incompatible type.", message_key='result_output_port_invalid')
    port = result.ports[locator.output_index]
    indexes = [locator.member_index] if locator.member_index is not None else list(range(len(port.members)))
    if any(not 0 <= index < len(port.members) for index in indexes):
        raise not_found()
    def resolve(index: int, member: CheckedResultMember) -> ResolvedOutputInput:
        validate_member_scope(settings, result, member)
        checked = validate_result_file(settings, member.checked, full=True)
        return ResolvedOutputInput(kind="run_output", reference_index=0, locator=locator.model_copy(update={"member_index": index}),
            read_path=checked.path, format=checked.format, selection={'kind':'fits_hdu','hdu_index':member.selection['hdu_index']} if member.selection.get('hdu_index') is not None else {'kind':'whole_file'}, byte_size=checked.byte_size,
            content_hash=checked.content_hash, mtime_ns=checked.path.stat().st_mtime_ns, scientific_metadata=checked.scientific_metadata)
    return [resolve(index, port.members[index]) for index in indexes], [resolve(index, member) for index, member in enumerate(port.supporting)] if locator.member_index is None else []


def read_result_analysis(path):
    from pydantic import TypeAdapter

    from astrophotoflow.contracts.bundles import AnalysisResult
    return TypeAdapter(list[AnalysisResult]).validate_json(path.read_bytes())

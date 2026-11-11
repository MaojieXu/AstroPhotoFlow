"""Assemble directory admission from current data and concrete software calls."""

from pathlib import Path

from astrophotoflow.modules.data.public import (
    find_library_organization,
    organize_library,
    plan_library_organization,
    referenced_asset_ids,
)
from astrophotoflow.modules.software.public import unfinished_software_calls


def organization_blockers(database, settings, plan, exports=None) -> list[str]:
    identities = {str(move.asset_id) for move in plan.moves}
    paths = {str((settings.data_dir / 'library' / Path(move.source)).resolve()) for move in plan.moves}
    return original_use_blockers(database, settings, identities, paths, exports)


def original_use_blockers(database, settings, identities, paths, exports=None) -> list[str]:
    blockers = []
    for _, call_id, record in unfinished_software_calls(settings):
        if record.invocation is not None:
            used = {
                str(item.asset_id)
                for group in (record.invocation.inputs, record.invocation.supporting_inputs)
                for members in group.values() for item in members if item.kind == 'asset'
            }
        else:
            references = [reference for value in record.request.inputs.values()
                          for reference in (value if isinstance(value, list) else [value])
                          if reference.kind in {'asset', 'dataset'}]
            used = referenced_asset_ids(database, references)
        if identities.intersection(used):
            blockers.append(f'Software call {call_id} is still using selected originals ({record.state}).')
    if exports is not None:
        blockers.extend(exports.busy_library_paths(paths))
    return blockers


def preflight_organization(database, settings, body, exports=None):
    with database.read_session() as session:
        plan = plan_library_organization(session, settings, body)
    plan.blockers.extend(organization_blockers(database, settings, plan, exports))
    return plan


def execute_organization(database, settings, body, exports=None):
    with database.read_session() as session:
        previous = find_library_organization(session, body)
    if previous is not None:
        return previous
    plan = preflight_organization(database, settings, body, exports)
    return organize_library(database, settings, body, blockers=plan.blockers)


def preflight_cleanup(database, settings, body, exports=None):
    from astrophotoflow.modules.data.public import cleanup_originals, plan_cleanup
    with database.read_session() as session:
        result = plan_cleanup(session, settings, body)
        identities, paths = cleanup_originals(session, settings, body)
    result.blockers = original_use_blockers(database, settings, identities, paths, exports)
    return result


def execute_cleanup(database, settings, body, exports=None):
    from astrophotoflow.core.errors import ApiError
    from astrophotoflow.modules.data.public import delete_library_trash
    result = preflight_cleanup(database, settings, body, exports)
    if result.blockers:
        raise ApiError(409, 'ORIGINALS_IN_USE', 'Selected originals are still in use.',
                       [{'path': 'tasks', 'message': blocker} for blocker in result.blockers],
                       message_key='originals_in_use')
    with database.read_session() as session:
        return delete_library_trash(session=session, database=database, settings=settings, body=body)

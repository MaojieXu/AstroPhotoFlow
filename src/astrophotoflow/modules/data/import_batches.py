"""Confirmed batch intake and aggregate observation over existing import tasks."""
import hashlib
import json
import time
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select

from astrophotoflow.contracts.import_batches import BatchOut, ImportBatchProjectRetry, ImportBatchSubmit, ImportBatchWait
from astrophotoflow.contracts.imports import ImportCreate
from astrophotoflow.contracts.projects import ProjectDatasetReferenceCreate
from astrophotoflow.core import http as deps
from astrophotoflow.core.errors import ApiError, not_found
from .import_inspection import read_manifest, source_stamp
from .imports import create_import
from .models import AssetTask, AssetTaskItem, Dataset, Project, ProjectDatasetReference
from .projects import add_project_dataset_reference
from pathlib import Path

router = APIRouter(prefix='/api/v1/import-batches', dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)
ACTIVE = {'queued', 'running', 'cancelling'}


def batch_tasks(session, request_id):
    return list(session.scalars(select(AssetTask).where(
        AssetTask.report['agent_batch']['request_id'].as_string() == str(request_id)
    ).order_by(AssetTask.created_at, AssetTask.id)))


def batch_roots(tasks):
    return sorted((task for task in tasks if not task.report['agent_batch'].get('root_task_id')),
                  key=lambda task: task.report['agent_batch']['position'])


def group_items(session, tasks, root):
    family = [task for task in tasks if task.id == root.id or task.report['agent_batch'].get('root_task_id') == root.id]
    latest = {}
    for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id.in_([task.id for task in family]))
                                .order_by(AssetTaskItem.created_at, AssetTaskItem.id)):
        latest[item.root_item_id] = item
    return family, list(latest.values())


def _summary(session, request_id):
    tasks = batch_tasks(session, request_id)
    if not tasks:
        raise not_found()
    groups, errors = [], []
    running = False
    for root in batch_roots(tasks):
        family, items = group_items(session, tasks, root)
        pending = any(task.status in ACTIVE for task in family)
        running |= pending
        batch = root.report['agent_batch']
        running |= batch['project_link']['state'] == 'pending' and all(task.status not in {'interrupted', 'failed', 'cancelled'} for task in family)
        stages = {key: {state: sum(getattr(item, key + '_status') == state for item in items)
                       for state in sorted({getattr(item, key + '_status') for item in items})}
                  for key in ('content', 'metadata', 'preview')}
        groups.append({'name': batch['name'], 'task_id': root.id,
                       'tasks': [{'task_id': task.id, 'status': task.status} for task in family],
                       'dataset_id': root.dataset_id or root.target_dataset_id, 'items_total': len(items),
                       'registration_completed': all(task.enumeration_completed for task in family) and all(item.asset_version_id or item.status in {'failed', 'skipped', 'cancelled'} for item in items),
                       **stages, 'project_link': batch['project_link']})
        errors.extend({'task_id': item.task_id, 'item_id': item.id, 'error': item.error}
                      for item in items if item.error)
        errors.extend({'task_id': task.id, 'error': task.error} for task in family
                      if task.error and (task.id == family[-1].id or any(item.task_id == task.id and item.error for item in items)))
        errors.extend({'task_id': item.task_id, 'item_id': item.id, 'status': item.status}
                      for item in items if item.status in {'failed', 'cancelled', 'interrupted'} and not item.error)
        if batch['project_link']['state'] in {'failed', 'skipped'}:
            errors.append({'task_id': root.id, 'project_link': batch['project_link']})
    needs_attention = bool(errors) or any(group['tasks'][-1]['status'] in {'failed', 'cancelled', 'interrupted', 'completed_with_errors'} for group in groups)
    return {'request_id': str(request_id), 'state': 'running' if running else 'needs_attention' if needs_attention else 'completed',
            'groups': groups, 'errors': errors[:20], 'errors_total': len(errors),
            'next_poll_seconds': 5 if running else None}


@router.post('', response_model=BatchOut, status_code=202)
def submit(body: ImportBatchSubmit, request: Request, background: BackgroundTasks,
           admission: deps.TaskAdmission, session: deps.WriteSession):
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json', exclude_unset=True),
                                           sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    previous = batch_tasks(session, body.request_id)
    if previous:
        if any(task.report['agent_batch']['fingerprint'] != fingerprint for task in previous):
            raise ApiError(409, 'IMPORT_REQUEST_CONFLICT', 'The request_id was already accepted with different content.')
        return _summary(session, body.request_id)
    manifest = read_manifest(request.app.state.settings, body.scan_id)
    entries = {entry['id']: entry for entry in manifest['files']}
    groups = {group['id']: group for group in manifest['groups']}
    planned, seen = [], set()
    if body.project_id is not None:
        project = session.get(Project, str(body.project_id))
        if project is None or project.status != 'active':
            raise ApiError(422, 'INVALID_REFERENCE', 'Project must exist and be active.')
        if project.revision != body.project_revision:
            raise ApiError(409, 'REVISION_CONFLICT', 'Project changed; read its current revision and reconcile before submitting.')
    for group in body.groups:
        if group.group_id is not None:
            selected = groups.get(str(group.group_id))
            if selected is None:
                raise ApiError(422, 'INVALID_REFERENCE', 'Group is not in this inspection.')
            member_ids = selected['member_ids']
        else:
            member_ids = [str(identity) for identity in group.member_ids]
        sources = []
        frozen = []
        for identity in member_ids:
            if identity not in entries or identity in seen:
                raise ApiError(422, 'INVALID_REFERENCE', 'Every selected member must belong to this scan and occur in only one group.')
            seen.add(identity)
            entry = entries[identity]
            path = Path(entry['path'])
            try:
                unchanged = path.is_file() and source_stamp(path) == entry['source_stamp']
            except OSError:
                unchanged = False
            if not unchanged or any(issue['code'] == 'SOURCE_CHANGED' for issue in entry['issues']):
                raise ApiError(409, 'SOURCE_CHANGED', f'Source changed since inspection: {path}')
            sources.append({'path': str(path)})
            frozen.append(entry)
        planned.append((group, ImportCreate(sources=sources, storage_mode='managed', dataset_name=group.name,
                                          **group.options.model_dump(exclude_unset=True)), frozen))
    for position, (group, intake, frozen) in enumerate(planned):
        accepted = create_import(intake, request, background, admission, session)
        task = session.get(AssetTask, str(accepted['task_id']))
        # Keep the inspected stamps through registration and copy, including the acceptance race window.
        stamps = {entry['path']: entry['source_stamp'] for entry in frozen}
        task.sources = [{**source, 'entries': [{**entry, 'source_stamp': stamps[entry['path']]}
                                               for entry in source['entries']]} for source in task.sources]
        task.report = {**task.report, 'agent_batch': {
            'request_id': str(body.request_id), 'fingerprint': fingerprint, 'scan_id': str(body.scan_id),
            'position': position, 'name': group.name,
            'project_id': str(body.project_id) if body.project_id else None,
            'project_revision': body.project_revision,
            'project_link': {'state': 'pending' if body.project_id else 'not_requested'},
        }}
    session.flush()
    return _summary(session, body.request_id)


def finalize_project_links(database, request_id):
    """Called after intake, resume or retry. One write transaction preserves project revisions."""
    with database.write_session() as session:
        tasks = batch_tasks(session, request_id)
        roots = batch_roots(tasks)
        if not roots or not roots[0].report['agent_batch']['project_id'] or any(task.status in ACTIVE for task in tasks):
            return
        project_id = roots[0].report['agent_batch']['project_id']
        linked = sum(root.report['agent_batch']['project_link'].get('revision_delta', 0) for root in roots)
        expected = roots[0].report['agent_batch']['project_revision'] + linked
        for root in roots:
            batch = dict(root.report['agent_batch'])
            if batch['project_link']['state'] != 'pending':
                continue
            family, items = group_items(session, tasks, root)
            dataset_id = root.dataset_id or root.target_dataset_id
            dataset = session.get(Dataset, dataset_id) if dataset_id else None
            project = session.get(Project, project_id)
            if not items or any(item.content_status != 'available' for item in items) or dataset is None:
                result = {'state': 'skipped', 'code': 'IMPORT_NOT_READY', 'message': 'Only groups with all originals available are linked. Retry failed items, then explicitly retry project linking.'}
            elif project is None or project.status != 'active' or project.revision != expected:
                result = {'state': 'failed', 'code': 'REVISION_CONFLICT', 'message': 'Project changed after confirmation. Read it before retrying project linking.'}
            else:
                existing = session.scalar(select(ProjectDatasetReference).where(
                    ProjectDatasetReference.project_id == project_id,
                    ProjectDatasetReference.dataset_version_id == dataset.current_version_id))
                if existing:
                    result = {'state': 'linked', 'reference_id': existing.id, 'dataset_version_id': dataset.current_version_id, 'revision_delta': 0}
                else:
                    reference = add_project_dataset_reference(UUID(project_id), ProjectDatasetReferenceCreate(
                        base_revision=expected, dataset_id=dataset.id, dataset_version_id=dataset.current_version_id), session)
                    expected += 1
                    result = {'state': 'linked', 'reference_id': str(reference['id']), 'dataset_version_id': dataset.current_version_id, 'revision_delta': 1}
            # projects routes expire ORM instances; merge against the current report.
            root.report = {**root.report, 'agent_batch': {**root.report['agent_batch'], 'project_link': result}}
            session.flush()


def finalize_task_batch(database, task_id):
    with database.read_session() as session:
        task = session.get(AssetTask, task_id)
        batch = (task.report or {}).get('agent_batch') if task else None
    if batch is None:
        return
    try:
        finalize_project_links(database, batch['request_id'])
    except Exception as exc:
        logging.getLogger(__name__).exception('Batch project linking failed request_id=%s', batch['request_id'])
        with database.write_session() as session:
            for root in batch_roots(batch_tasks(session, batch['request_id'])):
                if root.report['agent_batch']['project_link']['state'] == 'pending':
                    root.report = {**root.report, 'agent_batch': {**root.report['agent_batch'],
                        'project_link': {'state': 'failed', 'code': 'PROJECT_LINK_FAILED', 'message': str(exc)}}}


def recover_batch_links(database):
    with database.read_session() as session:
        identities = list(session.scalars(select(AssetTask.id).where(
            AssetTask.report['agent_batch']['project_link']['state'].as_string() == 'pending')))
    for identity in identities:
        finalize_task_batch(database, identity)


@router.get('/{request_id}', response_model=BatchOut)
def status(request_id: UUID, session: deps.ReadSession):
    return _summary(session, request_id)


@router.post('/wait', response_model=BatchOut)
def wait_batch(body: ImportBatchWait, request: Request):
    deadline = time.monotonic() + body.wait_seconds
    while True:
        with request.app.state.database.read_session() as session:
            result = _summary(session, body.request_id)
        if result['state'] != 'running' or time.monotonic() >= deadline:
            return result
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))


@router.post('/{request_id}/project-references', response_model=BatchOut)
def retry_project_links(request_id: UUID, body: ImportBatchProjectRetry, request: Request,
                        background: BackgroundTasks, session: deps.WriteSession):
    tasks = batch_tasks(session, request_id)
    roots = batch_roots(tasks)
    if not roots:
        raise not_found()
    if any(task.status in ACTIVE for task in tasks):
        raise ApiError(409, 'IMPORT_NOT_READY', 'Wait for active tasks before retrying project links.')
    project_id = roots[0].report['agent_batch']['project_id']
    project = session.get(Project, project_id) if project_id else None
    if project is None or project.status != 'active' or project.revision != body.base_revision:
        raise ApiError(409, 'REVISION_CONFLICT', 'Read the active project and reconcile its current revision first.')
    linked = sum(root.report['agent_batch']['project_link'].get('revision_delta', 0) for root in roots)
    for root in roots:
        batch = {**root.report['agent_batch'], 'project_revision': body.base_revision - linked}
        if batch['project_link']['state'] != 'linked':
            batch['project_link'] = {'state': 'pending'}
        root.report = {**root.report, 'agent_batch': batch}
    background.add_task(finalize_project_links, request.app.state.database, str(request_id))
    return _summary(session, request_id)

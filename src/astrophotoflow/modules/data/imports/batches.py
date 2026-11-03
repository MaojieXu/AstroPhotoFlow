"""Confirmed batch intake and aggregate observation over existing import tasks."""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.import_batches import BatchOut, ImportBatchProjectRetry, ImportBatchSubmit, ImportBatchWait
from astrophotoflow.contracts.imports import ImportCreate
from astrophotoflow.contracts.projects import ProjectDatasetReferenceCreate
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import localized_error
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.projects.models import Project, ProjectDatasetReference

from ..projects.references import add_project_dataset_reference
from .inspection import read_manifest, source_stamp
from .submission import create_import


@dataclass(frozen=True)
class BatchAcceptance:
    result: BatchOut
    scheduled_task_ids: tuple[str, ...]


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


def submit_import_batch(session: Session, settings: Settings, body: ImportBatchSubmit) -> BatchAcceptance:
    scheduled = []
    fingerprint = hashlib.sha256(json.dumps(body.model_dump(mode='json', exclude_unset=True),
                                           sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    previous = batch_tasks(session, body.request_id)
    if previous:
        if any(task.report['agent_batch']['fingerprint'] != fingerprint for task in previous):
            raise ApiError(409, 'IMPORT_REQUEST_CONFLICT', 'The request_id was already accepted with different content.', message_key='import_request_identity_conflict')
        return BatchAcceptance(BatchOut.model_validate(_summary(session, body.request_id)), tuple(scheduled))
    manifest = read_manifest(settings, body.scan_id)
    entries = {entry['id']: entry for entry in manifest['files']}
    groups = {group['id']: group for group in manifest['groups']}
    planned, seen = [], set()
    if body.project_id is not None:
        project = session.get(Project, str(body.project_id))
        if project is None or project.status != 'active':
            raise ApiError(422, 'INVALID_REFERENCE', 'Project must exist and be active.', message_key='import_project_inactive')
        if project.revision != body.project_revision:
            raise ApiError(409, 'REVISION_CONFLICT', 'Project changed; read its current revision and reconcile before submitting.', message_key='import_project_revision_changed')
    for group in body.groups:
        if group.group_id is not None:
            selected = groups.get(str(group.group_id))
            if selected is None:
                raise ApiError(422, 'INVALID_REFERENCE', 'Group is not in this inspection.', message_key='import_group_outside_inspection')
            member_ids = selected['member_ids']
        else:
            member_ids = [str(identity) for identity in group.member_ids]
        sources = []
        frozen = []
        for identity in member_ids:
            if identity not in entries or identity in seen:
                raise ApiError(422, 'INVALID_REFERENCE', 'Every selected member must belong to this scan and occur in only one group.', message_key='import_group_members_invalid')
            seen.add(identity)
            entry = entries[identity]
            path = Path(entry['path'])
            try:
                unchanged = path.is_file() and source_stamp(path) == entry['source_stamp']
            except OSError:
                unchanged = False
            if not unchanged or any(issue['code'] == 'SOURCE_CHANGED' for issue in entry['issues']):
                raise ApiError(409, 'SOURCE_CHANGED', f'Source changed since inspection: {path}', message_key='inspection_source_changed', message_params={'path': str(path)})
            sources.append({'path': str(path)})
            frozen.append(entry)
        planned.append((group, ImportCreate(sources=sources, storage_mode='managed', dataset_name=group.name,
                                          **group.options.model_dump(exclude_unset=True)), frozen))
    for position, (group, intake, frozen) in enumerate(planned):
        accepted = create_import(session, settings, intake)
        scheduled.append(str(accepted.task_id))
        task = session.get(AssetTask, str(accepted.task_id))
        # Keep the inspected stamps through registration and copy, including the acceptance race window.
        observations = {entry['path']: entry for entry in frozen}
        task.sources = [{**source, 'entries': [{**entry, 'source_stamp': observations[entry['path']]['source_stamp'],
            'metadata_snapshot': observations[entry['path']].get('metadata_snapshot')}
                                               for entry in source['entries']]} for source in task.sources]
        task.report = {**task.report, 'agent_batch': {
            'request_id': str(body.request_id), 'fingerprint': fingerprint, 'scan_id': str(body.scan_id),
            'position': position, 'name': group.name,
            'project_id': str(body.project_id) if body.project_id else None,
            'project_revision': body.project_revision,
            'project_link': {'state': 'pending' if body.project_id else 'not_requested'},
        }}
    session.flush()
    return BatchAcceptance(BatchOut.model_validate(_summary(session, body.request_id)), tuple(scheduled))



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
            published_ids = {task.report.get('dataset_version_id') for task in family} - {None}
            expected_members = [item.asset_version_id for item in items]
            published = None
            for version in session.scalars(select(DatasetVersion).where(
                    DatasetVersion.id.in_(published_ids), DatasetVersion.dataset_id == dataset_id
            ).order_by(DatasetVersion.version_number.desc())):
                members = list(session.scalars(select(DatasetMember.asset_version_id).where(
                    DatasetMember.dataset_version_id == version.id).order_by(DatasetMember.position)))
                if len(members) == len(expected_members) and set(members) == set(expected_members):
                    published = version
                    break
            project = session.get(Project, project_id)
            if not items or any(item.content_status != 'available' for item in items) or dataset is None or published is None:
                result = project_link_failure('skipped', 'IMPORT_NOT_READY', 'import_link_originals_not_ready')
            elif dataset.status != 'active':
                result = project_link_failure('failed', 'INVALID_REFERENCE', 'import_link_dataset_archived')
            elif project is None or project.status != 'active' or project.revision != expected:
                result = project_link_failure('failed', 'REVISION_CONFLICT', 'import_link_project_changed')
            else:
                existing = session.scalar(select(ProjectDatasetReference).where(
                    ProjectDatasetReference.project_id == project_id,
                    ProjectDatasetReference.dataset_version_id == published.id))
                if existing:
                    result = {'state': 'linked', 'reference_id': existing.id, 'dataset_version_id': published.id, 'revision_delta': 0}
                else:
                    reference = add_project_dataset_reference(session, UUID(project_id), ProjectDatasetReferenceCreate(
                        base_revision=expected, dataset_id=dataset.id, dataset_version_id=published.id))
                    expected += 1
                    result = {'state': 'linked', 'reference_id': str(reference.id), 'dataset_version_id': published.id, 'revision_delta': 1}
            # Project reference updates expire ORM instances; merge against the current report.
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


def get_import_batch(session: Session, request_id: UUID) -> BatchOut:
    return BatchOut.model_validate(_summary(session, request_id))



def wait_import_batch(database: Database, body: ImportBatchWait) -> BatchOut:
    deadline = time.monotonic() + body.wait_seconds
    while True:
        with database.read_session() as session:
            result = _summary(session, body.request_id)
        if result['state'] != 'running' or time.monotonic() >= deadline:
            return BatchOut.model_validate(result)
        time.sleep(min(0.5, max(0, deadline - time.monotonic())))



def prepare_batch_project_retry(session: Session, request_id: UUID, body: ImportBatchProjectRetry) -> tuple[BatchOut, str]:
    tasks = batch_tasks(session, request_id)
    roots = batch_roots(tasks)
    if not roots:
        raise not_found()
    if any(task.status in ACTIVE for task in tasks):
        raise ApiError(409, 'IMPORT_NOT_READY', 'Wait for active tasks before retrying project links.', message_key='import_project_retry_tasks_active')
    project_id = roots[0].report['agent_batch']['project_id']
    project = session.get(Project, project_id) if project_id else None
    if project is None or project.status != 'active' or project.revision != body.base_revision:
        raise ApiError(409, 'REVISION_CONFLICT', 'Read the active project and reconcile its current revision first.', message_key='import_project_retry_revision_required')
    linked = sum(root.report['agent_batch']['project_link'].get('revision_delta', 0) for root in roots)
    for root in roots:
        batch = {**root.report['agent_batch'], 'project_revision': body.base_revision - linked}
        if batch['project_link']['state'] != 'linked':
            batch['project_link'] = {'state': 'pending'}
        root.report = {**root.report, 'agent_batch': batch}
    return BatchOut.model_validate(_summary(session, request_id)), roots[0].id



def project_link_failure(state: str, code: str, message_key: str) -> dict:
    # Persist the same canonical English facts as existing task records.
    detail = localized_error('en', code, message_key)
    return {'state': state, 'code': detail.code, 'message': detail.message}

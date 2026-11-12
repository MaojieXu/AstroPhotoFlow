from __future__ import annotations
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from astrophotoflow.contracts.projects import ProjectCreate, ProjectOut, ProjectPage, ProjectPatch
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.names import named_changes
from astrophotoflow.modules.data.projects.mapping import project_out
from astrophotoflow.modules.data.projects.models import Project

def get_project(session: Session, project_id: UUID) -> ProjectOut:
    row = session.get(Project, str(project_id))
    if row is None:
        raise not_found()
    return project_out(row)

def list_projects(session: Session, limit: int=50, offset: int=0, sort_by: Literal['created_at', 'name']='created_at', order: Literal['asc', 'desc']='desc', q: str | None=None, status: Literal['active', 'archived', 'all']='active', target_name: str | None=None) -> ProjectPage:
    filters = []
    status_clause = None if status == 'all' else Project.status == status
    if status_clause is not None:
        filters.append(status_clause)
    if q:
        filters.append(Project.name_search_key.contains(q.casefold(), autoescape=True))
    if target_name:
        filters.append(Project.target_name.contains(target_name, autoescape=True))
    total = session.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    column = Project.name_search_key if sort_by == 'name' else Project.created_at
    rows = session.scalars(select(Project).where(*filters).order_by(column.desc() if order == 'desc' else column.asc(), Project.id.asc()).limit(limit).offset(offset)).all()
    return ProjectPage.model_validate({'items': [project_out(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset})

def create_project(session: Session, body: ProjectCreate) -> ProjectOut:
    now = datetime.now(UTC)
    row = Project(id=str(uuid4()), name=body.name, target_name=body.target_name, notes=body.notes, status='active', revision=1, created_at=now, updated_at=now)
    session.add(row)
    session.flush()
    return project_out(row)

def advance_project_revision(session: Session, project_id: UUID | str, expected: int, changes: dict | None=None) -> None:
    identity = str(project_id)
    result = session.execute(update(Project).where(Project.id == identity, Project.revision == expected).values(**named_changes(changes or {}), revision=expected + 1, updated_at=datetime.now(UTC)))
    if result.rowcount != 1:
        if session.get(Project, identity) is None:
            raise not_found()
        raise ApiError(409, 'REVISION_CONFLICT', 'The project changed in another window.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')

def update_project(session: Session, project_id: UUID, body: ProjectPatch) -> ProjectOut:
    changes = body.model_dump(exclude_unset=True, exclude={'base_revision'})
    fields = [name for name in ('name', 'status') if name in changes and changes[name] is None]
    if fields:
        raise ApiError(422, 'VALIDATION_ERROR', 'These project fields cannot be null.', [{'path': name, 'message': 'Cannot be null.'} for name in fields], message_key='invalid_request_fields', field_message_keys={name: 'field_not_nullable' for name in fields})
    advance_project_revision(session, project_id, body.base_revision, changes)
    session.flush()
    session.expire_all()
    return get_project(session, project_id)

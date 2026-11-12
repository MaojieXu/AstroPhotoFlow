"""Bounded relational equipment and setup searches."""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.equipment import EquipmentPage, EquipmentQuery
from astrophotoflow.contracts.setups import EquipmentSetupPage, EquipmentSetupQuery
from astrophotoflow.modules.data.equipment.mapping import equipment_out, setup_out
from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup, EquipmentSetupMember

def list_equipment(session: Session, query: EquipmentQuery) -> EquipmentPage:
    filters = []
    if query.status != 'all':
        filters.append(Equipment.status == query.status)
    if query.kind is not None:
        filters.append(Equipment.kind == query.kind)
    if query.q:
        filters.append(or_(Equipment.name_search_key.contains(query.q.casefold(), autoescape=True), Equipment.model.contains(query.q, autoescape=True)))
    total = session.scalar(select(func.count()).select_from(Equipment).where(*filters)) or 0
    column = Equipment.name_search_key if query.sort_by == 'name' else Equipment.created_at
    ordering = column.desc() if query.order == 'desc' else column.asc()
    rows = session.scalars(select(Equipment).where(*filters).order_by(ordering, Equipment.id.asc()).limit(query.limit).offset(query.offset))
    return EquipmentPage(items=[equipment_out(row) for row in rows], total=total, limit=query.limit, offset=query.offset)

def list_setups(session: Session, query: EquipmentSetupQuery) -> EquipmentSetupPage:
    kind = func.coalesce(Equipment.kind, EquipmentSetupMember.inline_equipment['kind'].as_string())
    label = func.coalesce(Equipment.name, EquipmentSetupMember.inline_equipment['name'].as_string())
    filters = [] if query.status == 'all' else [EquipmentSetup.status == query.status]
    if query.q:
        filters.append(EquipmentSetup.name_search_key.contains(query.q.casefold(), autoescape=True))
    if query.component_kind is not None:
        filters.append(select(EquipmentSetupMember.id).outerjoin(Equipment).where(EquipmentSetupMember.setup_id == EquipmentSetup.id, kind == query.component_kind).exists())
    total = session.scalar(select(func.count()).select_from(EquipmentSetup).where(*filters)) or 0
    if query.sort_by in {'created_at', 'name'}:
        column = EquipmentSetup.name_search_key if query.sort_by == 'name' else EquipmentSetup.created_at
        ordering = [column.desc() if query.order == 'desc' else column.asc()]
    else:
        kinds = (query.sort_by,)
        names = select(label.label('name')).select_from(EquipmentSetupMember).outerjoin(Equipment).where(EquipmentSetupMember.setup_id == EquipmentSetup.id, kind.in_(kinds)).order_by(EquipmentSetupMember.position).correlate(EquipmentSetup).subquery()
        column = select(func.group_concat(names.c.name, ' / ')).scalar_subquery().collate('apf_casefold')
        ordering = [column.is_(None), column.desc() if query.order == 'desc' else column.asc(), EquipmentSetup.name_search_key.asc()]
        if query.sort_by == 'filter':
            channel = func.nullif(func.trim(func.coalesce(Equipment.specs['channel'].as_string(), EquipmentSetupMember.inline_equipment['specs']['channel'].as_string())), '')
            bandwidth = func.coalesce(Equipment.specs['bandwidth_nm'].as_float(), EquipmentSetupMember.inline_equipment['specs']['bandwidth_nm'].as_float())

            def first_filter_value(expression):
                return select(expression).select_from(EquipmentSetupMember).outerjoin(Equipment).where(EquipmentSetupMember.setup_id == EquipmentSetup.id, kind == 'filter').order_by(EquipmentSetupMember.position, EquipmentSetupMember.id).limit(1).correlate(EquipmentSetup).scalar_subquery()
            channel_key = first_filter_value(channel).collate('apf_casefold')
            bandwidth_key = first_filter_value(bandwidth)
            ordering = [column.is_(None), channel_key.is_(None), channel_key.desc() if query.order == 'desc' else channel_key.asc(), bandwidth_key.is_(None), bandwidth_key.desc() if query.order == 'desc' else bandwidth_key.asc(), column.desc() if query.order == 'desc' else column.asc(), EquipmentSetup.name_search_key.asc()]
    rows = session.scalars(select(EquipmentSetup).where(*filters).order_by(*ordering, EquipmentSetup.id.asc()).limit(query.limit).offset(query.offset))
    return EquipmentSetupPage(items=[setup_out(row) for row in rows], total=total, limit=query.limit, offset=query.offset)

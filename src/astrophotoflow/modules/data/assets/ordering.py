"""Database ordering keeps unknown/mixed partitions stable in both directions."""
from sqlalchemy import and_, case, or_

def compound_states(columns):

    def state(field):
        return columns[field + '__state']
    classification = case((and_(state('frame_class') == 2, state('frame_type') == 2), 2), (and_(state('frame_class') == 0, or_(state('frame_type') == 0, and_(columns.frame_class__value == 'video', state('frame_type') == 2))), 0), else_=1)
    binning = case((and_(state('binning_x') == 2, state('binning_y') == 2), 2), (and_(state('binning_x') == 0, state('binning_y') == 0), 0), else_=1)
    result = {'classification_summary_state': classification, 'binning_summary_state': binning}
    for slot in ('camera', 'optical_system', 'filter'):
        result[slot + '_summary_state'] = case((and_(state(slot + '_name') == 2, state(slot + '_id') == 2), 2), (and_(state(slot + '_name') == 0, state(slot + '_id') != 1), 0), else_=1)
    return result

def metadata_order(columns, sort_by: str, order: str):

    def direction(expression):
        return expression.desc() if order == 'desc' else expression.asc()
    if sort_by == 'created_at':
        result = [direction(columns.created_at)]
    elif sort_by == 'name':
        result = [direction(columns.name_search_key)]
    elif sort_by in {'status', 'notes'}:
        value = columns[sort_by]
        result = [case((value.is_(None), 2), else_=0).asc(), direction(value.collate('apf_casefold'))]
    elif sort_by == 'parameter_mode':
        mode, state = (columns.parameter_mode__value, columns.parameter_mode__state)
        group = case((state == 1, 2), (and_(state == 0, mode == 'iso'), 0), (and_(state == 0, mode == 'gain'), 1), else_=3)
        known = case((and_(group == 0, columns.iso__state == 0), 0), (and_(group == 1, columns.gain__state == 0, columns.offset__state != 1), 0), else_=1)
        number = case((and_(known == 0, group == 0), columns.iso__value), (and_(known == 0, group == 1), columns.gain__value))
        offset_missing = case((and_(group == 1, known == 0, columns.offset__state == 0), 0), else_=1)
        offset = case((offset_missing == 0, columns.offset__value))
        result = [group.asc(), known.asc(), direction(number), offset_missing.asc(), direction(offset)]
    else:
        if sort_by in {'classification', 'binning'}:
            state = columns[sort_by + '_summary_state']
            fields = ('frame_class', 'frame_type') if sort_by == 'classification' else ('binning_x', 'binning_y')
        elif sort_by in {'camera', 'optical_system', 'filter'}:
            state, fields = (columns[sort_by + '_summary_state'], (sort_by + '_name',))
        else:
            state, fields = (columns[sort_by + '__state'], (sort_by,))
        result = [state.asc()]
        for field in fields:
            value = case((state == 0, columns[field + '__value']))
            if field in {'frame_class', 'frame_type', 'camera_name', 'optical_system_name', 'filter_name', 'cfa_pattern', 'storage_mode'}:
                value = value.collate('apf_casefold')
            result.append(direction(value))
    return [*result, columns.entry_type.asc(), columns.id.asc()]

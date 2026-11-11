"""Translate explicit choices to the existing sparse relational binding map."""
from astrophotoflow.core.errors import ApiError
SLOTS = ('bias', 'dark', 'flat', 'dark_flat')
UNCONFIGURED = {'mode': 'unconfigured'}

def json_value(value):
    return value.model_dump(mode='json', exclude_unset=True) if hasattr(value, 'model_dump') else value

def patch_bindings(previous: dict, changes) -> dict:
    result = dict(previous)
    for slot, raw_choice in json_value(changes).items():
        if slot not in SLOTS:
            raise ApiError(422, 'INVALID_REQUEST', 'Unknown calibration slot.', message_key='unknown_calibration_slot')
        choice = json_value(raw_choice)
        mode = choice.get('mode') if isinstance(choice, dict) else None
        if mode == 'unconfigured':
            result[slot] = dict(UNCONFIGURED)
        elif mode == 'disabled':
            result[slot] = None
        elif mode == 'target':
            result[slot] = dict(choice['target'])
        else:
            raise ApiError(422, 'INVALID_REQUEST', 'An explicit calibration choice is required.', message_key='an_explicit_calibration_choice_is_required')
    return result

def explicit_choices(bindings: dict, *, complete: bool=False) -> dict:
    return {slot: {'mode': 'unconfigured'} if slot not in bindings or bindings[slot] == UNCONFIGURED else {'mode': 'disabled'} if bindings[slot] is None else {'mode': 'target', 'target': bindings[slot]} for slot in (SLOTS if complete else bindings)}

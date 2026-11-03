"""Translate explicit choices to the existing sparse relational binding map."""

from astrophotoflow.core.errors import ApiError

SLOTS = ("bias", "dark", "flat", "dark_flat")
UNCONFIGURED = {"mode": "unconfigured"}


def json_value(value):
    return value.model_dump(mode="json", exclude_unset=True) if hasattr(value, "model_dump") else value


def patch_bindings(previous: dict, changes, *, allow_inherit: bool = False) -> dict:
    result = dict(previous)
    for slot, raw_choice in json_value(changes).items():
        if slot not in SLOTS:
            raise ApiError(422, "INVALID_REQUEST", "Unknown calibration slot.")
        choice = json_value(raw_choice)
        mode = choice.get("mode") if isinstance(choice, dict) else None
        if mode == "inherit":
            if not allow_inherit:
                raise ApiError(422, "INVALID_REQUEST", "Inheritance is only valid for group members.")
            result.pop(slot, None)
        elif mode == "unconfigured":
            result[slot] = dict(UNCONFIGURED)
        elif mode == "disabled":
            result[slot] = None
        elif mode == "target":
            result[slot] = dict(choice["target"])
        else:
            raise ApiError(422, "INVALID_REQUEST", "An explicit calibration choice is required.")
    return result


def explicit_choices(bindings: dict, *, complete: bool = False) -> dict:
    return {slot: ({"mode": "unconfigured"} if slot not in bindings or bindings[slot] == UNCONFIGURED
                   else {"mode": "disabled"} if bindings[slot] is None
                   else {"mode": "target", "target": bindings[slot]})
            for slot in (SLOTS if complete else bindings)}


def incoming_bindings(changes=None) -> dict:
    # Explicit append never inherits a previous night's flat implicitly.
    initial = {slot: dict(UNCONFIGURED) for slot in SLOTS}
    if changes is None:
        return initial
    patch = json_value(changes)
    result = patch_bindings(initial, {slot: choice for slot, choice in patch.items()
                                      if json_value(choice).get("mode") != "inherit"})
    for slot, choice in patch.items():
        if json_value(choice).get("mode") == "inherit":
            result.pop(slot, None)
    return result

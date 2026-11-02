"""Serialize typed capability results at CLI and MCP presentation boundaries."""
from pydantic import JsonValue, TypeAdapter

_RESULT = TypeAdapter(object)


def json_value(value: object) -> JsonValue:
    return _RESULT.dump_python(value, mode="json", exclude_unset=True)

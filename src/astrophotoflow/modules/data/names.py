"""One Unicode search-key rule for named data records and revision updates."""
from collections.abc import Mapping
from sqlalchemy import String
from sqlalchemy.engine.default import DefaultExecutionContext
from sqlalchemy.orm import Mapped, mapped_column, validates

def name_search_key(value: str) -> str:
    return value.casefold()

def _insert_search_key(context: DefaultExecutionContext) -> str:
    return name_search_key(context.get_current_parameters()['name'])

class SearchableName:
    name_search_key: Mapped[str] = mapped_column(String, nullable=False, index=True, default=_insert_search_key)

    @validates('name')
    def index_name(self, _attribute: str, value: str) -> str:
        self.name_search_key = name_search_key(value)
        return value

def named_changes(changes: Mapping[str, object]) -> dict[str, object]:
    result = dict(changes)
    if 'name' in result:
        value = result['name']
        if not isinstance(value, str):
            raise TypeError('A persisted name must be a string')
        result['name_search_key'] = name_search_key(value)
    return result

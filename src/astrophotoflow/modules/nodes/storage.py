import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from filelock import FileLock

from astrophotoflow.contracts.nodes import (
    NodeDefinition,
    SavedDefinition,
)
from astrophotoflow.core.errors import ApiError

from .changes import saved_definition


def definition_directory(workspace: Path) -> Path:
    return workspace / "nodes"

def definition_path(workspace: Path, definition_id: UUID) -> Path:
    return definition_directory(workspace) / f"{definition_id}.json"

def read_definition(path: Path) -> SavedDefinition:
    definition = NodeDefinition.model_validate_json(path.read_text(encoding="utf-8"))
    if path.stem != str(definition.definition_id):
        raise ValueError(f"节点定义文件名与内容ID不匹配：{path}")
    return saved_definition(definition)

def write_definition(path: Path, definition: NodeDefinition, *, exclusive: bool) -> SavedDefinition:
    content = json.dumps(definition.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if exclusive:
        created = False
        try:
            stream = path.open("x", encoding="utf-8", newline="\n")
            created = True
            with stream:
                stream.write(content)
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise
    else:
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(content)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return saved_definition(definition)

def definition_lock(workspace: Path) -> FileLock:
    return FileLock(str(workspace / ".nodes.lock"), timeout=0)

def list_definitions(workspace: Path) -> list[SavedDefinition]:
    directory = definition_directory(workspace)
    if not directory.exists():
        return []
    return [read_definition(path) for path in sorted(directory.glob("*.json"))]

def get_definition(workspace: Path, definition_id: UUID) -> SavedDefinition:
    path = definition_path(workspace, definition_id)
    if not path.is_file():
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的节点定义。", message_key='the_requested_node_definition_was_not_found')
    return read_definition(path)

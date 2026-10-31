from astrophotoflow.interfaces.mcp.localization import tool_description
from pathlib import Path
from typing import Any

from astrophotoflow.contracts.imports import ImportCreate, RetryCreate
from astrophotoflow.contracts.imports import PhotoImportOptions



def register(server, call, locale='en'):
    @server.tool(description=tool_description(locale, 'import_photo'))
    def import_photo(path: str, options: PhotoImportOptions | None = None) -> dict[str, Any]:
        """Upload one local photo and start ingestion. Omitted classification uses file and frozen preset rules; unknown stays unknown."""
        return call(lambda client: client.import_photo(Path(path), options))


    @server.tool(description=tool_description(locale, 'import_photos'))
    def import_photos(paths: list[str], options: PhotoImportOptions | None = None) -> dict[str, Any]:
        """Upload multiple local photos in supplied order. Set options.create_dataset and dataset_name to register a logical group."""
        return call(lambda client: client.import_photos([Path(path) for path in paths], options))


    @server.tool(description=tool_description(locale, 'list_import_roots'))
    def list_import_roots() -> dict[str, Any]:
        """List the configured service-side local import roots."""
        return call(lambda client: {"items": client.list_import_roots()})


    @server.tool(description=tool_description(locale, 'browse_import_root'))
    def browse_import_root(root_id: str, path: str = "", limit: int = 50, offset: int = 0, q: str | None = None) -> dict[str, Any]:
        """Browse files and folders inside one configured root using relative POSIX paths."""
        return call(lambda client: client.browse_import_root(root_id, path, limit, offset, q))


    @server.tool(description=tool_description(locale, 'import_local'))
    def import_local(body: ImportCreate) -> dict[str, Any]:
        """Import local absolute paths with managed storage and no configured root; folders select their current level only. Existing root_id relative sources also support reference mode. Preset values freeze at acceptance."""
        return call(lambda client: client.import_local(body))


    @server.tool(description=tool_description(locale, 'list_import_tasks'))
    def list_import_tasks(limit: int = 50, offset: int = 0, status: str | None = None) -> dict[str, Any]:
        """List import tasks. Registration completion and original/metadata/preview readiness are separate states."""
        return call(lambda client: client.list_import_tasks(limit, offset, status))


    @server.tool(description=tool_description(locale, 'get_import_task'))
    def get_import_task(task_id: str, items_limit: int = 50, items_offset: int = 0) -> dict[str, Any]:
        """Read task progress, paged member outcomes and retry IDs. Registration does not imply original readiness."""
        return call(lambda client: client.get_import_task(task_id, items_limit, items_offset))


    @server.tool(description=tool_description(locale, 'cancel_import_task'))
    def cancel_import_task(task_id: str) -> dict[str, Any]:
        """Request cancellation of an import task."""
        return call(lambda client: client.cancel_import_task(task_id))


    @server.tool(description=tool_description(locale, 'resume_import_task'))
    def resume_import_task(task_id: str) -> dict[str, Any]:
        """Resume a service-interrupted task while retaining asset identities and accepted preset snapshot."""
        return call(lambda client: client.resume_import_task(task_id))


    @server.tool(description=tool_description(locale, 'retry_import_items'))
    def retry_import_items(task_id: str, body: RetryCreate) -> dict[str, Any]:
        """Retry selected task item IDs; retain the original accepted preset snapshot."""
        return call(lambda client: client.retry_import_items(task_id, body))

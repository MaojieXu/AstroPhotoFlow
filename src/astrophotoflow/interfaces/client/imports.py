from astrophotoflow.contracts.imports import PhotoImportOptions
from pathlib import Path
from typing import Any

from pydantic import Field

from astrophotoflow.contracts.assets import AssetClassification, AssetParameters
from astrophotoflow.contracts.imports import ImportCreate, RetryCreate, UploadFile, UploadImportCreate
from astrophotoflow.contracts.common import StrictModel, UuidInput




class ImportOperations:
    def inspect_import_sources(self, body):
        return self._result(self.client.post('/import-inspections', json=body.model_dump(mode='json'), timeout=None))

    def get_import_inspection(self, scan_id: str):
        return self.request('GET', f'/import-inspections/{scan_id}')

    def list_inspection_entries(self, scan_id: str, kind: str = 'files', group_id: str | None = None, limit: int = 50, offset: int = 0):
        return self.request('GET', f'/import-inspections/{scan_id}/entries', params={'kind': kind, 'group_id': group_id, 'limit': limit, 'offset': offset})

    def submit_import_batch(self, body):
        return self.request('POST', '/import-batches', json=body)

    def get_import_batch(self, request_id: str):
        return self.request('GET', f'/import-batches/{request_id}')

    def wait_import_batch(self, body):
        return self.request('POST', '/import-batches/wait', json=body)

    def retry_batch_project_links(self, request_id: str, body):
        return self.request('POST', f'/import-batches/{request_id}/project-references', json=body)

    def import_photo(self, path: Path, options: PhotoImportOptions | None = None) -> dict[str, Any]:
        return self.import_photos([path], options)

    def import_photos(self, paths: list[Path], options: PhotoImportOptions | None = None) -> dict[str, Any]:
        paths = [path.expanduser().resolve(strict=True) for path in paths]
        for path in paths:
            if not path.is_file():
                raise ValueError(f"不是文件：{path}")
        body = UploadImportCreate(
            files=[UploadFile(name=path.name, size=path.stat().st_size) for path in paths],
            **(options.model_dump(exclude_unset=True) if options else {}),
        )
        accepted = self.request("POST", "/uploads", json=body)
        task_id = str(accepted["task_id"])
        for index, path in enumerate(paths):
            with path.open("rb") as stream:
                def chunks():
                    while chunk := stream.read(1024 * 1024):
                        yield chunk
                response = self.client.put(f"/uploads/{task_id}/{index}", content=chunks(), timeout=None)
            self._result(response)
        return self.request("POST", f"/uploads/{task_id}/start")

    def list_import_roots(self) -> list[dict[str, Any]]:
        return self.request("GET", "/import-roots")

    def browse_import_root(self, root_id: str, path: str = "", limit: int = 50, offset: int = 0,
                           q: str | None = None) -> dict[str, Any]:
        return self.request("GET", f"/import-roots/{root_id}/entries",
                            params={"path": path, "limit": limit, "offset": offset, "q": q})

    def import_local(self, body: ImportCreate) -> dict[str, Any]:
        return self.request("POST", "/imports", json=body)

    def list_import_tasks(self, limit: int = 50, offset: int = 0, status: str | None = None) -> dict[str, Any]:
        return self.request("GET", "/asset-tasks", params={"limit": limit, "offset": offset, "status": status})

    def get_import_task(self, task_id: str, items_limit: int = 50, items_offset: int = 0) -> dict[str, Any]:
        return self.request("GET", f"/asset-tasks/{task_id}", params={"items_limit": items_limit, "items_offset": items_offset})

    def cancel_import_task(self, task_id: str) -> dict[str, Any]:
        return self.request("POST", f"/asset-tasks/{task_id}/cancel")

    def resume_import_task(self, task_id: str) -> dict[str, Any]:
        return self.request("POST", f"/asset-tasks/{task_id}/resume")

    def retry_import_items(self, task_id: str, body: RetryCreate) -> dict[str, Any]:
        return self.request("POST", f"/asset-tasks/{task_id}/retry", json=body)

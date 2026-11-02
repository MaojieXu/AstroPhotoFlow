from pathlib import Path

from pydantic import TypeAdapter

from astrophotoflow.contracts.import_batches import (
    BatchOut,
    ImportBatchProjectRetry,
    ImportBatchSubmit,
    ImportBatchWait,
    InspectionOut,
    InspectionPage,
    SourceInspection,
)
from astrophotoflow.contracts.imports import (
    AssetTaskOut,
    AssetTaskPage,
    ImportAccepted,
    ImportCreate,
    ImportRootEntryPage,
    ImportRootOut,
    ImportTaskStateOut,
    PhotoImportOptions,
    RetryCreate,
    UploadFile,
    UploadImportCreate,
    UploadReceipt,
)


class ImportOperations:
    def inspect_import_sources(self, body: SourceInspection) -> InspectionOut:
        return self._result(self.client.post('/import-inspections', json=body.model_dump(mode='json'), timeout=None), adapter=TypeAdapter(InspectionOut))

    def get_import_inspection(self, scan_id: str) -> InspectionOut:
        return self.request('GET', f'/import-inspections/{scan_id}', adapter=TypeAdapter(InspectionOut))

    def list_inspection_entries(self, scan_id: str, kind: str = 'files', group_id: str | None = None, limit: int = 50, offset: int = 0) -> InspectionPage:
        return self.request('GET', f'/import-inspections/{scan_id}/entries', params={'kind': kind, 'group_id': group_id, 'limit': limit, 'offset': offset}, adapter=TypeAdapter(InspectionPage))

    def submit_import_batch(self, body: ImportBatchSubmit) -> BatchOut:
        return self.request('POST', '/import-batches', json=body, adapter=TypeAdapter(BatchOut))

    def get_import_batch(self, request_id: str) -> BatchOut:
        return self.request('GET', f'/import-batches/{request_id}', adapter=TypeAdapter(BatchOut))

    def wait_import_batch(self, body: ImportBatchWait) -> BatchOut:
        return self.request('POST', '/import-batches/wait', json=body, adapter=TypeAdapter(BatchOut))

    def retry_batch_project_links(self, request_id: str, body: ImportBatchProjectRetry) -> BatchOut:
        return self.request('POST', f'/import-batches/{request_id}/project-references', json=body, adapter=TypeAdapter(BatchOut))

    def import_photo(self, path: Path, options: PhotoImportOptions | None = None) -> ImportAccepted:
        return self.import_photos([path], options)

    def import_photos(self, paths: list[Path], options: PhotoImportOptions | None = None) -> ImportAccepted:
        paths = [path.expanduser().resolve(strict=True) for path in paths]
        for path in paths:
            if not path.is_file():
                raise ValueError(f"不是文件：{path}")
        body = UploadImportCreate(
            files=[UploadFile(name=path.name, size=path.stat().st_size) for path in paths],
            **(options.model_dump(exclude_unset=True) if options else {}),
        )
        accepted = self.request("POST", "/uploads", json=body, adapter=TypeAdapter(ImportAccepted))
        task_id = str(accepted.task_id)
        for index, path in enumerate(paths):
            with path.open("rb") as stream:
                def chunks():
                    while chunk := stream.read(1024 * 1024):
                        yield chunk
                response = self.client.put(f"/uploads/{task_id}/{index}", content=chunks(), timeout=None)
            self._result(response, adapter=TypeAdapter(UploadReceipt))
        return self.request("POST", f"/uploads/{task_id}/start", adapter=TypeAdapter(ImportAccepted))

    def list_import_roots(self) -> list[ImportRootOut]:
        return self.request("GET", "/import-roots", adapter=TypeAdapter(list[ImportRootOut]))

    def browse_import_root(self, root_id: str, path: str = "", limit: int = 50, offset: int = 0,
                           q: str | None = None) -> ImportRootEntryPage:
        return self.request("GET", f"/import-roots/{root_id}/entries",
                            params={"path": path, "limit": limit, "offset": offset, "q": q}, adapter=TypeAdapter(ImportRootEntryPage))

    def import_local(self, body: ImportCreate) -> ImportAccepted:
        return self.request("POST", "/imports", json=body, adapter=TypeAdapter(ImportAccepted))

    def list_import_tasks(self, limit: int = 50, offset: int = 0, status: str | None = None) -> AssetTaskPage:
        return self.request("GET", "/asset-tasks", params={"limit": limit, "offset": offset, "status": status}, adapter=TypeAdapter(AssetTaskPage))

    def get_import_task(self, task_id: str, items_limit: int = 50, items_offset: int = 0) -> AssetTaskOut:
        return self.request("GET", f"/asset-tasks/{task_id}", params={"items_limit": items_limit, "items_offset": items_offset}, adapter=TypeAdapter(AssetTaskOut))

    def cancel_import_task(self, task_id: str) -> ImportTaskStateOut:
        return self.request("POST", f"/asset-tasks/{task_id}/cancel", adapter=TypeAdapter(ImportTaskStateOut))

    def resume_import_task(self, task_id: str) -> ImportAccepted:
        return self.request("POST", f"/asset-tasks/{task_id}/resume", adapter=TypeAdapter(ImportAccepted))

    def retry_import_items(self, task_id: str, body: RetryCreate) -> ImportAccepted:
        return self.request("POST", f"/asset-tasks/{task_id}/retry", json=body, adapter=TypeAdapter(ImportAccepted))

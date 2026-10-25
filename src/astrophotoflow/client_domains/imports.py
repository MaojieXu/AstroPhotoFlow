from pathlib import Path
from typing import Any

from pydantic import Field

from ..backend.import_schemas import (
    AssetClassification, AssetParameters, ImportCreate, RetryCreate, UploadFile, UploadImportCreate,
)
from ..backend.schemas import StrictModel, UuidInput


class PhotoImportOptions(StrictModel):
    """Upload metadata; file names and sizes are read from the supplied local paths."""

    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    create_dataset: bool = False
    capture_preset_id: UuidInput | None = None


class ImportOperations:
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

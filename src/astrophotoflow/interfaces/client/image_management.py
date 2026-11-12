"""HTTP client for explicit image intake and fixed calibration management."""

from __future__ import annotations
from typing import Any
from pydantic import TypeAdapter


def _json(value):
    return TypeAdapter(Any).dump_python(value, mode="json", exclude_unset=True)


class ImageManagementOperations:
    def thumbnail_batch_create(self, body):
        return self.request("POST", "/thumbnail-batches", json=_json(body))

    def thumbnail_batch_status(self, request_id, limit=50, offset=0):
        return self.request("GET", f"/thumbnail-batches/{request_id}", params={"limit": limit, "offset": offset})

    def thumbnail_batch_retry(self, request_id, item_ids):
        return self.request("POST", f"/thumbnail-batches/{request_id}/retry", json=_json({"item_ids": item_ids}))

    def image_imports_inspect(self, paths, recursive=True):
        return self.request("POST", "/import-inspections", json={"paths": paths, "recursive": recursive, "file_facts_only": True})

    def image_imports_get_inspection(self, scan_id):
        return self.request("GET", f"/import-inspections/{scan_id}", params={"file_facts_only": True})

    def image_imports_entries(self, scan_id, kind="files", query=None):
        return self.request(
            "GET",
            f"/import-inspections/{scan_id}/entries",
            params={"file_facts_only": True, "kind": kind, **(_json(query) if query is not None else {})},
        )

    def image_imports_import_asset(self, request_id, scan_id, file, defaults=None, storage_mode="managed", accept_unknown=False, project_id=None, project_base_revision=None):
        body = {
            "project_id": project_id,
            "project_base_revision": project_base_revision,
            "request_id": request_id,
            "scan_id": scan_id,
            "files": [file],
            "destination": {"mode": "standalone"},
            "storage_mode": storage_mode,
            "accept_unknown": accept_unknown,
        }
        if defaults is not None:
            body["defaults"] = defaults
        return self.request("POST", "/imports", json=_json(body))

    def image_imports_import_dataset(
        self, request_id, scan_id, name, files, defaults=None, calibration=None, notes=None, storage_mode="managed", accept_unknown=False, project_id=None, project_base_revision=None
    ):
        body = {
            "project_id": project_id,
            "project_base_revision": project_base_revision,
            "request_id": request_id,
            "scan_id": scan_id,
            "files": files,
            "destination": {"mode": "new_dataset", "name": name},
            "storage_mode": storage_mode,
            "accept_unknown": accept_unknown,
        }
        if notes is not None:
            body["destination"]["notes"] = notes
        if defaults is not None:
            body["defaults"] = defaults
        if calibration is not None:
            body["calibration"] = calibration
        return self.request("POST", "/imports", json=_json(body))

    def image_imports_append_dataset(
        self, request_id, scan_id, dataset_id, expected_revision, files, defaults=None, storage_mode="managed", accept_unknown=False, project_id=None, project_base_revision=None
    ):
        body = {
            "project_id": project_id,
            "project_base_revision": project_base_revision,
            "request_id": request_id,
            "scan_id": scan_id,
            "files": files,
            "destination": {"mode": "append_dataset", "dataset_id": dataset_id, "expected_revision": expected_revision},
            "storage_mode": storage_mode,
            "accept_unknown": accept_unknown,
        }
        if defaults is not None:
            body["defaults"] = defaults
        return self.request("POST", "/imports", json=_json(body))

    def image_imports_retry_publication(self, request_id, task_id, expected_revision):
        return self.request(
            "POST",
            f"/imports/{task_id}/dataset-publication",
            json=_json({"request_id": request_id, "expected_revision": expected_revision}),
        )

    def image_assets_search(self, query=None):
        return self.request("GET", "/library/assets", params={"image_query": True, **(_json(query) if query is not None else {})})

    def image_assets_get(self, asset_id):
        return self.request("GET", f"/library/assets/{asset_id}/detail", params=_json({}))

    def image_assets_update(self, asset_id, expected_revision, changes):
        return self.request(
            "PATCH", f"/library/assets/{asset_id}", json=_json({"expected_revision": expected_revision, "changes": changes})
        )

    def image_assets_update_metadata_batch(self, items):
        return self.request("POST", "/library/assets/metadata-updates", json=_json({"items": items}))

    def image_assets_apply_equipment(self, assets, equipment):
        body = {"assets": assets, "equipment": equipment}
        return self.request("POST", "/library/assets/equipment-applications", json=_json(body))

    def image_assets_read_header(self, asset_id, hdu_index=0, keywords=None, limit=100, offset=0):
        return self.request(
            "GET",
            f"/library/assets/{asset_id}/hdus/{hdu_index}/header",
            params={"keywords": keywords, "limit": limit, "offset": offset, "paged": True},
        )

    def image_assets_get_master_provenance(self, asset_id):
        return self.request("GET", f"/library/assets/{asset_id}/master-provenance", params=_json({}))

    def image_assets_update_master_provenance(self, asset_id, expected_revision, changes):
        return self.request(
            "PATCH",
            f"/library/assets/{asset_id}/master-provenance",
            json=_json({"expected_revision": expected_revision, "changes": changes}),
        )

    def image_datasets_search(self, query=None):
        return self.request("GET", "/datasets", params={"image_query": True, **(_json(query) if query is not None else {})})

    def image_datasets_get(self, dataset_id):
        return self.request("GET", f"/datasets/{dataset_id}/detail", params=_json({}))

    def image_datasets_create(self, request_id, name, members, calibration=None, notes=None, accept_unknown=False, project_id=None, project_base_revision=None):
        body = {"request_id": request_id, "name": name, "members": members, "accept_unknown": accept_unknown}
        if notes is not None:
            body["notes"] = notes
        if calibration is not None:
            body["calibration"] = calibration
        if project_id is not None or project_base_revision is not None:
            body.update(project_id=project_id, project_base_revision=project_base_revision)
        return self.request("POST", "/datasets", json=_json(body))

    def image_datasets_update(self, dataset_id, expected_revision, changes):
        return self.request("PATCH", f"/datasets/{dataset_id}", json=_json({"expected_revision": expected_revision, "changes": changes}))

    def image_datasets_members(self, dataset_id, query=None):
        return self.request(
            "GET", f"/datasets/{dataset_id}/members", params={"image_query": True, **(_json(query) if query is not None else {})}
        )

    def image_datasets_edit_members(self, request_id, dataset_id, expected_revision, add=None, remove=None, accept_unknown=False):
        body = {"request_id": request_id, "expected_revision": expected_revision, "accept_unknown": accept_unknown}
        if add is not None:
            body["add"] = add
        if remove is not None:
            body["remove"] = remove
        return self.request("POST", f"/datasets/{dataset_id}/member-edits", json=_json(body))

    def image_calibration_search(self, slot, consumer=None, query=None):
        body = {"slot": slot}
        if consumer is not None:
            body["consumer"] = consumer
        if query is not None:
            body["query"] = query
        return self.request("POST", "/calibration/search", json=_json(body))

    def image_calibration_check(self, consumer, proposal=None, limit=50, offset=0):
        body = {"consumer": consumer, "limit": limit, "offset": offset}
        if proposal is not None:
            body["proposal"] = proposal
        return self.request("POST", "/calibration/check", json=_json(body))

    def image_calibration_check_import(self, scan_id, files, defaults=None, calibration=None, destination=None, limit=50, offset=0):
        return self.request(
            "POST",
            "/calibration/import-check",
            json=_json(
                {
                    "scan_id": scan_id,
                    "files": files,
                    "defaults": defaults,
                    "calibration": calibration,
                    "destination": destination,
                    "limit": limit,
                    "offset": offset,
                }
            ),
        )

    def image_calibration_get_image(self, asset_id):
        return self.request("GET", f"/library/assets/{asset_id}/calibration", params=_json({}))

    def image_calibration_update_image(self, request_id, asset_id, expected_revision, changes, accept_unknown=False):
        return self.request(
            "POST",
            f"/library/assets/{asset_id}/calibration",
            json=_json(
                {"request_id": request_id, "expected_revision": expected_revision, "changes": changes, "accept_unknown": accept_unknown}
            ),
        )

    def image_calibration_get_dataset(self, dataset_id):
        return self.request("GET", f"/datasets/{dataset_id}/calibration")

    def image_calibration_update_dataset(self, request_id, dataset_id, expected_revision, changes, accept_unknown=False):
        return self.request(
            "POST",
            f"/datasets/{dataset_id}/calibration",
            json=_json(
                {"request_id": request_id, "expected_revision": expected_revision, "changes": changes, "accept_unknown": accept_unknown}
            ),
        )

    def image_calibration_get_operation(self, request_id):
        return self.request("GET", f"/calibration/operations/{request_id}")

    def image_tasks_status(self, request_id):
        return self.request("GET", f"/imports/requests/{request_id}")

    def image_tasks_get(self, task_id, items_limit=50, items_offset=0):
        return self.request(
            "GET", f"/asset-tasks/{task_id}", params={"image_query": True, "items_limit": items_limit, "items_offset": items_offset}
        )

    def image_tasks_wait(self, request_id, wait_seconds=20):
        return self.request("POST", f"/imports/requests/{request_id}/wait", json={"wait_seconds": wait_seconds})

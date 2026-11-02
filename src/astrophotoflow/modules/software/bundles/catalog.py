import hashlib
import json
from pathlib import Path

from astrophotoflow.contracts.bundles import (
    BundleManifest,
)
from astrophotoflow.contracts.software import SoftwareOperation
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import development
from astrophotoflow.modules.software.metadata import catalog, read_bundle


def release(package_id):
    value = catalog().get(package_id)
    if value is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到项目维护的软件包。', message_key='the_maintained_software_package_was_not_found')
    manifest = BundleManifest.model_validate(value['manifest'])
    if value['tag'] != 'v' + manifest.bundle_version:
        raise ValueError('Catalog tag does not match its version and release channel.')
    return value


def metadata(workspace: Path, package_id: str):
    root = development.source_root(workspace, package_id)
    if root.is_dir():
        return read_bundle(root)
    item = release(package_id)
    return BundleManifest.model_validate(item['manifest']), item['operations'], item['nodes']


def operation(workspace: Path, package_id: str, operation_id: str, ready: bool, reason: str | None):
    _, entries, _ = metadata(workspace, package_id)
    entry = next((value for value in entries if value['operation']['operation_id'] == operation_id), None)
    if entry is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到软件操作。', message_key='the_software_operation_was_not_found')
    return operation_from_entry(entry, ready, reason)


def operation_from_entry(entry, ready: bool, reason: str | None):
    value = SoftwareOperation.model_validate(dict(entry['operation'], content_token='', ready=ready, reason=reason))
    encoded = json.dumps(value.model_dump(mode='json', exclude={'content_token', 'ready', 'reason'}), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return value.model_copy(update={'content_token': hashlib.sha256(encoded.encode()).hexdigest()})

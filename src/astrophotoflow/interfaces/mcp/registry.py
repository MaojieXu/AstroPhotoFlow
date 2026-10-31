"""Private operation registry; only the two domain gateways are MCP tools."""
import inspect
import re
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ConfigDict, ValidationError, create_model


DATA_NAMES = {
    'import_photo': 'imports.upload_one', 'import_photos': 'imports.upload',
    'list_import_roots': 'imports.roots', 'browse_import_root': 'imports.browse',
    'import_local': 'imports.local', 'list_import_tasks': 'import_tasks.list',
    'get_import_task': 'import_tasks.get', 'cancel_import_task': 'import_tasks.cancel',
    'resume_import_task': 'import_tasks.resume', 'retry_import_items': 'import_tasks.retry',
    'prepare_canvas_data': 'assets.prepare_canvas_data',
    'list_assets': 'assets.list', 'list_library_items': 'library.search',
    'get_asset': 'assets.get', 'update_asset': 'assets.update',
    'update_asset_parameters': 'assets.update_parameters',
    'list_asset_versions': 'assets.list_versions', 'get_asset_version': 'assets.get_version',
    'create_dataset': 'datasets.create', 'list_datasets': 'datasets.list',
    'get_dataset': 'datasets.get', 'update_dataset': 'datasets.update',
    'list_dataset_versions': 'datasets.list_versions', 'get_dataset_version': 'datasets.get_version',
    'publish_dataset_version': 'datasets.publish_version', 'update_dataset_members': 'datasets.update_members',
    'list_calibration_targets': 'calibration.targets', 'remove_library_items': 'trash.remove',
    'list_trash': 'trash.list', 'restore_trash': 'trash.restore',
    'preview_trash_delete': 'trash.preview_delete', 'delete_trash': 'trash.delete',
    'schedule_display_preview': 'previews.schedule', 'get_display_preview_status': 'previews.status',
    'read_display_preview': 'previews.read',
    **{f'{verb}_project': f'projects.{verb}' for verb in ('create', 'get', 'update')},
    'list_projects': 'projects.list',
    **{f'{verb}_project_{kind}': f'projects.{verb}_{kind}' for kind in ('assets', 'datasets') for verb in ('list',)},
    **{f'{verb}_project_{kind}': f'projects.{verb}_{kind}' for kind in ('asset', 'dataset') for verb in ('get', 'add', 'remove')},
    **{f'{verb}_{kind}': f'equipment.{verb}_{suffix}'
       for kind, suffix in (('equipment', 'item'), ('equipment_setup', 'setup'), ('capture_preset', 'preset'))
       for verb in ('create', 'get', 'update')},
    'list_equipment': 'equipment.list_items', 'list_equipment_setups': 'equipment.list_setups',
    'list_capture_presets': 'equipment.list_presets',
}
CANVAS_NAMES = {
    'list_nodes': 'nodes.search', 'get_node': 'nodes.get', 'get_nodes': 'nodes.get_many',
    'list_run_calls': 'runs.list_calls', 'get_run_call': 'runs.get_call', 'get_run_analysis': 'runs.analysis',
    'get_canvas': 'canvas.get', 'edit_canvas': 'canvas.edit',
    'list_canvas_pages': 'canvas.pages', 'add_canvas_data': 'canvas.add_data',
    'get_canvas_request': 'receipts.get',
}

GROUP_TERMS = {
    'exports': '导出 保存 格式 精度 本机 完整结果',
    'imports': '导入 文件 路径 文件夹 检查 上传', 'import_tasks': '任务 等待 进度 取消 重试',
    'library': '素材库 搜索', 'assets': '素材 单图 资料 版本', 'datasets': '组 集合 成员 校准',
    'projects': '项目 关联 加入 素材组', 'equipment': '设备 器材 组合 预设',
    'calibration': '校准 目标', 'previews': '预览 图片', 'trash': '回收站 删除 恢复',
    'nodes': '节点 定义 参数', 'canvas': '画布 图 页面 编辑', 'receipts': '回执 结果',
    'runs': '运行 调用 分析',
}


@dataclass
class Operation:
    name: str
    fn: Any
    description: str
    model: Any

    def describe(self):
        return {'operation': self.name, 'description': self.description,
                'input_schema': self.model.model_json_schema(),
                'call_template': {'operation': self.name, 'arguments': {
                    key: f'<{key}>' for key, value in self.model.model_fields.items() if value.is_required()}}}


class Registry:
    def __init__(self, names):
        self.names = names
        self.operations = {}

    def tool(self, *, description=None):
        def register(fn):
            signature = inspect.signature(fn)
            annotations = inspect.get_annotations(fn, eval_str=True)
            model = create_model(fn.__name__ + 'Arguments', __config__=ConfigDict(extra='forbid'), **{
                key: (annotations[key], ... if value.default is inspect.Parameter.empty else value.default)
                for key, value in signature.parameters.items()})
            name = self.names[fn.__name__]
            if name in self.operations:
                raise ValueError(f'Duplicate operation: {name}')
            self.operations[name] = Operation(name, fn, description or inspect.getdoc(fn) or name, model)
            return fn
        return register

    def invoke(self, operation, arguments):
        try:
            if operation == 'describe':
                names = arguments.get('operations', [])
                if set(arguments) != {'operations'} or not isinstance(names, list) or not 1 <= len(names) <= 10:
                    raise ValueError('describe requires operations: a list of 1–10 exact names')
                return {'items': [self.operations[name].describe() for name in names]}
            if operation == 'discover':
                return self.discover(arguments)
            entry = self.operations[operation]
            body = entry.model.model_validate(arguments)
            return entry.fn(**{key: getattr(body, key) for key in entry.model.model_fields})
        except ValidationError as exc:
            raise ToolError(str(exc)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolError(f'Invalid operation/arguments: {exc}. Use discover or describe in this domain.') from exc

    def discover(self, arguments):
        if set(arguments) - {'query', 'group', 'limit', 'offset'}:
            raise ValueError('discover accepts query, group, limit, offset')
        query, group = arguments.get('query', ''), arguments.get('group', '')
        limit, offset = arguments.get('limit', 10), arguments.get('offset', 0)
        if not isinstance(query, str) or not isinstance(group, str) or type(limit) is not int or type(offset) is not int or not 1 <= limit <= 10 or offset < 0:
            raise ValueError('query/group must be strings; limit 1–10; offset >= 0')
        candidates = [entry for entry in self.operations.values() if not group or entry.name.startswith(group + '.')]
        exact = next((entry for entry in candidates if entry.name == query), None)
        tokens = re.findall(r'[\w]+', query.casefold())
        def score(entry):
            text = (entry.name + ' ' + entry.description + ' ' + GROUP_TERMS.get(entry.name.split('.')[0], '')).casefold()
            return sum(token in text for token in tokens) + sum(char in text for char in query if '\u4e00' <= char <= '\u9fff')
        if query:
            candidates = sorted((entry for entry in candidates if score(entry)), key=lambda entry: (-score(entry), entry.name))
        else:
            candidates.sort(key=lambda entry: entry.name)
        result = {'items': [{'operation': entry.name, 'description': entry.description.split('\n')[0]}
                            for entry in candidates[offset:offset + limit]],
                  'total': len(candidates), 'limit': limit, 'offset': offset}
        if exact or len(candidates) == 1:
            result['definition'] = (exact or candidates[0]).describe()
        return result

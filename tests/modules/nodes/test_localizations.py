import copy
import hashlib
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from astrophotoflow.contracts.nodes import NodeDefinition, definition_content_token
from astrophotoflow.modules.nodes import public
from astrophotoflow.modules.nodes.display import node_displays
from astrophotoflow.modules.nodes.changes import saved_definition
from astrophotoflow.modules.nodes.catalog import _describe_node
from astrophotoflow.modules.software.metadata import catalog


def raw_node():
    return copy.deepcopy(catalog()['siril']['nodes'][0])


def test_old_json_token_and_localization_round_trip(tmp_path):
    raw = raw_node()
    raw['source'] = 'custom'
    raw['definition_id'] = str(uuid4())
    before = NodeDefinition.model_validate(raw)
    old_content = before.model_dump(mode='json')
    old_content.pop('localizations')
    for parameter in old_content['parameters']:
        parameter.pop('unit')
        if parameter['editor'] is None:
            parameter.pop('editor')
    if not before.category:
        old_content.pop('category')
    expected = hashlib.sha256(json.dumps(old_content, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert definition_content_token(before) == expected
    raw['localizations'] = {'zh': {'name': '我的拉伸', 'description': '', 'parameters': {'targetbg': {'label': '目标'}}}}
    after = NodeDefinition.model_validate(raw)
    from astrophotoflow.modules.nodes.storage import write_definition, read_definition
    path = tmp_path / f'{after.definition_id}.json'
    write_definition(path, after, exclusive=True)
    restored = read_definition(path).definition
    assert restored.localizations['zh'].model_dump() == raw['localizations']['zh']
    assert definition_content_token(restored) == definition_content_token(after) != expected


@pytest.mark.parametrize('overrides', [
    None, {'fr': {}}, {'zh': None}, {'zh': {'name': None}}, {'zh': {'name': ' '}},
    {'zh': {'description': None}}, {'zh': {'parameters': None}},
    {'zh': {'inputs': {'image': {'label': ''}}}}, {'zh': {'inputs': {'image': None}}},
    {'zh': {'parameters': {'unknown': {'label': '未知'}}}},
    {'zh': {'category': ['wrong', '', 'depth']}},
])
def test_invalid_localizations_are_rejected(overrides):
    with pytest.raises(ValidationError):
        NodeDefinition.model_validate(dict(raw_node(), localizations=overrides))


def test_custom_bindings_inherit_labels_and_preserve_authored_text():
    raw = raw_node()
    raw.update(source='custom', name='My stretch', description='My explanation', category=['mine'])
    raw['inputs'][0]['name'] = 'source'
    raw['outputs'][0]['name'] = 'result'
    raw['execution']['inputs'] = {'image': 'source'}
    raw['execution']['outputs'] = {'result': 'image'}
    next(item for item in raw['parameters'] if item['name'] == 'targetbg')['name'] = 'target'
    raw['execution']['parameters']['targetbg'] = {'kind': 'parameter', 'name': 'target'}
    raw['localizations'] = {'zh': {'name': '我的节点', 'help': '', 'parameters': {'target': {'description': ''}}}}
    source = {'zh': {'name': '软件节点', 'description': '软件说明', 'help': '操作帮助', 'category': ['软件分类'],
                     'inputs': {'image': {'label': '原始输入', 'description': '输入说明'}},
                     'outputs': {'image': {'label': '处理输出', 'description': ''}},
                     'parameters': {'targetbg': {'label': '目标背景', 'description': '参数说明'}}}}
    displays = node_displays(NodeDefinition.model_validate(raw), source)
    assert displays['zh'].name == '我的节点'
    assert displays['zh'].description == 'My explanation'
    assert displays['zh'].help == ''
    assert displays['zh'].category == ['mine']
    assert displays['zh'].inputs['source'].label == '原始输入'
    assert displays['zh'].outputs['result'].label == '处理输出'
    assert displays['zh'].parameters['target'].label == '目标背景'
    assert displays['zh'].parameters['target'].description == ''
    assert displays['en'].name == 'My stretch'
    assert displays['en'].parameters['target'].label == 'target'


def test_conflicting_labels_and_fixed_parameters():
    raw = raw_node()
    raw['execution']['parameters']['other'] = {'kind': 'parameter', 'name': 'targetbg'}
    raw['execution']['parameters']['fixed'] = {'kind': 'fixed', 'value': 0}
    source = {'zh': {'parameters': {'targetbg': {'label': '目标', 'description': ''},
                                   'other': {'label': '另一个', 'description': ''},
                                   'fixed': {'label': '固定', 'description': ''}}}}
    display = node_displays(NodeDefinition.model_validate(raw), source)['zh']
    assert display.parameters['targetbg'].label == 'targetbg'
    assert 'fixed' not in display.parameters
    source['zh']['parameters']['other'] = source['zh']['parameters']['targetbg']
    assert node_displays(NodeDefinition.model_validate(raw), source)['zh'].parameters['targetbg'].label == '目标'
    raw['localizations'] = {'zh': {'parameters': {'targetbg': {'label': '明确覆盖'}}}}
    assert node_displays(NodeDefinition.model_validate(raw), source)['zh'].parameters['targetbg'].label == '明确覆盖'


def test_missing_operation_retains_node_display():
    raw = raw_node()
    raw['localizations'] = {'zh': {'name': '离线节点', 'description': '仍可查看'}}
    node = saved_definition(NodeDefinition.model_validate(raw))
    capability = _describe_node(node, {'entries': {}, 'operations': {}, 'package': None, 'display': {}, 'locale': 'zh'})
    assert not capability.available
    assert capability.display['zh'].name == '离线节点'
    assert capability.display['zh'].description == '仍可查看'


@pytest.mark.parametrize('source', ['package', 'custom'])
def test_catalog_returns_effective_display_from_the_shared_package_reader(tmp_path, monkeypatch, source):
    from astrophotoflow.modules.nodes import catalog as node_catalog
    from astrophotoflow.core.config import Settings
    from types import SimpleNamespace
    raw = raw_node()
    raw['source'] = source
    definition = NodeDefinition.model_validate(raw)
    from astrophotoflow.modules.nodes.storage import write_definition
    (tmp_path / 'nodes').mkdir()
    write_definition(tmp_path / 'nodes' / f'{definition.definition_id}.json', definition, exclusive=True)
    operation = public.describe_node(Settings('127.0.0.1', 0, tmp_path, (), workspace=tmp_path), definition.definition_id).operation
    package = SimpleNamespace(development_source=None, effective_bundle_commit='fixed', effective_availability='ready', effective_reason=None)
    monkeypatch.setattr(node_catalog, 'get_package', lambda *_: package)
    monkeypatch.setattr(node_catalog, 'get_bundle_display', lambda *_: {'zh': {definition.execution.operation_id:
        {'name': '软件译文', 'description': '说明', 'help': '帮助', 'category': definition.category}}})
    capability = public.describe_node(Settings('127.0.0.1', 0, tmp_path, (), workspace=tmp_path), definition.definition_id)
    assert capability.operation == operation
    assert capability.display['zh'].name == ('软件译文' if source == 'package' else definition.name)



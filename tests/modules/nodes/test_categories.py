import hashlib
import json

import pytest
from pydantic import ValidationError

from astrophotoflow.contracts.nodes import NodeDefinition, definition_content_token
from astrophotoflow.contracts.localization import CapabilityDisplay
from astrophotoflow.modules.software.metadata import catalog


def test_legacy_node_category_preserves_identity_and_content_token():
    raw = dict(catalog()['siril']['nodes'][0])
    raw.pop('category', None)
    node = NodeDefinition.model_validate(raw)
    content = node.model_dump(mode='json')
    content.pop('category')
    content.pop('localizations')
    for parameter in content['parameters']:
        parameter.pop('unit')
        if parameter['editor'] is None:
            parameter.pop('editor')
    expected = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert node.category == []
    assert definition_content_token(node) == expected
    categorized = node.model_copy(update={'category': ['stretch-color', 'automatic-stretch']})
    assert categorized.definition_id == node.definition_id
    assert categorized.execution == node.execution
    assert categorized.parameters == node.parameters
    assert definition_content_token(categorized) != expected
    assert CapabilityDisplay(name='Old display', description='', help='').category == []


@pytest.mark.parametrize('category', [[''], [' '], ['one/two'], [' padded']])
def test_invalid_category_levels_are_rejected(category):
    raw = dict(catalog()['siril']['nodes'][0], category=category)
    with pytest.raises(ValidationError, match='Category levels'):
        NodeDefinition.model_validate(raw)

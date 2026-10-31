import math
import pytest
from pydantic import ValidationError
from uuid import uuid4

from astrophotoflow.interfaces.data_reference_node import DataReferenceNode, FileReferenceNode
from astrophotoflow.contracts.data_nodes import NativeDataExecute


def test_data_is_a_real_native_output_node_with_exclusive_typed_inputs():
    schema = DataReferenceNode.INPUT_TYPES()
    assert schema['optional'] == {'science': ('APF_SCIENCE',), 'images': ('IMAGE',)}
    assert DataReferenceNode.RETURN_TYPES == ('APF_SCIENCE',)
    assert DataReferenceNode.RETURN_NAMES == ('science',)
    assert DataReferenceNode.OUTPUT_NODE is True
    assert DataReferenceNode.VALIDATE_INPUTS({'images': 'IMAGE'}, '') is True
    assert DataReferenceNode.VALIDATE_INPUTS({'science': 'APF_SCIENCE', 'images': 'IMAGE'}, '') is not True
    assert DataReferenceNode.VALIDATE_INPUTS({'science': 'APF_FILE'}, '') is not True
    assert math.isnan(DataReferenceNode.IS_CHANGED(reference='fixed'))


def test_file_node_retains_its_original_non_image_contract():
    assert 'optional' not in FileReferenceNode.INPUT_TYPES()
    assert FileReferenceNode.RETURN_TYPES == ('APF_FILE',)
    assert FileReferenceNode.OUTPUT_NODE is False
    assert FileReferenceNode.IS_CHANGED(reference='fixed') == 'fixed'
    text = '{"kind":"asset_version","asset_version_id":"00000000-0000-4000-8000-000000000001","selection":{"kind":"whole_file"}}'
    assert FileReferenceNode().reference(text)[0]['kind'] == 'asset_version'


def test_service_rejects_missing_or_conflicting_native_sources():
    body = {'run_id': uuid4(), 'execution_id': uuid4(), 'node_id': '1'}
    with pytest.raises(ValidationError): NativeDataExecute(**body)
    with pytest.raises(ValidationError): NativeDataExecute(**body, image_count=1)
    reference = {'kind': 'asset_version', 'asset_version_id': uuid4(), 'selection': {'kind': 'whole_file'}}
    with pytest.raises(ValidationError): NativeDataExecute(**body, reference=reference, image_count=1, input_dtype='float32')

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from astrophotoflow.contracts.inputs import OutputLocator
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import NativeBundleCall, SoftwareObservation
from astrophotoflow.contracts.software_calls import SoftwareCallBundle, SoftwareCallRecord
from astrophotoflow.core.config import Settings
from astrophotoflow.modules.software import bundles
from astrophotoflow.modules.software.execution.records import (
    call_record_path,
    list_software_call_records,
    read_software_call,
    save_software_call,
    unfinished_software_calls,
)


@pytest.fixture
def call(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    definition = NodeDefinition.model_validate(bundles.release('siril')['nodes'][0])
    request = NativeBundleCall(prompt_id=uuid4(), call_id=uuid4(), node_id='3',
        definition_id=definition.definition_id, definition_token='fixture', inputs={}, parameters={})
    record = SoftwareCallRecord(request=request, definition=definition,
        operation=bundles.operation(tmp_path, 'siril', 'autostretch', True, None),
        bundle=SoftwareCallBundle(version='0.2.0-dev.2', commit='fixture'),
        parameters={'gain': 0, 'cleared': None}, output_display='direct', state='starting')
    return settings, record


def test_record_round_trip_preserves_identity_zero_null_and_member_order(call):
    settings, record = call
    prompt, call_id = record.request.prompt_id, record.request.call_id
    record.outputs = [OutputLocator(kind='run_output', run_id=prompt, execution_id=call_id, output_index=index)
                      for index in (2, 0)]
    record.observation = SoftwareObservation(run_id=prompt, call_id=call_id, node_execution_id='3',
        observed_at=datetime.now(UTC), state='running', active=None, runtime_ref=None)
    save_software_call(settings, prompt, call_id, record)
    restored = read_software_call(settings, prompt, call_id)
    assert restored == record
    assert restored.parameters == {'gain': 0, 'cleared': None}
    assert [item.output_index for item in restored.outputs] == [2, 0]
    assert restored.observation.active is None
    assert list_software_call_records(settings, prompt) == [(call_id, record)]
    assert list(unfinished_software_calls(settings)) == [(prompt, call_id, record)]


def test_wrong_storage_identity_is_rejected_before_write_and_on_read(call):
    settings, record = call
    wrong = uuid4()
    with pytest.raises(ValueError, match='storage path'):
        save_software_call(settings, record.request.prompt_id, wrong, record)
    path = call_record_path(settings, record.request.prompt_id, wrong)
    assert not path.exists()
    path.parent.mkdir(parents=True)
    path.write_text(record.model_dump_json())
    with pytest.raises(ValueError, match='storage path'):
        read_software_call(settings, record.request.prompt_id, wrong)


def test_mutated_nested_identity_and_false_completion_cannot_be_saved(call):
    settings, record = call
    prompt, call_id = record.request.prompt_id, record.request.call_id
    record.outputs = [OutputLocator(kind='run_output', run_id=uuid4(), execution_id=call_id, output_index=0)]
    with pytest.raises(ValueError, match='another native call'):
        save_software_call(settings, prompt, call_id, record)
    record.outputs = []
    record.state = 'completed'
    with pytest.raises(ValueError, match='checked result registration'):
        save_software_call(settings, prompt, call_id, record)


def test_raw_or_corrupt_records_do_not_reintroduce_a_dictionary_compatibility_path(call):
    settings, record = call
    prompt, call_id = record.request.prompt_id, record.request.call_id
    with pytest.raises(TypeError, match='typed SoftwareCallRecord'):
        save_software_call(settings, prompt, call_id, record.model_dump())
    path = call_record_path(settings, prompt, call_id)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'state': 'unknown'}))
    with pytest.raises(ValueError):
        read_software_call(settings, prompt, call_id)


def test_arbitrary_string_cannot_escape_the_call_directory(call):
    settings, record = call
    with pytest.raises(ValueError):
        call_record_path(settings, '../outside', record.request.call_id)

from uuid import uuid4

import pytest
from pydantic import ValidationError

from astrophotoflow.contracts.software import SoftwareCallResult
from astrophotoflow.interfaces.native.replies import software_call_reply


def reply(prompt, call):
    return SoftwareCallResult(prompt_id=prompt, call_id=call, log_url='/checked/log', node_id='3',state='completed',
        ports=[{'name':'science','type':'APF_SCIENCE','members':[{'name':'full.fit','format':'fits','view_base':'/checked/view','file_url':'/checked/file'}]}]).model_dump(mode='json')


def test_native_publication_uses_the_complete_shared_contract():
    prompt, call = uuid4(), uuid4()
    value = reply(prompt, call)
    parsed = software_call_reply(value, str(prompt), str(call))
    assert parsed.model_dump(mode='json') == value
    assert parsed.ports[0].members[0].view_base == '/checked/view'
    assert parsed.observation is None and parsed.error is None


@pytest.mark.parametrize('change',[{'prompt_id':str(uuid4())},{'call_id':str(uuid4())},{'state':'failed'}])
def test_native_publication_rejects_another_or_failed_call(change):
    prompt, call = uuid4(), uuid4()
    with pytest.raises(ValueError):
        software_call_reply({**reply(prompt,call),**change},str(prompt),str(call))


def test_native_publication_does_not_synthesize_missing_file_references():
    prompt, call = uuid4(), uuid4()
    value = reply(prompt,call)
    del value['ports'][0]['members'][0]['file_url']
    with pytest.raises(ValidationError):
        software_call_reply(value,str(prompt),str(call))

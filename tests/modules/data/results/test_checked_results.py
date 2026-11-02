from uuid import uuid4
import os

import numpy as np
import pytest
from astropy.io import fits
from pydantic import ValidationError

from astrophotoflow.contracts.inputs import OutputLocator
from astrophotoflow.contracts.results import CheckedResult,CheckedResultPort,CheckedResultMember
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import check_output,publish_checked_result,resolve_result_inputs,get_result_member


def make_result(settings,prompt,execution,value):
    work=settings.workspace/'runs'/str(prompt)/'work'/str(execution);work.mkdir(parents=True)
    source=work/'full.fit';fits.PrimaryHDU(np.full((4,5),value,dtype=np.float32)).writeto(source)
    checked=check_output(settings,run_directory=work,path=source,expected_format='fits')
    checked=checked.model_copy(update={'scientific_metadata':{**(checked.scientific_metadata or {}),'parameters':{'gain':0}}})
    result=CheckedResult(run_id=prompt,execution_id=execution,source_kind='software',ports=[CheckedResultPort(name='science',type='APF_SCIENCE',members=[CheckedResultMember(checked=checked,name=source.name,selection={'hdu_index':0})])])
    publish_checked_result(settings,result)
    return result,source


def test_exact_call_reference_never_scans_or_requires_a_software_private_record(tmp_path):
    settings=Settings('127.0.0.1',8190,tmp_path/'data',(),workspace=tmp_path)
    prompt,first,second=uuid4(),uuid4(),uuid4()
    _,a=make_result(settings,prompt,first,1);_,b=make_result(settings,prompt,second,2)
    items,support=resolve_result_inputs(settings,prompt,OutputLocator(kind='run_output',run_id=prompt,execution_id=second,output_index=0),'APF_SCIENCE')
    assert [item.read_path for item in items]==[b] and not support
    assert items[0].selection.kind=='fits_hdu' and items[0].selection.hdu_index==0
    assert items[0].scientific_metadata['parameters']['gain']==0
    assert not (tmp_path/'runs'/str(prompt)/'calls').exists()
    assert a.read_bytes()!=b.read_bytes()


def test_node_name_is_not_an_execution_reference():
    with pytest.raises(ValidationError):
        OutputLocator(kind='run_output',run_id=uuid4(),node_execution_id='same-node',output_index=0)


def test_checked_result_is_immutable_and_rejects_wrong_prompt_or_port(tmp_path):
    settings=Settings('127.0.0.1',8190,tmp_path/'data',(),workspace=tmp_path)
    prompt,execution=uuid4(),uuid4();result,_=make_result(settings,prompt,execution,0)
    assert publish_checked_result(settings,result)==result
    with pytest.raises(ApiError) as conflict:
        publish_checked_result(settings,result.model_copy(update={'ports':[]}))
    assert conflict.value.code=='RESULT_CONTENT_CONFLICT'
    locator=OutputLocator(kind='run_output',run_id=prompt,execution_id=execution,output_index=0)
    with pytest.raises(ApiError):resolve_result_inputs(settings,uuid4(),locator,'APF_SCIENCE')
    with pytest.raises(ApiError):resolve_result_inputs(settings,prompt,locator,'APF_FILE')


def test_scientific_read_checks_hash_even_when_size_and_mtime_are_restored(tmp_path):
    settings=Settings('127.0.0.1',8190,tmp_path/'data',(),workspace=tmp_path)
    prompt,execution=uuid4(),uuid4();_,source=make_result(settings,prompt,execution,0)
    stamp=source.stat();content=bytearray(source.read_bytes());content[2883]^=1;source.write_bytes(content)
    os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
    with pytest.raises(ApiError) as changed:
        resolve_result_inputs(settings,prompt,OutputLocator(kind='run_output',run_id=prompt,execution_id=execution,output_index=0),'APF_SCIENCE')
    assert changed.value.code=='SOURCE_CHANGED'


def test_missing_checked_file_does_not_fall_back_to_a_preview(tmp_path):
    settings=Settings('127.0.0.1',8190,tmp_path/'data',(),workspace=tmp_path)
    prompt,execution=uuid4(),uuid4();_,source=make_result(settings,prompt,execution,0);source.unlink()
    with pytest.raises(ApiError) as missing:get_result_member(settings,prompt,execution,0,0,full=True)
    assert missing.value.code=='OUTPUT_UNAVAILABLE'


def test_read_rejects_a_corrupted_software_record_pointing_outside_its_execution(tmp_path):
    from astrophotoflow.modules.data.results.records import result_record_path
    settings=Settings('127.0.0.1',8190,tmp_path/'data',(),workspace=tmp_path)
    prompt,execution=uuid4(),uuid4();result,source=make_result(settings,prompt,execution,0)
    outside=tmp_path/'outside.fit';outside.write_bytes(source.read_bytes())
    wrong=check_output(settings,run_directory=tmp_path,path=outside,expected_format='fits')
    corrupted=result.model_copy(deep=True);corrupted.ports[0].members[0].checked=wrong
    result_record_path(settings,prompt,execution).write_text(corrupted.model_dump_json(),encoding='utf-8')
    with pytest.raises(ApiError) as invalid:get_result_member(settings,prompt,execution,0,0,full=True)
    assert invalid.value.code=='INVALID_REFERENCE'

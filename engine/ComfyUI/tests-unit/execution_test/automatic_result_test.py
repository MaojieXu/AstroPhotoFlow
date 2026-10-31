import asyncio

import execution
import nodes


def test_explicit_automatic_target_does_not_change_ordinary_output_semantics(monkeypatch):
    class Process:
        APF_AUTOMATIC_RESULT = True
        RETURN_TYPES = ('IMAGE',)
        OUTPUT_NODE = False

        @classmethod
        def INPUT_TYPES(cls):
            return {'required': {}}

    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, 'AutomaticProcess', Process)
    prompt = {'1': {'class_type': 'AutomaticProcess', 'inputs': {}}}
    normal = asyncio.run(execution.validate_prompt('test', prompt, None))
    assert normal[0] is False and normal[1]['type'] == 'prompt_no_outputs'
    automatic = asyncio.run(execution.validate_prompt('test', prompt, ['1'], {'targets': ['1'], 'signatures': {'1': 'a' * 64}}))
    assert automatic[0] is True and automatic[2] == ['1']
    assert Process.OUTPUT_NODE is False


def test_automatic_target_cannot_pull_in_a_manual_ancestor(monkeypatch):
    class Manual:
        APF_AUTOMATIC_RESULT = False
    class Automatic:
        APF_AUTOMATIC_RESULT = True
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, 'Manual', Manual)
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, 'Automatic', Automatic)
    prompt = {'1': {'class_type': 'Manual', 'inputs': {}}, '2': {'class_type': 'Automatic', 'inputs': {'image': ['1', 0]}}}
    result = asyncio.run(execution.validate_prompt('test', prompt, ['2'], {'targets': ['2'], 'signatures': {'1': 'a' * 64, '2': 'b' * 64}}))
    assert result[0] is False and result[1]['type'] == 'automatic_result_invalid'

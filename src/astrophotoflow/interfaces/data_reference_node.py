from pydantic import TypeAdapter

from astrophotoflow.contracts.inputs import InputReference
from astrophotoflow.contracts.data_nodes import ScienceReference


class DataReferenceNode:
    APF_AUTOMATIC_RESULT = True
    CATEGORY = "Data"
    RETURN_TYPES = ("APF_SCIENCE",)
    RETURN_NAMES = ("science",)
    FUNCTION = "reference"
    OUTPUT_NODE = True
    DESCRIPTION = "Preview and pass scientific references or native IMAGE data. Saving/exporting full results is an explicit separate action."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"reference": ("STRING", {"multiline": False, "default": "", "forceInput": False})},
                'optional': {'science': ('APF_SCIENCE',), 'images': ('IMAGE',)},
                'hidden': {'extra_pnginfo': 'EXTRA_PNGINFO', 'prompt': 'PROMPT'}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # A runtime locator is scoped to its native prompt, while upstream IMAGE may stay cached.
        return kwargs.get('reference', '') if cls is FileReferenceNode else float('nan')

    @classmethod
    def VALIDATE_INPUTS(cls, input_types, reference):
        if 'science' in input_types and 'images' in input_types:
            return 'Connect either science or images, not both.'
        for name, expected in (('science', 'APF_SCIENCE'), ('images', 'IMAGE')):
            if name in input_types and input_types[name] != expected:
                return f'{name} requires {expected}.'
        return True

    async def reference(self, reference: str, science=None, images=None, extra_pnginfo=None, prompt=None):
        import os
        from pathlib import Path
        from uuid import NAMESPACE_URL, uuid5
        import aiohttp
        import numpy as np
        from comfy_execution.utils import get_executing_context
        from astrophotoflow.core.config import load_running_settings

        if science is not None and images is not None:
            raise ValueError('Connect either science or images, not both.')
        context = get_executing_context()
        if context is None: raise RuntimeError('Data requires a native execution context.')
        settings = load_running_settings(Path(os.environ['APF_WORKSPACE']))
        execution_id = uuid5(NAMESPACE_URL, f'apf:data:{context.prompt_id}:{context.node_id}:{context.list_index}')
        body = {'run_id': context.prompt_id, 'execution_id': str(execution_id), 'node_id': str(context.node_id),
                'workflow_id': ((extra_pnginfo or {}).get('workflow') or {}).get('id')}
        inputs = ((prompt or {}).get(str(context.node_id)) or {}).get('inputs', {})
        body['input_bindings'] = {key: [str(value[0]), value[1]] for key, value in inputs.items()
                                  if key in {'science', 'images'} and isinstance(value, list) and len(value) == 2}
        if images is not None:
            pixels = images.detach().cpu().numpy()
            if pixels.dtype.name not in {'float16', 'float32', 'float64'} or pixels.ndim != 4 or pixels.shape[-1] not in {1, 3} or not all(pixels.shape):
                raise ValueError('IMAGE requires a nonempty BHWC floating batch with one or three channels.')
            directory = settings.workspace / 'runs' / str(context.prompt_id) / 'data' / str(execution_id)
            directory.mkdir(parents=True, exist_ok=True)
            for index, array in enumerate(pixels):
                with (directory / f'input-{index:06}.npy').open('xb') as stream:
                    np.save(stream, array[..., 0] if array.shape[-1] == 1 else array, allow_pickle=False)
            body.update(image_count=len(pixels), input_dtype=pixels.dtype.name)
        else:
            value = TypeAdapter(ScienceReference).validate_python(science) if science is not None else TypeAdapter(InputReference).validate_json(reference)
            body['reference'] = value.model_dump(mode='json')
        token = settings.token_path.read_text(encoding='utf-8').strip()
        async with aiohttp.ClientSession() as session:
            async with session.post(settings.service_url + '/internal/native/data', json=body,
                                    headers={'Authorization': f'Bearer {token}'}, timeout=aiohttp.ClientTimeout(total=None)) as response:
                result = await response.json()
                if response.status >= 400: raise RuntimeError(result.get('error', {}).get('message', 'Data preparation failed.'))
        return {'ui': {'apf_data': [result]}, 'result': (result['reference'],)}


class FileReferenceNode(DataReferenceNode):
    RETURN_TYPES = ('APF_FILE',)
    RETURN_NAMES = ('file',)
    DESCRIPTION = 'Fixed library file or ordered file group. Content identity is pinned before software processing.'
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'reference': ('STRING', {'multiline': False, 'default': '', 'forceInput': False})}}

    def reference(self, reference: str):
        value = TypeAdapter(InputReference).validate_json(reference)
        return (value.model_dump(mode='json'),)

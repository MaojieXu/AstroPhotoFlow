from pydantic import TypeAdapter

from astrophotoflow.contracts.inputs import InputReference


class DataReferenceNode:
    CATEGORY = "Data"
    RETURN_TYPES = ("APF_SCIENCE",)
    RETURN_NAMES = ("science",)
    FUNCTION = "reference"
    DESCRIPTION = "Fixed scientific asset or ordered group reference. Preview images are not processing inputs."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"reference": ("STRING", {"multiline": False, "default": "", "forceInput": False})}}

    def reference(self, reference: str):
        value = TypeAdapter(InputReference).validate_json(reference)
        return (value.model_dump(mode="json"),)


class FileReferenceNode(DataReferenceNode):
    RETURN_TYPES = ('APF_FILE',)
    RETURN_NAMES = ('file',)
    DESCRIPTION = 'Fixed library file or ordered file group. Content identity is pinned before software processing.'

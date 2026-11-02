from uuid import uuid4

import pytest
from pydantic import ValidationError

from astrophotoflow.contracts.nodes import NodeDefinition, NodePort, SavedDefinition
from astrophotoflow.contracts.software import ParameterDefinition, SoftwareInputDefinition, SoftwareOperation, SoftwareOutputDefinition
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.nodes import public
from astrophotoflow.modules.software.public import get_bundled_definitions, get_operation


def _settings(workspace):
    return Settings("127.0.0.1", 8190, workspace, (), workspace=workspace)


def _definition(settings, *, definition_id=None, source="custom", name="Auto Stretch"):
    raw = get_bundled_definitions(settings, "siril", "1.4.4")[0]
    raw["definition_id"] = str(definition_id or uuid4())
    raw["source"] = source
    raw["name"] = name
    return NodeDefinition.model_validate(raw)


def test_custom_definition_create_read_token_and_optional_unready_operation(tmp_path):
    settings = _settings(tmp_path)
    operation = get_operation(settings, "siril", "1.4.4", "autostretch")
    definition = _definition(settings)
    saved = public.create_definition(tmp_path, definition, operation)
    assert saved.definition == definition
    assert saved.native_type == f"APF_{definition.definition_id.hex}"
    assert saved.content_token == public.get_definition(tmp_path, definition.definition_id).content_token
    assert public.list_definitions(tmp_path) == [saved]
    assert operation.ready is False
    with pytest.raises(ApiError) as duplicate:
        public.create_definition(tmp_path, definition, operation)
    assert duplicate.value.status_code == 409


def test_definition_validation_rejects_duplicate_names_and_invalid_binding(tmp_path):
    settings = _settings(tmp_path)
    raw = get_bundled_definitions(settings, "siril", "1.4.4")[0]
    raw["definition_id"] = str(uuid4())
    raw["inputs"].append(raw["inputs"][0].copy())
    with pytest.raises(ValidationError):
        NodeDefinition.model_validate(raw)
    with pytest.raises(ValidationError):
        ParameterDefinition(name="target", kind="float", default=1.2, minimum=0, maximum=1)

    definition = _definition(settings)
    bad = definition.model_copy(update={"execution": definition.execution.model_copy(update={"inputs": {"missing": "image"}})})
    with pytest.raises(ApiError) as invalid:
        public.create_definition(tmp_path, bad, get_operation(settings, "siril", "1.4.4", "autostretch"))
    assert invalid.value.code == "INVALID_NODE_BINDING"
    operation = get_operation(settings, "siril", "1.4.4", "autostretch")
    nullable_parameters = [parameter.model_copy(update={"nullable": True}) if parameter.name == "targetbg" else parameter
                           for parameter in definition.parameters]
    wrong_nullable = definition.model_copy(update={"parameters": nullable_parameters})
    with pytest.raises(ApiError) as invalid_nullable:
        public.create_definition(tmp_path, wrong_nullable, operation)
    assert invalid_nullable.value.code == "INVALID_NODE_BINDING"
    assert not (tmp_path / "nodes").exists()


def test_failed_exclusive_create_removes_partial_json(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    definition = _definition(settings)
    operation = get_operation(settings, "siril", "1.4.4", "autostretch")
    target = tmp_path / "nodes" / f"{definition.definition_id}.json"
    original_open = type(target).open

    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return self.stream.__exit__(exc_type, exc_value, traceback)

        def write(self, value):
            self.stream.write(value[:8])
            self.stream.flush()
            raise OSError("disk full")

    def failing_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return PartialWriter(stream) if path == target else stream

    monkeypatch.setattr(type(target), "open", failing_open)
    with pytest.raises(OSError, match="disk full"):
        public.create_definition(tmp_path, definition, operation)
    assert not target.exists()
    assert public.list_definitions(tmp_path) == []


def test_preview_and_update_preserve_only_same_name_type_ports(tmp_path):
    definition_id = uuid4()
    operation = get_operation(_settings(tmp_path), "siril", "1.4.4", "autostretch").model_copy(update={
        "inputs": [
            SoftwareInputDefinition(name="first", type="IMAGE_A", formats=["fits"], cardinality="one", required=True, supports_hdu=None, supports_slice=None),
            SoftwareInputDefinition(name="second", type="IMAGE_B", formats=["fits"], cardinality="one", required=True, supports_hdu=None, supports_slice=None),
        ],
        "outputs": [
            SoftwareOutputDefinition(name="first", type="IMAGE_A", formats=["fits"], cardinality="one"),
            SoftwareOutputDefinition(name="second", type="IMAGE_B", formats=["fits"], cardinality="one"),
        ],
        "parameters": [
            ParameterDefinition(name="zero", kind="int", default=0),
            ParameterDefinition(name="nullable", kind="string", default=None, nullable=True),
        ],
    })
    updated_operation = operation.model_copy(update={"outputs": [
        SoftwareOutputDefinition(name="first", type="IMAGE_A", formats=["fits"], cardinality="one"),
        SoftwareOutputDefinition(name="second", type="IMAGE_C", formats=["fits"], cardinality="one"),
        SoftwareOutputDefinition(name="third", type="IMAGE_Z", formats=["fits"], cardinality="one"),
    ]})
    before = NodeDefinition.model_validate({
        "definition_id": definition_id, "source": "custom", "name": "Two ports", "description": "",
        "inputs": [{"name": "a", "type": "IMAGE_A"}, {"name": "b", "type": "IMAGE_B"}],
        "outputs": [{"name": "x", "type": "IMAGE_A"}, {"name": "y", "type": "IMAGE_B"}],
        "parameters": [
            {"name": "zero", "kind": "int", "default": 0},
            {"name": "nullable", "kind": "string", "default": None, "nullable": True},
        ],
        "execution": {
            "package_id": "siril", "operation_id": "autostretch",
            "inputs": {"first": "a", "second": "b"}, "outputs": {"x": "first", "y": "second"},
            "parameters": {"zero": {"kind": "parameter", "name": "zero"},
                           "nullable": {"kind": "parameter", "name": "nullable"}},
        },
    })
    saved = public.create_definition(tmp_path, before, operation)
    after = before.model_copy(update={
        "inputs": [before.inputs[1], before.inputs[0]],
        "outputs": [before.outputs[0], NodePort(name="y", type="IMAGE_C") , NodePort(name="z", type="IMAGE_Z")],
        "execution": before.execution.model_copy(update={"outputs": {"x": "first", "y": "second", "z": "third"}}),
    })
    change = public.preview_definition_update(tmp_path, after, saved.content_token, updated_operation)
    assert [(item.name, item.before_index, item.after_index) for item in change.input_remap] == [("a", 0, 1), ("b", 1, 0)]
    assert [(item.name, item.before_index, item.after_index) for item in change.output_remap] == [("x", 0, 0)]
    assert change.disconnected_outputs == ["y"]
    assert change.parameter_defaults == {"zero": 0, "nullable": None}
    updated = public.update_definition(tmp_path, change)
    assert updated.definition.inputs == after.inputs
    assert updated.native_type == saved.native_type
    assert public.get_definition(tmp_path, definition_id) == updated


def test_update_rejects_stale_content_token(tmp_path):
    settings = _settings(tmp_path)
    operation = get_operation(settings, "siril", "1.4.4", "autostretch")
    saved = public.create_definition(tmp_path, _definition(settings), operation)
    changed = saved.definition.model_copy(update={"name": "Changed"})
    with pytest.raises(ApiError) as conflict:
        public.preview_definition_update(tmp_path, changed, "stale", operation)
    assert conflict.value.status_code == 409


def test_update_rechecks_token_before_replacement(tmp_path):
    settings = _settings(tmp_path)
    operation = get_operation(settings, "siril", "1.4.4", "autostretch")
    saved = public.create_definition(tmp_path, _definition(settings), operation)
    first = saved.definition.model_copy(update={"name": "First update"})
    second = saved.definition.model_copy(update={"description": "Competing update"})
    first_change = public.preview_definition_update(tmp_path, first, saved.content_token, operation)
    second_change = public.preview_definition_update(tmp_path, second, saved.content_token, operation)
    public.update_definition(tmp_path, first_change)
    with pytest.raises(ApiError) as conflict:
        public.update_definition(tmp_path, second_change)
    assert conflict.value.status_code == 409


def test_package_replacement_checks_complete_tokens_and_keeps_custom(tmp_path):
    settings = _settings(tmp_path)
    bundled = _definition(settings, source="package")
    created = public.replace_package_definitions(tmp_path, "siril", [bundled], {})
    assert created[0].action == "create" and created[0].applied
    custom = public.create_definition(tmp_path, _definition(settings, name="Custom"), get_operation(settings, "siril", "1.4.4", "autostretch"))
    with pytest.raises(ApiError) as conflict:
        public.replace_package_definitions(tmp_path, "siril", [], {})
    assert conflict.value.status_code == 409
    removed = public.replace_package_definitions(tmp_path, "siril", [], {bundled.definition_id: created[0].content.content_token})
    assert removed[0].action == "remove" and removed[0].content is None
    assert [item.definition.definition_id for item in public.list_definitions(tmp_path)] == [custom.definition.definition_id]


def test_package_replacement_stops_at_first_failed_file_without_rollback(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    first = _definition(settings, source="package", name="First")
    second = _definition(settings, source="package", name="Second")
    from astrophotoflow.modules.nodes import definitions
    original = definitions.write_definition
    calls = 0

    def fail_second(path, definition, *, exclusive):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return original(path, definition, exclusive=exclusive)

    monkeypatch.setattr(definitions, "write_definition", fail_second)
    results = public.replace_package_definitions(tmp_path, "siril", [first, second], {})
    assert len(results) == 2
    assert results[0].applied is True
    assert results[1].applied is False
    assert results[1].error.code == "FILE_WRITE_FAILED"
    assert [item.definition.name for item in public.list_definitions(tmp_path)] == [results[0].content.definition.name]


def test_corrupt_definition_fails_list_instead_of_being_skipped(tmp_path):
    directory = tmp_path / "nodes"
    directory.mkdir()
    (directory / f"{uuid4()}.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        public.list_definitions(tmp_path)

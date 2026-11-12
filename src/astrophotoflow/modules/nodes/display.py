"""Resolve operation display bindings into node-owned display fields."""
from astrophotoflow.contracts.localization import CapabilityDisplay, DisplayLabel
from astrophotoflow.contracts.nodes import NodeDefinition


def node_displays(definition: NodeDefinition, operation_displays: dict) -> dict:
    result = {}
    for locale in ('en', 'zh'):
        source = operation_displays.get(locale, {})
        package = definition.source == 'package'
        display = {
            'name': source.get('name', definition.name) if package else definition.name,
            'description': source.get('description', definition.description) if package else definition.description,
            'help': source.get('help', definition.description),
            'category': source.get('category', definition.category) if package else definition.category,
        }
        override = definition.localizations.get(locale)
        overrides = override.model_dump(exclude_unset=True) if override else {}
        for section in ('inputs', 'outputs', 'parameters'):
            labels = {}
            bindings = getattr(definition.execution, section)
            for field in getattr(definition, section):
                if section == 'parameters':
                    originals = [name for name, binding in bindings.items()
                                 if binding.kind == 'parameter' and binding.name == field.name]
                elif section == 'outputs':
                    originals = [bindings[field.name]] if field.name in bindings else []
                else:
                    originals = [name for name, target in bindings.items() if target == field.name]
                candidates = [source.get(section, {}).get(name) for name in originals]
                label = DisplayLabel(label=field.name).model_dump()
                if candidates and candidates[0] is not None and all(value == candidates[0] for value in candidates):
                    label.update(candidates[0])
                label.update(overrides.get(section, {}).get(field.name, {}))
                labels[field.name] = label
            display[section] = labels
        display.update({name: value for name, value in overrides.items()
                        if name not in ('inputs', 'outputs', 'parameters')})
        result[locale] = CapabilityDisplay.model_validate(display)
    return result

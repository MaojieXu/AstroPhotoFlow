"""Calibration facts for successfully checked outputs, independent of bindings."""

from astrophotoflow.contracts.calibration_status import CalibrationState


def _input_fact(item) -> dict:
    return {
        'asset_id': str(item.asset_id) if item.kind == 'asset' else None,
        'locator': item.locator.model_dump(mode='json') if item.kind == 'run_output' else None,
        'content_hash': item.content_hash, 'reference_index': item.reference_index,
        'member_index': item.member_index if item.kind == 'asset' else None,
        'calibration_status': item.calibration_status,
    }


def checked_output_calibration(effect, inputs, *, output_name, position, output_count, call, parameters) -> tuple[CalibrationState, object | None]:
    primary = inputs.get(effect.input, []) if effect.input else []
    source = primary[position] if len(primary) == output_count else None
    selected = [source] if source is not None else primary
    masters = {purpose: [_input_fact(item) for item in inputs.get(port, [])]
               for purpose, port in effect.masters.items() if inputs.get(port)}
    status = 'Unknown'
    behavior = effect.behavior if output_name in effect.outputs else 'unknown'
    if behavior == 'preserve' and selected:
        states = {item.calibration_status for item in selected}
        status = next(iter(states)) if len(states) == 1 else 'Unknown'
    elif behavior == 'calibrate' and selected and (masters or effect.parameter_calibrations):
        status = 'Calibrated'
    evidence = {
        'source': 'platform', 'behavior': behavior, 'call': call, 'calibration_status': status,
        'inputs': [_input_fact(item) for item in selected],
        'applied_masters': masters if behavior == 'calibrate' else {},
        'applied_parameters': effect.parameter_calibrations if behavior == 'calibrate' else {},
        'parameters': parameters,
    }
    return CalibrationState(calibration_status=status, calibration_evidence=evidence), source


def calibration_metadata(state, source=None) -> dict:
    metadata = state.model_dump(mode='json')
    if state.calibration_evidence.get('source') == 'platform':
        metadata['processing_calibration'] = state.calibration_evidence
    if source is not None and source.kind == 'run_output':
        source = source.source_input
    if source is not None:
        metadata.update(
            parameters=source.parameters, equipment_snapshot=source.equipment_snapshot, value_sources=source.value_sources,
            classification=source.classification.model_dump(mode='json') if source.classification else None,
        )
    return metadata

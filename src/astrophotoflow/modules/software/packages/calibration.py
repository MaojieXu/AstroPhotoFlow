"""Explicit calibration semantics for reviewed Siril command definitions."""

from astrophotoflow.contracts.calibration_status import CalibrationEffect


def declared_calibration_effect(operation) -> CalibrationEffect:
    if operation.package_id != 'siril' or operation.version != '1.4.4':
        return CalibrationEffect()
    inputs = {port.name for port in operation.inputs if port.type == 'APF_SCIENCE'}
    outputs = {port.name for port in operation.outputs if port.type == 'APF_SCIENCE'}
    if operation.operation_id == 'autostretch' and 'image' in inputs and 'image' in outputs:
        return CalibrationEffect(behavior='preserve', input='image', outputs=['image'])
    if operation.operation_id in {'calibrate', 'calibrate_single'} and {'image', 'bias', 'dark', 'flat'} <= inputs and 'image' in outputs:
        return CalibrationEffect(behavior='calibrate', input='image', outputs=['image'],
                                 masters={'bias': 'bias', 'dark': 'dark', 'flat': 'flat'})
    return CalibrationEffect()


def effective_calibration_effect(operation, parameters) -> CalibrationEffect:
    effect = operation.calibration_effect
    if operation.package_id == 'siril' and operation.version == '1.4.4' and operation.operation_id in {'calibrate', 'calibrate_single'}:
        # Siril consumes the bias image only in the explicitly selected image mode.
        masters = dict(effect.masters)
        if parameters.get('bias_mode') != 'image':
            masters.pop('bias', None)
        applied = {}
        if parameters.get('bias_mode') == 'expression' and parameters.get('bias_expression'):
            applied['bias_expression'] = parameters['bias_expression']
        return effect.model_copy(update={'masters': masters, 'parameter_calibrations': applied})
    return effect

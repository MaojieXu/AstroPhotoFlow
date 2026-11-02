import type InlineField from '../components/InlineField.vue'
import type ParameterModeField from '../equipment/ParameterModeField.vue'

type InlineProps = InstanceType<typeof InlineField>['$props']
export type AssetDetailField = 'name' | 'frame_class' | 'frame_type' | 'camera_id' | 'optical_system_id' | 'filter_id' | 'exposure_seconds' | 'integration_seconds' | 'sensor_temperature_c' | 'cfa_pattern' | 'status' | 'notes'
export type AssetDetailBindings = Record<AssetDetailField, InlineProps['save']> & {
  parameters: InstanceType<typeof ParameterModeField>['$props']['save']
  binning: InlineProps['save']
}
export type EquipmentDetailControls = Record<'camera_id' | 'optical_system_id' | 'filter_id', {
  display: string
  choices: NonNullable<InlineProps['choices']>
  message: string
}>
export type BinningDetailControl = { value: string; display: string; choices: NonNullable<InlineProps['choices']> }

<script setup lang="ts">
import { computed } from 'vue'
import type { AssetOut } from '../../../generated/api/types.gen'
import type { AssetDetailBindings, AssetDetailField, EquipmentDetailControls, BinningDetailControl } from './detailTypes'
import InlineField from '../components/InlineField.vue'
import ParameterModeField from '../equipment/ParameterModeField.vue'
import { displayLabel, parameterSummary } from '../library/presentation'
import { cfaChoices, cfaLabel } from '../equipment/fields'

defineProps<{
  asset: AssetOut
  recordId: string
  title: string
  bindings: AssetDetailBindings
  equipment: EquipmentDetailControls
  binning: BinningDetailControl
  temperatureDisplay: string
}>()
const emit = defineEmits<{ 'cancel-field': [field: AssetDetailField | 'parameter_mode' | 'binning', recordId: string] }>()
const frameClasses = ['subframe', 'masterframe', 'video']
const frameTypes = ['light', 'bias', 'dark', 'flat', 'dark_flat']
const equipmentFields = computed(() => [
  { key: 'camera_id' as const, kind: 'camera' }, { key: 'optical_system_id' as const, kind: 'optical_system' }, { key: 'filter_id' as const, kind: 'filter' }
])
</script>
<template>
  <div class="apf-detail-fields">
    <label>{{ $t('apfUi.name') }}<InlineField :value="title" :save="bindings.name" @cancelled="emit('cancel-field','name',recordId)" /></label>
    <label>{{ $t('apfUi.asset_form') }}<InlineField :value="asset.classification.frame_class??''" :display="displayLabel(asset.classification.frame_class)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...frameClasses.map(value=>({value,label:displayLabel(value)}))]" :save="bindings.frame_class" @cancelled="emit('cancel-field','frame_class',recordId)" /></label>
    <label v-if="asset.classification.frame_class!=='video'">{{ $t('apfUi.frame_use') }}<InlineField :value="asset.classification.frame_type??''" :display="displayLabel(asset.classification.frame_type)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...frameTypes.map(value=>({value,label:displayLabel(value)}))]" :save="bindings.frame_type" @cancelled="emit('cancel-field','frame_type',recordId)" /></label>
    <label>ISO／Gain<ParameterModeField :value="{parameter_mode:asset.parameters.parameter_mode,iso:asset.parameters.iso,gain:asset.parameters.gain,offset:asset.parameters.offset}" :display="parameterSummary(asset.parameters)" unset-mode="standard" :save="bindings.parameters" @cancelled="emit('cancel-field','parameter_mode',recordId)" /></label>
    <label v-for="field in equipmentFields" :key="field.key">{{field.kind==='camera'?$t('apfUi.camera_dacf07'):field.kind==='filter'?$t('apfUi.filter'):$t('apfUi.imaging_system')}}<InlineField :value="asset.parameters[field.key]??''" :display="equipment[field.key].display" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...equipment[field.key].choices]" :choices-message="equipment[field.key].message" :save="bindings[field.key]" @cancelled="emit('cancel-field',field.key,recordId)" /></label>
    <label v-if="asset.equipment_snapshot.mount_id">{{ $t('apfUi.mount') }}<output>{{asset.equipment_snapshot.mount_id.name}}</output></label>
    <label>{{ $t('apfUi.exposure_per_frame_seconds') }}<InlineField :value="asset.parameters.exposure_seconds" kind="number" :save="bindings.exposure_seconds" @cancelled="emit('cancel-field','exposure_seconds',recordId)" /></label>
    <label>{{ $t('apfUi.total_exposure_seconds') }}<InlineField :value="asset.parameters.integration_seconds" kind="number" :save="bindings.integration_seconds" @cancelled="emit('cancel-field','integration_seconds',recordId)" /></label>
    <label>{{ $t('apfUi.temperature_c') }}<InlineField :value="asset.parameters.sensor_temperature_c" :display="temperatureDisplay" kind="number" :save="bindings.sensor_temperature_c" @cancelled="emit('cancel-field','sensor_temperature_c',recordId)" /></label>
    <label>Bin<InlineField :value="binning.value" :display="binning.display" kind="select" :choices="binning.choices" :save="bindings.binning" @cancelled="emit('cancel-field','binning',recordId)" /></label>
    <label>{{ $t('apfUi.cfa_pattern') }}<InlineField :value="asset.parameters.cfa_pattern??''" :display="cfaLabel(asset.parameters.cfa_pattern)" kind="select" :choices="cfaChoices" :save="bindings.cfa_pattern" @cancelled="emit('cancel-field','cfa_pattern',recordId)" /></label>
    <label>{{ $t('apfUi.status') }}<InlineField :value="asset.status" :display="displayLabel(asset.status)" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="bindings.status" @cancelled="emit('cancel-field','status',recordId)" /></label>
    <label>{{ $t('apfUi.notes') }}<InlineField :value="asset.notes" kind="textarea" :save="bindings.notes" @cancelled="emit('cancel-field','notes',recordId)" /></label>
  </div>
</template>

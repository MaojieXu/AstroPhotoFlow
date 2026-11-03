<script setup lang="ts">
import {computed} from 'vue'
import LibraryInfo from '../components/LibraryInfo.vue'
import type {CalibrationBinding,CalibrationTarget,CalibrationTargetOption} from '../api/contracts'
const props=defineProps<{modelValue:CalibrationBinding;frameType:string;targets:CalibrationTargetOption[];inherit?:boolean;disabled?:boolean;label:string}>()
const emit=defineEmits<{'update:modelValue':[value:CalibrationBinding]}>()
const token=(value:CalibrationTarget)=>value.kind+':'+value.id
const value=computed(()=>props.modelValue===undefined?'inherit':props.modelValue===null?'none':'mode' in props.modelValue?'unconfigured':token(props.modelValue))
const choices=computed(()=>props.targets.filter(target=>target.frame_type===props.frameType))
const historical=computed(()=>props.modelValue!=null&&'kind' in props.modelValue&&!choices.value.some(item=>token(item.target)===value.value))
function changed(event:Event){
  if(!(event.target instanceof HTMLSelectElement))return
  const selected=event.target.value
  if(selected==='inherit')emit('update:modelValue',undefined)
  else if(selected==='none')emit('update:modelValue',null)
  else if(selected==='unconfigured')emit('update:modelValue',{mode:'unconfigured'})
  else {const target=choices.value.find(item=>token(item.target)===selected);if(target)emit('update:modelValue',target.target)}
}
</script>
<template>
  <span class="apf-binding-select"><select :aria-label="label" :value="value" :disabled="disabled" @change="changed">
    <option value="inherit">{{inherit?$t('apfUi.inherit_group_default'):$t('apfUi.no_default_set')}}</option>
    <option value="none">{{ $t('apfUi.do_not_use') }}</option>
    <option value="unconfigured">{{ $t('apfUi.calibration_unconfigured') }}</option>
    <option v-if="historical" :value="value">{{ $t('apfUi.pinned_historical_version') }}</option>
    <option v-for="target in choices" :key="token(target.target)" :value="token(target.target)">{{target.name}} · {{target.target.kind==='asset_version'?'Master':$t('apfUi.calibration_group')}} v{{target.version_number}}</option>
  </select><LibraryInfo v-if="modelValue&&'kind' in modelValue" :label="label+$t('apfUi.fixed_reference')" :text="modelValue.id" /></span>
</template>

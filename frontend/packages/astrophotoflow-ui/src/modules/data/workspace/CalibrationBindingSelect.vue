<script setup lang="ts">
import {computed} from 'vue'
import LibraryInfo from './LibraryInfo.vue'
import type {CalibrationTarget,CalibrationTargetOption} from '../api/contracts'
const props=defineProps<{modelValue:CalibrationTarget|null|undefined;frameType:string;targets:CalibrationTargetOption[];inherit?:boolean;disabled?:boolean;label:string}>()
const emit=defineEmits<{'update:modelValue':[value:CalibrationTarget|null|undefined]}>()
const token=(value:CalibrationTarget)=>value.kind+':'+value.id
const value=computed(()=>props.modelValue===undefined?'inherit':props.modelValue===null?'none':token(props.modelValue))
const choices=computed(()=>props.targets.filter(target=>target.frame_type===props.frameType))
const historical=computed(()=>props.modelValue!=null&&!choices.value.some(item=>token(item.target)===value.value))
function changed(event:Event){
  const selected=(event.target as HTMLSelectElement).value
  if(selected==='inherit')emit('update:modelValue',undefined)
  else if(selected==='none')emit('update:modelValue',null)
  else {const [kind,id]=selected.split(':');emit('update:modelValue',{kind:kind as CalibrationTarget['kind'],id})}
}
</script>
<template>
  <span class="apf-binding-select"><select :aria-label="label" :value="value" :disabled="disabled" @change="changed">
    <option value="inherit">{{inherit?'继承组默认':'未设置默认值'}}</option>
    <option value="none">不使用</option>
    <option v-if="historical" :value="value">已固定的历史版本</option>
    <option v-for="target in choices" :key="token(target.target)" :value="token(target.target)">{{target.name}} · {{target.target.kind==='asset_version'?'Master':'校准组'}} v{{target.version_number}}</option>
  </select><LibraryInfo v-if="modelValue" :label="label+'固定引用'" :text="modelValue.id" /></span>
</template>

<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { onMounted, ref } from 'vue'
import { ApiClientError } from '../api/client'
import { assetApi } from '../api/index'
import { assetSchema, equipmentSchema, pageSchema, type Asset } from '../api/contracts'

const props=defineProps<{asset:Asset}>()
const emit=defineEmits<{close:[];saved:[asset:Asset]}>()
const draft=ref(JSON.parse(JSON.stringify(props.asset)) as Asset)
const equipment=ref<Array<Record<string,any>>>([])
const saving=ref(false)
const error=ref('')
function nullableNumber(value:unknown){if(value===''||value==null)return null;const n=Number(value);return Number.isFinite(n)?n:null}
function pagePath(path:string,offset:number){
  const query=new URLSearchParams({limit:'200',offset:String(offset),sort_by:'name',order:'asc',status:'all'})
  return '/astrophotoflow/api/v1'+path+'?'+query.toString()
}
async function loadEquipment(){
  const rows:Array<Record<string,any>>=[]
  for(let offset=0;;offset+=200){
    const page=await assetApi.get(pagePath('/equipment',offset),pageSchema(equipmentSchema))
    rows.push(...page.items)
    if(offset+page.limit>=page.total)break
  }
  equipment.value=rows
}
function paramsPayload(){
  const p=draft.value.parameters as Record<string,unknown>
  return {
    camera_id:p.camera_id||null,optical_system_id:p.optical_system_id||null,filter_id:p.filter_id||null,
    parameter_mode:p.parameter_mode||'standard',iso:nullableNumber(p.iso),gain:nullableNumber(p.gain),
    offset:nullableNumber(p.offset),exposure_seconds:nullableNumber(p.exposure_seconds),
    integration_seconds:nullableNumber(p.integration_seconds),sensor_temperature_c:nullableNumber(p.sensor_temperature_c),
    binning_x:nullableNumber(p.binning_x),binning_y:nullableNumber(p.binning_y),
    cfa_pattern:p.cfa_pattern||null
  }
}
function classificationPatch(){
  const current=draft.value.classification as Record<string,unknown>|null
  const original=props.asset.classification as Record<string,unknown>|null
  if(!current||!original)return current
  return Object.fromEntries(Object.entries(current).filter(([key,value])=>value!==original[key]))
}
function parametersPatch(){
  const current=paramsPayload()
  const original=props.asset.parameters as Record<string,unknown>
  return Object.fromEntries(Object.entries(current).filter(([key,value])=>value!==original[key]))
}
function changeFrameClass(){
  const classification=draft.value.classification
  if(classification?.frame_class==='video')classification.frame_type=null
  else if(classification?.frame_type==null&&classification)classification.frame_type='light'
}
async function save(){
  saving.value=true;error.value=''
  try{
    const changes:Record<string,unknown>={
      base_revision:draft.value.revision,name:draft.value.name,notes:draft.value.notes,status:draft.value.status
    }
    const classification=classificationPatch()
    const parameters=parametersPatch()
    if(classification&&Object.keys(classification).length)changes.classification=classification
    if(Object.keys(parameters).length)changes.parameters=parameters
    const current=await assetApi.send(
      '/astrophotoflow/api/v1/library/assets/'+props.asset.id,assetSchema,'PATCH',{
        ...changes
      }
    )
    emit('saved',current)
  }catch(cause){
    error.value=cause instanceof ApiClientError?cause.message:uiT('apfUi.request_failed')
  }finally{saving.value=false}
}
onMounted(()=>{void loadEquipment().catch(cause=>{error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_read_the_equipment_list')})})
</script>

<template>
  <section class="apf-editor" :aria-label="$t('apfUi.edit_asset_metadata')">
    <form @submit.prevent="save">
      <h2>{{ $t('apfUi.edit_asset_metadata') }}</h2>
      <label>{{ $t('apfUi.name') }}<input v-model="draft.name" required /></label>
      <label>{{ $t('apfUi.asset_role') }}<select v-model="draft.role" disabled><option value="raw">{{ $t('apfUi.raw_asset') }}</option><option value="calibration">{{ $t('apfUi.calibration_asset') }}</option></select><small>{{ $t('apfUi.derived_automatically_from_frame_use') }}</small></label>
      <label>{{ $t('apfUi.asset_form') }}<select v-model="draft.classification!.frame_class" @change="changeFrameClass">
        <option value="subframe">Subframe</option><option value="masterframe">Masterframe</option><option value="video">Video</option>
      </select></label>
      <label v-if="draft.classification?.frame_class!=='video'">{{ $t('apfUi.frame_use') }}<select v-model="draft.classification!.frame_type">
        <option value="light">Light</option><option value="bias">Bias</option><option value="dark">Dark</option><option value="flat">Flat</option><option value="dark_flat">Dark Flat</option>
      </select></label>
      <label>{{ $t('apfUi.parameter_input_mode') }}<select v-model="draft.parameters.parameter_mode">
        <option value="standard">{{ $t('apfUi.general') }}</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option>
      </select></label>
      <label>{{ $t('apfUi.camera_dacf07') }}<select v-model="draft.parameters.camera_id"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="item in equipment.filter(x=>x.kind==='camera')" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
      <label v-if="['light','flat'].includes(draft.classification?.frame_type||'')">{{ $t('apfUi.imaging_system') }}<select v-model="draft.parameters.optical_system_id"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="item in equipment.filter(x=>x.kind==='optical_system')" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
      <label v-if="['light','flat'].includes(draft.classification?.frame_type||'')">{{ $t('apfUi.filter') }}<select v-model="draft.parameters.filter_id"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="item in equipment.filter(x=>x.kind==='filter')" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
      <label v-for="field in [
        {key:'iso',label:'ISO',step:'1'}, {key:'gain',label:'Gain',step:'any'}, {key:'offset',label:'Offset',step:'any'},
        {key:'exposure_seconds',label:$t('apfUi.exposure_per_frame_seconds'),step:'any'}, {key:'integration_seconds',label:$t('apfUi.total_exposure_seconds'),step:'any'},
        {key:'sensor_temperature_c',label:$t('apfUi.measured_sensor_temperature_c'),step:'any'},
        {key:'binning_x',label:$t('apfUi.horizontal_binning'),step:'1'}, {key:'binning_y',label:$t('apfUi.vertical_binning'),step:'1'}
      ]" :key="field.key">{{field.label}}<input v-model="draft.parameters[field.key]" type="number" :step="field.step" /></label>
      <label>{{ $t('apfUi.cfa_pattern') }}<select v-model="draft.parameters.cfa_pattern"><option value="">{{ $t('apfUi.not_specified') }}</option><option>RGGB</option><option>BGGR</option><option>GRBG</option><option>GBRG</option></select></label>
      <label>{{ $t('apfUi.multiline_notes') }}<textarea v-model="draft.notes" rows="4" /></label>
      <label>{{ $t('apfUi.status') }}<select v-model="draft.status"><option value="active">{{ $t('apfUi.active') }}</option><option value="archived">{{ $t('apfUi.archive') }}</option></select></label>
      <p v-if="error" class="apf-error" role="alert">{{error}}</p>
      <footer class="apf-form-actions"><button type="button" @click="emit('close')">{{ $t('apfUi.cancel') }}</button><button type="submit" :disabled="saving">{{saving?$t('apfUi.saving'):$t('apfUi.save')}}</button></footer>
    </form>
  </section>
</template>

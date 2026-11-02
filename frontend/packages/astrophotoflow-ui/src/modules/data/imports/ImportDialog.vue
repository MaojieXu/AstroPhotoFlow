<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useSubmitImport } from './mutations'
import { validatedInput } from '../../../core/api/input'
import { zCreateImportApiV1ImportsPostBody } from '../../../generated/api/zod.gen'
import { ApiClientError } from '../api/client'
import type { LocalImportFile } from '../api/contracts'
import CapturePresetPicker from '../equipment/CapturePresetPicker.vue'
import { useEquipmentChoices } from '../equipment/queries'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryInput from '../components/LibraryInput.vue'
import LibraryTextField from '../components/LibraryTextField.vue'

type Field = { key: string; title: string; integer?: boolean; positive?: boolean; nonnegative?: boolean }

const props = defineProps<{ workspaceId: string; open: boolean; files: LocalImportFile[]; createDataset?: boolean; datasetName?: string }>()
const emit = defineEmits<{ close: []; submitted: [taskId: string] }>()
const submission=useSubmitImport()
const submitting=submission.isPending
let inFlight=false
let dialogSession={}
onBeforeUnmount(()=>{dialogSession={}})
const error = ref('')
const datasetName = ref('')
const notes = ref('')
const capturePresetId = ref('')
const manualClassification = ref(false)
const frameClass = ref<'subframe'|'masterframe'|'video'|''>('')
const frameType = ref<'light'|'bias'|'dark'|'flat'|'dark_flat'|''>('')
const parameterMode = ref<'iso'|'gain'|''>('')
const parameters = ref<Record<string,string>>({
  camera_id:'', optical_system_id:'', filter_id:'', iso:'', gain:'', offset:'',
  exposure_seconds:'', integration_seconds:'', sensor_temperature_c:'',
  binning:'', cfa_pattern:''
})
const equipmentQuery=useEquipmentChoices(()=>props.open?props.workspaceId:'')
const equipment=computed(()=>equipmentQuery.data.value??[])
const equipmentError=computed(()=>equipmentQuery.error.value?clientError(equipmentQuery.error.value):'')
const fields: Field[] = [
  {key:'exposure_seconds',get title() { return uiT('apfUi.exposure_per_frame_seconds') },nonnegative:true},
  {key:'integration_seconds',get title() { return uiT('apfUi.total_exposure_seconds') },nonnegative:true},
  {key:'sensor_temperature_c',get title() { return uiT('apfUi.measured_sensor_temperature_c') }}
]
const isDataset = computed(() => Boolean(props.createDataset) || props.files.length > 1)
const cameraOptions = computed(() => equipment.value.filter(item => item.kind === 'camera'))
const opticalOptions = computed(() => equipment.value.filter(item => item.kind === 'telescope'))
const filterOptions = computed(() => equipment.value.filter(item => item.kind === 'filter'))
function clientError(cause: unknown) {
  return cause instanceof ApiClientError ? cause.message : uiT('apfUi.request_failed')
}
function fieldValue(field:Field) {
  const value=parameters.value[field.key]
  if(value==='')return null
  const parsed=Number(value)
  return Number.isFinite(parsed)?parsed:null
}
function buildParameters() {
  const ids=['camera_id','optical_system_id','filter_id']
  const params:Record<string,unknown>={}
  for(const key of ids)if(parameters.value[key]!=='')params[key]=parameters.value[key]
  if(parameterMode.value)params.parameter_mode=parameterMode.value
  for(const field of fields)if(parameters.value[field.key]!=='')params[field.key]=fieldValue(field)
  if(parameters.value.iso!=='')params.iso=fieldValue({key:'iso',title:'ISO'})
  if(parameters.value.gain!=='')params.gain=fieldValue({key:'gain',title:'Gain'})
  if(parameters.value.offset!=='')params.offset=fieldValue({key:'offset',title:'Offset'})
  const bin=fieldValue({key:'binning',title:'Bin',integer:true,positive:true})
  if(bin!==null){params.binning_x=bin;params.binning_y=bin}
  if(parameters.value.cfa_pattern)params.cfa_pattern=parameters.value.cfa_pattern
  if(frameClass.value==='video'){
    delete params.exposure_seconds
    delete params.integration_seconds
  } else if(frameClass.value!=='masterframe'){
    delete params.integration_seconds
  }
  return params
}
async function submitImport(){
  if(!props.files.length||inFlight)return
  const currentSession=dialogSession
  const workspaceId=props.workspaceId
  inFlight=true;error.value=''
  try{
    const accepted=await submission.mutateAsync({workspaceId,body:validatedInput(zCreateImportApiV1ImportsPostBody,{
      sources:props.files.map(file=>({...(file.root_id?{root_id:file.root_id}:{}),path:file.path})),
      storage_mode:'managed',
      ...(manualClassification.value?{classification:{frame_class:frameClass.value||null,frame_type:frameClass.value==='video'?null:frameType.value||null}}:{}),
      parameters:buildParameters(),
      ...(capturePresetId.value ? {capture_preset_id:capturePresetId.value} : {}),
      notes:notes.value||null,
      dataset_name:isDataset.value?(datasetName.value||props.datasetName||null):null,
    })})
    if(currentSession!==dialogSession)return
    emit('submitted',accepted.task_id)
  }catch(cause){if(currentSession===dialogSession)error.value=clientError(cause)}
  finally{inFlight=false}
}
watch([()=>props.workspaceId,()=>props.open,()=>props.files],()=>{dialogSession={};if(props.open){
  error.value='';datasetName.value=props.datasetName??'';notes.value='';manualClassification.value=false;frameClass.value='';frameType.value='';parameterMode.value=''
  parameters.value={camera_id:'',optical_system_id:'',filter_id:'',iso:'',gain:'',offset:'',exposure_seconds:'',integration_seconds:'',sensor_temperature_c:'',binning:'',cfa_pattern:''}
  capturePresetId.value=''
}})
</script>

<template>
  <div v-if="open" class="apf-import-overlay" role="dialog" aria-modal="true" :aria-label="$t('apfUi.import_astronomy_assets')">
    <section class="apf-import-dialog">
      <header><h2>{{ $t('apfUi.confirm_asset_details') }}</h2><LibraryButton type="button" @click="emit('close')">{{ $t('apfUi.close') }}</LibraryButton></header>
      <p v-if="equipmentError" role="alert">{{equipmentError}}</p>
    <form @submit.prevent="submitImport">
        <p>{{ $t('apfUi.selected_files_value', { p0: (files.length) }) }}<LibraryInfo :label="$t('apfUi.selected_files')" :text="files.map(file=>file.root_id?file.root_id+':/'+file.path:file.path).join('\n')" /></p>
        <p class="apf-optional-note">{{ $t('apfUi.local_files_will_be_copied_into_the_workbench_data_directory_as_manage') }}</p>
        <p class="apf-optional-note">{{ $t('apfUi.value_mib_files_selected_for_this_import_only', { p0: ((files.reduce((sum,file)=>sum+file.size,0)/1024/1024).toFixed(1)) }) }}</p>
        <CapturePresetPicker :workspace-id="workspaceId" v-model="capturePresetId" :disabled="submitting" />
        <LibraryTextField v-if="isDataset" id="import-dataset-name" v-model="datasetName" :name="$t('apfUi.image_group_name_optional')" :hint="$t('apfUi.leave_blank_to_use_the_source_name')" />
        <label><span><input v-model="manualClassification" type="checkbox" />{{ $t('apfUi.set_classification_for_the_whole_batch') }}<LibraryInfo :label="$t('apfUi.batch_classification')" :text="$t('apfUi.classify_each_file_using_its_capture_metadata_by_default_retain_unknow')" /></span></label><small v-if="!manualClassification">{{ $t('apfUi.read_capture_metadata_from_each_file') }}</small>
        <label v-if="manualClassification">{{ $t('apfUi.asset_form') }}<select v-model="frameClass"><option value="">{{ $t('apfUi.not_specified') }}</option><option value="subframe">{{ $t('apfUi.subframe') }}</option><option value="masterframe">{{ $t('apfUi.master_frame') }}</option><option value="video">{{ $t('apfUi.video') }}</option></select></label>
        <label v-if="manualClassification&&frameClass!==''&&frameClass!=='video'">{{ $t('apfUi.frame_use') }}<select v-model="frameType"><option value="">{{ $t('apfUi.not_specified') }}</option><option value="light">{{ $t('apfUi.light') }}</option><option value="bias">{{ $t('apfUi.bias') }}</option><option value="dark">{{ $t('apfUi.dark') }}</option><option value="flat">{{ $t('apfUi.flat') }}</option><option value="dark_flat">{{ $t('apfUi.dark_flat') }}</option></select></label>
        <label>{{ $t('apfUi.camera_dacf07') }}<select v-model="parameters.camera_id"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="item in cameraOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label v-if="['light','flat'].includes(frameType)">{{ $t('apfUi.imaging_system') }}<select v-model="parameters.optical_system_id"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="item in opticalOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label v-if="['light','flat'].includes(frameType)">{{ $t('apfUi.filter') }}<select v-model="parameters.filter_id"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="item in filterOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label>{{ $t('apfUi.gain_mode') }}<select v-model="parameterMode"><option value="">{{ $t('apfUi.not_specified') }}</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option></select></label>
        <label v-if="parameterMode==='iso'">ISO<LibraryInput v-model="parameters.iso" type="number" step="1" /></label>
        <template v-else-if="parameterMode==='gain'"><label>Gain<LibraryInput v-model="parameters.gain" type="number" step="any" /></label><label>Offset<LibraryInput v-model="parameters.offset" type="number" step="any" /></label></template>
        <label v-for="field in fields" :key="field.key" v-show="field.key!=='integration_seconds'||frameClass==='masterframe'">{{field.title}}<input v-model="parameters[field.key]" type="number" :step="field.integer?'1':'any'" /></label>
        <label>Bin<select v-model="parameters.binning"><option value="">{{ $t('apfUi.not_specified') }}</option><option v-for="value in 16" :key="value" :value="String(value)">Bin{{value}}</option></select></label>
        <label>{{ $t('apfUi.cfa_pattern') }}<select v-model="parameters.cfa_pattern"><option value="">{{ $t('apfUi.not_specified') }}</option><option value="MONO">{{ $t('apfUi.no_cfa_monochrome') }}</option><option value="RGGB">RGGB</option><option value="BGGR">BGGR</option><option value="GRBG">GRBG</option><option value="GBRG">GBRG</option><option value="XTRANS">X-Trans 6×6</option><option value="QUAD_BAYER">Quad Bayer</option></select></label>
        <label>{{isDataset?$t('apfUi.image_group_notes_optional'):$t('apfUi.asset_notes_optional')}}<LibraryInfo v-if="isDataset" :label="$t('apfUi.notes')" :text="$t('apfUi.notes_for_a_multiple_file_import_are_saved_on_the_image_group_members_')" /><textarea v-model="notes" rows="3" /></label>
        <p v-if="error" class="apf-error" role="alert">{{ error }}</p>
        <footer class="apf-import-actions"><LibraryButton type="button" :disabled="submitting" @click="emit('close')">{{ $t('apfUi.cancel') }}</LibraryButton><LibraryButton type="submit" variant="primary" :disabled="submitting">{{submitting?$t('apfUi.creating_batch'):$t('apfUi.start_import')}}</LibraryButton></footer>
      </form>
    </section>
  </div>
</template>

<style scoped>
.apf-import-overlay{position:absolute;inset:0;z-index:5;display:flex;justify-content:center;align-items:center;padding:12px;background:#0009}
.apf-import-dialog{display:flex;flex-direction:column;min-height:0;width:min(760px,100%);max-height:100%;overflow:hidden;padding:16px;background:var(--comfy-menu-bg,#272727);border:1px solid var(--border-color,#555);border-radius:10px;color:var(--input-text,#ddd);box-shadow:0 12px 44px #0008}
.apf-import-dialog header,.apf-import-actions,.apf-import-pages,.apf-import-entry{display:flex;align-items:center;gap:8px}
.apf-import-dialog header{flex:none}.apf-import-dialog header h2{margin-right:auto}.apf-import-dialog form{min-height:0;overflow:auto;padding-right:4px}.apf-import-actions{position:sticky;bottom:0;background:var(--comfy-menu-bg,#272727);padding:12px 0;border-top:1px solid var(--border-color,#555)}.apf-optional-note{color:var(--descrip-text,#999);font-size:12px}
.apf-import-dialog label{display:flex;flex-direction:column;gap:4px;margin:8px 0}
.apf-import-dialog input,.apf-import-dialog select,.apf-import-dialog textarea{min-height:34px;padding:6px 8px;color:var(--input-text,#ddd);background:var(--comfy-input-bg,#202020);border:1px solid var(--border-color,#555);border-radius:6px;font:inherit}
.apf-import-dialog input[type=checkbox]{min-height:auto}
.apf-import-crumbs,.apf-import-pages{display:flex;align-items:center;gap:6px;margin:8px 0}
.apf-import-list{max-height:36vh;overflow:auto;margin-top:10px;border:1px solid var(--border-color,#555);border-radius:6px}
.apf-import-entry{justify-content:space-between;padding:5px 8px;border-bottom:1px solid var(--border-color,#444)}
.apf-import-entry label{display:flex;flex-direction:row;align-items:center;margin:0}.apf-import-entry .disabled{opacity:.55}
.apf-import-entry small{color:var(--descrip-text,#999)}
.apf-import-pages span{margin-right:auto}.apf-import-actions{justify-content:flex-end;margin-top:14px}
.apf-error{color:#ffaaaa}
</style>

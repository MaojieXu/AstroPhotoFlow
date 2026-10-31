<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import {computed,inject,onBeforeUnmount,ref,watch} from 'vue'
import {z} from 'zod'
import {assetApi} from '../api/index'
import {calibrationTargetOptionSchema,datasetSchema,datasetVersionSchema,pageSchema,type CalibrationBindings,type CalibrationTarget,type CalibrationTargetOption} from '../api/contracts'
import type {WorkspaceContext} from './Workspace.vue'
import CalibrationBindingSelect from './CalibrationBindingSelect.vue'
import LibraryInfo from './LibraryInfo.vue'
import LibraryButton from './LibraryButton.vue'
import LibraryTextField from './LibraryTextField.vue'
import { displayLabel } from './presentation'

const props=defineProps<{datasetId:string}>()
const emit=defineEmits<{updated:[dataset:z.infer<typeof datasetSchema>]}>()
const context=inject<WorkspaceContext>('workspace')
const dataset=ref<z.infer<typeof datasetSchema>>()
const version=ref<z.infer<typeof datasetVersionSchema>>()
const versions=ref<z.infer<typeof datasetVersionSchema>[]>([])
const targets=ref<CalibrationTargetOption[]>([])
const defaults=ref<CalibrationBindings>({})
const overrides=ref<Record<string,CalibrationBindings>>({})
const name=ref(''),notes=ref(''),error=ref(''),notice=ref('')
const loading=ref(false),saving=ref(false),opened=ref(false)
const original=ref('')
const frameTypes=['bias','dark','flat','dark_flat'] as const
const current= computed(()=>version.value?.id===dataset.value?.current_version_id)
const state=()=>JSON.stringify({name:name.value,notes:notes.value,defaults:defaults.value,overrides:overrides.value})
const dirty=computed(()=>Boolean(version.value)&&state()!==original.value)
watch(dirty,value=>{if(context)context.calibrationDirty.value=value})
onBeforeUnmount(()=>{if(context)context.calibrationDirty.value=false})
function showVersion(row:z.infer<typeof datasetVersionSchema>){
  version.value=row;defaults.value=JSON.parse(JSON.stringify(row.calibration_defaults))
  overrides.value=Object.fromEntries(row.members.map(member=>[member.asset_version_id,JSON.parse(JSON.stringify(member.calibration_overrides))]))
  original.value=JSON.stringify({name:dataset.value!.name,notes:dataset.value!.notes??'',defaults:defaults.value,overrides:overrides.value})
}
async function load(){
  if(dirty.value&&!window.confirm(uiT('apfUi.reading_again_discards_unsaved_group_descriptions_or_calibration_bindi')))return
  loading.value=true;error.value=''
  try{
    dataset.value=await assetApi.get('/astrophotoflow/api/v1/datasets/'+props.datasetId,datasetSchema)
    const result:z.infer<typeof datasetVersionSchema>[]=[]
    for(let offset=0;;offset+=200){
      const page=await assetApi.get('/astrophotoflow/api/v1/datasets/'+props.datasetId+'/versions?limit=200&offset='+offset,pageSchema(datasetVersionSchema));result.push(...page.items)
      if(offset+page.limit>=page.total)break
    }
    versions.value=result
    targets.value=[]
    for(let offset=0;;offset+=200){
      const page=await assetApi.get('/astrophotoflow/api/v1/calibration/targets?limit=200&offset='+offset,pageSchema(calibrationTargetOptionSchema));targets.value.push(...page.items)
      if(offset+page.limit>=page.total)break
    }
    name.value=dataset.value.name;notes.value=dataset.value.notes??''
    const row=versions.value.find(row=>row.id===dataset.value!.current_version_id)
    if(row)showVersion(row)
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_read_calibration_bindings')}
  finally{loading.value=false}
}
function toggle(event:Event){opened.value=(event.target as HTMLDetailsElement).open;if(opened.value&&!dataset.value)void load()}
function changeVersion(event:Event){
  if(dirty.value&&!window.confirm(uiT('apfUi.calibration_bindings_have_unsaved_changes_discard_them'))){(event.target as HTMLSelectElement).value=version.value!.id;return}
  const row=versions.value.find(row=>row.id===(event.target as HTMLSelectElement).value)
  if(row){name.value=dataset.value!.name;notes.value=dataset.value!.notes??'';showVersion(row)}
}
function setBinding(map:CalibrationBindings,key:typeof frameTypes[number],value:CalibrationTarget|null|undefined){
  if(value===undefined)delete map[key];else map[key]=value
}
async function saveNotes(){
  saving.value=true;error.value='';notice.value=''
  try{
    dataset.value=await assetApi.send('/astrophotoflow/api/v1/datasets/'+props.datasetId,datasetSchema,'PATCH',{base_revision:dataset.value!.revision,name:name.value,notes:notes.value||null})
    original.value=JSON.stringify({...JSON.parse(original.value),name:name.value,notes:notes.value})
    notice.value=uiT('apfUi.group_description_saved');emit('updated',dataset.value)
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_save_the_group_description')}finally{saving.value=false}
}
async function saveBindings(){
  saving.value=true;error.value='';notice.value=''
  try{
    const saved=await assetApi.send('/astrophotoflow/api/v1/datasets/'+props.datasetId+'/versions',datasetVersionSchema,'POST',{
      base_revision:dataset.value!.revision,asset_version_ids:version.value!.members.map(member=>member.asset_version_id),
      calibration_defaults:defaults.value,member_calibration_overrides:overrides.value
    })
    dataset.value=await assetApi.get('/astrophotoflow/api/v1/datasets/'+props.datasetId,datasetSchema)
    versions.value=[saved,...versions.value.filter(row=>row.id!==saved.id)];showVersion(saved)
    notice.value=uiT('apfUi.saved_fixed_version_v')+saved.version_number+uiT('apfUi.calibration_bindings');emit('updated',dataset.value)
  }catch(cause){error.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_save_calibration_bindings')}finally{saving.value=false}
}
</script>
<template>
  <details class="apf-calibration-editor" @toggle="toggle">
    <summary>{{ $t('apfUi.group_description_history_and_calibration_bindings') }}</summary>
    <p v-if="loading" role="status">{{ $t('apfUi.reading_the_full_group_version') }}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}} <LibraryButton type="button" @click="load">{{ $t('apfUi.read_again') }}</LibraryButton></p>
    <template v-if="dataset&&version">
      <LibraryTextField id="calibration-group-name" v-model="name" :name="$t('apfUi.group_name')" :disabled="saving" /><label>{{ $t('apfUi.description') }}<textarea v-model="notes" :disabled="saving" /></label>
      <LibraryButton type="button" :disabled="saving" @click="saveNotes">{{ $t('apfUi.save_group_description') }}</LibraryButton>
      <label><span>{{ $t('apfUi.fixed_group_version') }}<LibraryInfo :label="$t('apfUi.fixed_group_version')" :text="$t('apfUi.current_full_version')+version.id+$t('apfUi.filtering_this_list_does_not_change_the_full_member_selection_calibrat')" /></span><select :value="version.id" :disabled="saving" @change="changeVersion"><option v-for="row in versions" :key="row.id" :value="row.id">v{{row.version_number}}{{row.id===dataset.current_version_id?$t('apfUi.current'):$t('apfUi.read_only_history')}}</option></select></label>
      <p>{{ $t('apfUi.full_group_value_photos_calibration_changes_apply_to_every_member', { p0: (version.members.length) }) }}</p>
      <p v-if="!current">{{ $t('apfUi.historical_versions_are_read_only') }}<LibraryInfo :label="$t('apfUi.historical_versions')" :text="$t('apfUi.previously_selected_project_references_remain_unchanged_the_group_name')" /></p>
      <fieldset :disabled="saving||!current"><legend>{{ $t('apfUi.default_group_calibration') }}<LibraryInfo :label="$t('apfUi.default_group_calibration')" :text="$t('apfUi.members_inherit_group_calibration_by_default_choose_do_not_use_to_disa')" /></legend>
        <label v-for="frameType in frameTypes" :key="frameType">{{displayLabel(frameType)}}<CalibrationBindingSelect :model-value="defaults[frameType]" :frame-type="frameType" :targets="targets" :label="$t('apfUi.group_default')+displayLabel(frameType)" @update:model-value="setBinding(defaults,frameType,$event)" /></label>
      </fieldset>
      <div class="apf-calibration-members"><table><thead><tr><th>{{ $t('apfUi.full_member_list') }}</th><th v-for="frameType in frameTypes" :key="frameType">{{displayLabel(frameType)}}</th></tr></thead><tbody>
        <tr v-for="member in version.members" :key="member.asset_version_id"><th>{{member.asset.name}} · v{{member.version.version_number}}<small>{{displayLabel(member.asset.classification?.frame_type)}}</small></th>
          <td v-for="frameType in frameTypes" :key="frameType"><span>{{displayLabel(frameType)}}</span><CalibrationBindingSelect :model-value="overrides[member.asset_version_id]?.[frameType]" :frame-type="frameType" :targets="targets" inherit :disabled="saving||!current" :label="member.asset.name+' '+displayLabel(frameType)" @update:model-value="setBinding(overrides[member.asset_version_id],frameType,$event)" /></td>
        </tr>
      </tbody></table></div>
      <LibraryButton type="button" :disabled="saving||!current" @click="saveBindings">{{ $t('apfUi.save_calibration_bindings_as_a_new_version') }}</LibraryButton>
      <p v-if="notice" role="status">{{notice}}</p>
    </template>
  </details>
</template>
<style scoped>
.apf-calibration-editor{flex:none;min-width:0;margin:10px;padding:12px;border:1px solid var(--border-color,#555);border-radius:8px}.apf-calibration-editor label{display:flex;flex-direction:column;gap:4px;margin:8px 0}.apf-calibration-editor fieldset{display:flex;gap:12px;flex-wrap:wrap}.apf-calibration-members{overflow:auto;margin:12px 0}.apf-calibration-members table{border-collapse:collapse;width:100%;min-width:0}.apf-calibration-members td,.apf-calibration-members th{padding:6px;text-align:left;border-bottom:1px solid var(--border-color,#555)}.apf-calibration-members thead{display:none}.apf-calibration-members tbody tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px 0;border-bottom:1px solid var(--border-color,#555)}.apf-calibration-members th{grid-column:1/-1}.apf-calibration-members td{min-width:0;border:0}.apf-calibration-members td>span{display:block;margin-bottom:4px;font-size:12px}.apf-calibration-members small{display:block;font-weight:normal}
</style>

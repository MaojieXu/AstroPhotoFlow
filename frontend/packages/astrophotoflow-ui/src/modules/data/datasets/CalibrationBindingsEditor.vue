<script setup lang="ts">
import { uiT } from '../../../core/i18n'
import { computed,nextTick,onBeforeUnmount,ref,shallowRef,watch } from 'vue'
import type { DatasetOut,DatasetVersionOut } from '../../../generated/api/types.gen'
import type { CalibrationBindings,CalibrationTarget } from '../api/contracts'
import { useCalibrationData } from './calibrationQueries'
import { useSaveDatasetDescription,usePublishCalibration } from './mutations'
import CalibrationBindingSelect from '../library/CalibrationBindingSelect.vue'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryTextField from '../components/LibraryTextField.vue'
import { displayLabel } from '../library/presentation'

const props=defineProps<{workspaceId:string;datasetId:string}>()
const emit=defineEmits<{updated:[dataset:DatasetOut];dirty:[value:boolean]}>()
// Explicit editing basis: background responses must not rebase an unsaved draft.
const dataset=shallowRef<DatasetOut>(),version=shallowRef<DatasetVersionOut>()
const defaults=ref<CalibrationBindings>({}),overrides=ref<Record<string,CalibrationBindings>>({})
const name=ref(''),notes=ref(''),actionError=ref(''),notice=ref(''),original=ref('')
const saving=ref(false),opened=ref(false),pendingMetadata=ref(false)
const selectedVersion=ref<string>()
const session=shallowRef({})
const frameTypes=['bias','dark','flat','dark_flat'] as const
const state=()=>JSON.stringify({name:name.value,notes:notes.value,defaults:defaults.value,overrides:overrides.value})
const dirty=computed(()=>Boolean(version.value)&&state()!==original.value)
const current=computed(()=>!pendingMetadata.value&&Boolean(version.value)&&version.value?.id===dataset.value?.current_version_id)
const query=useCalibrationData(()=>({workspaceId:props.workspaceId,datasetId:props.datasetId,versionId:selectedVersion.value}),
  ()=>!opened.value||dirty.value||saving.value||pendingMetadata.value)
const versions=computed(()=>query.data.value?.versions??[]),targets=computed(()=>query.data.value?.targets??[])
const loading=query.isFetching
const error=computed(()=>actionError.value||(query.error.value instanceof Error?query.error.value.message:query.isError.value?uiT('apfUi.could_not_read_calibration_bindings'):''))
const saveDescription=useSaveDatasetDescription(),publishCalibration=usePublishCalibration()
function showVersion(row:DatasetVersionOut){
  version.value=row;defaults.value=JSON.parse(JSON.stringify(row.calibration_defaults))
  overrides.value=Object.fromEntries(row.members.map(member=>[member.asset_version_id,JSON.parse(JSON.stringify(member.calibration_overrides))]))
  original.value=JSON.stringify({name:dataset.value!.name,notes:dataset.value!.notes??'',defaults:defaults.value,overrides:overrides.value})
}
function adopt(data:NonNullable<typeof query.data.value>){
  dataset.value=data.dataset;name.value=data.dataset.name;notes.value=data.dataset.notes??''
  if(data.version)showVersion(data.version)
  else{version.value=undefined;defaults.value={};overrides.value={};original.value=state()}
}
watch([query.data,query.fetchStatus],([data,status])=>{
  if(data&&status==='idle'&&!query.isError.value&&!dirty.value&&!saving.value&&!pendingMetadata.value)adopt(data)
})
watch(dirty,value=>emit('dirty',value))
watch(()=>[props.workspaceId,props.datasetId] as const,()=>{
  session.value={};dataset.value=undefined;version.value=undefined;selectedVersion.value=undefined
  name.value='';notes.value='';defaults.value={};overrides.value={};original.value='';saving.value=false;pendingMetadata.value=false;actionError.value='';notice.value=''
},{flush:'sync'})
onBeforeUnmount(()=>{session.value={};emit('dirty',false)})
async function read(){
  const owner=session.value
  const description=pendingMetadata.value?{name:name.value,notes:notes.value}:undefined
  const result=await query.refetch({cancelRefetch:false})
  if(owner!==session.value||result.isError||!result.data)return
  const verify=pendingMetadata.value
  pendingMetadata.value=false;adopt(result.data)
  if(description){name.value=description.name;notes.value=description.notes}
  if(verify)emit('updated',result.data.dataset)
}
async function load(){
  if(dirty.value&&!pendingMetadata.value&&!window.confirm(uiT('apfUi.reading_again_discards_unsaved_group_descriptions_or_calibration_bindi')))return
  actionError.value='';await read()
}
function toggle(event:Event){opened.value=(event.target as HTMLDetailsElement).open}
async function changeVersion(event:Event){
  if(dirty.value&&!window.confirm(uiT('apfUi.calibration_bindings_have_unsaved_changes_discard_them'))){(event.target as HTMLSelectElement).value=version.value!.id;return}
  selectedVersion.value=(event.target as HTMLSelectElement).value
  actionError.value='';await nextTick();await read()
}
function setBinding(map:CalibrationBindings,key:typeof frameTypes[number],value:CalibrationTarget|null|undefined){
  if(value===undefined)delete map[key];else map[key]=value
}
async function saveNotes(){
  const base=dataset.value,owner=session.value
  if(!base||saving.value||pendingMetadata.value)return
  const body={base_revision:base.revision,name:name.value,notes:notes.value||null}
  saving.value=true;actionError.value='';notice.value=''
  try{
    const updated=await saveDescription.mutateAsync({workspaceId:props.workspaceId,datasetId:base.id,body})
    if(owner!==session.value)return
    dataset.value=updated
    original.value=JSON.stringify({...JSON.parse(original.value),name:body.name,notes:body.notes??''})
    notice.value=uiT('apfUi.group_description_saved');emit('updated',updated)
  }catch(cause){if(owner===session.value)actionError.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_save_the_group_description')}
  finally{if(owner===session.value)saving.value=false}
}
async function saveBindings(){
  const base=dataset.value,pinned=version.value,owner=session.value
  if(!base||!pinned||saving.value||!current.value)return
  saving.value=true;actionError.value='';notice.value=''
  try{
    const saved=await publishCalibration.mutateAsync({workspaceId:props.workspaceId,datasetId:base.id,body:{
      base_revision:base.revision,asset_version_ids:pinned.members.map(member=>member.asset_version_id),
      calibration_defaults:JSON.parse(JSON.stringify(defaults.value)),member_calibration_overrides:JSON.parse(JSON.stringify(overrides.value))}})
    if(owner!==session.value)return
    pendingMetadata.value=true;version.value=saved;selectedVersion.value=saved.id
    notice.value=uiT('apfUi.saved_fixed_version_v')+saved.version_number+uiT('apfUi.calibration_bindings')
    await nextTick();await read()
  }catch(cause){if(owner===session.value)actionError.value=cause instanceof Error?cause.message:uiT('apfUi.could_not_save_calibration_bindings')}
  finally{if(owner===session.value)saving.value=false}
}
</script>
<template>
  <details class="apf-calibration-editor" @toggle="toggle">
    <summary>{{ $t('apfUi.group_description_history_and_calibration_bindings') }}</summary>
    <p v-if="loading" role="status">{{ $t('apfUi.reading_the_full_group_version') }}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}} <LibraryButton type="button" @click="load">{{ $t('apfUi.read_again') }}</LibraryButton></p>
    <template v-if="dataset&&version">
      <LibraryTextField id="calibration-group-name" v-model="name" :name="$t('apfUi.group_name')" :disabled="saving||loading" /><label>{{ $t('apfUi.description') }}<textarea v-model="notes" :disabled="saving||loading" /></label>
      <LibraryButton type="button" :disabled="saving||loading||pendingMetadata" @click="saveNotes">{{ $t('apfUi.save_group_description') }}</LibraryButton>
      <label><span>{{ $t('apfUi.fixed_group_version') }}<LibraryInfo :label="$t('apfUi.fixed_group_version')" :text="$t('apfUi.current_full_version')+version.id+$t('apfUi.filtering_this_list_does_not_change_the_full_member_selection_calibrat')" /></span><select :value="version.id" :disabled="saving||loading" @change="changeVersion"><option v-for="row in versions" :key="row.id" :value="row.id">v{{row.version_number}}{{row.id===dataset.current_version_id?$t('apfUi.current'):$t('apfUi.read_only_history')}}</option></select></label>
      <p>{{ $t('apfUi.full_group_value_photos_calibration_changes_apply_to_every_member', { p0: (version.members.length) }) }}</p>
      <p v-if="!current">{{ $t('apfUi.historical_versions_are_read_only') }}<LibraryInfo :label="$t('apfUi.historical_versions')" :text="$t('apfUi.previously_selected_project_references_remain_unchanged_the_group_name')" /></p>
      <fieldset :disabled="saving||loading||!current"><legend>{{ $t('apfUi.default_group_calibration') }}<LibraryInfo :label="$t('apfUi.default_group_calibration')" :text="$t('apfUi.members_inherit_group_calibration_by_default_choose_do_not_use_to_disa')" /></legend>
        <label v-for="frameType in frameTypes" :key="frameType">{{displayLabel(frameType)}}<CalibrationBindingSelect :model-value="defaults[frameType]" :frame-type="frameType" :targets="targets" :label="$t('apfUi.group_default')+displayLabel(frameType)" @update:model-value="setBinding(defaults,frameType,$event)" /></label>
      </fieldset>
      <div class="apf-calibration-members"><table><thead><tr><th>{{ $t('apfUi.full_member_list') }}</th><th v-for="frameType in frameTypes" :key="frameType">{{displayLabel(frameType)}}</th></tr></thead><tbody>
        <tr v-for="member in version.members" :key="member.asset_version_id"><th>{{member.asset.name}} · v{{member.version.version_number}}<small>{{displayLabel(member.asset.classification?.frame_type)}}</small></th>
          <td v-for="frameType in frameTypes" :key="frameType"><span>{{displayLabel(frameType)}}</span><CalibrationBindingSelect :model-value="overrides[member.asset_version_id]?.[frameType]" :frame-type="frameType" :targets="targets" inherit :disabled="saving||loading||!current" :label="member.asset.name+' '+displayLabel(frameType)" @update:model-value="setBinding(overrides[member.asset_version_id],frameType,$event)" /></td>
        </tr>
      </tbody></table></div>
      <LibraryButton type="button" :disabled="saving||loading||!current" @click="saveBindings">{{ $t('apfUi.save_calibration_bindings_as_a_new_version') }}</LibraryButton>
      <p v-if="notice" role="status">{{notice}}</p>
    </template>
  </details>
</template>
<style scoped>
.apf-calibration-editor{flex:none;min-width:0;margin:10px;padding:12px;border:1px solid var(--border-color,#555);border-radius:8px}.apf-calibration-editor label{display:flex;flex-direction:column;gap:4px;margin:8px 0}.apf-calibration-editor fieldset{display:flex;gap:12px;flex-wrap:wrap}.apf-calibration-members{overflow:auto;margin:12px 0}.apf-calibration-members table{border-collapse:collapse;width:100%;min-width:0}.apf-calibration-members td,.apf-calibration-members th{padding:6px;text-align:left;border-bottom:1px solid var(--border-color,#555)}.apf-calibration-members thead{display:none}.apf-calibration-members tbody tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px 0;border-bottom:1px solid var(--border-color,#555)}.apf-calibration-members th{grid-column:1/-1}.apf-calibration-members td{min-width:0;border:0}.apf-calibration-members td>span{display:block;margin-bottom:4px;font-size:12px}.apf-calibration-members small{display:block;font-weight:normal}
</style>

<script setup lang="ts">
import {computed,inject,onBeforeUnmount,ref,watch} from 'vue'
import {z} from 'zod'
import {assetApi} from '../api/index'
import {calibrationTargetOptionSchema,datasetSchema,datasetVersionSchema,pageSchema,type CalibrationBindings,type CalibrationTarget,type CalibrationTargetOption} from '../api/contracts'
import type {WorkspaceContext} from './Workspace.vue'
import CalibrationBindingSelect from './CalibrationBindingSelect.vue'

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
  if(dirty.value&&!window.confirm('重新读取将放弃未保存的组说明或校准关联。继续吗？'))return
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
  }catch(cause){error.value=cause instanceof Error?cause.message:'校准关联读取失败。'}
  finally{loading.value=false}
}
function toggle(event:Event){opened.value=(event.target as HTMLDetailsElement).open;if(opened.value&&!dataset.value)void load()}
function changeVersion(event:Event){
  if(dirty.value&&!window.confirm('校准关联有未保存修改。放弃修改吗？')){(event.target as HTMLSelectElement).value=version.value!.id;return}
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
    notice.value='组说明已保存。';emit('updated',dataset.value)
  }catch(cause){error.value=cause instanceof Error?cause.message:'组说明保存失败。'}finally{saving.value=false}
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
    notice.value='已保存固定版本 v'+saved.version_number+' 的校准关联。';emit('updated',dataset.value)
  }catch(cause){error.value=cause instanceof Error?cause.message:'校准关联保存失败。'}finally{saving.value=false}
}
</script>
<template>
  <details class="apf-calibration-editor" @toggle="toggle">
    <summary>组说明、历史版本与校准关联</summary>
    <p v-if="loading" role="status">正在读取完整组版本…</p>
    <p v-if="error" role="alert" class="apf-error">{{error}} <button type="button" @click="load">重新读取</button></p>
    <template v-if="dataset&&version">
      <label>组名称<input v-model="name" :disabled="saving" /></label><label>场景说明<textarea v-model="notes" :disabled="saving" /></label>
      <button type="button" :disabled="saving" @click="saveNotes">保存组说明</button>
      <label>固定组版本<select :value="version.id" :disabled="saving" @change="changeVersion"><option v-for="row in versions" :key="row.id" :value="row.id">v{{row.version_number}}{{row.id===dataset.current_version_id?' · 当前':' · 历史只读'}}</option></select></label>
      <p>当前展示此版本的全部 {{version.members.length}} 个成员；列表筛选不会改变本次成员范围。关联只保存固定版本，不执行校准或合成。</p>
      <p v-if="!current">历史版本只读；项目中已选的旧版关联保持原样。组名称和场景说明显示当前资料。</p>
      <fieldset :disabled="saving||!current"><legend>组默认校准</legend>
        <label v-for="frameType in frameTypes" :key="frameType">{{frameType}}<CalibrationBindingSelect :model-value="defaults[frameType]" :frame-type="frameType" :targets="targets" :label="'组默认 '+frameType" @update:model-value="setBinding(defaults,frameType,$event)" /></label>
      </fieldset>
      <div class="apf-calibration-members"><table><thead><tr><th>完整成员列表</th><th v-for="frameType in frameTypes" :key="frameType">{{frameType}}</th></tr></thead><tbody>
        <tr v-for="member in version.members" :key="member.asset_version_id"><th>{{member.asset.name}} · v{{member.version.version_number}}<small>{{member.asset.classification?.frame_type??'未知用途'}}</small></th>
          <td v-for="frameType in frameTypes" :key="frameType"><CalibrationBindingSelect :model-value="overrides[member.asset_version_id]?.[frameType]" :frame-type="frameType" :targets="targets" inherit :disabled="saving||!current" :label="member.asset.name+' '+frameType" @update:model-value="setBinding(overrides[member.asset_version_id],frameType,$event)" /></td>
        </tr>
      </tbody></table></div>
      <button type="button" :disabled="saving||!current" @click="saveBindings">保存校准关联为新版本</button>
      <p v-if="notice" role="status">{{notice}}</p>
    </template>
  </details>
</template>
<style scoped>
.apf-calibration-editor{margin:10px;padding:12px;border:1px solid var(--border-color,#555);border-radius:8px}.apf-calibration-editor label{display:flex;flex-direction:column;gap:4px;margin:8px 0}.apf-calibration-editor fieldset{display:flex;gap:12px;flex-wrap:wrap}.apf-calibration-members{overflow:auto;margin:12px 0}.apf-calibration-members table{border-collapse:collapse;width:100%;min-width:680px}.apf-calibration-members td,.apf-calibration-members th{padding:6px;text-align:left;border-bottom:1px solid var(--border-color,#555)}.apf-calibration-members small{display:block;font-weight:normal}
</style>

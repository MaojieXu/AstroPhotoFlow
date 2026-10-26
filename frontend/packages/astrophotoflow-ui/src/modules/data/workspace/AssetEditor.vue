<script setup lang="ts">
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
    error.value=cause instanceof ApiClientError?cause.message:'请求失败。'
  }finally{saving.value=false}
}
onMounted(()=>{void loadEquipment().catch(cause=>{error.value=cause instanceof Error?cause.message:'设备列表读取失败。'})})
</script>

<template>
  <section class="apf-editor" aria-label="编辑素材资料">
    <form @submit.prevent="save">
      <h2>编辑素材资料</h2>
      <label>名称<input v-model="draft.name" required /></label>
      <label>用途角色<select v-model="draft.role" disabled><option value="raw">原始素材</option><option value="calibration">校准素材</option></select><small>由帧用途自动派生</small></label>
      <label>素材形态<select v-model="draft.classification!.frame_class" @change="changeFrameClass">
        <option value="subframe">Subframe</option><option value="masterframe">Masterframe</option><option value="video">Video</option>
      </select></label>
      <label v-if="draft.classification?.frame_class!=='video'">帧用途<select v-model="draft.classification!.frame_type">
        <option value="light">Light</option><option value="bias">Bias</option><option value="dark">Dark</option><option value="flat">Flat</option><option value="dark_flat">Dark Flat</option>
      </select></label>
      <label>参数填写模式<select v-model="draft.parameters.parameter_mode">
        <option value="standard">常规</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option>
      </select></label>
      <label>相机<select v-model="draft.parameters.camera_id"><option value="">未指定</option><option v-for="item in equipment.filter(x=>x.kind==='camera')" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
      <label v-if="['light','flat'].includes(draft.classification?.frame_type||'')">成像系统<select v-model="draft.parameters.optical_system_id"><option value="">未指定</option><option v-for="item in equipment.filter(x=>x.kind==='optical_system')" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
      <label v-if="['light','flat'].includes(draft.classification?.frame_type||'')">滤镜<select v-model="draft.parameters.filter_id"><option value="">未指定</option><option v-for="item in equipment.filter(x=>x.kind==='filter')" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
      <label v-for="field in [
        {key:'iso',label:'ISO',step:'1'}, {key:'gain',label:'Gain',step:'any'}, {key:'offset',label:'Offset',step:'any'},
        {key:'exposure_seconds',label:'单帧曝光（秒）',step:'any'}, {key:'integration_seconds',label:'累计曝光（秒）',step:'any'},
        {key:'sensor_temperature_c',label:'传感器实测温度（°C）',step:'any'},
        {key:'binning_x',label:'水平 Binning',step:'1'}, {key:'binning_y',label:'垂直 Binning',step:'1'}
      ]" :key="field.key">{{field.label}}<input v-model="draft.parameters[field.key]" type="number" :step="field.step" /></label>
      <label>CFA 排列<select v-model="draft.parameters.cfa_pattern"><option value="">未指定</option><option>RGGB</option><option>BGGR</option><option>GRBG</option><option>GBRG</option></select></label>
      <label>多行备注<textarea v-model="draft.notes" rows="4" /></label>
      <label>状态<select v-model="draft.status"><option value="active">启用</option><option value="archived">归档</option></select></label>
      <p v-if="error" class="apf-error" role="alert">{{error}}</p>
      <footer class="apf-form-actions"><button type="button" @click="emit('close')">取消</button><button type="submit" :disabled="saving">{{saving?'保存中…':'保存'}}</button></footer>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { assetApi } from '../assets/host-client'
import { equipmentSchema, importAcceptedSchema, pageSchema, taskActionSchema, uploadCreatedSchema } from '../assets/contracts'
import { ApiClientError } from '../assets/client'
import CapturePresetPicker from './CapturePresetPicker.vue'

type Field = { key: string; title: string; integer?: boolean; positive?: boolean; nonnegative?: boolean }

const props = defineProps<{ open: boolean; files: File[]; createDataset?: boolean; datasetName?: string }>()
const emit = defineEmits<{ close: []; submitted: [taskId: string]; 'upload-progress': [taskId: string, index: number, loaded: number, total: number]; 'upload-failed': [taskId: string] }>()
const submitting = ref(false)
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
const equipment = ref<Array<Record<string,any>>>([])
const fields: Field[] = [
  {key:'exposure_seconds',title:'单帧曝光（秒）',nonnegative:true},
  {key:'integration_seconds',title:'累计曝光（秒）',nonnegative:true},
  {key:'sensor_temperature_c',title:'传感器实测温度（°C）'}
]
const isDataset = computed(() => Boolean(props.createDataset) || props.files.length > 1)
const cameraOptions = computed(() => equipment.value.filter(item => item.kind === 'camera'))
const opticalOptions = computed(() => equipment.value.filter(item => item.kind === 'optical_system'))
const filterOptions = computed(() => equipment.value.filter(item => item.kind === 'filter'))
function clientError(cause: unknown) {
  return cause instanceof ApiClientError ? cause.message : '请求失败。'
}
async function loadEquipment() {
  const result:Record<string,any>[]=[]
  for (let next=0;;next+=200) {
    const page=await assetApi.get('/astrophotoflow/api/v1/equipment?limit=200&offset='+next+'&sort_by=name&order=asc&status=all',pageSchema(equipmentSchema))
    result.push(...page.items)
    if(next+page.limit>=page.total) break
  }
  equipment.value=result
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
  if(!props.files.length)return
  submitting.value=true;error.value=''
  try{
    const accepted=await assetApi.send('/astrophotoflow/api/v1/uploads',uploadCreatedSchema,'POST',{
      files:props.files.map(file=>({name:file.name,size:file.size})),
      ...(manualClassification.value?{classification:{frame_class:frameClass.value||null,frame_type:frameClass.value==='video'?null:frameType.value||null}}:{}),
      parameters:buildParameters(),
      ...(capturePresetId.value ? {capture_preset_id:capturePresetId.value} : {}),
      notes:notes.value||null,
      dataset_name:isDataset.value?(datasetName.value||props.datasetName||null):null,
      create_dataset:Boolean(props.createDataset)
    })
    emit('submitted',accepted.task_id)
    void uploadFiles(accepted.task_id)
  }catch(cause){error.value=clientError(cause)}
  finally{submitting.value=false}
}
async function uploadFiles(taskId:string){
  try{
    const loadedByFile = props.files.map(()=>0)
    const totalBytes = props.files.reduce((sum,file)=>sum+file.size,0)
    for(const [index,file] of props.files.entries()){
      await assetApi.upload('/astrophotoflow/api/v1/uploads/'+taskId+'/'+index,file,loaded=>{
        loadedByFile[index]=loaded
        emit('upload-progress',taskId,index,loadedByFile.reduce((sum,value)=>sum+value,0),totalBytes)
      })
    }
    await assetApi.send('/astrophotoflow/api/v1/uploads/'+taskId+'/start',importAcceptedSchema,'POST',{})
  }catch(cause){
    error.value=clientError(cause)
    await assetApi.send('/astrophotoflow/api/v1/uploads/'+taskId+'/fail',taskActionSchema,'POST',{}).catch(()=>undefined)
    emit('upload-failed',taskId)
  }
}
watch(()=>props.open,open=>{if(open){
  error.value='';datasetName.value=props.datasetName??'';notes.value='';manualClassification.value=false;frameClass.value='';frameType.value='';parameterMode.value=''
  parameters.value={camera_id:'',optical_system_id:'',filter_id:'',iso:'',gain:'',offset:'',exposure_seconds:'',integration_seconds:'',sensor_temperature_c:'',binning:'',cfa_pattern:''}
  capturePresetId.value=''
  void loadEquipment()
}})
</script>

<template>
  <div v-if="open" class="apf-import-overlay" role="dialog" aria-modal="true" aria-label="导入天文素材">
    <section class="apf-import-dialog">
      <header><h2>确认素材信息</h2><button type="button" @click="emit('close')">关闭</button></header>
      <form @submit.prevent="submitImport">
        <p>已选择 {{ files.length }} 个文件：{{ files.map(file=>file.name).join('、') }}</p>
        <CapturePresetPicker v-model="capturePresetId" :disabled="submitting" />
        <label v-if="isDataset">数据集名称<input v-model="datasetName" :placeholder="props.datasetName||'可留空，使用来源名称'" /></label>
        <label><span><input v-model="manualClassification" type="checkbox" /> 手动指定整批分类</span></label>
        <p v-if="!manualClassification">按每个文件的明确 Header 分类；缺少资料时保留未知。</p>
        <label v-if="manualClassification">素材形态<select v-model="frameClass"><option value="">未指定</option><option value="subframe">Subframe</option><option value="masterframe">Masterframe</option><option value="video">Video</option></select></label>
        <label v-if="manualClassification&&frameClass!==''&&frameClass!=='video'">帧用途<select v-model="frameType"><option value="">未指定</option><option value="light">Light</option><option value="bias">Bias</option><option value="dark">Dark</option><option value="flat">Flat</option><option value="dark_flat">Dark Flat</option></select></label>
        <label>相机<select v-model="parameters.camera_id"><option value="">未指定</option><option v-for="item in cameraOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label v-if="['light','flat'].includes(frameType)">成像系统<select v-model="parameters.optical_system_id"><option value="">未指定</option><option v-for="item in opticalOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label v-if="['light','flat'].includes(frameType)">滤镜<select v-model="parameters.filter_id"><option value="">未指定</option><option v-for="item in filterOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label>增益模式<select v-model="parameterMode"><option value="">未指定</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option></select></label>
        <label v-if="parameterMode==='iso'">ISO<input v-model="parameters.iso" type="number" step="1" /></label>
        <template v-else-if="parameterMode==='gain'"><label>Gain<input v-model="parameters.gain" type="number" step="any" /></label><label>Offset<input v-model="parameters.offset" type="number" step="any" /></label></template>
        <label v-for="field in fields" :key="field.key" v-show="field.key!=='integration_seconds'||frameClass==='masterframe'">{{field.title}}<input v-model="parameters[field.key]" type="number" :step="field.integer?'1':'any'" /></label>
        <label>Bin<select v-model="parameters.binning"><option value="">未指定</option><option v-for="value in 16" :key="value" :value="String(value)">Bin{{value}}</option></select></label>
        <label>CFA 排列<select v-model="parameters.cfa_pattern"><option value="">未指定</option><option value="MONO">无 CFA（单色）</option><option value="RGGB">RGGB</option><option value="BGGR">BGGR</option><option value="GRBG">GRBG</option><option value="GBRG">GBRG</option><option value="XTRANS">X-Trans 6×6</option><option value="QUAD_BAYER">Quad Bayer</option></select></label>
        <label>多行备注<textarea v-model="notes" rows="3" /></label>
        <p v-if="isDataset">备注写入数据集；图片资产仍分别保留自己的分类及参数。</p>
        <p v-if="error" class="apf-error" role="alert">{{ error }}</p>
        <footer class="apf-import-actions"><button type="button" :disabled="submitting" @click="emit('close')">取消</button><button type="submit" :disabled="submitting">{{submitting?'创建批次…':'开始导入'}}</button></footer>
      </form>
    </section>
  </div>
</template>

<style scoped>
.apf-import-overlay{position:absolute;inset:0;z-index:5;display:flex;justify-content:center;align-items:center;padding:12px;background:#0009}
.apf-import-dialog{width:min(760px,100%);max-height:100%;overflow:auto;padding:16px;background:var(--comfy-menu-bg,#272727);border:1px solid var(--border-color,#555);border-radius:10px;color:var(--input-text,#ddd);box-shadow:0 12px 44px #0008}
.apf-import-dialog header,.apf-import-actions,.apf-import-pages,.apf-import-entry{display:flex;align-items:center;gap:8px}
.apf-import-dialog header h2{margin-right:auto}
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

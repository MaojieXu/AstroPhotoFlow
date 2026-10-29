<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { assetApi } from '../api/index'
import { equipmentSchema, importAcceptedSchema, pageSchema } from '../api/contracts'
import { ApiClientError } from '../api/client'
import type { LocalImportFile } from '../api/contracts'
import CapturePresetPicker from './CapturePresetPicker.vue'
import LibraryInfo from './LibraryInfo.vue'
import LibraryButton from './LibraryButton.vue'
import LibraryInput from './LibraryInput.vue'
import LibraryTextField from './LibraryTextField.vue'

type Field = { key: string; title: string; integer?: boolean; positive?: boolean; nonnegative?: boolean }

const props = defineProps<{ open: boolean; files: LocalImportFile[]; createDataset?: boolean; datasetName?: string }>()
const emit = defineEmits<{ close: []; submitted: [taskId: string] }>()
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
    const accepted=await assetApi.send('/astrophotoflow/api/v1/imports',importAcceptedSchema,'POST',{
      sources:props.files.map(file=>({...(file.root_id?{root_id:file.root_id}:{}),path:file.path})),
      storage_mode:'managed',
      ...(manualClassification.value?{classification:{frame_class:frameClass.value||null,frame_type:frameClass.value==='video'?null:frameType.value||null}}:{}),
      parameters:buildParameters(),
      ...(capturePresetId.value ? {capture_preset_id:capturePresetId.value} : {}),
      notes:notes.value||null,
      dataset_name:isDataset.value?(datasetName.value||props.datasetName||null):null,
    })
    emit('submitted',accepted.task_id)
  }catch(cause){error.value=clientError(cause)}
  finally{submitting.value=false}
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
      <header><h2>确认素材信息</h2><LibraryButton type="button" @click="emit('close')">关闭</LibraryButton></header>
      <form @submit.prevent="submitImport">
        <p>已选择 {{ files.length }} 个文件<LibraryInfo label="选中文件" :text="files.map(file=>file.root_id?file.root_id+':/'+file.path:file.path).join('\n')" /></p>
        <p class="apf-optional-note">本机文件将复制并托管到工作台数据目录。以下资料均为可选。</p>
        <p class="apf-optional-note">{{(files.reduce((sum,file)=>sum+file.size,0)/1024/1024).toFixed(1)}} MiB · 仅本次选择的文件</p>
        <CapturePresetPicker v-model="capturePresetId" :disabled="submitting" />
        <LibraryTextField v-if="isDataset" id="import-dataset-name" v-model="datasetName" name="图像组名称（可选）" hint="留空使用来源名称。" />
        <label><span><input v-model="manualClassification" type="checkbox" /> 手动指定整批分类<LibraryInfo label="整批分类" text="默认按每个文件内的拍摄信息分类；缺少资料时保留未知。手动指定时对本批次全部文件生效。" /></span></label><small v-if="!manualClassification">自动识别文件拍摄信息</small>
        <label v-if="manualClassification">素材形态<select v-model="frameClass"><option value="">未指定</option><option value="subframe">单帧</option><option value="masterframe">合成帧</option><option value="video">视频</option></select></label>
        <label v-if="manualClassification&&frameClass!==''&&frameClass!=='video'">帧用途<select v-model="frameType"><option value="">未指定</option><option value="light">亮场</option><option value="bias">偏置场</option><option value="dark">暗场</option><option value="flat">平场</option><option value="dark_flat">暗平场</option></select></label>
        <label>相机<select v-model="parameters.camera_id"><option value="">未指定</option><option v-for="item in cameraOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label v-if="['light','flat'].includes(frameType)">成像系统<select v-model="parameters.optical_system_id"><option value="">未指定</option><option v-for="item in opticalOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label v-if="['light','flat'].includes(frameType)">滤镜<select v-model="parameters.filter_id"><option value="">未指定</option><option v-for="item in filterOptions" :key="item.id" :value="item.id">{{item.name}}</option></select></label>
        <label>增益模式<select v-model="parameterMode"><option value="">未指定</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option></select></label>
        <label v-if="parameterMode==='iso'">ISO<LibraryInput v-model="parameters.iso" type="number" step="1" /></label>
        <template v-else-if="parameterMode==='gain'"><label>Gain<LibraryInput v-model="parameters.gain" type="number" step="any" /></label><label>Offset<LibraryInput v-model="parameters.offset" type="number" step="any" /></label></template>
        <label v-for="field in fields" :key="field.key" v-show="field.key!=='integration_seconds'||frameClass==='masterframe'">{{field.title}}<input v-model="parameters[field.key]" type="number" :step="field.integer?'1':'any'" /></label>
        <label>Bin<select v-model="parameters.binning"><option value="">未指定</option><option v-for="value in 16" :key="value" :value="String(value)">Bin{{value}}</option></select></label>
        <label>CFA 排列<select v-model="parameters.cfa_pattern"><option value="">未指定</option><option value="MONO">无 CFA（单色）</option><option value="RGGB">RGGB</option><option value="BGGR">BGGR</option><option value="GRBG">GRBG</option><option value="GBRG">GBRG</option><option value="XTRANS">X-Trans 6×6</option><option value="QUAD_BAYER">Quad Bayer</option></select></label>
        <label>{{isDataset?'图像组备注（可选）':'素材备注（可选）'}}<LibraryInfo v-if="isDataset" label="备注" text="多文件备注写入图像组；成员仍分别保留自己的分类及参数。" /><textarea v-model="notes" rows="3" /></label>
        <p v-if="error" class="apf-error" role="alert">{{ error }}</p>
        <footer class="apf-import-actions"><LibraryButton type="button" :disabled="submitting" @click="emit('close')">取消</LibraryButton><LibraryButton type="submit" variant="primary" :disabled="submitting">{{submitting?'创建批次…':'开始导入'}}</LibraryButton></footer>
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

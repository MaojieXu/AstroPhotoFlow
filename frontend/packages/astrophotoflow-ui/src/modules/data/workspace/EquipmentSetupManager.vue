<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { assetApi } from '../api/index'
import { capturePresetSchema, equipmentSchema, equipmentSetupSchema, pageSchema, type CapturePreset, type EquipmentSetup, type SetupComponent } from '../api/contracts'
import type { WorkspaceContext } from './Workspace.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'
import LibraryTextField from './LibraryTextField.vue'
import LibraryButton from './LibraryButton.vue'
import LibraryInput from './LibraryInput.vue'
import LibraryDialog from './LibraryDialog.vue'
import LibraryMultiSelect from './LibraryMultiSelect.vue'
import LibrarySelect from './LibrarySelect.vue'
import LibraryTextarea from './LibraryTextarea.vue'
import EquipmentFields from './EquipmentFields.vue'
import type { EquipmentDraft } from './EquipmentFields.vue'

const context = inject<WorkspaceContext>('workspace')!
const { selected, equipmentKinds, equipmentKindLabels, relatedEquipment, loadRelatedEquipment, loadRecords } = context
const selectedSetup = computed(() => selected.value as EquipmentSetup | undefined)
const editingSetup = ref<EquipmentSetup | null>()
const setupDraft = ref({name:'',notes:'',status:'active' as 'active'|'archived',components:[] as SetupComponent[]})
const setupOriginal = ref('')
const deviceEditor = ref<{source:'new';equipment:EquipmentDraft}|{source:'inline';index:number;equipment:EquipmentDraft}>()
const equipmentOriginal = ref('')
const equipmentNotice = ref('')
const presets = ref<CapturePreset[]>([])
const selectedPresetIds = ref<string[]>([])
const presetStatus = ref('active')
const presetLoading = ref(false)
const presetError = ref('')
const editingPreset = ref<CapturePreset | null>()
const presetDraft = ref({name:'',notes:'',status:'active' as 'active'|'archived',classification:{} as CapturePreset['classification'],parameters:{} as CapturePreset['parameters']})
const presetOriginal = ref('')
const saving = ref(false)
watch(saving,value=>{context.setupSaving.value=value},{flush:'sync'})
const error = ref('')
let presetGeneration = 0
let setupSelectionGeneration = 0
watch(() => selectedSetup.value?.id, () => {setupSelectionGeneration++}, {flush:'sync'})
const numericParameters = [
  {key:'exposure_seconds',label:'曝光（秒）',min:0},
  {key:'sensor_temperature_c',label:'温度（°C）'},
  {key:'iso',label:'ISO',integer:true,min:1}, {key:'gain',label:'增益（Gain）'},
  {key:'offset',label:'Offset'}
] as const
const visibleNumericParameters = computed(() => numericParameters.filter(field =>
  field.key === 'iso' ? presetDraft.value.parameters.parameter_mode === 'iso' :
  field.key === 'gain' || field.key === 'offset' ? presetDraft.value.parameters.parameter_mode === 'gain' : true))
const presetFilters = computed(() => (selectedSetup.value?.components ?? []).flatMap(component => {
  if (component.source !== 'registered') return []
  const equipment = relatedEquipment.value.find(item => item.id === component.equipment_id)
  return equipment?.kind === 'filter' ? [{value:equipment.id,name:equipment.name}] : []
}))
const presetFilterOptions = computed(() => {
  const options = [{value:'',name:'使用组合默认滤镜'},...presetFilters.value]
  const filterId = presetDraft.value.parameters.filter_id
  if (filterId && !options.some(option => option.value === filterId)) {
    options.push({value:filterId,name:'原预设滤镜：'+context.equipmentName(filterId)})
  }
  return options
})
const presetName = computed(() => [presetDraft.value.name.trim(),presetNameSuffix(presetDraft.value.parameters)].filter(Boolean).join(' ') || '拍摄预设')
const dirty = computed(() =>
  (editingSetup.value !== undefined && JSON.stringify(setupDraft.value) !== setupOriginal.value) ||
  (editingPreset.value !== undefined && JSON.stringify(presetDraft.value) !== presetOriginal.value) ||
  (deviceEditor.value !== undefined && JSON.stringify(deviceEditor.value.equipment) !== equipmentOriginal.value))
watch(dirty, value => {context.setupDirty.value = value})
onBeforeUnmount(() => {context.setupDirty.value = false; context.setupSaving.value = false; presetGeneration++; setupSelectionGeneration++})

function leaveDraft() {
  if (saving.value) return false
  if (dirty.value && !window.confirm('当前组合或预设有未保存修改。放弃修改吗？')) return false
  editingSetup.value = undefined; editingPreset.value = undefined; deviceEditor.value = undefined; error.value = ''
  return true
}
function beginSetup(row: EquipmentSetup | null) {
  if (!leaveDraft()) return
  editingSetup.value = row
  setupDraft.value = {name:row?.name ?? '',notes:row?.notes ?? '',status:row?.status ?? 'active',components:JSON.parse(JSON.stringify(row?.components ?? []))}
  setupOriginal.value = JSON.stringify(setupDraft.value)
  equipmentNotice.value = ''
  void loadRelatedEquipment(true)
}
function registeredIds(kind:string){
  return setupDraft.value.components.flatMap(component=>component.source==='registered'&&componentKind(component)===kind?[component.equipment_id]:[])
}
function setRegistered(kind:string,ids:string[]){
  const retained=setupDraft.value.components.filter(component=>component.source!=='registered'||componentKind(component)!==kind||ids.includes(component.equipment_id))
  const present=new Set(retained.flatMap(component=>component.source==='registered'?[component.equipment_id]:[]))
  setupDraft.value.components=[...retained,...ids.filter(id=>!present.has(id)).map(equipment_id=>({source:'registered' as const,equipment_id}))]
}
function equipmentOptions(kind:string){return relatedEquipment.value.filter(item=>item.kind===kind&&item.status==='active').map(item=>({value:item.id as string,name:item.name as string}))}
function componentKind(component:SetupComponent){return component.source==='inline'?component.equipment.kind:relatedEquipment.value.find(row=>row.id===component.equipment_id)?.kind}
function beginEquipment(kind:EquipmentDraft['kind']){
  deviceEditor.value={source:'new',equipment:{kind,name:'',model:null,serial_number:null,notes:null,specs:{}}}
  equipmentOriginal.value=JSON.stringify(deviceEditor.value.equipment);error.value=''
}
function editInline(index:number){
  const component=setupDraft.value.components[index]
  if(component.source!=='inline')return
  deviceEditor.value={source:'inline',index,equipment:JSON.parse(JSON.stringify(component.equipment))}
  equipmentOriginal.value=JSON.stringify(deviceEditor.value.equipment);error.value=''
}
function returnToSetup(){
  if(saving.value)return
  if(deviceEditor.value&&JSON.stringify(deviceEditor.value.equipment)!==equipmentOriginal.value&&!window.confirm('设备有未保存修改。放弃修改并返回组合吗？'))return
  deviceEditor.value=undefined;error.value=''
}
function closeSetup(){if(deviceEditor.value)returnToSetup();else leaveDraft()}
async function saveEquipment(){
  if(saving.value)return
  const current=deviceEditor.value!
  if(current.source==='inline'){
    setupDraft.value.components[current.index]={source:'inline',equipment:JSON.parse(JSON.stringify(current.equipment))}
    deviceEditor.value=undefined;return
  }
  const generation=setupSelectionGeneration
  saving.value=true;error.value=''
  try{
    const device=current.equipment
    const saved=await assetApi.send('/astrophotoflow/api/v1/equipment',equipmentSchema,'POST',{
      ...device,model:device.model||null,serial_number:device.serial_number||null,notes:device.notes||null
    })
    if(generation!==setupSelectionGeneration)return
    relatedEquipment.value=[...relatedEquipment.value,saved]
    setupDraft.value.components.push({source:'registered',equipment_id:saved.id})
    deviceEditor.value=undefined
    equipmentNotice.value=`“${saved.name}”已保存到我的设备；取消组合仍会保留此设备。`
  }catch(cause){error.value=cause instanceof Error?cause.message:'设备保存失败。'}
  finally{saving.value=false}
}
async function saveSetup() {
  if(saving.value)return
  const generation = setupSelectionGeneration
  const { section, query, offset } = context.store
  const status = context.statusFilter.value
  const currentView = () => generation === setupSelectionGeneration && context.store.section === section &&
    context.store.query === query && context.store.offset === offset && context.statusFilter.value === status
  saving.value = true; error.value = ''
  try {
    const payload = {...setupDraft.value,notes:setupDraft.value.notes || null}
    const current = editingSetup.value
    const saved = await assetApi.send('/astrophotoflow/api/v1/equipment-setups' + (current ? '/' + current.id : ''),equipmentSetupSchema,current ? 'PATCH' : 'POST',
      current ? {...payload,base_revision:current.revision} : {name:payload.name,components:payload.components,notes:payload.notes})
    if (!currentView()) return
    editingSetup.value = undefined
    equipmentNotice.value = ''
    await loadRecords()
    if (currentView()) selected.value = saved
  } catch (cause) {error.value = cause instanceof Error ? cause.message : '组合保存失败。'}
  finally {saving.value = false}
}
async function loadPresets() {
  const setupId = selectedSetup.value?.id
  const generation = ++presetGeneration
  presets.value = []; selectedPresetIds.value = []; presetError.value = ''
  if (!setupId) return
  presetLoading.value = true
  try {
    const result:CapturePreset[] = []
    for (let offset=0;;offset+=200) {
      const page = await assetApi.get('/astrophotoflow/api/v1/equipment-setups/'+setupId+'/presets?limit=200&offset='+offset+'&sort_by=name&order=asc&status='+presetStatus.value,pageSchema(capturePresetSchema))
      result.push(...page.items)
      if (offset + page.limit >= page.total) break
    }
    if (generation === presetGeneration) presets.value = result
  } catch (cause) {if (generation === presetGeneration) presetError.value = cause instanceof Error ? cause.message : '预设读取失败。'}
  finally {if (generation === presetGeneration) presetLoading.value = false}
}
watch([() => selectedSetup.value?.id,presetStatus,() => context.managementChangeToken.value], () => {editingSetup.value=undefined; editingPreset.value=undefined; deviceEditor.value=undefined; void loadPresets()}, {immediate:true})
function beginPreset(row: CapturePreset | null) {
  if (!leaveDraft()) return
  editingPreset.value = row
  const suffix = presetNameSuffix(row?.parameters ?? {})
  const name = row?.name ?? ''
  const prefix = suffix && name.endsWith(suffix) && (name === suffix || name.endsWith(' '+suffix)) ? name.slice(0,-suffix.length).trimEnd() : name
  presetDraft.value = {name:prefix,notes:row?.notes ?? '',status:row?.status ?? 'active',classification:{...row?.classification},parameters:{...row?.parameters}}
  presetOriginal.value = JSON.stringify(presetDraft.value)
}
function presetNameSuffix(parameters: CapturePreset['parameters']) {
  const parts:string[] = []
  const filterId = parameters.filter_id ?? presetFilters.value[0]?.value
  if (filterId) parts.push(context.equipmentName(filterId))
  if (parameters.exposure_seconds != null) parts.push(parameters.exposure_seconds+' s')
  if (parameters.sensor_temperature_c != null) parts.push(parameters.sensor_temperature_c+' °C')
  if (parameters.parameter_mode === 'iso' && parameters.iso != null) parts.push('ISO '+parameters.iso)
  if (parameters.parameter_mode === 'gain') {
    if (parameters.gain != null) parts.push('Gain '+parameters.gain)
    if (parameters.offset != null) parts.push('Offset '+parameters.offset)
  }
  return parts.length ? '['+parts.join(' · ')+']' : ''
}
function setParameter(key: string, value: string, numeric = false) {
  const parameters:Record<string,unknown> = presetDraft.value.parameters
  parameters[key] = value === '' ? null : numeric ? Number(value) : value
}
async function savePreset() {
  if(saving.value)return
  saving.value = true; error.value = ''
  try {
    const current = editingPreset.value
    const payload = {...presetDraft.value,name:presetName.value,notes:presetDraft.value.notes || null}
    await assetApi.send('/astrophotoflow/api/v1/' + (current ? 'capture-presets/'+current.id : 'equipment-setups/'+selectedSetup.value!.id+'/presets'),capturePresetSchema,current ? 'PATCH' : 'POST',
      current ? {...payload,base_revision:current.revision} : {name:payload.name,notes:payload.notes,classification:payload.classification,parameters:payload.parameters})
    editingPreset.value = undefined
    await loadPresets()
  } catch (cause) {error.value = cause instanceof Error ? cause.message : '预设保存失败。'}
  finally {saving.value = false}
}
defineExpose({ beginSetup })
</script>

<template>
  <section class="apf-setup-manager" aria-label="设备组合和拍摄预设">
    <WorkspaceRecords />
    <section v-if="selectedSetup" class="apf-setup-presets" aria-label="组合拍摄预设">
      <div class="flex flex-wrap gap-2" role="group" aria-label="组合操作">
        <LibraryButton v-if="selectedSetup.status!=='archived'" type="button" :disabled="saving||context.loading.value" @click="beginPreset(null)">新建拍摄预设</LibraryButton>
        <LibraryButton type="button" :disabled="saving||dirty||context.loading.value" @click="beginSetup(selectedSetup)">编辑设备组合</LibraryButton>
      </div>
      <p v-if="presetLoading" role="status">正在读取预设…</p>
      <p v-else-if="presetError" role="alert">{{presetError}} <LibraryButton type="button" @click="loadPresets">重试</LibraryButton></p>
      <ul v-else-if="presets.length"><li v-for="preset in presets" :key="preset.id">
        <input v-model="selectedPresetIds" type="checkbox" :value="preset.id" :aria-label="'选择预设 '+preset.name" :disabled="saving||dirty" />
        <LibraryButton type="button" class="apf-preset-name" :tooltip="preset.name" :disabled="saving||context.loading.value" @click="beginPreset(preset)"><span class="truncate">{{preset.name}}</span></LibraryButton>
        <LibraryButton type="button" :disabled="saving||dirty||context.loading.value" @click="context.requestEquipmentDelete(preset,'capture_preset')">删除预设</LibraryButton>
      </li></ul>
      <LibraryButton v-if="selectedPresetIds.length" type="button" :disabled="saving||dirty" @click="context.requestEquipmentDeleteSelection(presets.filter(row=>selectedPresetIds.includes(row.id)).map(row=>({entry_type:'capture_preset',id:row.id,revision:row.revision})))">删除所选预设（{{selectedPresetIds.length}}）</LibraryButton>
    </section>
    <LibraryDialog :open="editingSetup!==undefined" :title="deviceEditor?(deviceEditor.source==='new'?'新建'+equipmentKindLabels[deviceEditor.equipment.kind]:'编辑组合内设备'):(editingSetup?'编辑':'新建')+'设备组合'" :label="deviceEditor?'设备表单':'设备组合表单'" :busy="saving" @close="closeSetup">
      <form v-if="editingSetup!==undefined" class="apf-editor" :aria-label="deviceEditor?'新建设备表单':'设备组合表单'" @submit.prevent="deviceEditor?saveEquipment():saveSetup()">
        <div class="apf-equipment-dialog-body">
          <template v-if="deviceEditor">
            <EquipmentFields v-model="deviceEditor.equipment" :kind-editable="deviceEditor.source==='inline'" />
          </template>
          <template v-else>
            <LibraryTextField id="setup-name" v-model="setupDraft.name" class="apf-field-row" name="组合名称" required autofocus />
            <label class="apf-field-row">组合说明<LibraryTextarea v-model="setupDraft.notes" /></label>
            <div class="apf-combination-fields" aria-label="组合设备">
              <div v-for="kind in equipmentKinds" :key="kind" class="apf-combination-row">
                <span>{{equipmentKindLabels[kind]}}</span>
                <LibraryMultiSelect :model-value="registeredIds(kind)" :label="'选择'+equipmentKindLabels[kind]" :options="equipmentOptions(kind)" :disabled="saving||context.relatedEquipmentLoading.value" @update:model-value="setRegistered(kind,$event)" />
                <LibraryButton type="button" :aria-label="'新建'+equipmentKindLabels[kind]" :tooltip="'新建'+equipmentKindLabels[kind]" :disabled="saving" @click="beginEquipment(kind)">+</LibraryButton>
              </div>
            </div>
            <div v-for="(component,index) in setupDraft.components" :key="index">
              <div v-if="component.source==='inline'||componentKind(component)==='optical_system'" class="apf-legacy-component">
                <span>{{component.source==='inline'?component.equipment.name:context.equipmentName(component.equipment_id)}} · {{component.source==='inline'?'组合内设备':'成像系统'}}</span>
                <LibraryButton v-if="component.source==='inline'" type="button" @click="editInline(index)">编辑</LibraryButton>
                <LibraryButton type="button" @click="setupDraft.components.splice(index,1)">移除</LibraryButton>
              </div>
            </div>
            <p v-if="context.relatedEquipmentError.value" role="alert">{{context.relatedEquipmentError.value}}</p>
            <p v-if="equipmentNotice" role="status">{{equipmentNotice}}</p>
          </template>
          <p v-if="error" role="alert" class="apf-error">{{error}}</p>
        </div>
        <footer class="apf-equipment-dialog-footer">
          <LibraryButton type="button" :disabled="saving" @click="closeSetup">{{deviceEditor?'返回组合':'取消'}}</LibraryButton>
          <LibraryButton type="submit" variant="primary" :disabled="saving">{{saving?'保存中…':deviceEditor?(deviceEditor.source==='new'?'保存设备并加入':'应用到组合草稿'):'保存设备组合'}}</LibraryButton>
        </footer>
      </form>
    </LibraryDialog>
    <LibraryDialog :open="editingPreset!==undefined" :title="(editingPreset?'编辑':'新建')+'拍摄预设'" label="拍摄预设表单" :busy="saving" @close="leaveDraft">
      <form v-if="editingPreset!==undefined" class="apf-editor" aria-label="拍摄预设表单" @submit.prevent="savePreset">
        <div class="apf-equipment-dialog-body">
          <LibraryTextField id="preset-name" v-model="presetDraft.name" class="apf-field-row" name="名称前缀（可选）" autofocus />
          <label class="apf-field-row">滤镜<LibrarySelect :model-value="presetDraft.parameters.filter_id??''" label="预设滤镜" :options="presetFilterOptions" :disabled="saving||context.relatedEquipmentLoading.value" @update:model-value="setParameter('filter_id',String($event??''))" /></label>
          <label class="apf-field-row">ISO／增益<LibrarySelect :model-value="presetDraft.parameters.parameter_mode??''" label="ISO／增益" :options="[{value:'',name:'未设置'},{value:'standard',name:'常规'},{value:'iso',name:'ISO'},{value:'gain',name:'增益'}]" @update:model-value="setParameter('parameter_mode',String($event))" /></label>
          <label v-for="field in visibleNumericParameters" :key="field.key" class="apf-field-row">{{field.label}}<LibraryInput :model-value="presetDraft.parameters[field.key]??''" :aria-label="field.label" type="number" :step="'integer' in field?1:'any'" :min="'min' in field?field.min:undefined" @update:model-value="setParameter(field.key,String($event??''),true)" /></label>
          <div class="apf-field-row"><span>完整名称</span><output aria-label="完整预设名称" class="min-w-0 break-words">{{presetName}}</output></div>
          <p v-if="context.relatedEquipmentError.value" role="alert">{{context.relatedEquipmentError.value}}</p>
          <p v-if="error" role="alert" class="apf-error">{{error}}</p>
        </div>
        <footer class="apf-equipment-dialog-footer"><LibraryButton type="button" :disabled="saving" @click="leaveDraft">取消</LibraryButton><LibraryButton type="submit" variant="primary" :disabled="saving">保存拍摄预设</LibraryButton></footer>
      </form>
    </LibraryDialog>
    <p v-if="equipmentNotice&&editingSetup===undefined" role="status">{{equipmentNotice}}</p>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
  </section>
</template>

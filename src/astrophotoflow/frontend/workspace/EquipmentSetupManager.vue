<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { assetApi } from '../assets/host-client'
import { capturePresetSchema, equipmentSetupSchema, pageSchema, type CapturePreset, type EquipmentSetup, type SetupComponent } from '../assets/contracts'
import type { WorkspaceContext } from './Workspace.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'

const context = inject<WorkspaceContext>('workspace')!
const { selected, specFields, equipmentKinds, equipmentKindLabels, relatedEquipment, loadRelatedEquipment, loadRecords, selectSection } = context
const selectedSetup = computed(() => selected.value as EquipmentSetup | undefined)
const editingSetup = ref<EquipmentSetup | null>()
const setupDraft = ref({name:'',notes:'',status:'active' as 'active'|'archived',components:[] as SetupComponent[]})
const setupOriginal = ref('')
const registeredId = ref('')
const presets = ref<CapturePreset[]>([])
const presetStatus = ref('active')
const presetLoading = ref(false)
const presetError = ref('')
const editingPreset = ref<CapturePreset | null>()
const presetDraft = ref({name:'',notes:'',status:'active' as 'active'|'archived',classification:{} as CapturePreset['classification'],parameters:{} as CapturePreset['parameters']})
const presetOriginal = ref('')
const saving = ref(false)
const error = ref('')
let presetGeneration = 0
const numericParameters = [
  {key:'iso',label:'ISO',integer:true,min:1}, {key:'gain',label:'Gain'}, {key:'offset',label:'Offset'},
  {key:'exposure_seconds',label:'曝光（秒）',min:0}, {key:'integration_seconds',label:'累计曝光（秒）',min:0},
  {key:'sensor_temperature_c',label:'传感器温度（°C）'},
  {key:'binning_x',label:'Bin X',integer:true,min:1}, {key:'binning_y',label:'Bin Y',integer:true,min:1}
] as const
const dirty = computed(() =>
  (editingSetup.value !== undefined && JSON.stringify(setupDraft.value) !== setupOriginal.value) ||
  (editingPreset.value !== undefined && JSON.stringify(presetDraft.value) !== presetOriginal.value))
watch(dirty, value => {context.setupDirty.value = value})
onBeforeUnmount(() => {context.setupDirty.value = false; presetGeneration++})

function leaveDraft() {
  if (dirty.value && !window.confirm('当前组合或预设有未保存修改。放弃修改吗？')) return false
  editingSetup.value = undefined; editingPreset.value = undefined; error.value = ''
  return true
}
function beginSetup(row: EquipmentSetup | null) {
  if (!leaveDraft()) return
  editingSetup.value = row
  setupDraft.value = {name:row?.name ?? '',notes:row?.notes ?? '',status:row?.status ?? 'active',components:JSON.parse(JSON.stringify(row?.components ?? []))}
  setupOriginal.value = JSON.stringify(setupDraft.value)
  void loadRelatedEquipment(true)
}
function addRegistered() {
  if (!registeredId.value) return
  setupDraft.value.components.push({source:'registered',equipment_id:registeredId.value})
  registeredId.value = ''
}
function addInline() {
  setupDraft.value.components.push({source:'inline',equipment:{kind:'camera',name:'',model:null,serial_number:null,notes:null,specs:{}}})
}
function changeInlineKind(component: SetupComponent) {
  if (component.source === 'inline') component.equipment.specs = {}
}
async function saveSetup() {
  const generation = presetGeneration
  const { section, query, offset } = context.store
  const status = context.statusFilter.value
  const currentView = () => generation === presetGeneration && context.store.section === section &&
    context.store.query === query && context.store.offset === offset && context.statusFilter.value === status
  saving.value = true; error.value = ''
  try {
    const payload = {...setupDraft.value,notes:setupDraft.value.notes || null}
    const current = editingSetup.value
    const saved = await assetApi.send('/astrophotoflow/api/v1/equipment-setups' + (current ? '/' + current.id : ''),equipmentSetupSchema,current ? 'PATCH' : 'POST',
      current ? {...payload,base_revision:current.revision} : {name:payload.name,components:payload.components,notes:payload.notes})
    if (!currentView()) return
    editingSetup.value = undefined
    await loadRecords()
    if (currentView()) selected.value = saved
  } catch (cause) {error.value = cause instanceof Error ? cause.message : '组合保存失败。'}
  finally {saving.value = false}
}
async function loadPresets() {
  const setupId = selectedSetup.value?.id
  const generation = ++presetGeneration
  presets.value = []; presetError.value = ''
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
watch([() => selectedSetup.value?.id,presetStatus], () => {editingSetup.value=undefined; editingPreset.value=undefined; void loadPresets()}, {immediate:true})
function beginPreset(row: CapturePreset | null) {
  if (!leaveDraft()) return
  editingPreset.value = row
  presetDraft.value = {name:row?.name ?? '',notes:row?.notes ?? '',status:row?.status ?? 'active',classification:{...row?.classification},parameters:{...row?.parameters}}
  presetOriginal.value = JSON.stringify(presetDraft.value)
}
function setParameter(key: string, value: string, numeric = false) {
  const parameters:Record<string,unknown> = presetDraft.value.parameters
  parameters[key] = value === '' ? null : numeric ? Number(value) : value
}
function setFrameClass(value: string) {
  presetDraft.value.classification.frame_class = value as CapturePreset['classification']['frame_class'] || null
  if (value === 'video') presetDraft.value.classification.frame_type = null
}
async function savePreset() {
  saving.value = true; error.value = ''
  try {
    const current = editingPreset.value
    const payload = {...presetDraft.value,notes:presetDraft.value.notes || null}
    await assetApi.send('/astrophotoflow/api/v1/' + (current ? 'capture-presets/'+current.id : 'equipment-setups/'+selectedSetup.value!.id+'/presets'),capturePresetSchema,current ? 'PATCH' : 'POST',
      current ? {...payload,base_revision:current.revision} : {name:payload.name,notes:payload.notes,classification:payload.classification,parameters:payload.parameters})
    editingPreset.value = undefined
    await loadPresets()
  } catch (cause) {error.value = cause instanceof Error ? cause.message : '预设保存失败。'}
  finally {saving.value = false}
}
</script>

<template>
  <section class="apf-setup-manager" aria-label="使用组合和拍摄预设">
    <p>把同一次使用的设备保存为组合，并在组合内维护拍摄预设。导入时选择预设，仍可填写本批次的人工值。</p>
    <div class="apf-setup-actions">
      <button type="button" :disabled="saving||context.loading.value" @click="beginSetup(null)">新建使用组合</button>
      <button type="button" :disabled="saving" @click="selectSection('capture-profiles')">旧版拍摄配置</button>
    </div>
    <WorkspaceRecords />
    <section v-if="selectedSetup" class="apf-details" aria-label="使用组合详情">
      <h2>{{selectedSetup.name}}</h2><p>{{selectedSetup.notes}}</p>
      <p>{{selectedSetup.components.length}} 个设备 · {{selectedSetup.status==='active'?'启用':'已归档'}}</p>
      <ul><li v-for="(component,index) in selectedSetup.components" :key="index">
        <template v-if="component.source==='registered'">{{context.equipmentName(component.equipment_id)}} · 注册设备</template>
        <template v-else>{{component.equipment.name}} · {{equipmentKindLabels[component.equipment.kind]}} · 组合内设备</template>
      </li></ul>
      <button type="button" :disabled="saving||context.loading.value" @click="beginSetup(selectedSetup)">编辑使用组合</button>
      <h3>组合内拍摄预设</h3>
      <label>预设状态<select v-model="presetStatus" :disabled="saving||dirty"><option value="active">启用</option><option value="archived">归档</option><option value="all">全部</option></select></label>
      <button type="button" :disabled="saving||context.loading.value" @click="beginPreset(null)">新建拍摄预设</button>
      <p v-if="presetLoading" role="status">正在读取预设…</p>
      <p v-else-if="presetError" role="alert">{{presetError}} <button type="button" @click="loadPresets">重试</button></p>
      <p v-else-if="!presets.length">此组合尚无拍摄预设。</p>
      <ul v-else><li v-for="preset in presets" :key="preset.id"><button type="button" :disabled="saving||context.loading.value" @click="beginPreset(preset)">{{preset.name}} · {{preset.status==='active'?'启用':'已归档'}}</button></li></ul>
    </section>
    <form v-if="editingSetup!==undefined" class="apf-editor" aria-label="使用组合表单" @submit.prevent="saveSetup">
      <h2>{{editingSetup?'编辑':'新建'}}使用组合</h2>
      <label>组合名称<input v-model="setupDraft.name" required /></label>
      <label>组合说明<textarea v-model="setupDraft.notes" /></label>
      <label v-if="editingSetup">组合状态<select v-model="setupDraft.status"><option value="active">启用</option><option value="archived">归档</option></select></label>
      <fieldset><legend>组合设备</legend>
        <p>注册设备保持关联；组合内设备独立保存在此组合中。</p>
        <p v-if="context.relatedEquipmentError.value" role="alert">{{context.relatedEquipmentError.value}}</p>
        <label>注册设备<select v-model="registeredId" :disabled="context.relatedEquipmentLoading.value"><option value="">选择已登记设备</option><option v-for="equipment in relatedEquipment" :key="equipment.id" :value="equipment.id">{{equipmentKindLabels[equipment.kind]}} · {{equipment.name}}{{equipment.status==='archived'?' · 已归档':''}}</option></select></label>
        <button type="button" :disabled="!registeredId||saving" @click="addRegistered">加入注册设备</button>
        <button type="button" :disabled="saving" @click="addInline">添加组合内设备</button>
        <fieldset v-for="(component,index) in setupDraft.components" :key="index"><legend>设备 {{index+1}}</legend>
          <template v-if="component.source==='registered'"><p>{{context.equipmentName(component.equipment_id)}} · 注册设备</p></template>
          <template v-else>
            <label>设备类别<select v-model="component.equipment.kind" @change="changeInlineKind(component)"><option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{equipmentKindLabels[kind]}}</option></select></label>
            <label>设备名称<input v-model="component.equipment.name" required /></label>
            <label>型号<input v-model="component.equipment.model" /></label>
            <label>序列号<input v-model="component.equipment.serial_number" /></label>
            <label>设备说明<textarea v-model="component.equipment.notes" /></label>
            <label v-for="field in specFields[component.equipment.kind]" :key="field.key">{{field.label}}
              <select v-if="field.options||field.key==='cfa_pattern'" :value="component.equipment.specs[field.key]??''" @change="component.equipment.specs[field.key]=($event.target as HTMLSelectElement).value||null"><option v-for="choice in context.specChoices(field)" :key="choice.value" :value="choice.value">{{choice.label}}</option></select>
              <input v-else :value="component.equipment.specs[field.key]??''" :type="field.type??'text'" :step="field.integer?1:'any'" @input="component.equipment.specs[field.key]=($event.target as HTMLInputElement).value===''?null:field.type==='number'?Number(($event.target as HTMLInputElement).value):($event.target as HTMLInputElement).value" />
            </label>
          </template>
          <button type="button" :disabled="saving" @click="setupDraft.components.splice(index,1)">移除此设备</button>
        </fieldset>
      </fieldset>
      <div class="apf-form-actions"><button type="button" :disabled="saving" @click="leaveDraft">取消</button><button type="submit" :disabled="saving">保存使用组合</button></div>
    </form>
    <form v-if="editingPreset!==undefined" class="apf-editor" aria-label="拍摄预设表单" @submit.prevent="savePreset">
      <h2>{{selectedSetup?.name}} / {{editingPreset?'编辑':'新建'}}拍摄预设</h2>
      <label>预设名称<input v-model="presetDraft.name" required /></label>
      <p>留空表示不设置默认值。人工填写与文件实测值优先于预设。</p>
      <label>默认素材形态<select :value="presetDraft.classification.frame_class??''" @change="setFrameClass(($event.target as HTMLSelectElement).value)"><option value="">未设置</option><option value="subframe">Subframe</option><option value="masterframe">Masterframe</option><option value="video">Video</option></select></label>
      <label v-if="presetDraft.classification.frame_class!=='video'">默认帧用途<select v-model="presetDraft.classification.frame_type"><option :value="null">未设置</option><option v-for="type in context.frameTypes" :key="type" :value="type">{{context.frameTypeLabel(type)}}</option></select></label>
      <label v-for="kind in ['camera','optical_system','filter']" :key="kind">{{equipmentKindLabels[kind]}}默认值<select :value="presetDraft.parameters[(kind+'_id') as keyof CapturePreset['parameters']]??''" @change="setParameter(kind+'_id',($event.target as HTMLSelectElement).value)"><option value="">使用组合设备</option><option v-for="equipment in relatedEquipment.filter(item=>item.kind===kind)" :key="equipment.id" :value="equipment.id">{{equipment.name}}</option></select></label>
      <label>默认增益模式<select :value="presetDraft.parameters.parameter_mode??''" @change="setParameter('parameter_mode',($event.target as HTMLSelectElement).value)"><option value="">未设置</option><option value="standard">常规</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option></select></label>
      <label v-for="field in numericParameters" :key="field.key">{{field.label}}<input :value="presetDraft.parameters[field.key]??''" type="number" :step="'integer' in field?1:'any'" :min="'min' in field?field.min:undefined" @input="setParameter(field.key,($event.target as HTMLInputElement).value,true)" /></label>
      <label>默认 CFA<select :value="presetDraft.parameters.cfa_pattern??''" @change="setParameter('cfa_pattern',($event.target as HTMLSelectElement).value)"><option v-for="choice in context.cfaChoices" :key="choice.value" :value="choice.value">{{choice.label}}</option></select></label>
      <label>预设说明<textarea v-model="presetDraft.notes" /></label>
      <label v-if="editingPreset">预设状态<select v-model="presetDraft.status"><option value="active">启用</option><option value="archived">归档</option></select></label>
      <div class="apf-form-actions"><button type="button" :disabled="saving" @click="leaveDraft">取消</button><button type="submit" :disabled="saving">保存拍摄预设</button></div>
    </form>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
  </section>
</template>

<style scoped>
.apf-setup-manager{min-height:0;overflow:auto}.apf-setup-manager>p,.apf-setup-actions{margin:10px}.apf-setup-actions{display:flex;gap:8px}.apf-setup-manager li{margin:6px 0}.apf-setup-manager fieldset{margin:10px 0}.apf-setup-manager label{display:flex;flex-direction:column;gap:4px;margin:8px 0}
</style>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  assetSchema, capabilitiesSchema, captureProfileSchema, equipmentSchema, pageSchema,
  projectAssetReferenceSchema, projectSchema
} from '../assets/contracts'
import { ApiClientError } from '../assets/client'
import { assetApi } from '../assets/host-client'
import type { ZodType } from 'zod'
import { useWorkspaceStore, type WorkspaceSection } from './store'

type RecordData = Record<string, any>
type EditorType = 'project' | 'equipment' | 'capture-profile'
type InputField = { key: string; label: string; type?: string; options?: string[]; integer?: boolean }
type WorkspaceArea = 'library' | 'nodes' | 'software' | 'agent' | 'settings'

const store = useWorkspaceStore()
const activeArea = ref<WorkspaceArea>('library')
const lastManagementSection = ref<WorkspaceSection>('projects')
const capabilities = ref<ReturnType<typeof capabilitiesSchema.parse>>()
const rows = ref<RecordData[]>([])
const selected = ref<RecordData>()
const total = ref(0)
const loading = ref(false)
const error = ref<ApiClientError>()
const capabilityError = ref<ApiClientError>()
const statusFilter = ref<'active' | 'archived' | 'all'>('active')
const roleFilter = ref('')
const frameTypeFilter = ref('')
const viewingProjectAssets = ref(false)
const editorType = ref<EditorType>()
const editingId = ref<string>()
const draft = ref<RecordData>({})
const originalDraft = ref('')
const saving = ref(false)
const relatedEquipment = ref<RecordData[]>([])
const relatedProfiles = ref<RecordData[]>([])
let searchTimer: ReturnType<typeof setTimeout> | undefined

const dirty = computed(() => editorType.value !== undefined && JSON.stringify(draft.value) !== originalDraft.value)
const isAssetSection = computed(() => store.section === 'library' || store.section === 'calibration' || viewingProjectAssets.value)
const areaTitles: Record<WorkspaceArea, string> = {
  library: '素材库',
  nodes: '节点仓库',
  software: '可安装软件',
  agent: 'Agent 聊天',
  settings: '设置'
}
const areaMessages: Partial<Record<WorkspaceArea, string>> = {
  nodes: '节点仓库区域已预留，目录功能尚未接入。',
  software: '可安装软件区域已预留，软件目录和安装功能尚未接入。',
  agent: 'Agent 聊天区域已预留，聊天功能尚未接入。'
}
let loadGeneration = 0

const specFields: Record<string, InputField[]> = {
  camera: [
    { key: 'sensor_mode', label: '传感器类型', options: ['mono', 'color'] },
    { key: 'sensor_width_px', label: '宽度（px）', type: 'number', integer: true },
    { key: 'sensor_height_px', label: '高度（px）', type: 'number', integer: true },
    { key: 'pixel_size_x_um', label: '像元宽度（μm）', type: 'number' },
    { key: 'pixel_size_y_um', label: '像元高度（μm）', type: 'number' },
    { key: 'native_bit_depth', label: '原生位深', type: 'number', integer: true },
    { key: 'cfa_pattern', label: 'CFA 排列' }
  ],
  optical_system: [
    { key: 'aperture_mm', label: '口径（mm）', type: 'number' },
    { key: 'native_focal_length_mm', label: '基础焦距（mm）', type: 'number' },
    { key: 'effective_focal_length_mm', label: '有效焦距（mm，手动填写）', type: 'number' },
    { key: 'focal_adjustment_note', label: '减焦／增焦说明' }
  ],
  filter: [
    { key: 'filter_type', label: '滤镜类型' },
    { key: 'central_wavelength_nm', label: '中心波长（nm）', type: 'number' },
    { key: 'bandwidth_nm', label: '带宽（nm）', type: 'number' },
    { key: 'bandpass_note', label: '带通说明' }
  ]
}
const frameTypes = ['light', 'bias', 'dark', 'flat', 'dark_flat']
const equipmentKinds = ['camera', 'optical_system', 'filter']

function apiPath(path: string, params: Record<string, string | number | undefined> = {}) {
  const query = new URLSearchParams()
  query.set('limit', '50')
  query.set('offset', String(store.offset))
  query.set('sort_by', 'created_at')
  query.set('order', 'desc')
  if (store.query) query.set('q', store.query)
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return '/astrophotoflow/api/v1' + path + '?' + query.toString()
}

function formListPath(path: string, offset: number) {
  const query = new URLSearchParams({ limit: '200', offset: String(offset), sort_by: 'name', order: 'asc', status: 'all' })
  return '/astrophotoflow/api/v1' + path + '?' + query.toString()
}

async function loadAll<T>(path: string, schema: ZodType<T>) {
  const items: T[] = []
  let offset = 0
  let total = 1
  while (offset < total) {
    const page = await assetApi.get(formListPath(path, offset), pageSchema(schema))
    items.push(...page.items)
    offset += page.limit
    total = page.total
  }
  return items
}

async function loadCapabilities() {
  try {
    capabilities.value = await assetApi.get('/astrophotoflow/api/v1/capabilities', capabilitiesSchema)
    capabilityError.value = undefined
  } catch (cause) {
    capabilityError.value = presentError(cause)
  }
}

async function loadRecords() {
  const generation = ++loadGeneration
  loading.value = true
  error.value = undefined
  try {
    let loadedRows: RecordData[]
    let loadedTotal: number
    if (store.section === 'library' || store.section === 'calibration') {
      const role = store.section === 'calibration' ? 'calibration' : roleFilter.value
      const params: Record<string, string> = {}
      if (role) params.role = role
      if (frameTypeFilter.value) params.frame_type = frameTypeFilter.value
      const page = await assetApi.get(apiPath('/library/assets', params), pageSchema(assetSchema))
      loadedRows = page.items
      loadedTotal = page.total
    } else if (viewingProjectAssets.value && store.activeProjectId) {
      const page = await assetApi.get(
        apiPath('/projects/' + store.activeProjectId + '/assets', {
          role: roleFilter.value, frame_type: frameTypeFilter.value
        }),
        pageSchema(projectAssetReferenceSchema)
      )
      loadedRows = page.items
      loadedTotal = page.total
    } else if (store.section === 'projects') {
      const page = await assetApi.get(apiPath('/projects', { status: statusFilter.value }), pageSchema(projectSchema))
      loadedRows = page.items
      loadedTotal = page.total
    } else if (store.section === 'equipment') {
      const page = await assetApi.get(apiPath('/equipment', { status: statusFilter.value }), pageSchema(equipmentSchema))
      loadedRows = page.items
      loadedTotal = page.total
    } else {
      const page = await assetApi.get(apiPath('/capture-profiles', { status: statusFilter.value }), pageSchema(captureProfileSchema))
      loadedRows = page.items
      loadedTotal = page.total
    }
    if (generation !== loadGeneration) return
    rows.value = loadedRows
    total.value = loadedTotal
    selected.value = rows.value.find(row => row.id === selected.value?.id)
  } catch (cause) {
    if (generation === loadGeneration) {
      error.value = presentError(cause)
      rows.value = []
      total.value = 0
      selected.value = undefined
    }
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

function presentError(cause: unknown): ApiClientError {
  if (cause instanceof ApiClientError) return cause
  return new ApiClientError('请求失败。', 'contract')
}

function errorText(value: ApiClientError) {
  if (value.kind === 'network') return '资产服务未连接，请检查服务是否运行。'
  if (value.kind === 'contract') return value.message
  if (value.code === 'SERVICE_NOT_CONFIGURED') return '本机服务尚未配置访问凭据。'
  if (value.code === 'SERVICE_UNAVAILABLE') return '资产服务当前不可用。'
  if (value.code === 'SERVICE_TIMEOUT') return '资产服务响应超时。'
  if (value.code === 'AUTHENTICATION_REQUIRED') return '本机服务认证失败。'
  if (value.code === 'REVISION_CONFLICT') return '记录已被其他窗口修改。草稿仍保留，请重新读取后决定如何处理。'
  return value.message + (value.requestId ? '（请求 ' + value.requestId + '）' : '')
}

function selectSection(section: WorkspaceSection) {
  if (dirty.value && !window.confirm('当前表单有未保存修改。放弃修改并切换吗？')) return
  editorType.value = undefined
  viewingProjectAssets.value = false
  store.selectSection(section)
  if (section === 'projects' || section === 'equipment' || section === 'capture-profiles') {
    lastManagementSection.value = section
  }
  selected.value = undefined
  loadRecords()
}

function selectArea(area: WorkspaceArea) {
  if (area === activeArea.value) return
  if (dirty.value && !window.confirm('当前表单有未保存修改。放弃修改并切换吗？')) return
  editorType.value = undefined
  viewingProjectAssets.value = false
  selected.value = undefined
  activeArea.value = area
  if (area === 'library') {
    store.selectSection('library')
    loadRecords()
  } else if (area === 'settings') {
    store.selectSection(lastManagementSection.value)
    loadRecords()
  } else {
    loadGeneration++
    loading.value = false
    error.value = undefined
  }
}

function setQuery(event: Event) {
  store.setQuery((event.target as HTMLInputElement).value)
}

function selectRow(row: RecordData) {
  selected.value = row
  if (store.section === 'projects' && !viewingProjectAssets.value) store.activeProjectId = row.id
}

function openProjectAssets() {
  if (!store.activeProjectId) return
  viewingProjectAssets.value = true
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

function leaveProjectAssets() {
  viewingProjectAssets.value = false
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

function emptySpecs(kind: string) {
  return Object.fromEntries(specFields[kind].map(field => [field.key, null]))
}

function openCreate(type: EditorType) {
  editorType.value = type
  editingId.value = undefined
  if (type === 'project') draft.value = { name: '', target_name: '', notes: '', capture_profile_ids: [] }
  if (type === 'equipment') draft.value = { kind: 'camera', name: '', model: '', serial_number: '', notes: '', specs: emptySpecs('camera') }
  if (type === 'capture-profile') draft.value = {
    name: '', camera_id: '', optical_system_id: '', filter_id: '', frame_type: 'light',
    exposure_seconds: '', gain: '', offset: '', sensor_temperature_c: '', binning_x: '', binning_y: '', notes: ''
  }
  originalDraft.value = JSON.stringify(draft.value)
  selected.value = undefined
  loadRelated()
}

function textInput(value: unknown) {
  return value == null ? '' : String(value)
}

function inputNumber(value: unknown) {
  if (value === '' || value == null) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function nullableString(value: unknown) {
  return value === '' ? null : value
}

function editEquipment(row: RecordData) {
  const specs = Object.fromEntries(specFields[row.kind].map(field => [field.key, textInput(row.specs[field.key])]))
  draft.value = {
    name: row.name, kind: row.kind, model: textInput(row.model), serial_number: textInput(row.serial_number),
    notes: textInput(row.notes), status: row.status, revision: row.revision, specs
  }
  beginEdit('equipment', row.id)
}

function editProject(row: RecordData) {
  draft.value = {
    name: row.name, target_name: textInput(row.target_name), notes: textInput(row.notes),
    capture_profile_ids: [...row.capture_profile_ids], status: row.status, revision: row.revision
  }
  beginEdit('project', row.id)
}

function editProfile(row: RecordData) {
  draft.value = {
    name: row.name, camera_id: row.camera_id, optical_system_id: textInput(row.optical_system_id),
    filter_id: textInput(row.filter_id), frame_type: row.frame_type,
    exposure_seconds: textInput(row.exposure_seconds), gain: textInput(row.gain), offset: textInput(row.offset),
    sensor_temperature_c: textInput(row.sensor_temperature_c), binning_x: textInput(row.binning_x),
    binning_y: textInput(row.binning_y), notes: textInput(row.notes), status: row.status, revision: row.revision
  }
  beginEdit('capture-profile', row.id)
}

function beginEdit(type: EditorType, id: string) {
  editorType.value = type
  editingId.value = id
  originalDraft.value = JSON.stringify(draft.value)
  loadRelated()
}

async function loadRelated() {
  relatedEquipment.value = []
  relatedProfiles.value = []
  if (editorType.value === 'project' || editorType.value === 'capture-profile') {
    try {
      relatedEquipment.value = await loadAll('/equipment', equipmentSchema)
      if (editorType.value === 'project') {
        relatedProfiles.value = await loadAll('/capture-profiles', captureProfileSchema)
      }
    } catch (cause) {
      error.value = presentError(cause)
    }
  }
}

function closeEditor() {
  if (dirty.value && !window.confirm('放弃未保存的修改吗？')) return
  editorType.value = undefined
  editingId.value = undefined
  draft.value = {}
}

function onEquipmentKindChange() {
  draft.value.specs = emptySpecs(draft.value.kind)
}

function buildPayload() {
  if (editorType.value === 'project') {
    const payload: RecordData = {
      name: draft.value.name, target_name: nullableString(draft.value.target_name),
      notes: nullableString(draft.value.notes), capture_profile_ids: draft.value.capture_profile_ids
    }
    if (editingId.value) Object.assign(payload, { base_revision: draft.value.revision, status: draft.value.status })
    return payload
  }
  if (editorType.value === 'equipment') {
    const specs = Object.fromEntries(specFields[draft.value.kind].map(field => [
      field.key, field.type ? inputNumber(draft.value.specs[field.key]) : nullableString(draft.value.specs[field.key])
    ]))
    const payload: RecordData = {
      kind: draft.value.kind, name: draft.value.name, model: nullableString(draft.value.model),
      serial_number: nullableString(draft.value.serial_number), notes: nullableString(draft.value.notes), specs
    }
    if (editingId.value) Object.assign(payload, { base_revision: draft.value.revision, status: draft.value.status })
    return payload
  }
  const payload: RecordData = {
    name: draft.value.name, camera_id: draft.value.camera_id,
    optical_system_id: nullableString(draft.value.optical_system_id),
    filter_id: nullableString(draft.value.filter_id), frame_type: draft.value.frame_type,
    exposure_seconds: inputNumber(draft.value.exposure_seconds), gain: inputNumber(draft.value.gain),
    offset: inputNumber(draft.value.offset), sensor_temperature_c: inputNumber(draft.value.sensor_temperature_c),
    binning_x: inputNumber(draft.value.binning_x), binning_y: inputNumber(draft.value.binning_y),
    notes: nullableString(draft.value.notes)
  }
  if (editingId.value) Object.assign(payload, { base_revision: draft.value.revision, status: draft.value.status })
  return payload
}

async function saveEditor() {
  if (!editorType.value) return
  saving.value = true
  error.value = undefined
  const paths: Record<EditorType, string> = {
    project: '/projects', equipment: '/equipment', 'capture-profile': '/capture-profiles'
  }
  const schemas: Record<EditorType, any> = {
    project: projectSchema, equipment: equipmentSchema, 'capture-profile': captureProfileSchema
  }
  const path = paths[editorType.value] + (editingId.value ? '/' + editingId.value : '')
  try {
    await assetApi.send('/astrophotoflow/api/v1' + path, schemas[editorType.value], editingId.value ? 'PATCH' : 'POST', buildPayload())
    editorType.value = undefined
    editingId.value = undefined
    draft.value = {}
    await loadRecords()
  } catch (cause) {
    error.value = presentError(cause)
  } finally {
    saving.value = false
  }
}

const itemTitle = (row: RecordData) => row.asset?.name ?? row.name ?? '未命名记录'
const itemSubtitle = (row: RecordData) => {
  if (row.version) return '固定版本 v' + row.version.version_number + ' · ' + (row.version.frame_type ?? '未分类')
  if (row.current_version) return '版本 v' + row.current_version.version_number + ' · ' + (row.current_version.frame_type ?? '未分类')
  if (row.kind) return row.kind + (row.model ? ' · ' + row.model : '')
  if (row.camera_id) return row.frame_type + ' · 相机 ' + row.camera_id
  return row.status ?? ''
}
const detailData = computed(() => selected.value ?? null)

watch(
  [() => store.query, () => store.offset, statusFilter, roleFilter, frameTypeFilter],
  ([query, offset, status, role, frameType], [previousQuery, , previousStatus, previousRole, previousFrameType]) => {
    const queryChanged = query !== previousQuery
    const filtersChanged = status !== previousStatus || role !== previousRole || frameType !== previousFrameType
    if (queryChanged || filtersChanged) {
      loadGeneration++
      clearTimeout(searchTimer)
      if (offset !== 0) {
        store.offset = 0
        return
      }
      if (queryChanged) {
        loading.value = true
        searchTimer = setTimeout(() => loadRecords(), 250)
        return
      }
    }
    loadRecords()
  }
)
onMounted(async () => {
  await loadCapabilities()
  await loadRecords()
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
})
</script>

<template>
  <section class="apf-workspace" aria-label="AstroPhotoFlow 天文资产工作台">
      <nav class="apf-nav" aria-label="AstroPhotoFlow 模块">
        <button v-for="(title, area) in areaTitles" :key="area" type="button"
          :aria-label="title" :title="title" :aria-current="activeArea === area ? 'page' : undefined"
          @click="selectArea(area as WorkspaceArea)">
          <i :class="['pi', ({ library: 'pi-images', nodes: 'pi-sitemap', software: 'pi-box', agent: 'pi-comments', settings: 'pi-cog' } as Record<WorkspaceArea, string>)[area]]" aria-hidden="true"></i>
        </button>
      </nav>

      <main class="apf-main">
        <template v-if="activeArea === 'library' || activeArea === 'settings'">
          <div class="apf-toolbar">
            <div class="apf-heading">
              <button v-if="viewingProjectAssets" type="button" @click="leaveProjectAssets">← 返回项目</button>
              <h1>{{ activeArea === 'library' ? '素材库' : '设置' }}</h1>
              <div v-if="activeArea === 'library' && !viewingProjectAssets" class="apf-heading-actions">
                <button type="button" class="apf-import" :disabled="!capabilities?.asset_import"
                  title="文件导入将在后续阶段接入">
                  <i class="pi pi-upload" aria-hidden="true"></i><span>导入</span>
                </button>
              </div>
            </div>
            <div v-if="activeArea === 'settings' && !viewingProjectAssets" class="apf-management-tabs" aria-label="设置类别">
              <button v-for="(title, section) in { projects: '项目', equipment: '设备', 'capture-profiles': '拍摄设置' }"
                :key="section" type="button" :aria-current="store.section === section ? 'page' : undefined"
                @click="selectSection(section as WorkspaceSection)">{{ title }}</button>
            </div>
            <label class="apf-search">
              <i class="pi pi-search" aria-hidden="true"></i>
              <input :value="store.query" aria-label="搜索" placeholder="搜索名称" @input="setQuery" />
            </label>
            <select v-if="store.section === 'projects' || store.section === 'equipment' || store.section === 'capture-profiles'"
              v-model="statusFilter" aria-label="状态筛选">
              <option value="active">启用</option><option value="archived">已归档</option><option value="all">全部</option>
            </select>
            <select v-if="isAssetSection" v-model="roleFilter" aria-label="资产用途">
              <option value="">全部用途</option><option value="raw">原始素材</option>
              <option value="calibration">校准素材</option><option value="intermediate">中间产物</option><option value="final">成品</option>
            </select>
            <select v-if="isAssetSection" v-model="frameTypeFilter" aria-label="帧类型">
              <option value="">全部帧类型</option><option v-for="type in frameTypes" :key="type" :value="type">{{ type }}</option>
            </select>
            <div class="apf-layout">
              <button type="button" :aria-pressed="store.layout === 'grid'" @click="store.layout = 'grid'">网格</button>
              <button type="button" :aria-pressed="store.layout === 'list'" @click="store.layout = 'list'">列表</button>
            </div>
            <button type="button" @click="loadRecords"><i class="pi pi-refresh" aria-hidden="true"></i><span>刷新</span></button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets" type="button" @click="openCreate('project')">新建项目</button>
            <button v-if="store.section === 'equipment'" type="button" @click="openCreate('equipment')">添加设备</button>
            <button v-if="store.section === 'capture-profiles'" type="button" @click="openCreate('capture-profile')">新建配置</button>
          </div>

          <p v-if="capabilityError" class="apf-error" role="alert">能力状态读取失败：{{ errorText(capabilityError) }}</p>
          <p v-if="error" class="apf-error" role="alert">{{ errorText(error) }}<span v-if="error.requestId"> 请求 ID：{{ error.requestId }}</span></p>
          <p v-if="loading" class="apf-state" role="status">正在读取服务数据…</p>
          <p v-else-if="!error && rows.length === 0" class="apf-state">此处目前没有记录。</p>

          <section v-if="!loading && rows.length" :class="['apf-records', store.layout]">
            <button v-for="row in rows" :key="row.id" type="button"
              :class="['apf-record', selected?.id === row.id ? 'selected' : '']" @click="selectRow(row)">
              <span class="apf-record-icon">{{ row.asset ? '✦' : row.kind ? '◉' : row.camera_id ? '⚙' : '▣' }}</span>
              <span><strong>{{ itemTitle(row) }}</strong><small>{{ itemSubtitle(row) }}</small></span>
            </button>
          </section>

          <footer class="apf-pagination">
            <span>{{ total }} 条记录</span>
            <button type="button" :disabled="store.offset === 0 || loading" @click="store.movePage(-50)">上一页</button>
            <button type="button" :disabled="store.offset + rows.length >= total || loading" @click="store.movePage(50)">下一页</button>
          </footer>
          <p v-if="isAssetSection && capabilities && !capabilities.asset_preview" class="apf-disabled">资产预览将在后续阶段接入。</p>

          <section v-if="editorType" class="apf-editor" aria-label="记录编辑表单">
            <form @submit.prevent="saveEditor">
              <h2>{{ editingId ? '编辑' : '创建' }}{{ editorType === 'project' ? '项目' : editorType === 'equipment' ? '设备' : '拍摄配置' }}</h2>
              <label>名称<input v-model="draft.name" required /></label>
              <template v-if="editorType === 'project'">
                <label>拍摄目标<input v-model="draft.target_name" /></label>
                <label>说明<textarea v-model="draft.notes" /></label>
                <label>拍摄配置（可多选）
                  <select v-model="draft.capture_profile_ids" multiple size="5">
                    <option v-for="profile in relatedProfiles" :key="profile.id" :value="profile.id">{{ profile.name }} · {{ profile.status }}</option>
                  </select>
                </label>
              </template>
              <template v-if="editorType === 'equipment'">
                <label>设备类型<select v-model="draft.kind" :disabled="!!editingId" @change="onEquipmentKindChange">
                  <option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{ kind }}</option>
                </select></label>
                <label>型号<input v-model="draft.model" /></label>
                <label>序列号<input v-model="draft.serial_number" /></label>
                <label>说明<input v-model="draft.notes" /></label>
                <fieldset><legend>设备参数</legend>
                  <label v-for="field in specFields[draft.kind]" :key="field.key">{{ field.label }}
                    <select v-if="field.options" v-model="draft.specs[field.key]">
                      <option value="">未填写</option><option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
                    </select>
                    <input v-else v-model="draft.specs[field.key]" :type="field.type ?? 'text'" :step="field.integer ? 1 : 'any'" />
                  </label>
                </fieldset>
              </template>
              <template v-if="editorType === 'capture-profile'">
                <label>相机<select v-model="draft.camera_id" required><option value="">选择相机</option>
                  <option v-for="item in relatedEquipment.filter(e => e.kind === 'camera')" :key="item.id" :value="item.id">{{ item.name }} · {{ item.status }}</option>
                </select></label>
                <label>成像系统<select v-model="draft.optical_system_id"><option value="">未指定</option>
                  <option v-for="item in relatedEquipment.filter(e => e.kind === 'optical_system')" :key="item.id" :value="item.id">{{ item.name }} · {{ item.status }}</option>
                </select></label>
                <label>滤镜<select v-model="draft.filter_id"><option value="">未指定</option>
                  <option v-for="item in relatedEquipment.filter(e => e.kind === 'filter')" :key="item.id" :value="item.id">{{ item.name }} · {{ item.status }}</option>
                </select></label>
                <label>帧类型<select v-model="draft.frame_type"><option v-for="type in frameTypes" :key="type" :value="type">{{ type }}</option></select></label>
                <label v-for="field in [
                  {key:'exposure_seconds',label:'曝光（秒）',step:'any'},
                  {key:'gain',label:'Gain',step:'any'}, {key:'offset',label:'Offset',step:'any'},
                  {key:'sensor_temperature_c',label:'传感器温度（°C）',step:'any'},
                  {key:'binning_x',label:'水平 binning',step:'1'}, {key:'binning_y',label:'垂直 binning',step:'1'}
                ]" :key="field.key">{{ field.label }}<input v-model="draft[field.key]" type="number" :step="field.step" /></label>
                <label>说明<textarea v-model="draft.notes" /></label>
              </template>
              <label v-if="editingId">状态<select v-model="draft.status"><option value="active">启用</option><option value="archived">归档</option></select></label>
              <div class="apf-form-actions">
                <button type="button" @click="closeEditor">取消</button>
                <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
              </div>
            </form>
          </section>
        <aside v-if="selected" class="apf-details" aria-label="记录详情">
          <template v-if="selected">
            <h2>{{ itemTitle(selected) }}</h2>
            <p>{{ itemSubtitle(selected) }}</p>
            <button v-if="store.section === 'projects' && !viewingProjectAssets" type="button" @click="openProjectAssets">查看项目资产</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets" type="button" @click="editProject(selected)">编辑项目</button>
            <button v-if="store.section === 'equipment'" type="button" @click="editEquipment(selected)">编辑设备</button>
            <button v-if="store.section === 'capture-profiles'" type="button" @click="editProfile(selected)">编辑配置</button>
            <pre>{{ JSON.stringify(detailData, null, 2) }}</pre>
          </template>
        </aside>
        </template>

        <section v-else class="apf-placeholder" :aria-label="areaTitles[activeArea]">
          <h1>{{ areaTitles[activeArea] }}</h1>
          <p>{{ areaMessages[activeArea] }}</p>
        </section>
      </main>
  </section>
</template>

<style>
.apf-workspace { position:relative; display:flex; flex:1 1 auto; width:100%; height:100%; min-height:0; font:inherit; color:var(--input-text,inherit); }
.apf-workspace button { display:inline-flex; min-height:32px; align-items:center; justify-content:center; gap:8px; padding:8px; border:0; border-radius:8px; color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); font:inherit; font-size:12px; font-weight:500; line-height:1; white-space:nowrap; cursor:pointer; transition:background-color .1s ease; }
.apf-workspace button:hover:not(:disabled) { background:var(--comfy-menu-bg,#353535); }
.apf-workspace button:focus-visible, .apf-workspace input:focus-visible, .apf-workspace select:focus-visible, .apf-workspace textarea:focus-visible { outline:1px solid var(--border-color,#4e4e4e); outline-offset:1px; }
.apf-workspace button:disabled { opacity:.5; cursor:not-allowed; }
.apf-nav { display:flex; flex:0 0 48px; flex-direction:column; align-items:center; gap:6px; padding:8px 4px; border-right:1px solid var(--border-color,#4e4e4e); background:var(--comfy-menu-bg,#202124); }
.apf-workspace .apf-nav button { display:grid; width:40px; min-height:42px; height:42px; padding:0; border-radius:6px; color:var(--descrip-text,#999); background:transparent; font-size:18px; }
.apf-workspace .apf-nav button:hover:not(:disabled) { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-workspace .apf-nav button[aria-current="page"] { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-record.selected { outline:1px solid var(--border-color,#4e4e4e); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-main { display:flex; flex:1; flex-direction:column; gap:10px; min-width:0; min-height:0; overflow:auto; }
.apf-toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.apf-toolbar, .apf-error, .apf-state, .apf-disabled, .apf-records, .apf-pagination, .apf-details { margin-left:10px; margin-right:10px; }
.apf-heading { display:flex; flex:1 0 100%; align-items:center; gap:8px; }
.apf-heading h1 { margin:4px 0; color:var(--input-text,#ddd); font-size:16px; font-weight:600; line-height:1.25; }
.apf-heading-actions { display:flex; align-items:center; gap:6px; margin-left:auto; }
.apf-import { display:flex; align-items:center; }
.apf-management-tabs { display:flex; flex:1 0 100%; gap:4px; padding:0 0 4px; border-bottom:1px solid var(--border-color,#4e4e4e); }
.apf-workspace .apf-management-tabs button { background:transparent; color:var(--descrip-text,#999); }
.apf-workspace .apf-management-tabs button:hover:not(:disabled), .apf-workspace .apf-management-tabs button[aria-current="page"] { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-toolbar select { max-width:100%; height:32px; padding:0 10px; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; color:var(--input-text,#ddd); background:var(--comfy-input-bg,#222); font:inherit; font-size:12px; }
.apf-search { display:flex; flex:1 1 145px; min-width:0; height:36px; align-items:center; gap:8px; padding:0 10px; border:1px solid var(--border-color,#4e4e4e); border-radius:9px; color:var(--descrip-text,#999); background:var(--comfy-input-bg,#222); }
.apf-search:focus-within { border-color:var(--input-text,#ddd); }
.apf-search input { width:100%; min-width:0; border:0; outline:0; color:var(--input-text,#ddd); background:transparent; font:inherit; font-size:12px; }
.apf-search input::placeholder { color:var(--descrip-text,#999); }
.apf-layout { display:flex; gap:2px; padding:2px; border-radius:9px; background:var(--comfy-input-bg,#222); }
.apf-workspace .apf-layout button { min-height:28px; padding:6px 8px; border-radius:7px; background:transparent; color:var(--descrip-text,#999); }
.apf-workspace .apf-layout button:hover:not(:disabled), .apf-workspace .apf-layout button[aria-pressed="true"] { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-records.grid { display:grid; grid-template-columns:1fr; gap:8px; }
.apf-records.list { display:flex; flex-direction:column; gap:6px; }
.apf-workspace .apf-record { display:flex; width:100%; min-height:68px; justify-content:flex-start; gap:12px; padding:10px; border:1px solid var(--border-color,#4e4e4e); text-align:left; white-space:normal; background:var(--comfy-menu-secondary-bg,#292929); }
.apf-record span:last-child { display:flex; flex-direction:column; gap:4px; min-width:0; }
.apf-record small { color:var(--descrip-text,#999); }
.apf-record-icon { font-size:22px; }
.apf-pagination { display:flex; gap:8px; align-items:center; margin-top:auto; }
.apf-pagination span { margin-right:auto; }
.apf-details { padding:10px; overflow:auto; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-bg,#353535); }
.apf-details pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:11px; }
.apf-error { padding:10px; border:1px solid #b44; border-radius:8px; color:#ffaaaa; background:var(--comfy-menu-secondary-bg,#292929); }
.apf-state, .apf-disabled { padding:16px 4px; color:var(--descrip-text,#999); }
.apf-placeholder { padding:12px; }
.apf-placeholder h1 { margin:4px 0 12px; font-size:17px; }
.apf-placeholder p { color:var(--descrip-text,#999); }
.apf-editor { position:absolute; inset:6px; z-index:2; overflow:auto; padding:12px; border:1px solid var(--border-color,#4e4e4e); border-radius:10px; background:var(--comfy-menu-bg,#353535); box-shadow:0 8px 40px #0009; }
.apf-editor form { display:grid; grid-template-columns:1fr; gap:10px; }
.apf-editor h2, .apf-editor fieldset, .apf-form-actions { grid-column:1/-1; }
.apf-editor label { display:flex; flex-direction:column; gap:4px; }
.apf-editor input, .apf-editor select, .apf-editor textarea { width:100%; min-height:36px; padding:8px 10px; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; color:var(--input-text,#ddd); background:var(--comfy-input-bg,#222); font:inherit; }
.apf-editor fieldset { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.apf-form-actions { display:flex; justify-content:flex-end; gap:8px; }
.apf-workspace .apf-form-actions button[type="submit"] { background:var(--primary-bg,#236692); color:var(--primary-fg,#fff); }
.apf-workspace .apf-form-actions button[type="submit"]:hover:not(:disabled) { background:var(--primary-hover-bg,#3485bb); }
</style>

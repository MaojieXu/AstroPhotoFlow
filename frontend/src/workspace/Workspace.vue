<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { z } from 'zod'
import {
  assetSchema, capabilitiesSchema, captureProfileSchema, datasetReferenceSchema, datasetSchema, libraryEntriesRemoveRequestSchema,
  libraryEntriesRemoveSchema,
  datasetVersionSchema, datasetMemberParametersUpdateSchema, equipmentSchema, importAcceptedSchema, pageSchema, projectAssetReferenceSchema,
  projectSchema, libraryItemSchema, taskSchema, type Asset
} from '../assets/contracts'
import { ApiClientError } from '../assets/client'
import { assetApi } from '../assets/host-client'
import type { ZodType } from 'zod'
import { useWorkspaceStore, type WorkspaceSection } from './store'
import DatasetEditor from './DatasetEditor.vue'
import ImportDialog from './ImportDialog.vue'
import ImportTasks from './ImportTasks.vue'
import LibraryFilterPanel from './LibraryFilterPanel.vue'
import InlineField from './InlineField.vue'
import InlineMultiSelect from './InlineMultiSelect.vue'
import ParameterModeField from './ParameterModeField.vue'
import { firstLevelImportFiles } from './folder-selection'

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
type LibraryFilters = Record<string, string[] | string>
function emptyFilters(): LibraryFilters { return {} }
const activeFilters = ref<LibraryFilters>(emptyFilters())
const filterPanelOpen = ref(false)
const filterButton = ref<HTMLButtonElement>()
const activeFilterCount = computed(() => Object.values(activeFilters.value).filter(value =>
  Array.isArray(value) ? value.length > 0 : value !== ''
).length)
const viewingProjectAssets = ref(false)
const viewingProjectDatasets = ref(false)
const addingProjectAssets = ref(false)
const addingProjectDatasets = ref(false)
const importDialogOpen = ref(false)
const importFiles = ref<File[]>([])
const filePicker = ref<HTMLInputElement>()
const folderPicker = ref<HTMLInputElement>()
const importMenuOpen = ref(false)
const importCreatesDataset = ref(false)
const importDatasetName = ref('')
const libraryViewMode = ref<'simple' | 'detail'>('simple')
const librarySort = ref({by: 'created_at', order: 'desc' as 'asc' | 'desc'})
const bulkSelectMode = ref(false)
const bulkSelection = ref<Set<string>>(new Set())
const bulkDeleteBusy = ref(false)
const bulkDeleteNotice = ref('')
const progressRefreshToken = ref(0)
const uploadProgress = ref<Record<string, { loaded: number; total: number }>>({})
const watchedTaskIds = ref<string[]>([])
type ImportTask = ReturnType<typeof taskSchema.parse>
const datasetEditorId = ref<string>()
const datasetPendingIds = ref<string[]>([])
const previewUrl = ref<string>()
const previewError = ref('')
const previewUrls = ref<Record<string,string>>({})
const editorType = ref<EditorType>()
const editingId = ref<string>()
const draft = ref<RecordData>({})
const originalDraft = ref('')
const saving = ref(false)
const savingInline = ref(0)
const inlineSaveFailures = ref<Record<string,string>>({})
const inlineSaveFailure = computed(() => Object.values(inlineSaveFailures.value).at(-1) ?? '')
const relatedEquipment = ref<RecordData[]>([])
const relatedEquipmentLoading = ref(false)
const relatedEquipmentError = ref('')
const relatedEquipmentReady = ref(false)
const relatedProfiles = ref<RecordData[]>([])
const relatedProfilesLoading = ref(false)
const relatedProfilesError = ref('')
const relatedProfilesReady = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | undefined
let recordsLoadPending = false
let previewRequestId = 0

const dirty = computed(() => editorType.value !== undefined && JSON.stringify(draft.value) !== originalDraft.value)
const isAssetSection = computed(() =>
  store.section === 'calibration' || viewingProjectAssets.value ||
  (activeArea.value === 'library' && !viewingProjectDatasets.value)
)
const isAssetTable = computed(() => (activeArea.value === 'library' && !viewingProjectDatasets.value) ||
  store.section === 'calibration' || viewingProjectAssets.value)
const isDatasetTable = computed(() => store.section === 'projects' && viewingProjectDatasets.value)
const isLibraryItemsView = computed(() => activeArea.value === 'library' && !viewingProjectAssets.value && !viewingProjectDatasets.value)
const pageSelectionKeys = computed(() => rows.value.map(row => bulkKey(row)))
const pageAllSelected = computed(() => pageSelectionKeys.value.length > 0 && pageSelectionKeys.value.every(key => bulkSelection.value.has(key)))
const pagePartiallySelected = computed(() => pageSelectionKeys.value.some(key => bulkSelection.value.has(key)) && !pageAllSelected.value)
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
const frameClasses = ['subframe', 'masterframe', 'video']
const cfaChoices=[
  {value:'',label:'未指定'},{value:'MONO',label:'无 CFA（单色）'},
  {value:'RGGB',label:'RGGB'},{value:'BGGR',label:'BGGR'},{value:'GRBG',label:'GRBG'},{value:'GBRG',label:'GBRG'},
  {value:'XTRANS',label:'X-Trans 6×6'},{value:'QUAD_BAYER',label:'Quad Bayer'}
]
const equipmentKinds = ['camera', 'optical_system', 'filter']
function specKind(field:InputField):'number'|'select'|'text'{
  return field.key==='cfa_pattern'||field.options?'select':field.type==='number'?'number':'text'
}
function specChoices(field:InputField){
  if(field.key==='cfa_pattern')return cfaChoices
  if(field.options)return [{value:'',label:'未指定'},...field.options.map(value=>({value,label:field.key==='sensor_mode'?({mono:'单色',color:'彩色'} as Record<string,string>)[value]??value:value}))]
  return []
}
function specDisplay(field:InputField,value:unknown){
  if(value===null||value===undefined||value==='')return '未指定'
  if(field.key==='cfa_pattern')return cfaLabel(value)
  if(field.options)return specChoices(field).find(choice=>choice.value===String(value))?.label??String(value)
  return String(value)
}

function apiPath(path: string, params: Record<string, string | number | string[] | undefined> = {}) {
  const query = new URLSearchParams()
  query.set('limit', String(store.pageSize === 'all' ? 200 : store.pageSize))
  query.set('offset', String(store.offset))
  if (store.query) query.set('q', store.query)
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) value.forEach(item => query.append(key, item))
    else if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return '/astrophotoflow/api/v1' + path + '?' + query.toString()
}

async function loadWorkspacePage<T>(path: string, schema: ZodType<T>, params: Record<string, string | number | string[] | undefined> = {}) {
  const limit = store.pageSize === 'all' ? 200 : store.pageSize
  const getPage = (offset: number) => assetApi.get(
    apiPath(path, {...params, limit, offset}), pageSchema(schema)
  )
  const first = await getPage(store.pageSize === 'all' ? 0 : store.offset)
  if (store.pageSize !== 'all') return first
  const items = [...first.items]
  for (let offset = first.limit; offset < first.total; offset += first.limit) {
    const page = await getPage(offset)
    items.push(...page.items)
  }
  return {...first, items, offset: 0}
}

function libraryFilterParams(filters: LibraryFilters) {
  const names:Record<string,string>={
    frame_classes:'frame_class',frame_types:'frame_type',roles:'role',
    exposure_seconds_min:'exposure_min',exposure_seconds_max:'exposure_max',
    integration_seconds_min:'integration_min',integration_seconds_max:'integration_max',
    sensor_temperature_c_min:'temperature_min',sensor_temperature_c_max:'temperature_max'
  }
  return Object.fromEntries(Object.entries(filters).map(([key,value])=>[names[key]??key,value])) as Record<string,string|string[]>
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

async function loadRelatedEquipment(force=false) {
  if(relatedEquipmentLoading.value||(!force&&relatedEquipmentReady.value))return
  relatedEquipmentLoading.value=true
  relatedEquipmentError.value=''
  try{
    relatedEquipment.value=await loadAll('/equipment',equipmentSchema)
    relatedEquipmentReady.value=true
  }catch(cause){
    relatedEquipmentError.value=errorText(presentError(cause))
    relatedEquipmentReady.value=false
  }finally{relatedEquipmentLoading.value=false}
}

function equipmentChoiceMessage(kind:string){
  if(relatedEquipmentLoading.value)return '正在读取设备列表…'
  if(relatedEquipmentError.value)return relatedEquipmentError.value
  const names:Record<string,string>={camera:'相机',optical_system:'成像系统',filter:'滤镜'}
  return relatedEquipment.value.some(item=>item.kind===kind)?'':'尚未登记'+(names[kind]??'设备')+'。请先在设置→设备中添加。'
}

function equipmentChoices(kind:string){
  return relatedEquipment.value.filter(item=>item.kind===kind).map(item=>({
    value:item.id,label:item.name+(item.status==='archived'?' · 已归档':''),disabled:relatedEquipmentLoading.value||Boolean(relatedEquipmentError.value)
  }))
}

function profileChoices(){
  return relatedProfiles.value.map(profile=>({
    value:profile.id,label:profile.name+(profile.status==='archived'?' · 已归档':''),disabled:relatedProfilesLoading.value||Boolean(relatedProfilesError.value)
  }))
}

function profileChoiceMessage(){
  if(relatedProfilesLoading.value)return '正在读取拍摄设置…'
  if(relatedProfilesError.value)return relatedProfilesError.value
  return relatedProfiles.value.length?'':'尚未创建拍摄设置。'
}

async function loadRelatedProfiles(force=false){
  if(relatedProfilesLoading.value||(!force&&relatedProfilesReady.value))return
  relatedProfilesLoading.value=true
  relatedProfilesError.value=''
  try{relatedProfiles.value=await loadAll('/capture-profiles',captureProfileSchema);relatedProfilesReady.value=true}
  catch(cause){relatedProfilesError.value=errorText(presentError(cause));relatedProfilesReady.value=false}
  finally{relatedProfilesLoading.value=false}
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
  if(savingInline.value||inlineSaveFailure.value) {
    recordsLoadPending = true
    loadGeneration++
    if(inlineSaveFailure.value)loading.value=false
    return
  }
  if(bulkDeleteBusy.value)return
  const generation = ++loadGeneration
  loading.value = true
  error.value = undefined
  try {
    let loadedRows: RecordData[]
    let loadedTotal: number
    if (store.section === 'library' && !viewingProjectAssets.value && !viewingProjectDatasets.value) {
      const page = await loadWorkspacePage('/library/items', libraryItemSchema, {
        ...libraryFilterParams(activeFilters.value), sort_by: librarySort.value.by, order: librarySort.value.order
      })
      loadedRows = page.items.map(item => item.entry_type === 'asset'
        ? {...item.asset, entry_type: 'asset', import_issue: item.import_issue}
        : {...item.dataset, dataset: item.dataset, version: item.version, entry_type: 'dataset', import_issue: item.import_issue})
      loadedTotal = page.total
    } else if (store.section === 'calibration' || addingProjectAssets.value) {
      const role = store.section === 'calibration' ? 'calibration' : roleFilter.value
      const params: Record<string, string> = {}
      if (role) params.role = role
      if (frameTypeFilter.value) params.frame_type = frameTypeFilter.value
      const page = await loadWorkspacePage('/library/assets', assetSchema, params)
      loadedRows = page.items
      loadedTotal = page.total
    } else if (viewingProjectAssets.value && store.activeProjectId) {
      const page = await loadWorkspacePage(
        '/projects/' + store.activeProjectId + '/assets', projectAssetReferenceSchema,
        {role: roleFilter.value, frame_type: frameTypeFilter.value}
      )
      loadedRows = page.items
      loadedTotal = page.total
    } else if (store.section === 'projects' && viewingProjectDatasets.value && store.activeProjectId) {
      const isAdding = addingProjectDatasets.value
      const path = isAdding ? '/datasets' : '/projects/' + store.activeProjectId + '/datasets'
      const schema = isAdding ? datasetSchema : datasetReferenceSchema
      const page = await loadWorkspacePage(path, schema as ZodType<any>, isAdding ? {status: statusFilter.value} : {})
      loadedRows = page.items
      loadedTotal = page.total
    } else if (store.section === 'projects') {
      const page = await loadWorkspacePage('/projects', projectSchema, {status: statusFilter.value})
      loadedRows = page.items
      loadedTotal = page.total
    } else if (store.section === 'equipment') {
      const page = await loadWorkspacePage('/equipment', equipmentSchema, {status: statusFilter.value})
      loadedRows = page.items
      loadedTotal = page.total
    } else {
      const page = await loadWorkspacePage('/capture-profiles', captureProfileSchema, {status: statusFilter.value})
      loadedRows = page.items
      loadedTotal = page.total
    }
    if (isDatasetTable.value) {
      loadedRows = await Promise.all(loadedRows.map(async row => {
        if (row.version?.members || !row.current_version_id) return row
        const version = await assetApi.get(
          '/astrophotoflow/api/v1/datasets/' + row.id + '/versions/' + row.current_version_id,
          datasetVersionSchema
        )
        return {...row, version}
      }))
    }
    if (generation !== loadGeneration) return
    rows.value = loadedRows
    total.value = loadedTotal
    selected.value = rows.value.find(row => row.id === selected.value?.id)
    for (const url of Object.values(previewUrls.value)) URL.revokeObjectURL(url)
    previewUrls.value = {}
    void loadThumbnails(rows.value, generation)
  } catch (cause) {
    if (generation === loadGeneration) {
      error.value = presentError(cause)
      rows.value = []
      total.value = 0
      selected.value = undefined
      for (const url of Object.values(previewUrls.value)) URL.revokeObjectURL(url)
      previewUrls.value = {}
    }
  } finally {
    if (generation === loadGeneration) loading.value = false
  }
}

async function loadThumbnails(items: RecordData[], generation: number) {
  for (const row of items) {
    try {
      const member = await previewMember(row)
      if (!member) continue
      const blob = await assetApi.getBlob(
        '/astrophotoflow/api/v1/library/assets/' + member.asset.id + '/versions/' + member.version.id + '/previews/thumbnail'
      )
      const url = URL.createObjectURL(blob)
      if (generation !== loadGeneration) URL.revokeObjectURL(url)
      else previewUrls.value[row.id] = url
    } catch {
      // Unsupported or missing previews remain unavailable in the row.
    }
  }
}

async function previewMember(row: RecordData): Promise<{asset: Asset; version: RecordData}|undefined> {
  if (row.version?.members) {
    const member = row.version.members[0]
    return member ? {asset: member.asset, version: member.version} : undefined
  }
  if (row.current_version_id && row.member_count != null) {
    const version = await assetApi.get(
      '/astrophotoflow/api/v1/datasets/' + row.id + '/versions/' + row.current_version_id,
      datasetVersionSchema
    )
    const member = version.members[0]
    return member ? {asset: member.asset, version: member.version} : undefined
  }
  if (row.asset && row.version) return {asset: row.asset, version: row.version}
  const asset = row.asset ?? row
  return asset.current_version ? {asset, version: asset.current_version} : undefined
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

async function waitForInlineSave(){
  while(savingInline.value)await new Promise(resolve=>setTimeout(resolve,25))
  return !inlineSaveFailure.value
}

async function selectSection(section: WorkspaceSection) {
  if (dirty.value && !window.confirm('当前表单有未保存修改。放弃修改并切换吗？')) return
  if(!await waitForInlineSave())return
  editorType.value = undefined
  editingId.value = undefined
  datasetEditorId.value = undefined
  datasetPendingIds.value = []
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = false
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  store.selectSection(section)
  if (section === 'projects' || section === 'equipment' || section === 'capture-profiles') {
    lastManagementSection.value = section
  }
  selected.value = undefined
  loadRecords()
}

async function selectArea(area: WorkspaceArea) {
  if (dirty.value && !window.confirm('当前表单有未保存修改。放弃修改并切换吗？')) return
  if(!await waitForInlineSave())return
  editorType.value = undefined
  editingId.value = undefined
  datasetEditorId.value = undefined
  datasetPendingIds.value = []
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = false
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  selected.value = undefined
  filterPanelOpen.value = false
  store.query = ''
  store.offset = 0
  store.activeProjectId = null
  store.activeProjectRevision = null
  statusFilter.value = 'active'
  roleFilter.value = ''
  frameTypeFilter.value = ''
  activeFilters.value = emptyFilters()
  activeArea.value = area
  if (area === 'library') {
    store.selectSection('library')
    void loadRelatedEquipment(true)
    loadRecords()
  } else if (area === 'settings') {
    lastManagementSection.value = 'projects'
    store.selectSection('projects')
    loadRecords()
  } else {
    loadGeneration++
    loading.value = false
    error.value = undefined
  }
}

function startImport(kind:'files'|'folder') {
  importMenuOpen.value=false
  if(kind==='folder')folderPicker.value?.click()
  else filePicker.value?.click()
}

function applyFilters(filters: LibraryFilters) {
  activeFilters.value=Object.fromEntries(Object.entries(filters).filter(([,value])=>Array.isArray(value)?value.length>0:value!==''))
  clearBulkSelection()
  store.offset = 0
  void loadRecords()
}

function filesChosen(event: Event) {
  const input = event.target as HTMLInputElement
  importFiles.value = Array.from(input.files ?? [])
  importCreatesDataset.value=false
  importDatasetName.value=''
  error.value=undefined
  input.value = ''
  if (importFiles.value.length) importDialogOpen.value = true
}

function foldersChosen(event: Event) {
  const input = event.target as HTMLInputElement
  const files=Array.from(input.files??[])
  input.value=''
  if(!files.length)return
  error.value=undefined
  const first=files.find(file=>file.webkitRelativePath)
  const selectedFolder=first?.webkitRelativePath.split('/')[0]??''
  importFiles.value=firstLevelImportFiles(files)
  importCreatesDataset.value=true
  importDatasetName.value=selectedFolder
  if(importFiles.value.length)importDialogOpen.value=true
  else{error.value=new ApiClientError('所选文件夹第一层没有可导入的受支持文件。','contract')}
}

function importSubmitted(taskId: string) {
  importDialogOpen.value = false
  watchedTaskIds.value = [...watchedTaskIds.value, taskId]
  progressRefreshToken.value++
  clearBulkSelection()
  void loadRecords()
}

function importTaskCompleted(taskId: string) {
  watchedTaskIds.value=watchedTaskIds.value.filter(id=>id!==taskId)
  clearBulkSelection()
  void loadRecords()
}
function datasetInlineSaving(active:boolean){savingInline.value=Math.max(0,savingInline.value+(active?1:-1))}
function datasetInlineFailure(message:string){
  const key='dataset-editor:'+datasetEditorId.value
  if(message)inlineSaveFailures.value={...inlineSaveFailures.value,[key]:message}
  else clearInlineSaveFailure(key)
}

function updateUploadProgress(taskId: string, _index: number, loaded: number, total: number) {
  uploadProgress.value = { ...uploadProgress.value, [taskId]: { loaded, total } }
}

function uploadTaskProgress(task: ImportTask) {
  const report = task.report as Record<string, any>
  const upload = uploadProgress.value[task.id]
  if (!report.upload_complete && upload) return upload.total ? Math.round(upload.loaded * 100 / upload.total) : 100
  if (!report.upload_complete && report.upload_manifest) {
    const totalBytes = report.upload_files.reduce((sum: number, file: { size: number }) => sum + file.size, 0)
    const received = report.upload_files.reduce((sum: number, file: { received: number }) => sum + file.received, 0)
    return totalBytes ? Math.round(received * 100 / totalBytes) : 0
  }
  return task.items_total ? Math.min(100, Math.round(task.items_completed * 100 / task.items_total)) : 0
}

function uploadTaskLabel(task: ImportTask) {
  const report = task.report as Record<string, any>
  if (task.status === 'failed') return String(task.error?.message ?? '导入失败。')
  if (report.upload_manifest && !report.upload_complete) return '上传中 · ' + task.items_total + ' 个文件'
  if (task.status === 'interrupted') return '已暂停，进度已保存 · ' + task.items_completed + ' / ' + task.items_total + ' 项'
  return '处理中 · ' + task.items_completed + ' / ' + task.items_total + ' 项'
}

function refreshLibrary() {
  if(savingInline.value||inlineSaveFailure.value)return
  clearBulkSelection()
  void loadRelatedEquipment(true)
  progressRefreshToken.value++
  void loadRecords()
}

async function saveInlineField(rowOrField: RecordData | string, fieldOrValue: string | number | null, nextValue?: string | number | null) {
  const row=typeof rowOrField==='string'?selected.value:rowOrField
  const field=typeof rowOrField==='string'?rowOrField:String(fieldOrValue)
  let value=typeof rowOrField==='string'?fieldOrValue:nextValue
  if(!row)return
  const failureKey=inlineFailureKey(row,field)
  if(field==='parameter_mode'&&value==='')value=row.asset||row.scope==='shared'||row.entry_type==='dataset'?'standard':null
  if(value===''&&field!=='name')value=null
  savingInline.value++
  clearInlineSaveFailure(failureKey)
  try { await performInlineFieldSave(row,field,value??null) }
  catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:'字段保存失败。');throw cause}
  finally { finishInlineSave() }
}

function selectedFieldSave(field:string){
  const row=selected.value!
  return (value:string|number|null)=>saveInlineField(row,field,value)
}
function selectedParameterSave(){
  const row=selected.value!
  return (changes:RecordData)=>saveParameterGroup(row,changes)
}
function selectedBinSave(){
  const row=selected.value!
  return (value:string|number|null)=>saveBin(row,value)
}
function selectedProfileSave(){
  const row=selected.value!
  return (profileIds:string[])=>saveProjectProfilesInline(row,profileIds)
}

function syncEditingDraft(row:RecordData,updated:RecordData){
  if(editingId.value!==row.id||!editorType.value)return
  const asset=row.asset??(row.scope==='shared'?row:undefined)
  if(asset){
    Object.assign(draft.value,updated.classification??{},updated.parameters??{}, {
      name:updated.name,notes:updated.notes,status:updated.status,revision:updated.revision
    })
  }else if(row.dataset){
    Object.assign(draft.value,updated,{revision:updated.revision})
  }else if(store.section==='equipment'){
    Object.assign(draft.value,updated,{specs:{...draft.value.specs,...updated.specs},revision:updated.revision})
  }else{
    Object.assign(draft.value,updated,{revision:updated.revision})
    if(store.section==='capture-profiles'&&('binning_x' in updated||'binning_y' in updated))draft.value.binning_value=binEditValue(updated)
  }
  originalDraft.value=JSON.stringify(draft.value)
}

function editorRow(){
  return editingId.value?rows.value.find(item=>item.id===editingId.value):undefined
}

async function saveEditorInline(field:string,value:string|number|null){
  const row=editorRow()
  if(!row)throw new Error('当前编辑记录已不存在。')
  await saveInlineField(row,field,value)
}

async function saveEditorBin(value:string|number|null){
  const row=editorRow()
  if(!row)throw new Error('当前编辑记录已不存在。')
  await saveBin(row,value)
}

async function saveEditorParameterGroup(changes:RecordData){
  const row=editorRow()
  if(!row)throw new Error('当前编辑记录已不存在。')
  await saveParameterGroup(row,changes)
}

async function saveEditorProjectProfiles(profileIds:string[]){
  const row=editorRow()
  if(!row)throw new Error('当前编辑记录已不存在。')
  await saveProjectProfilesInline(row,profileIds)
}

async function performInlineFieldSave(row: RecordData, field: string, value: string | number | null) {
  if(field==='parameter_mode'&&value==='')value=row.asset||row.scope==='shared'||row.entry_type==='dataset'?'standard':null
  if(value===''&&field!=='name')value=null
  if(row.entry_type==='dataset'&&['camera_id','optical_system_id','filter_id','parameter_mode','iso','gain','offset','exposure_seconds','integration_seconds','sensor_temperature_c','cfa_pattern'].includes(field)){
    return saveDatasetParameter(row,field,value)
  }
  if(row.entry_type==='dataset'&&['frame_class','frame_type'].includes(field))return saveDatasetClassification(row,field,value)
  const asset = row.asset ?? (row.scope === 'shared' ? row : undefined)
  let path: string
  let schema: ZodType<any>
  let payload: RecordData
  if (asset) {
    path='/library/assets/'+asset.id;schema=assetSchema
    if (['frame_class','frame_type'].includes(field)) payload={base_revision:asset.revision,classification:{[field]:value}}
    else if (['camera_id','optical_system_id','filter_id','parameter_mode','iso','gain','offset','exposure_seconds','integration_seconds','sensor_temperature_c','binning_x','binning_y','cfa_pattern'].includes(field)) payload={base_revision:asset.revision,parameters:{[field]:value}}
    else payload={base_revision:asset.revision,[field]:value}
  } else if (row.dataset) {
    path='/datasets/'+row.dataset.id;schema=datasetSchema;payload={base_revision:row.dataset.revision,[field]:value}
  } else if (store.section==='projects') {
    path='/projects/'+row.id;schema=projectSchema;payload={base_revision:row.revision,[field]:value}
  } else if (store.section==='equipment') {
    path='/equipment/'+row.id;schema=equipmentSchema
    const spec=field.startsWith('specs.')?specFields[row.kind]?.find(item=>item.key===field.slice(6)):undefined
    const fieldValue=spec?.type==='number'?(value==null||value===''?null:Number(value)):value
    payload=field.startsWith('specs.')
      ? {base_revision:row.revision,kind:row.kind,specs:{[field.slice(6)]:fieldValue}}
      : {base_revision:row.revision,kind:row.kind,[field]:value}
  } else {
    path='/capture-profiles/'+row.id;schema=captureProfileSchema;payload={base_revision:row.revision,[field]:value}
  }
  const updated=await assetApi.send('/astrophotoflow/api/v1'+path,schema,'PATCH',payload)
  const replace=(item:RecordData)=>{
    if(asset)return row.asset?{...item,asset:updated}:{...item,...updated,entry_type:item.entry_type,import_issue:item.import_issue}
    if(row.dataset)return row.id===row.dataset.id?{...item,...updated,dataset:updated}:{...item,dataset:updated}
    return updated
  }
  rows.value=rows.value.map(item=>item.id===row.id?replace(item):item)
  const current=selected.value
  if(current&&current.id===row.id)selected.value=replace(current)
  if(store.activeProjectId===row.id)store.activeProjectRevision=updated.revision
  syncEditingDraft(row,updated)
}

async function saveRowField(row: RecordData, field: string, value: string | number | null) {
  await saveInlineField(row,field,value)
}

async function saveDatasetParameter(row:RecordData,field:string,value:string|number|null){
  return saveDatasetParameters(row,{[field]:value})
}

async function saveDatasetClassification(row:RecordData,field:string,value:string|number|null){
  return updateDatasetMembers(row,{classification:{[field]:value===''?null:value}})
}

async function saveDatasetParameters(row:RecordData,parameters:RecordData){
  return updateDatasetMembers(row,{parameters})
}

async function saveParameterGroup(row:RecordData,parameters:RecordData){
  const failureKey=inlineFailureKey(row,'parameter_mode')
  savingInline.value++
  clearInlineSaveFailure(failureKey)
  try{
    if(row.entry_type==='dataset')return await saveDatasetParameters(row,parameters)
    const asset=row.asset??(row.scope==='shared'?row:undefined)
    if(asset){
      const updated=await assetApi.send('/astrophotoflow/api/v1/library/assets/'+asset.id,assetSchema,'PATCH',{
        base_revision:asset.revision,parameters
      })
      const replace=(item:RecordData)=>row.asset?{...item,asset:updated}:{...item,...updated,entry_type:item.entry_type,import_issue:item.import_issue}
      rows.value=rows.value.map(item=>item.id===row.id?replace(item):item)
      const current=selected.value
      if(current&&current.id===row.id)selected.value=replace(current)
      if(editingId.value===row.id){Object.assign(draft.value,updated.parameters,{revision:updated.revision});originalDraft.value=JSON.stringify(draft.value)}
      return
    }
    if(store.section==='capture-profiles'){
      const updated=await assetApi.send('/astrophotoflow/api/v1/capture-profiles/'+row.id,captureProfileSchema,'PATCH',{
        base_revision:row.revision,...parameters
      })
      rows.value=rows.value.map(item=>item.id===row.id?updated:item)
      if(selected.value?.id===row.id)selected.value=updated
      if(editingId.value===row.id){Object.assign(draft.value,updated,{revision:updated.revision});originalDraft.value=JSON.stringify(draft.value)}
      return
    }
    throw new Error('当前记录不支持拍摄参数编辑。')
  }catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:'参数保存失败。');throw cause}
  finally{finishInlineSave()}
}

async function updateDatasetMembers(row:RecordData,changes:RecordData){
  const members:RecordData[]=row.version?.members??[]
  const dataset=row.dataset
  if(!dataset?.id||!row.version?.id||!members.length)throw new Error('此数据集没有可修改的成员。')
  const updated=await assetApi.send(
    '/astrophotoflow/api/v1/datasets/'+dataset.id+'/member-parameters',
    datasetMemberParametersUpdateSchema,'PATCH',{
      base_revision:dataset.revision,base_version_id:row.version.id,
      members:members.map(member=>({asset_id:member.asset.id,revision:member.asset.revision})),
      ...changes
    }
  )
  const byId=new Map(updated.assets.map(asset=>[asset.id,asset]))
  const nextRow={...row,dataset:{...dataset,revision:updated.revision},version:{...row.version,members:members.map(member=>({...member,asset:byId.get(member.asset.id)??member.asset}))}}
  rows.value=rows.value.map(item=>item.id===row.id?nextRow:item)
  if(selected.value?.id===row.id)selected.value=nextRow
}

function binValue(parameters: RecordData) {
  const x=parameters.binning_x,y=parameters.binning_y
  if(x==null&&y==null)return null
  return x===y?'Bin'+x:'Bin'+String(x??'—')+'×'+String(y??'—')
}
function binEditValue(parameters:RecordData){
  const x=parameters.binning_x,y=parameters.binning_y
  return x==null&&y==null?'':x===y&&x>=1&&x<=16?'Bin'+x:`legacy:${x??''}x${y??''}`
}
function binEditChoices(parameters:RecordData){
  const current=binEditValue(parameters)
  return [{value:'',label:'未指定'},...Array.from({length:16},(_,i)=>({value:'Bin'+(i+1),label:'Bin'+(i+1)})),
    ...(current.startsWith('legacy:')?[{value:current,label:binValue(parameters)+'（现有值）'}]:[])]
}
function datasetBinChoices(row:RecordData){
  const current=datasetRawValue(row,member=>binEditValue(member.asset?.parameters??{}))
  return [{value:'',label:'未指定'},...(current==='mixed'?[{value:'mixed',label:'混合',disabled:true}]:[]),...Array.from({length:16},(_,i)=>({value:'Bin'+(i+1),label:'Bin'+(i+1)})),
    ...(current.startsWith('legacy:')?[{value:current,label:current.replace(/^legacy:/,'Bin').replace('x','×')+'（现有值）'}]:[])]
}
function datasetRawValue(row:RecordData,getValue:(member:RecordData)=>unknown){
  const values=datasetMembers(row).map(getValue)
  const known=values.filter(value=>value!==null&&value!==undefined&&value!=='')
  if(!known.length)return ''
  if(known.length<values.length||new Set(known.map(value=>JSON.stringify(value))).size>1)return 'mixed'
  return String(known[0])
}
function datasetParameterRaw(row:RecordData,key:'iso'|'gain'|'offset'){
  const values=datasetMembers(row).map(member=>member.asset?.parameters?.[key])
  const known=values.filter(value=>value!==null&&value!==undefined&&value!=='')
  if(!known.length)return ''
  if(new Set(known.map(value=>JSON.stringify(value))).size>1)return 'mixed'
  if(known.length<values.length)return 'partial'
  return known[0] as number
}
function parameterModeValue(row:RecordData):ParameterModeFieldValue{
  if(row.entry_type==='dataset'){
    const mode=datasetParameterMode(row)
    return {
      parameter_mode:mode||'standard',
      iso:datasetParameterRaw(row,'iso'),gain:datasetParameterRaw(row,'gain'),offset:datasetParameterRaw(row,'offset')
    }
  }
  if(!row.asset&&store.section==='capture-profiles')return {
    parameter_mode:row.parameter_mode,iso:row.iso,gain:row.gain,offset:row.offset
  }
  const parameters=rowParameters(row)
  return {parameter_mode:parameters.parameter_mode,iso:parameters.iso,gain:parameters.gain,offset:parameters.offset}
}
type ParameterModeFieldValue={parameter_mode:string|null|undefined;iso:number|string|null|undefined;gain:number|string|null|undefined;offset:number|string|null|undefined}
function parameterModeDisplay(row:RecordData){
  const value=parameterModeValue(row)
  const mode=value.parameter_mode
  if(mode==='mixed')return '混合'
  if(mode==='iso')return 'ISO · '+(row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.iso):captureValue(value.iso))
  if(mode==='gain'){
    const gain=row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.gain):captureValue(value.gain)
    const offset=row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.offset):captureValue(value.offset)
    return 'Gain · '+gain+' / Offset · '+offset
  }
  return '未指定'
}
function captureProfileModeDisplay(row:RecordData){
  if(row.parameter_mode==='iso')return 'ISO · '+captureValue(row.iso)
  if(row.parameter_mode==='gain')return 'Gain · '+captureValue(row.gain)+' / Offset · '+captureValue(row.offset)
  return '未指定'
}
function displayTemperature(value:unknown){
  if(value===null||value===undefined||value==='')return '—'
  const n=Number(value)
  if(!Number.isFinite(n))return String(value)
  const match=String(value).match(/^([+-]?)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i)
  if(!match)return n.toFixed(2)
  const digits=(match[2]+(match[3]??'')).replace(/^0+(?=\d)/,'')
  const decimalPlaces=(match[3]??'').length-Number(match[4]??0)
  const retained=digits.length-decimalPlaces+2
  const cents=retained<=0?0n:retained>=digits.length
    ?BigInt(digits)*10n**BigInt(retained-digits.length)
    :BigInt(digits.slice(0,retained))
  const sign=match[1]==='-'&&cents>0n?'-':''
  return sign+(cents/100n).toString()+'.'+(cents%100n).toString().padStart(2,'0')
}
function datasetTemperature(row:RecordData){
  const members=datasetMembers(row)
  const known=members.map(member=>member.asset?.parameters?.sensor_temperature_c).filter((value):value is number=>value!==null&&value!==undefined)
  if(!known.length)return '未指定'
  const displayed=[...new Set(known.map(displayTemperature))]
  if(displayed.length>1)return '混合'
  return displayed[0]+(known.length<members.length?'（部分缺失）':'')+' °C'
}
function inlineFailureKey(row:RecordData|undefined,field:string){return (row?.id??'unknown')+':'+field}
function editorInlineFailureKey(field:string){return inlineFailureKey(editorRow(),field)}
function setInlineSaveFailure(key:string,message:string){inlineSaveFailures.value={...inlineSaveFailures.value,[key]:message}}
function clearInlineSaveFailure(key:string){
  if(!(key in inlineSaveFailures.value))return
  const next={...inlineSaveFailures.value}
  delete next[key]
  inlineSaveFailures.value=next
  if(!savingInline.value&&recordsLoadPending&&!inlineSaveFailure.value){
    recordsLoadPending=false
    void loadRecords()
  }
}
function finishInlineSave(){
  savingInline.value--
  if(savingInline.value!==0||!recordsLoadPending)return
  if(inlineSaveFailure.value){loading.value=false;return}
  recordsLoadPending=false
  void loadRecords()
}
async function saveBin(row: RecordData, value: string | number | null) {
  const failureKey=inlineFailureKey(row,'binning')
  savingInline.value++
  clearInlineSaveFailure(failureKey)
  try { await performBinSave(row,value) }
  catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:'Bin 保存失败。');throw cause}
  finally { finishInlineSave() }
}
async function performBinSave(row: RecordData, value: string | number | null) {
  const number=value==null||value===''?null:Number(String(value).replace(/^Bin/i,''))
  if(number!==null&&(!Number.isInteger(number)||number<1||number>16))throw new Error('Bin 必须介于 Bin1 与 Bin16。')
  const asset=row.asset??(row.scope==='shared'?row:undefined)
  if(asset){
    const updated=await assetApi.send('/astrophotoflow/api/v1/library/assets/'+asset.id,assetSchema,'PATCH',{
      base_revision:asset.revision,parameters:{binning_x:number,binning_y:number}
    })
    const replace=(item:RecordData)=>row.asset?{...item,asset:updated}:{...item,...updated,entry_type:item.entry_type,import_issue:item.import_issue}
    rows.value=rows.value.map(item=>item.id===row.id?replace(item):item)
    const current=selected.value
    if(current&&current.id===row.id)selected.value=replace(current)
    syncEditingDraft(row,updated)
  }else if(store.section==='capture-profiles'){
    const updated=await assetApi.send('/astrophotoflow/api/v1/capture-profiles/'+row.id,captureProfileSchema,'PATCH',{
      base_revision:row.revision,binning_x:number,binning_y:number
    })
    rows.value=rows.value.map(item=>item.id===row.id?updated:item)
    const current=selected.value
    if(current&&current.id===row.id)selected.value=updated
    syncEditingDraft(row,updated)
  }else if(row.entry_type==='dataset'){
    await saveDatasetParameters(row,{binning_x:number,binning_y:number})
  }
}

function editDataset(row: RecordData) {
  datasetEditorId.value = row.dataset_id ?? row.dataset?.id ?? row.id
  datasetPendingIds.value = []
}

function datasetSaved() {
  datasetEditorId.value = undefined
  datasetPendingIds.value = []
  void loadRecords()
}

function closeDatasetEditor(){
  clearInlineSaveFailure('dataset-editor:'+datasetEditorId.value)
  datasetEditorId.value=undefined
  datasetPendingIds.value=[]
}

async function showPreview(row: RecordData) {
  closePreview()
  const requestId = previewRequestId
  previewError.value = ''
  try {
    const member = await previewMember(row)
    if (requestId !== previewRequestId) return
    if (!member) {
      previewError.value = '此资产尚无可查看的预览。'
      return
    }
    const blob = await assetApi.getBlob(
      '/astrophotoflow/api/v1/library/assets/' + member.asset.id + '/versions/' + member.version.id + '/previews/detail'
    )
    if (requestId !== previewRequestId) return
    previewUrl.value = URL.createObjectURL(blob)
  } catch (cause) {
    if (requestId !== previewRequestId) return
    previewError.value = cause instanceof ApiClientError && cause.code === 'RESOURCE_NOT_FOUND'
      ? '预览尚未生成或当前格式不支持。'
      : presentError(cause).message
  }
}

function closePreview() {
  previewRequestId++
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = undefined
  previewError.value = ''
}

async function addSelectedAsset() {
  const revision = store.activeProjectRevision
  if (!store.activeProjectId || revision == null || !selected.value?.current_version_id) return
  error.value = undefined
  try {
    await assetApi.send(
      '/astrophotoflow/api/v1/projects/' + store.activeProjectId + '/asset-references',
      projectAssetReferenceSchema,
      'POST',
      { base_revision: revision, asset_version_id: selected.value.current_version_id }
    )
    store.activeProjectRevision = revision + 1
    addingProjectAssets.value = false
    await loadRecords()
  } catch (cause) {
    error.value = presentError(cause)
  }
}

async function removeSelectedAssetReference() {
  const revision = store.activeProjectRevision
  if (!store.activeProjectId || revision == null || !selected.value?.id) return
  error.value = undefined
  try {
    await assetApi.send(
      '/astrophotoflow/api/v1/projects/' + store.activeProjectId + '/asset-references/' + selected.value.id,
      z.object({ deleted_id: z.string(), revision: z.number().int() }),
      'DELETE',
      { base_revision: revision }
    )
    store.activeProjectRevision = revision + 1
    await loadRecords()
  } catch (cause) {
    error.value = presentError(cause)
  }
}

async function addSelectedDataset() {
  const revision = store.activeProjectRevision
  if (!store.activeProjectId || revision == null || !selected.value?.current_version_id) return
  error.value = undefined
  try {
    await assetApi.send(
      '/astrophotoflow/api/v1/projects/' + store.activeProjectId + '/dataset-references',
      datasetReferenceSchema,
      'POST',
      {
        base_revision: revision,
        dataset_id: selected.value.id,
        dataset_version_id: selected.value.current_version_id
      }
    )
    store.activeProjectRevision = revision + 1
    addingProjectDatasets.value = false
    await loadRecords()
  } catch (cause) {
    error.value = presentError(cause)
  }
}

async function removeSelectedDatasetReference() {
  const revision = store.activeProjectRevision
  if (!store.activeProjectId || revision == null || !selected.value?.id) return
  error.value = undefined
  try {
    await assetApi.send(
      '/astrophotoflow/api/v1/projects/' + store.activeProjectId + '/dataset-references/' + selected.value.id,
      z.object({ deleted_id: z.string(), revision: z.number().int() }),
      'DELETE',
      { base_revision: revision }
    )
    store.activeProjectRevision = revision + 1
    await loadRecords()
  } catch (cause) {
    error.value = presentError(cause)
  }
}

function setQuery(event: Event) {
  store.setQuery((event.target as HTMLInputElement).value)
}

function bulkKey(row:RecordData){return row.entry_type+':'+row.id}
function clearBulkSelection(){bulkSelection.value=new Set()}
function toggleLibrarySort(by:string){
  librarySort.value=librarySort.value.by===by
    ?{by,order:librarySort.value.order==='asc'?'desc':'asc'}
    :{by,order:'asc'}
  store.offset=0
  clearBulkSelection()
  bulkDeleteNotice.value=''
  void loadRecords()
}
function sortAria(by:string){
  return librarySort.value.by!==by?undefined:librarySort.value.order==='asc'?'ascending':'descending'
}
function sortArrow(by:string){
  return librarySort.value.by!==by?'':librarySort.value.order==='asc'?' ▲':' ▼'
}
function toggleBulkSelection(row:RecordData){
  const key=bulkKey(row)
  const next=new Set(bulkSelection.value)
  if(next.has(key))next.delete(key)
  else next.add(key)
  bulkSelection.value=next
}
function togglePageSelection(event:Event){
  const checked=(event.target as HTMLInputElement).checked
  const next=new Set(bulkSelection.value)
  for(const key of pageSelectionKeys.value){if(checked)next.add(key);else next.delete(key)}
  bulkSelection.value=next
}
async function enterBulkSelectMode(){
  if(!await waitForInlineSave())return
  bulkSelection.value=new Set()
  bulkDeleteNotice.value=''
  error.value=undefined
  filterPanelOpen.value=false
  bulkSelectMode.value=true
}
function leaveBulkSelectMode(){
  bulkSelectMode.value=false
  clearBulkSelection()
  bulkDeleteNotice.value=''
  error.value=undefined
}
async function removeSelectedLibraryEntries(){
  if(bulkDeleteBusy.value||!bulkSelection.value.size)return
  const selectedRows=rows.value.filter(row=>bulkSelection.value.has(bulkKey(row)))
  if(!selectedRows.length)return
  const items=libraryEntriesRemoveRequestSchema.parse({items:selectedRows.map(row=>({
    entry_type:row.entry_type as 'asset'|'dataset',id:row.id,revision:row.revision,
    current_version_id:row.current_version_id??null,
  }))}).items
  if(!items.length)return
  bulkDeleteBusy.value=true
  bulkDeleteNotice.value=''
  error.value=undefined
  try{
    const result=await assetApi.send('/astrophotoflow/api/v1/library/items',libraryEntriesRemoveSchema,'DELETE',{items})
    total.value=Math.max(0,total.value-result.removed_count)
    const pageSize=store.pageSize==='all'?total.value:store.pageSize
    if(store.offset>=total.value&&store.offset>0&&pageSize>0)store.offset=Math.max(0,Math.floor((total.value-1)/pageSize)*pageSize)
    bulkSelectMode.value=false
    clearBulkSelection()
    bulkDeleteNotice.value='已移除'+result.removed_count+'条素材库记录，原始数据未删除。'
    bulkDeleteBusy.value=false
    await loadRecords()
  }catch(cause){
    error.value=presentError(cause)
  }finally{bulkDeleteBusy.value=false}
}

function onLibraryRowClick(row:RecordData){
  if(bulkSelectMode.value)toggleBulkSelection(row)
  else void selectRow(row)
}

async function selectRow(row: RecordData) {
  if(selected.value?.id===row.id)return
  if(!await waitForInlineSave())return
  selected.value = row
  if(store.section==='projects'&&!viewingProjectAssets.value&&!viewingProjectDatasets.value){
    void loadRelatedProfiles(true)
  }
  if(row.asset||row.scope==='shared'||row.entry_type==='dataset'||store.section==='capture-profiles')
    void loadRelatedEquipment(true)
  if (store.section === 'projects' && !viewingProjectAssets.value && !viewingProjectDatasets.value) {
    store.activeProjectId = row.id
    store.activeProjectRevision = row.revision
  }
}

async function saveProjectProfilesInline(row:RecordData,profileIds:string[]){
  const current=row.capture_profile_ids??[]
  if(current.length===profileIds.length&&current.every((id:string)=>profileIds.includes(id)))return
  const failureKey=inlineFailureKey(row,'capture_profile_ids')
  savingInline.value++
  clearInlineSaveFailure(failureKey)
  try{
    const updated=await assetApi.send('/astrophotoflow/api/v1/projects/'+row.id,projectSchema,'PATCH',{
      base_revision:row.revision,capture_profile_ids:profileIds
    })
    selected.value=updated;rows.value=rows.value.map(item=>item.id===row.id?updated:item)
    if(store.activeProjectId===row.id)store.activeProjectRevision=updated.revision
    syncEditingDraft(row,updated)
  }catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:'拍摄设置关联保存失败。');throw cause}
  finally{finishInlineSave()}
}

async function openProjectAssets() {
  if(!await waitForInlineSave())return
  if (!store.activeProjectId) return
  viewingProjectAssets.value = true
  viewingProjectDatasets.value = false
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

async function openProjectDatasets() {
  if(!await waitForInlineSave())return
  if (!store.activeProjectId) return
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = true
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

async function openAvailableAssets() {
  if(!await waitForInlineSave())return
  viewingProjectAssets.value = true
  addingProjectAssets.value = true
  addingProjectDatasets.value = false
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

async function toggleProjectAssetMode(){
  if(!await waitForInlineSave())return
  if(addingProjectAssets.value){addingProjectAssets.value=false;await loadRecords()}
  else await openAvailableAssets()
}

async function openAvailableDatasets() {
  if(!await waitForInlineSave())return
  viewingProjectDatasets.value = true
  addingProjectDatasets.value = true
  addingProjectAssets.value = false
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

async function toggleProjectDatasetMode(){
  if(!await waitForInlineSave())return
  if(addingProjectDatasets.value){addingProjectDatasets.value=false;await loadRecords()}
  else await openAvailableDatasets()
}

async function leaveProjectAssets() {
  if(!await waitForInlineSave())return
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = false
  bulkSelectMode.value=false
  clearBulkSelection()
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  store.offset = 0
  selected.value = undefined
  loadRecords()
}

function emptySpecs(kind: string) {
  return Object.fromEntries(specFields[kind].map(field => [field.key, null]))
}

async function openCreate(type: EditorType) {
  if(!await waitForInlineSave())return
  editorType.value = type
  editingId.value = undefined
  if (type === 'project') draft.value = { name: '', target_name: '', notes: '', capture_profile_ids: [] }
  if (type === 'equipment') draft.value = { kind: 'camera', name: '', model: '', serial_number: '', notes: '', specs: emptySpecs('camera') }
  if (type === 'capture-profile') draft.value = {
    name: '', camera_id: '', optical_system_id: '', filter_id: '', frame_type: 'light',
    parameter_mode: '', iso: '', exposure_seconds: '', gain: '', offset: '', sensor_temperature_c: '', binning_value: '', binning_x: '', binning_y: '', notes: ''
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
function binChoiceNumber(value:unknown){
  if(value===''||value==null)return null
  const match=String(value).match(/^Bin(\d+)$/)
  return match?Number(match[1]):Number.NaN
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
    filter_id: textInput(row.filter_id), frame_type: row.frame_type, parameter_mode: row.parameter_mode??'', iso:textInput(row.iso),
    exposure_seconds: textInput(row.exposure_seconds), gain: textInput(row.gain), offset: textInput(row.offset),
    sensor_temperature_c: textInput(row.sensor_temperature_c), binning_x: textInput(row.binning_x),
    binning_y: textInput(row.binning_y), binning_value:binEditValue(row), notes: textInput(row.notes), status: row.status, revision: row.revision
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
  relatedProfilesError.value=''
  if (editorType.value === 'project' || editorType.value === 'capture-profile') {
    await loadRelatedEquipment(true)
  }
  if (editorType.value === 'project') {
    await loadRelatedProfiles(true)
  }
}

function closeEditor() {
  if(saving.value||savingInline.value||inlineSaveFailure.value)return
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
    parameter_mode:nullableString(draft.value.parameter_mode), iso:draft.value.parameter_mode==='iso'?inputNumber(draft.value.iso):inputNumber(draft.value.iso),
    exposure_seconds: inputNumber(draft.value.exposure_seconds), gain: inputNumber(draft.value.gain),
    offset: inputNumber(draft.value.offset), sensor_temperature_c: inputNumber(draft.value.sensor_temperature_c),
    binning_x: draft.value.binning_value===binEditValue(draft.value)?inputNumber(draft.value.binning_x):binChoiceNumber(draft.value.binning_value),
    binning_y: draft.value.binning_value===binEditValue(draft.value)?inputNumber(draft.value.binning_y):binChoiceNumber(draft.value.binning_value),
    notes: nullableString(draft.value.notes)
  }
  if (editingId.value) Object.assign(payload, { base_revision: draft.value.revision, status: draft.value.status })
  return payload
}

async function saveEditor() {
  if (!editorType.value||editingId.value) return
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

const itemTitle = (row: RecordData) => row.asset?.name ?? row.dataset?.name ?? row.name ?? '未命名记录'
const itemSubtitle = (row: RecordData) => {
  if (row.entry_type === 'dataset') return (row.member_count ?? 0) + ' 个成员'
  if (row.version) return '固定版本 · ' + (row.version.frame_type ?? '未分类')
  if (row.current_version) return row.current_version.frame_type ?? '未分类'
  if (row.kind) return row.kind + (row.model ? ' · ' + row.model : '')
  if (row.camera_id) return row.frame_type + ' · 相机 ' + row.camera_id
  return row.status ?? ''
}
const rowAsset = (row: RecordData) => row.asset ?? row
const rowParameters = (row: RecordData) => rowAsset(row).parameters ?? {}
const rowClassification = (row: RecordData) => rowAsset(row).classification ?? {}
function equipmentName(id: string | null | undefined) {
  if (!id) return '未指定'
  return relatedEquipment.value.find(item => item.id === id)?.name ?? id.slice(0, 8)
}
function captureValue(value: unknown) { return value === null || value === undefined || value === '' ? '—' : String(value) }
function modeValue(parameters:RecordData){return parameters.parameter_mode==='standard'?'':parameters.parameter_mode??''}
function datasetParameterMode(row:RecordData){
  const values=datasetMembers(row).map(member=>member.asset?.parameters?.parameter_mode??'standard')
  const distinct=[...new Set(values)]
  return distinct.length>1?'mixed':distinct[0]==='standard'?'':distinct[0]??''
}
function cfaLabel(value:unknown){
  if(value===null||value===undefined||value==='')return '未指定'
  return ({MONO:'无 CFA（单色）',XTRANS:'X-Trans 6×6',QUAD_BAYER:'Quad Bayer'} as Record<string,string>)[String(value)]??String(value??'未指定')
}
function frameClassLabel(value:unknown){return value?String(value):'未指定'}
function frameTypeLabel(value:unknown){return value?String(value):'未指定'}
function rowFrame(row: RecordData) {
  if (row.version?.members) return row.version.members.length + ' 个成员'
  if (row.member_count != null || row.dataset_id) return row.member_count == null ? '数据集' : row.member_count + ' 个成员'
  const classification = rowClassification(row)
  return [classification.frame_class, classification.frame_type].filter(Boolean).join(' / ') || '未分类'
}
function datasetMembers(row: RecordData): RecordData[] {
  return row.version?.members ?? []
}
function datasetValue(row: RecordData, getValue: (member: RecordData) => unknown, format: (value: unknown) => string = captureValue) {
  const members = datasetMembers(row)
  if (!members.length) return '—'
  const values = members.map(getValue)
  const known = values.filter(value => value !== null && value !== undefined && value !== '')
  if (!known.length) return '—'
  const distinct = new Map(known.map(value => [JSON.stringify(value), value]))
  if (distinct.size > 1) return '混合'
  const displayed = format(distinct.values().next().value)
  return known.length < values.length ? displayed + '（部分缺失）' : displayed
}
function datasetClassification(row: RecordData) {
  return datasetValue(row, member => {
    const classification = member.asset?.classification
    return classification
      ? [classification.frame_class, classification.frame_type].filter(Boolean).join(' / ') || null
      : null
  }, value => String(value))
}

watch(
  [() => store.query, () => store.offset, () => store.pageSize, statusFilter, roleFilter, frameTypeFilter],
  ([query, offset, pageSize, status, role, frameType], [previousQuery, previousOffset, previousPageSize, previousStatus, previousRole, previousFrameType]) => {
    const queryChanged = query !== previousQuery
    const filtersChanged = pageSize !== previousPageSize || status !== previousStatus || role !== previousRole || frameType !== previousFrameType
    if(offset!==previousOffset||queryChanged||filtersChanged)clearBulkSelection()
    if (queryChanged || filtersChanged) {
      loadGeneration++
      clearTimeout(searchTimer)
      if (offset !== 0) {
        store.offset = 0
        return
      }
      if (queryChanged) {
        if(!savingInline.value&&!inlineSaveFailure.value)loading.value = true
        searchTimer = setTimeout(() => loadRecords(), 250)
        return
      }
    }
    loadRecords()
  }
)
onMounted(async () => {
  void loadRelatedEquipment()
  await loadCapabilities()
  await loadRecords()
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  for (const url of Object.values(previewUrls.value)) URL.revokeObjectURL(url)
  closePreview()
})
</script>

<template>
  <section class="apf-workspace" aria-label="AstroPhotoFlow 天文资产工作台"
    @pointerdown.stop @pointerup.stop @mousedown.stop @mouseup.stop
    @click.stop @contextmenu.stop @keydown.stop @keyup.stop>
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
              <button v-if="viewingProjectAssets || viewingProjectDatasets" type="button" @click="leaveProjectAssets">← 返回项目</button>
              <h1>{{ activeArea === 'library' ? '素材库' : (viewingProjectAssets ? '项目资产' : viewingProjectDatasets ? '项目数据集' : '设置') }}</h1>
              <div v-if="isLibraryItemsView" class="apf-heading-actions">
                <template v-if="bulkSelectMode">
                  <button type="button" :disabled="bulkDeleteBusy||bulkSelection.size===0||savingInline>0||Boolean(inlineSaveFailure)" @click="removeSelectedLibraryEntries">{{bulkDeleteBusy?'删除中…':'删除'}}</button>
                  <button type="button" :disabled="bulkDeleteBusy" @click="leaveBulkSelectMode">取消</button>
                </template>
                <template v-else>
                <button type="button" class="apf-import" :disabled="!capabilities?.asset_import" :aria-expanded="importMenuOpen" @click="importMenuOpen=!importMenuOpen"
                  title="选择文件或文件夹">
                  <i class="pi pi-upload" aria-hidden="true"></i><span>导入</span>
                </button>
                <button type="button" aria-label="刷新" @click="refreshLibrary"><i class="pi pi-refresh" aria-hidden="true"></i><span>刷新</span></button>
                <button type="button" :disabled="savingInline>0||Boolean(inlineSaveFailure)" @click="enterBulkSelectMode">批量删除</button>
                <div v-if="importMenuOpen" class="apf-import-menu">
                  <button type="button" @click="startImport('files')">选择文件</button>
                  <button type="button" @click="startImport('folder')">选择文件夹</button>
                </div>
                </template>
              </div>
            </div>
            <div v-if="activeArea === 'settings' && !viewingProjectAssets && !viewingProjectDatasets" class="apf-management-tabs" aria-label="设置类别">
              <button v-for="(title, section) in { projects: '项目', equipment: '设备', 'capture-profiles': '拍摄设置' }"
                :key="section" type="button" :aria-current="store.section === section ? 'page' : undefined"
                @click="selectSection(section as WorkspaceSection)">{{ title }}</button>
            </div>
            <label class="apf-search">
              <i class="pi pi-search" aria-hidden="true"></i>
              <input :value="store.query" aria-label="搜索" placeholder="搜索名称" :disabled="bulkDeleteBusy" @input="setQuery" />
            </label>
            <select v-if="store.section === 'projects' || store.section === 'equipment' || store.section === 'capture-profiles'"
              v-model="statusFilter" aria-label="状态筛选">
              <option value="active">启用</option><option value="archived">已归档</option><option value="all">全部</option>
            </select>
            <button v-if="activeArea==='library' && !viewingProjectAssets && !viewingProjectDatasets" ref="filterButton" type="button" :disabled="bulkDeleteBusy" :aria-expanded="filterPanelOpen" @click="filterPanelOpen=!filterPanelOpen">
              筛选<span v-if="activeFilterCount">（{{activeFilterCount}}）</span>
            </button>
            <div v-if="activeArea==='settings'" class="apf-layout">
              <button type="button" :aria-pressed="store.layout === 'grid'" @click="store.layout = 'grid'">网格</button>
              <button type="button" :aria-pressed="store.layout === 'list'" @click="store.layout = 'list'">列表</button>
            </div>
            <div v-if="activeArea==='library'&&!viewingProjectAssets&&!viewingProjectDatasets" class="apf-library-view" aria-label="素材显示方式">
              <button type="button" :aria-pressed="libraryViewMode==='simple'" @click="libraryViewMode='simple'">简约</button>
              <button type="button" :aria-pressed="libraryViewMode==='detail'" @click="libraryViewMode='detail'">细节</button>
            </div>
            <button v-if="activeArea !== 'library' || viewingProjectAssets || viewingProjectDatasets" type="button" @click="loadRecords"><i class="pi pi-refresh" aria-hidden="true"></i><span>刷新</span></button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets" type="button" @click="openCreate('project')">新建项目</button>
            <button v-if="store.section === 'equipment'" type="button" @click="openCreate('equipment')">添加设备</button>
            <button v-if="store.section === 'capture-profiles'" type="button" @click="openCreate('capture-profile')">新建配置</button>
            <button v-if="store.section==='projects' && viewingProjectAssets" type="button" @click="toggleProjectAssetMode">{{addingProjectAssets?'查看已选资产':'添加素材'}}</button>
            <button v-if="store.section==='projects' && viewingProjectDatasets" type="button" @click="toggleProjectDatasetMode">{{addingProjectDatasets?'查看已选数据集':'添加数据集'}}</button>
          </div>

          <LibraryFilterPanel v-if="filterPanelOpen" :filters="activeFilters" :anchor="filterButton" @apply="applyFilters" @cancel="filterPanelOpen=false" />
          <input ref="filePicker" type="file" multiple accept=".fits,.fit,.fts,.fits.fz,.fit.fz,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp,.cr2,.cr3,.nef,.arw,.dng,.raf,.orf,.rw2,.pef,.srw,.xisf,.ser,.mp4,.mov,.avi,.mkv" hidden @change="filesChosen" />
          <input ref="folderPicker" type="file" webkitdirectory directory multiple hidden @change="foldersChosen" />
          <p v-if="capabilityError" class="apf-error" role="alert">能力状态读取失败：{{ errorText(capabilityError) }}</p>
          <p v-if="inlineSaveFailure" class="apf-error" role="alert">{{inlineSaveFailure}}</p>
          <p v-if="bulkSelectMode" class="apf-state">只删除素材库引用，不删除原本数据。</p>
          <p v-if="bulkDeleteNotice" class="apf-state" role="status">{{bulkDeleteNotice}}</p>
          <p v-if="error" class="apf-error" role="alert">{{ errorText(error) }}<span v-if="error.requestId"> 请求 ID：{{ error.requestId }}</span></p>
          <p v-if="loading" class="apf-state" role="status">正在读取服务数据…</p>
          <p v-if="!loading && !error && rows.length === 0" class="apf-state">{{activeArea==='library'?'当前没有已完成的素材。':'此处目前没有记录。'}}</p>

          <div v-if="!loading && (rows.length || activeArea === 'library') && isAssetTable" class="apf-table-scroll" :class="activeArea==='library'?libraryViewMode:'detail'">
            <table :class="['apf-assets-table',{'is-selecting':bulkSelectMode,'is-deleting':bulkDeleteBusy}]">
              <thead><tr>
                <th v-if="bulkSelectMode&&isLibraryItemsView"><input type="checkbox" aria-label="全选当前页" :checked="pageAllSelected" :indeterminate="pagePartiallySelected" :aria-checked="pagePartiallySelected?'mixed':pageAllSelected" :disabled="rows.length===0||bulkDeleteBusy" @change="togglePageSelection" /></th>
                <th>预览</th>
                <th :aria-sort="isLibraryItemsView?sortAria('name'):undefined"><button v-if="isLibraryItemsView" type="button" class="apf-sort-button" @click="toggleLibrarySort('name')">名称{{sortArrow('name')}}</button><template v-else>名称</template></th>
                <th :aria-sort="isLibraryItemsView?sortAria('classification'):undefined"><button v-if="isLibraryItemsView" type="button" class="apf-sort-button" @click="toggleLibrarySort('classification')">分类{{sortArrow('classification')}}</button><template v-else>分类</template></th>
                <th :aria-sort="isLibraryItemsView?sortAria('camera'):undefined"><button v-if="isLibraryItemsView" type="button" class="apf-sort-button" @click="toggleLibrarySort('camera')">相机{{sortArrow('camera')}}</button><template v-else>相机</template></th>
                <th :aria-sort="isLibraryItemsView?sortAria('parameter_mode'):undefined"><button v-if="isLibraryItemsView" type="button" class="apf-sort-button" @click="toggleLibrarySort('parameter_mode')">ISO／Gain{{sortArrow('parameter_mode')}}</button><template v-else>ISO／Gain</template></th>
                <th :aria-sort="isLibraryItemsView?sortAria('exposure_seconds'):undefined"><button v-if="isLibraryItemsView" type="button" class="apf-sort-button" @click="toggleLibrarySort('exposure_seconds')">曝光{{sortArrow('exposure_seconds')}}</button><template v-else>曝光</template></th>
                <th :aria-sort="isLibraryItemsView?sortAria('sensor_temperature_c'):undefined"><button v-if="isLibraryItemsView" type="button" class="apf-sort-button" @click="toggleLibrarySort('sensor_temperature_c')">温度{{sortArrow('sensor_temperature_c')}}</button><template v-else>温度</template></th>
                <template v-if="libraryViewMode==='detail'&&isLibraryItemsView">
                  <th :aria-sort="sortAria('binning')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('binning')">Bin{{sortArrow('binning')}}</button></th>
                  <th :aria-sort="sortAria('cfa_pattern')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('cfa_pattern')">CFA{{sortArrow('cfa_pattern')}}</button></th>
                  <th :aria-sort="sortAria('optical_system')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('optical_system')">成像系统{{sortArrow('optical_system')}}</button></th>
                  <th :aria-sort="sortAria('filter')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('filter')">滤镜{{sortArrow('filter')}}</button></th>
                  <th :aria-sort="sortAria('integration_seconds')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('integration_seconds')">累计曝光{{sortArrow('integration_seconds')}}</button></th>
                  <th :aria-sort="sortAria('storage_mode')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('storage_mode')">存储{{sortArrow('storage_mode')}}</button></th>
                  <th :aria-sort="sortAria('status')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('status')">状态{{sortArrow('status')}}</button></th>
                  <th :aria-sort="sortAria('notes')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('notes')">备注{{sortArrow('notes')}}</button></th>
                </template>
                <template v-else-if="activeArea!=='library'"><th>成像系统</th><th>滤镜</th><th>存储</th><th>状态</th><th>备注</th></template></tr></thead>
              <tbody>
                <ImportTasks v-if="activeArea === 'library' && !viewingProjectAssets && !viewingProjectDatasets"
                  :refresh-token="progressRefreshToken" :watch-task-ids="watchedTaskIds" :upload-progress="uploadProgress" @completed="importTaskCompleted" v-slot="{tasks,resume,busyTaskId,error:taskError}">
                  <tr v-if="taskError"><td :colspan="(activeArea==='library'&&libraryViewMode==='detail'?15:activeArea==='library'?7:12)+(bulkSelectMode&&isLibraryItemsView?1:0)" class="apf-error" role="alert">{{taskError}}</td></tr>
                  <tr v-for="task in tasks" :key="'task-'+task.id" class="apf-import-row" :aria-disabled="true">
                    <td :colspan="(activeArea==='library'&&libraryViewMode==='detail'?15:activeArea==='library'?7:12)+(bulkSelectMode&&isLibraryItemsView?1:0)"><div class="apf-import-row__content">
                      <strong>{{task.dataset_name || (task.report as Record<string, any>).upload_files?.[0]?.name || '素材导入'}}</strong>
                      <span>{{uploadTaskLabel(task)}}</span>
                      <button v-if="task.status==='interrupted'" type="button" :disabled="busyTaskId===task.id" @click="resume(task)">{{busyTaskId===task.id?'恢复中…':'继续导入'}}</button>
                      <progress v-if="task.status!=='failed' && task.enumeration_completed" :value="uploadTaskProgress(task)" max="100" :aria-label="uploadTaskLabel(task)" />
                      <progress v-else-if="task.status!=='failed'" max="100" :aria-label="uploadTaskLabel(task)" />
                    </div></td>
                  </tr>
                </ImportTasks>
                <tr v-for="row in rows" :key="row.entry_type+':'+row.id" :aria-selected="bulkSelectMode?bulkSelection.has(bulkKey(row)):selected?.id===row.id" @click="onLibraryRowClick(row)" @dblclick.capture="bulkSelectMode?$event.stopPropagation():undefined">
                <td v-if="bulkSelectMode&&isLibraryItemsView"><input type="checkbox" :aria-label="'选择 '+itemTitle(row)" :checked="bulkSelection.has(bulkKey(row))" :disabled="bulkDeleteBusy" @click.stop @change="toggleBulkSelection(row)" /></td>
                <td><button class="apf-thumb" type="button" :aria-label="'查看 '+itemTitle(row)+' 预览'" @click.stop="showPreview(row)">
                  <img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" />
                  <span v-else>100px</span>
                </button></td>
                <td><InlineField :value="itemTitle(row)" :save="value=>saveRowField(row,'name',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'name'))" /><button v-if="row.entry_type==='dataset'" type="button" class="apf-member-open" @click.stop="editDataset(row)">{{itemSubtitle(row)}}</button><small v-else>{{itemSubtitle(row)}}</small></td>
                <td v-if="row.entry_type==='dataset'">
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_class)" :display="datasetValue(row,member=>member.asset?.classification?.frame_class,frameClassLabel)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameClasses.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_type)" :display="datasetValue(row,member=>member.asset?.classification?.frame_type,frameTypeLabel)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameTypes.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td v-else>
                  <InlineField :value="rowClassification(row).frame_class??''" :display="frameClassLabel(rowClassification(row).frame_class)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameClasses.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField v-if="rowClassification(row).frame_class!=='video'" :value="rowClassification(row).frame_type??''" :display="frameTypeLabel(rowClassification(row).frame_type)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameTypes.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.camera_id):rowParameters(row).camera_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.camera_id,value=>equipmentName(value as string|null)):equipmentName(rowParameters(row).camera_id)" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.camera_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="value=>saveRowField(row,'camera_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'camera_id'))" /></td>
                <td>
                  <ParameterModeField :value="parameterModeValue(row)" :display="parameterModeDisplay(row)" unset-mode="standard" :save="changes=>saveParameterGroup(row,changes)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'parameter_mode'))" />
                </td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds):rowParameters(row).exposure_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.exposure_seconds,value=>value==null?'未指定':String(value)+' s'):captureValue(rowParameters(row).exposure_seconds)+(rowParameters(row).exposure_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'exposure_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'exposure_seconds'))" /></td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c):rowParameters(row).sensor_temperature_c" :display="row.entry_type==='dataset'?datasetTemperature(row):rowParameters(row).sensor_temperature_c==null?'未指定':displayTemperature(rowParameters(row).sensor_temperature_c)+' °C'" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'sensor_temperature_c',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'sensor_temperature_c'))" /></td>
                <template v-if="libraryViewMode==='detail'&&isLibraryItemsView">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>binEditValue(member.asset?.parameters??{})):binEditValue(rowParameters(row))" :display="row.entry_type==='dataset'?datasetValue(row,member=>binValue(member.asset?.parameters??{}),value=>String(value??'未指定')):binValue(rowParameters(row))??'未指定'" kind="select" :choices="row.entry_type==='dataset'?datasetBinChoices(row):binEditChoices(rowParameters(row))" :save="value=>saveBin(row,value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'binning'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.cfa_pattern):rowParameters(row).cfa_pattern??''" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.cfa_pattern,cfaLabel):cfaLabel(rowParameters(row).cfa_pattern)" kind="select" :choices="row.entry_type==='dataset'?[...cfaChoices,{value:'mixed',label:'混合',disabled:true}]:cfaChoices" :save="value=>saveRowField(row,'cfa_pattern',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'cfa_pattern'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.optical_system_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).optical_system_id)" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.filter_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).filter_id)" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.filter_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds):rowParameters(row).integration_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.integration_seconds,value=>value==null?'未指定':String(value)+' s'):captureValue(rowParameters(row).integration_seconds)+(rowParameters(row).integration_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'integration_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'integration_seconds'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode):row.version?.storage_mode??row.current_version?.storage_mode??'—'}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue??row.version?.availability??row.current_version?.availability??''}}</small></td>
                  <td class="apf-note-cell"><InlineField :value="row.entry_type==='dataset'?row.dataset?.notes:row.notes" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
                <template v-else-if="activeArea!=='library'">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.optical_system_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).optical_system_id)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.filter_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).filter_id)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode):row.version?.storage_mode??row.current_version?.storage_mode??'—'}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue??row.version?.availability??row.current_version?.availability??''}}</small></td>
                  <td><InlineField :value="row.notes" :display="row.notes??'—'" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
              </tr></tbody>
            </table>
          </div>
          <div v-else-if="!loading && rows.length && isDatasetTable" class="apf-table-scroll">
            <table class="apf-assets-table apf-dataset-table">
              <thead><tr><th>封面</th><th>数据集</th><th>分类</th><th>成员数</th><th>相机</th><th>ISO／Gain</th><th>曝光</th><th>温度</th><th>成像系统</th><th>滤镜</th><th>存储</th><th>状态</th><th>备注</th><th>操作</th></tr></thead>
              <tbody><tr v-for="row in rows" :key="row.id" :aria-selected="selected?.id===row.id" @click="selectRow(row)">
                <td><button class="apf-thumb" type="button" @click.stop="showPreview(row)"><img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" /><span v-else>100px</span></button></td>
                <td><strong>{{row.dataset?.name??row.name}}</strong><small>{{row.dataset_version_id?'项目固定版本':'数据集'}}</small></td>
                <td>{{datasetClassification(row)}}</td>
                <td>{{row.version?.members?.length??row.member_count??'—'}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.camera_id, value=>equipmentName(typeof value==='string'?value:null))}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.iso)}} / {{datasetValue(row, member=>member.asset?.parameters?.gain)}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.exposure_seconds, value=>captureValue(value)+' s')}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.sensor_temperature_c, value=>captureValue(value)+' °C')}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.optical_system_id, value=>equipmentName(typeof value==='string'?value:null))}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.filter_id, value=>equipmentName(typeof value==='string'?value:null))}}</td>
                <td>{{datasetValue(row, member=>member.version?.storage_mode, value=>String(value))}}</td>
                <td>{{row.dataset?.status??row.status}}</td><td class="apf-note-cell">{{row.dataset?.notes??row.notes??'—'}}</td>
                <td><button type="button" @click.stop="editDataset(row)">{{row.dataset_version_id?'编辑当前数据集':'编辑成员'}}</button></td>
              </tr></tbody>
            </table>
          </div>
          <section v-else-if="!loading && rows.length && !isAssetTable && !isDatasetTable" :class="['apf-records', store.layout]">
            <button v-for="row in rows" :key="row.id" type="button"
              :class="['apf-record', selected?.id === row.id ? 'selected' : '']" @click="selectRow(row)">
              <span class="apf-record-icon">{{ row.asset ? '✦' : row.kind ? '◉' : row.camera_id ? '⚙' : '▣' }}</span>
              <span><strong>{{ itemTitle(row) }}</strong><small>{{ itemSubtitle(row) }}</small></span>
            </button>
          </section>
          <footer class="apf-pagination">
            <span>{{ total }} 条记录</span>
            <label>每页显示
              <select aria-label="每页显示数量" :value="store.pageSize" :disabled="loading||bulkDeleteBusy" @change="store.setPageSize(($event.target as HTMLSelectElement).value==='all'?'all':Number(($event.target as HTMLSelectElement).value) as 10|20|50)">
                <option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="all">全部</option>
              </select>
            </label>
            <template v-if="store.pageSize!=='all'">
              <button type="button" :disabled="store.offset === 0 || loading || bulkDeleteBusy" @click="store.movePage(-store.pageSize)">上一页</button>
              <button type="button" :disabled="store.offset + rows.length >= total || loading || bulkDeleteBusy" @click="store.movePage(store.pageSize)">下一页</button>
            </template>
          </footer>
          <p v-if="isAssetSection && capabilities && !capabilities.asset_preview" class="apf-disabled">资产预览将在后续阶段接入。</p>

          <section v-if="editorType" class="apf-editor" aria-label="记录编辑表单">
            <template v-if="editingId">
              <h2>编辑{{editorType==='project'?'项目':editorType==='equipment'?'设备':'拍摄设置'}}</h2>
              <button type="button" :disabled="saving||savingInline>0" @click="closeEditor">关闭</button>
              <label>名称<InlineField :value="draft.name" :save="value=>saveEditorInline('name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('name'))" /></label>
              <template v-if="editorType==='project'">
                <label>拍摄目标<InlineField :value="draft.target_name" :display="draft.target_name||'未指定'" :save="value=>saveEditorInline('target_name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('target_name'))" /></label>
                <label>说明<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>
                <label>拍摄设置<InlineMultiSelect :value="draft.capture_profile_ids??[]" :choices="profileChoices()" :choices-message="profileChoiceMessage()" :save="value=>saveEditorProjectProfiles(value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('capture_profile_ids'))" /></label>
                <label>状态<InlineField :value="draft.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveEditorInline('status',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('status'))" /></label>
              </template>
              <template v-else-if="editorType==='equipment'">
                <label>设备类型<select :value="draft.kind" disabled><option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{kind}}</option></select></label>
                <label>型号<InlineField :value="draft.model" :display="draft.model||'未指定'" :save="value=>saveEditorInline('model',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('model'))" /></label>
                <label>序列号<InlineField :value="draft.serial_number" :display="draft.serial_number||'未指定'" :save="value=>saveEditorInline('serial_number',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('serial_number'))" /></label>
                <label>说明<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>
                <fieldset><legend>设备参数</legend>
                  <label v-for="field in specFields[draft.kind]" :key="field.key">{{field.label}}<InlineField :value="draft.specs[field.key]" :display="specDisplay(field,draft.specs[field.key])" :kind="specKind(field)" :choices="specChoices(field)" :integer="field.integer" :save="value=>saveEditorInline('specs.'+field.key,value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('specs.'))" /></label>
                </fieldset>
                <label>状态<InlineField :value="draft.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveEditorInline('status',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('status'))" /></label>
              </template>
              <template v-else>
                <label>相机<InlineField :value="draft.camera_id??''" :display="equipmentName(draft.camera_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="value=>saveEditorInline('camera_id',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('camera_id'))" /></label>
                <label>成像系统<InlineField :value="draft.optical_system_id??''" :display="equipmentName(draft.optical_system_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveEditorInline('optical_system_id',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('optical_system_id'))" /></label>
                <label>滤镜<InlineField :value="draft.filter_id??''" :display="equipmentName(draft.filter_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveEditorInline('filter_id',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('filter_id'))" /></label>
                <label>帧用途<InlineField :value="draft.frame_type??''" :display="frameTypeLabel(draft.frame_type)" kind="select" :choices="[{value:'',label:'未指定'},...frameTypes.map(value=>({value,label:value}))]" :save="value=>saveEditorInline('frame_type',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('frame_type'))" /></label>
                <label>ISO／Gain<ParameterModeField :value="{parameter_mode:draft.parameter_mode,iso:draft.iso,gain:draft.gain,offset:draft.offset}" :display="captureProfileModeDisplay(draft)" :unset-mode="null" :save="changes=>saveEditorParameterGroup(changes)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('parameter_mode'))" /></label>
                <label>曝光（秒）<InlineField :value="draft.exposure_seconds" kind="number" :save="value=>saveEditorInline('exposure_seconds',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('exposure_seconds'))" /></label>
                <label>温度（°C）<InlineField :value="draft.sensor_temperature_c" :display="draft.sensor_temperature_c==null?'未指定':displayTemperature(draft.sensor_temperature_c)+' °C'" kind="number" :save="value=>saveEditorInline('sensor_temperature_c',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('sensor_temperature_c'))" /></label>
                <label>Bin<InlineField :value="binEditValue(draft)" :display="binValue(draft)??'未指定'" kind="select" :choices="binEditChoices(draft)" :save="value=>saveEditorBin(value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('binning'))" /></label>
                <label>说明<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>
                <label>状态<InlineField :value="draft.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveEditorInline('status',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('status'))" /></label>
              </template>
            </template>
            <form v-else @submit.prevent="saveEditor">
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
                    <select v-if="field.key==='cfa_pattern'" v-model="draft.specs[field.key]">
                      <option v-for="choice in cfaChoices" :key="choice.value" :value="choice.value">{{choice.label}}</option>
                    </select>
                    <select v-else-if="field.options" v-model="draft.specs[field.key]">
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
                <label>增益模式<select v-model="draft.parameter_mode"><option value="">未指定</option><option value="iso">ISO</option><option value="gain">Gain／Offset</option></select></label>
                <label v-for="field in [
                  {key:'exposure_seconds',label:'曝光（秒）',step:'any'},
                  {key:'sensor_temperature_c',label:'传感器温度（°C）',step:'any'},
                ]" :key="field.key">{{ field.label }}<input v-model="draft[field.key]" type="number" :step="field.step" /></label>
                <label v-if="draft.parameter_mode==='iso'">ISO<input v-model="draft.iso" type="number" step="1" /></label>
                <template v-else-if="draft.parameter_mode==='gain'"><label>Gain<input v-model="draft.gain" type="number" step="any" /></label><label>Offset<input v-model="draft.offset" type="number" step="any" /></label></template>
                <label>Bin<select v-model="draft.binning_value"><option value="">未指定</option><option v-for="choice in binEditChoices(draft)" :key="choice.value" :value="choice.value">{{choice.label}}</option></select></label>
                <label>说明<textarea v-model="draft.notes" /></label>
              </template>
              <label v-if="editingId">状态<select v-model="draft.status"><option value="active">启用</option><option value="archived">归档</option></select></label>
              <div class="apf-form-actions">
                <button type="button" :disabled="saving" @click="closeEditor">取消</button>
                <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
              </div>
            </form>
          </section>
        <aside v-if="selected&&activeArea!=='library'" class="apf-details" aria-label="记录详情">
          <template v-if="selected">
            <h2>{{ itemTitle(selected) }}</h2>
            <p>{{ itemSubtitle(selected) }}</p>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectAssets">查看项目资产</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectDatasets">查看项目数据集</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="editProject(selected)">编辑项目</button>
            <button v-if="store.section === 'projects' && viewingProjectAssets && !addingProjectAssets" type="button" @click="removeSelectedAssetReference">从项目移除</button>
            <button v-if="store.section === 'projects' && viewingProjectDatasets && !addingProjectDatasets" type="button" @click="removeSelectedDatasetReference">从项目移除数据集</button>
            <button v-if="store.section === 'projects' && addingProjectAssets" type="button" @click="addSelectedAsset">选用此资产版本</button>
            <button v-if="store.section === 'projects' && addingProjectDatasets" type="button" @click="addSelectedDataset">选用此数据集版本</button>
            <button v-if="selected.dataset || selected.dataset_id || selected.entry_type==='dataset'" type="button" @click="editDataset(selected)">编辑数据集成员</button>
            <div v-if="selected.asset || selected.scope==='shared'" class="apf-detail-fields">
              <label>名称<InlineField :value="itemTitle(selected)" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>素材形态<InlineField :value="rowClassification(selected).frame_class??''" :display="frameClassLabel(rowClassification(selected).frame_class)" kind="select" :choices="[{value:'',label:'未指定'},...frameClasses.map(value=>({value,label:value}))]" :save="selectedFieldSave('frame_class')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_class'))" /></label>
              <label v-if="rowClassification(selected).frame_class!=='video'">帧用途<InlineField :value="rowClassification(selected).frame_type??''" :display="frameTypeLabel(rowClassification(selected).frame_type)" kind="select" :choices="[{value:'',label:'未指定'},...frameTypes.map(value=>({value,label:value}))]" :save="selectedFieldSave('frame_type')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_type'))" /></label>
              <label>ISO／Gain<ParameterModeField :value="parameterModeValue(selected)" :display="parameterModeDisplay(selected)" unset-mode="standard" :save="selectedParameterSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'parameter_mode'))" /></label>
              <label>相机<InlineField :value="rowParameters(selected).camera_id??''" :display="equipmentName(rowParameters(selected).camera_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="selectedFieldSave('camera_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'camera_id'))" /></label>
              <label>成像系统<InlineField :value="rowParameters(selected).optical_system_id??''" :display="equipmentName(rowParameters(selected).optical_system_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="selectedFieldSave('optical_system_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'optical_system_id'))" /></label>
              <label>滤镜<InlineField :value="rowParameters(selected).filter_id??''" :display="equipmentName(rowParameters(selected).filter_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="selectedFieldSave('filter_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'filter_id'))" /></label>
              <label>单帧曝光（秒）<InlineField :value="rowParameters(selected).exposure_seconds" kind="number" :save="selectedFieldSave('exposure_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'exposure_seconds'))" /></label>
              <label>累计曝光（秒）<InlineField :value="rowParameters(selected).integration_seconds" kind="number" :save="selectedFieldSave('integration_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'integration_seconds'))" /></label>
              <label>温度（°C）<InlineField :value="rowParameters(selected).sensor_temperature_c" :display="rowParameters(selected).sensor_temperature_c==null?'未指定':displayTemperature(rowParameters(selected).sensor_temperature_c)+' °C'" kind="number" :save="selectedFieldSave('sensor_temperature_c')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'sensor_temperature_c'))" /></label>
              <label>Bin<InlineField :value="binEditValue(rowParameters(selected))" :display="binValue(rowParameters(selected))??'未指定'" kind="select" :choices="binEditChoices(rowParameters(selected))" :save="selectedBinSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'binning'))" /></label>
              <label>CFA 排列<InlineField :value="rowParameters(selected).cfa_pattern??''" :display="cfaLabel(rowParameters(selected).cfa_pattern)" kind="select" :choices="cfaChoices" :save="selectedFieldSave('cfa_pattern')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'cfa_pattern'))" /></label>
              <label>状态<InlineField :value="rowAsset(selected).status??'active'" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>备注<InlineField :value="rowAsset(selected).notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="selected.dataset" class="apf-detail-fields">
              <label>数据集名称<InlineField :value="selected.dataset.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>状态<InlineField :value="selected.dataset.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>备注<InlineField :value="selected.dataset.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="store.section==='projects'" class="apf-detail-fields">
              <label>名称<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>拍摄目标<InlineField :value="selected.target_name" :save="selectedFieldSave('target_name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'target_name'))" /></label>
              <label>备注<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
              <label>状态<InlineField :value="selected.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <fieldset class="apf-profile-links"><legend>拍摄设置</legend>
                <InlineMultiSelect :value="selected.capture_profile_ids??[]" :choices="profileChoices()" :choices-message="profileChoiceMessage()" :save="selectedProfileSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'capture_profile_ids'))" />
              </fieldset>
            </div>
            <div v-else-if="store.section==='equipment'" class="apf-detail-fields">
              <label>名称<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>型号<InlineField :value="selected.model" :display="selected.model??'未指定'" :save="selectedFieldSave('model')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'model'))" /></label>
              <label>序列号<InlineField :value="selected.serial_number" :display="selected.serial_number??'未指定'" :save="selectedFieldSave('serial_number')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'serial_number'))" /></label>
              <label v-for="field in specFields[selected.kind]" :key="field.key">{{field.label}}<InlineField :value="selected.specs?.[field.key]" :display="specDisplay(field,selected.specs?.[field.key])" :kind="specKind(field)" :choices="specChoices(field)" :integer="field.integer" :save="selectedFieldSave('specs.'+field.key)" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'specs.'+field.key))" /></label>
              <label>备注<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
              <label>状态<InlineField :value="selected.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
            </div>
            <div v-else-if="store.section==='capture-profiles'" class="apf-detail-fields">
              <label>名称<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>相机<InlineField :value="selected.camera_id??''" :display="equipmentName(selected.camera_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="selectedFieldSave('camera_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'camera_id'))" /></label>
              <label>成像系统<InlineField :value="selected.optical_system_id??''" :display="equipmentName(selected.optical_system_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="selectedFieldSave('optical_system_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'optical_system_id'))" /></label>
              <label>滤镜<InlineField :value="selected.filter_id??''" :display="equipmentName(selected.filter_id)" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="selectedFieldSave('filter_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'filter_id'))" /></label>
              <label>帧用途<InlineField :value="selected.frame_type??''" :display="frameTypeLabel(selected.frame_type)" kind="select" :choices="[{value:'',label:'未指定'},...frameTypes.map(value=>({value,label:value}))]" :save="selectedFieldSave('frame_type')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_type'))" /></label>
              <label>ISO／Gain<ParameterModeField :value="parameterModeValue(selected)" :display="captureProfileModeDisplay(selected)" :unset-mode="null" :save="selectedParameterSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'parameter_mode'))" /></label>

              <label>曝光（秒）<InlineField :value="selected.exposure_seconds" kind="number" :save="selectedFieldSave('exposure_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'exposure_seconds'))" /></label>
              <label>温度（°C）<InlineField :value="selected.sensor_temperature_c" :display="selected.sensor_temperature_c==null?'未指定':displayTemperature(selected.sensor_temperature_c)+' °C'" kind="number" :save="selectedFieldSave('sensor_temperature_c')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'sensor_temperature_c'))" /></label>
              <label>Bin<InlineField :value="binEditValue(selected)" :display="binValue(selected)??'未指定'" kind="select" :choices="binEditChoices(selected)" :save="selectedBinSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'binning'))" /></label>
              <label>备注<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
              <label>状态<InlineField :value="selected.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
            </div>
          </template>
        </aside>
        </template>

        <section v-else class="apf-placeholder" :aria-label="areaTitles[activeArea]">
          <h1>{{ areaTitles[activeArea] }}</h1>
          <p>{{ areaMessages[activeArea] }}</p>
        </section>
      </main>
      <ImportDialog :open="importDialogOpen" :files="importFiles" :create-dataset="importCreatesDataset" :dataset-name="importDatasetName" @close="importDialogOpen=false" @submitted="importSubmitted" @upload-progress="updateUploadProgress" @upload-failed="progressRefreshToken++" />
      <DatasetEditor v-if="datasetEditorId" :dataset-id="datasetEditorId" :pending-asset-version-ids="datasetPendingIds" @close="closeDatasetEditor" @saved="datasetSaved" @updated="loadRecords" @saving="datasetInlineSaving" @failure="datasetInlineFailure" />
      <div v-if="previewUrl || previewError" class="apf-preview-overlay" role="dialog" aria-modal="true" aria-label="素材预览" @click.self="closePreview" @keydown.stop>
        <div class="apf-preview-dialog"><button type="button" @click="closePreview">关闭预览</button><p v-if="previewError" role="alert">{{previewError}}</p><img v-else :src="previewUrl" alt="素材图像或视频首帧预览" /></div>
      </div>
  </section>
</template>

<style>
.apf-workspace { position:relative; display:flex; flex:1 1 auto; width:100%; height:100%; min-height:0; font:inherit; color:var(--input-text,inherit); }
.apf-workspace button { display:inline-flex; min-height:32px; align-items:center; justify-content:center; gap:8px; padding:8px; border:0; border-radius:8px; color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); font:inherit; font-size:12px; font-weight:500; line-height:1; white-space:nowrap; cursor:pointer; transition:background-color .1s ease; }
.apf-workspace button:hover:not(:disabled) { background:var(--comfy-menu-bg,#353535); }
.apf-workspace button:focus-visible, .apf-workspace input:focus-visible, .apf-workspace select:focus-visible, .apf-workspace textarea:focus-visible { outline:1px solid var(--border-color,#4e4e4e); outline-offset:1px; }
.apf-workspace button:disabled { opacity:.5; cursor:not-allowed; }
.apf-table-scroll { margin:0 10px; min-width:0; overflow:auto; }
.apf-assets-table { border-collapse:collapse; min-width:1120px; width:100%; font-size:12px; }
.apf-table-scroll.simple .apf-assets-table { min-width:820px; }
.apf-table-scroll.detail .apf-assets-table { min-width:1440px; }
.apf-assets-table th,.apf-assets-table td { padding:6px; border-bottom:1px solid var(--border-color,#4e4e4e); text-align:left; vertical-align:middle; }
.apf-assets-table th { position:sticky; top:0; background:var(--comfy-menu-bg,#292929); }
.apf-assets-table tbody tr { cursor:pointer; }
.apf-assets-table.is-selecting .apf-inline-value,.apf-assets-table.is-selecting .apf-member-open { pointer-events:none; }
.apf-assets-table.is-deleting .apf-sort-button { pointer-events:none; }
.apf-sort-button { min-height:0; padding:0; border:0; background:transparent; color:inherit; font:inherit; text-align:left; }
.apf-assets-table tbody tr:hover,.apf-assets-table tbody tr[aria-selected="true"] { background:var(--comfy-menu-secondary-bg,#292929); }
.apf-assets-table td strong,.apf-assets-table td small { display:block; }
.apf-assets-table small { color:var(--descrip-text,#999); }
.apf-assets-table .apf-note-cell { min-width:140px; max-width:280px; white-space:pre-wrap; overflow-wrap:anywhere; }
.apf-assets-table .apf-thumb { display:block; width:100px; height:64px; min-height:64px; padding:0; overflow:hidden; }
.apf-assets-table .apf-thumb img { width:100%; height:100%; object-fit:contain; }
.apf-preview-overlay { position:absolute; inset:0; z-index:8; display:grid; place-items:center; padding:12px; background:#000b; }
.apf-preview-dialog { max-width:100%; max-height:100%; overflow:auto; padding:12px; background:var(--comfy-menu-bg,#292929); border:1px solid var(--border-color,#555); border-radius:8px; }
.apf-preview-dialog img { display:block; max-width:min(1024px,80vw); max-height:80vh; object-fit:contain; }
.apf-dataset-editor { z-index:6; }
.apf-nav { display:flex; flex:0 0 48px; flex-direction:column; align-items:center; gap:6px; padding:8px 4px; border-right:1px solid var(--border-color,#4e4e4e); background:var(--comfy-menu-bg,#202124); }
.apf-workspace .apf-nav button { display:grid; width:40px; min-height:42px; height:42px; padding:0; border-radius:6px; color:var(--descrip-text,#999); background:transparent; font-size:18px; }
.apf-workspace .apf-nav button:hover:not(:disabled) { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-workspace .apf-nav button[aria-current="page"] { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-record.selected { outline:1px solid var(--border-color,#4e4e4e); background:var(--comfy-menu-secondary-bg,#292929); }
.apf-main { position:relative; display:flex; flex:1; flex-direction:column; gap:10px; min-width:0; min-height:0; overflow:auto; padding-top:8px; }
.apf-toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.apf-heading { display:flex; align-items:center; gap:8px; flex:0 0 100%; min-width:0; white-space:nowrap; }
.apf-heading h1 { flex:0 0 auto; white-space:nowrap; }
.apf-heading-actions { display:flex; flex:0 0 auto; align-items:center; gap:6px; }
.apf-import-row { cursor:default; }
.apf-import-row__content { display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:6px 10px; align-items:center; }
.apf-import-row__content strong,.apf-import-row__content span { opacity:.58; }
.apf-import-row__content progress { grid-column:1/-1; width:100%; height:8px; }
.apf-toolbar, .apf-error, .apf-state, .apf-disabled, .apf-records, .apf-pagination, .apf-details { margin-left:10px; margin-right:10px; }
.apf-heading { position:relative; display:flex; flex:1 0 100%; align-items:center; gap:8px; min-width:0; }
.apf-heading h1 { flex:0 0 auto; margin:4px 0; color:var(--input-text,#ddd); font-size:16px; font-weight:600; line-height:1.25; white-space:nowrap; }
.apf-heading-actions { position:relative; display:flex; flex-wrap:wrap; align-items:center; gap:5px; margin-left:auto; }
.apf-workspace .apf-heading-actions button { min-height:28px; gap:6px; padding:5px 7px; font-size:11px; }
.apf-import-menu { position:absolute; z-index:8; top:calc(100% + 4px); right:38px; display:flex; min-width:120px; flex-direction:column; gap:4px; padding:5px; border:1px solid var(--border-color,#555); border-radius:7px; background:var(--comfy-menu-bg,#272727); box-shadow:0 6px 18px #0008; }
.apf-workspace .apf-import-menu button { justify-content:flex-start; }
.apf-import { display:flex; align-items:center; }
.apf-library-view { display:flex; gap:2px; padding:2px; border-radius:8px; background:var(--comfy-input-bg,#222); }
.apf-workspace .apf-library-view button { min-height:28px; padding:5px 8px; background:transparent; color:var(--descrip-text,#999); }
.apf-workspace .apf-library-view button[aria-pressed="true"] { color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); }
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
.apf-workspace button.apf-inline-value { min-height:25px; justify-content:flex-start; padding:2px 4px; background:transparent; white-space:pre-wrap; }
.apf-workspace .apf-member-open { min-height:22px; padding:2px 4px; background:transparent; color:var(--descrip-text,#999); }
.apf-records.grid { display:grid; grid-template-columns:1fr; gap:8px; }
.apf-records.list { display:flex; flex-direction:column; gap:6px; }
.apf-workspace .apf-record { display:flex; width:100%; min-height:68px; justify-content:flex-start; gap:12px; padding:10px; border:1px solid var(--border-color,#4e4e4e); text-align:left; white-space:normal; background:var(--comfy-menu-secondary-bg,#292929); }
.apf-record span:last-child { display:flex; flex-direction:column; gap:4px; min-width:0; }
.apf-record small { color:var(--descrip-text,#999); }
.apf-record-icon { font-size:22px; }
.apf-pagination { display:flex; gap:8px; align-items:center; margin-top:auto; }
.apf-pagination span { margin-right:auto; }
.apf-pagination label { display:flex; align-items:center; gap:6px; color:var(--descrip-text,#999); font-size:12px; }
.apf-pagination select { height:28px; padding:0 8px; border:1px solid var(--border-color,#4e4e4e); border-radius:7px; color:var(--input-text,#ddd); background:var(--comfy-input-bg,#222); font:inherit; }
.apf-classification-separator { margin:0 5px; color:var(--descrip-text,#999); font-size:.8em; opacity:.6; }
.apf-details { padding:10px; overflow:auto; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-bg,#353535); }
.apf-details pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:11px; }
.apf-detail-fields { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px 12px; }
.apf-detail-fields label { display:flex; min-width:0; flex-direction:column; gap:4px; color:var(--descrip-text,#999); font-size:12px; }
.apf-profile-links { display:grid; grid-template-columns:1fr; gap:6px; border:1px solid var(--border-color,#555); border-radius:6px; padding:8px; }
.apf-profile-links label { display:flex; flex-direction:row; align-items:center; gap:6px; }
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

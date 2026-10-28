<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { z } from 'zod'
import {
  assetSchema, capabilitiesSchema, datasetReferenceSchema, datasetSchema, libraryEntriesRemoveRequestSchema,
  libraryEntriesRemoveSchema,
  datasetVersionSchema, datasetMemberParametersUpdateSchema, equipmentSchema, pageSchema, projectAssetReferenceSchema,
  projectSchema, libraryItemSchema, taskSchema, equipmentSetupSchema, type Asset
} from '../api/contracts'
import { ApiClientError } from '../api/client'
import { assetApi } from '../api/index'
import type { ZodType } from 'zod'
import { useWorkspaceStore, type WorkspaceSection } from './store'
import PhotoPreviewDialog, { type PreviewPhoto } from './PhotoPreviewDialog.vue'
import ImportDialog from './ImportDialog.vue'
import LibraryTrashDialog from './LibraryTrashDialog.vue'
import SettingsTrashDialog from './SettingsTrashDialog.vue'
import { firstLevelImportFiles } from './folder-selection'
import LibraryPage from './LibraryPage.vue'
import SettingsPage from './SettingsPage.vue'

type RecordData = Record<string, any>
type EditorType = 'project' | 'equipment'
type InputField = { key: string; label: string; type?: string; options?: string[]; integer?: boolean }
type WorkspaceArea = 'library' | 'nodes' | 'software' | 'agent' | 'settings'

const store = useWorkspaceStore()
const props = defineProps<{ native?: boolean; sidebar?: boolean }>()
const emit = defineEmits<{ 'manage-equipment': []; 'back-to-library': [] }>()
if (props.sidebar) {
  store.selectSection('library')
  store.setQuery('')
  store.activeProjectId = null
  store.activeProjectRevision = null
}
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
const equipmentKindFilter = ref('')
const projectTargetFilter = ref('')
const setupKindFilter = ref('')
const equipmentKindFilterDraft = ref('')
const projectTargetFilterDraft = ref('')
const setupKindFilterDraft = ref('')
const managementFilterOpen = ref(false)
const managementFilterCount = computed(()=>Number(Boolean(equipmentKindFilter.value))+Number(Boolean(projectTargetFilter.value))+Number(Boolean(setupKindFilter.value)))
const setupDirty = ref(false)
const setupSaving = ref(false)
const calibrationDirty = ref(false)
const libraryCategory = ref<'all'|'light'|'calibration'>('all')
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
const bulkConfirmOpen = ref(false)
const bulkConfirmRows = ref<RecordData[]>([])
const trashOpen = ref(false)
const pendingManagementArchive = ref<{section:WorkspaceSection;row:RecordData;entry_type?:'project'|'equipment'|'equipment_setup'|'capture_preset'}>()
const managementArchiveBusy = ref(false)
const managementSelectMode = ref(false)
const managementSelection = ref(new Map<string,{section:WorkspaceSection;row:RecordData}>())
const managementTrashOpen = ref(false)
const managementChangeToken = ref(0)
const progressRefreshToken = ref(0)
const uploadProgress = ref<Record<string, { loaded: number; total: number }>>({})
const watchedTaskIds = ref<string[]>([])
type ImportTask = ReturnType<typeof taskSchema.parse>
const activeDataset = ref<RecordData>()
const outerLibraryState = ref<{query:string;offset:number;pageSize:10|20|50|'all';sort:{by:string;order:'asc'|'desc'};view:'simple'|'detail'}>()
const restoringOuterLibraryState = ref(false)
const previewUrls = ref<Record<string,string>>({})
const photoPreview = ref<PreviewPhoto>()
let photoPreviewRequest = 0
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




let searchTimer: ReturnType<typeof setTimeout> | undefined
let recordsLoadPending = false

const managementFilterBlocked = computed(() => dirty.value || setupSaving.value || saving.value || savingInline.value > 0)
const dirty = computed(() => setupDirty.value || calibrationDirty.value || (editorType.value !== undefined && JSON.stringify(draft.value) !== originalDraft.value))
const isAssetSection = computed(() =>
  store.section === 'calibration' || viewingProjectAssets.value ||
  (activeArea.value === 'library' && !viewingProjectDatasets.value)
)
const isAssetTable = computed(() => (activeArea.value === 'library' && !viewingProjectDatasets.value) ||
  store.section === 'calibration' || viewingProjectAssets.value)
const isDatasetTable = computed(() => store.section === 'projects' && viewingProjectDatasets.value)
const isLibraryItemsView = computed(() => activeArea.value === 'library' && !viewingProjectAssets.value && !viewingProjectDatasets.value && !activeDataset.value)
const isLibraryTableView = computed(() => activeArea.value === 'library' && !viewingProjectAssets.value && !viewingProjectDatasets.value)
const isDatasetMembersView = computed(() => activeArea.value === 'library' && store.section === 'library' && Boolean(activeDataset.value) && !viewingProjectAssets.value && !viewingProjectDatasets.value)
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
let datasetRefreshGeneration = 0

const specFields: Record<string, InputField[]> = {
  camera: [
    { key: 'sensor_mode', label: '传感器类型', options: ['mono', 'color'] },
    { key: 'sensor_width_px', label: '宽度（px）', type: 'number', integer: true },
    { key: 'sensor_height_px', label: '高度（px）', type: 'number', integer: true },
    { key: 'pixel_size_um', label: '像元尺寸（μm）', type: 'number' },
    { key: 'cfa_pattern', label: 'CFA 排列' }
  ],
  optical_system: [
    { key: 'aperture_mm', label: '口径（mm）', type: 'number' },
    { key: 'native_focal_length_mm', label: '基础焦距（mm）', type: 'number' },
    { key: 'effective_focal_length_mm', label: '使用减焦／增距镜后的焦距（mm）', type: 'number' },
    { key: 'focal_adjustment_note', label: '减焦镜／增距镜说明（可选）' }
  ],
  filter: [
    { key: 'bandwidth_nm', label: '带宽（nm）', type: 'number' },
  ],
  mount: [],
  accessory: []
}
specFields.telescope = specFields.optical_system
const frameTypes = ['light', 'bias', 'dark', 'flat', 'dark_flat']
const frameClasses = ['subframe', 'masterframe', 'video']
const cfaChoices=[
  {value:'',label:'未指定'},{value:'MONO',label:'无 CFA（单色）'},
  {value:'RGGB',label:'RGGB'},{value:'BGGR',label:'BGGR'},{value:'GRBG',label:'GRBG'},{value:'GBRG',label:'GBRG'},
  {value:'XTRANS',label:'X-Trans 6×6'},{value:'QUAD_BAYER',label:'Quad Bayer'}
]
const equipmentKinds = ['camera', 'telescope', 'filter']
const equipmentKindLabels:Record<string,string> = {camera:'相机',telescope:'望远镜',filter:'滤镜',mount:'赤道仪',accessory:'配件',optical_system:'成像系统（既有）'}
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
function specValue(field:InputField,specs:Record<string,unknown>){
  return field.key==='pixel_size_um' ? specs.pixel_size_um ?? specs.pixel_size_x_um ?? specs.pixel_size_y_um : specs[field.key]
}
function equipmentSpecsPayload(kind:string,specs:Record<string,unknown>){
  const result={...specs}
  if(kind==='camera'){
    const pixelSize=result.pixel_size_um
    delete result.pixel_size_um
    result.pixel_size_x_um=pixelSize??null
    result.pixel_size_y_um=pixelSize??null
  }
  return result
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
  const current=relatedEquipment.value.filter(item=>item.kind===kind).map(item=>({
    value:item.id,label:item.name+(item.status==='archived'?' · 回收站':''),disabled:item.status==='archived'||relatedEquipmentLoading.value||Boolean(relatedEquipmentError.value)
  }))
  const ids=new Set(current.map(item=>item.value))
  for(const snapshot of historicalEquipmentSnapshots()){
    if(snapshot.kind===kind&&typeof snapshot.id==='string'&&!ids.has(snapshot.id)){
      current.push({value:snapshot.id,label:String(snapshot.name)+' · 已从设备库移除',disabled:true})
      ids.add(snapshot.id)
    }
  }
  return current
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
    if (isDatasetMembersView.value && activeDataset.value) {
      const dataset=activeDataset.value
      const version=await assetApi.get('/astrophotoflow/api/v1/datasets/'+dataset.id+'/versions/'+dataset.current_version_id,datasetVersionSchema)
      if (generation !== loadGeneration || !isDatasetMembersView.value || activeDataset.value?.id !== dataset.id || activeDataset.value.current_version_id !== dataset.current_version_id) return
      const members=version.members.map(member=>({...member.asset,asset:member.asset,version:member.version,entry_type:'asset',member_position:member.position}))
      const needle=store.query.trim().toLocaleLowerCase()
      const filtered=members.filter(row=>!needle||String(row.name??'').toLocaleLowerCase().includes(needle))
      const value=(row:RecordData,by:string)=>({name:row.name,classification:row.classification?.frame_class,camera:materialEquipmentValue(row,'camera_id'),parameter_mode:row.parameters?.iso??row.parameters?.gain,exposure_seconds:row.parameters?.exposure_seconds,sensor_temperature_c:row.parameters?.sensor_temperature_c,binning:row.parameters?.binning_x,cfa_pattern:row.parameters?.cfa_pattern,optical_system:materialEquipmentValue(row,'optical_system_id'),filter:materialEquipmentValue(row,'filter_id'),integration_seconds:row.parameters?.integration_seconds,storage_mode:row.version?.storage_mode,status:row.status,notes:row.notes,member_position:row.member_position} as Record<string,unknown>)[by]
      filtered.sort((a,b)=>{
        const left=value(a,librarySort.value.by),right=value(b,librarySort.value.by)
        const direction=librarySort.value.order==='asc'?1:-1
        if(['parameter_mode','exposure_seconds','sensor_temperature_c','integration_seconds'].includes(librarySort.value.by)){
          if(left==null)return right==null?0:1
          if(right==null)return -1
          return (Number(left)-Number(right))*direction
        }
        return String(left??'').localeCompare(String(right??''),undefined,{numeric:true})*direction
      })
      loadedTotal=filtered.length
      const pageSize=store.pageSize==='all'?filtered.length:store.pageSize
      loadedRows=filtered.slice(store.offset,store.offset+pageSize)
      activeDataset.value={...dataset,version}
    } else if (store.section === 'library' && !viewingProjectAssets.value && !viewingProjectDatasets.value) {
      const filters = libraryFilterParams(activeFilters.value)
      const categoryFilters: Record<string,string[]> = libraryCategory.value==='light'
        ? {frame_type:['light']} : libraryCategory.value==='calibration' ? {role:['calibration']} : {}
      const emptyIntersection = Object.entries(categoryFilters).some(([key,values]) =>
        filters[key] !== undefined && filters[key].length > 0 && !filters[key].includes(values[0]))
      if (emptyIntersection) {
        loadedRows = []; loadedTotal = 0
      } else {
        const page = await loadWorkspacePage('/library/items', libraryItemSchema, {
          ...filters, ...categoryFilters, sort_by: librarySort.value.by, order: librarySort.value.order
        })
        loadedRows = page.items.map(item => item.entry_type === 'asset'
          ? {...item.asset, entry_type: 'asset', import_issue: item.import_issue}
          : {...item.dataset, dataset: item.dataset, version: item.version, entry_type: 'dataset', import_issue: item.import_issue, matching_member_count:item.matching_member_count})
        loadedTotal = page.total
      }
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
      const page = await loadWorkspacePage('/projects', projectSchema, {status: statusFilter.value,target_name:projectTargetFilter.value||undefined})
      loadedRows = page.items
      loadedTotal = page.total
    } else if (store.section === 'equipment') {
      const page = await loadWorkspacePage('/equipment', equipmentSchema, {status: statusFilter.value,kind:equipmentKindFilter.value})
      loadedRows = page.items
      loadedTotal = page.total
    } else {
      const page = await loadWorkspacePage('/equipment-setups', equipmentSetupSchema, {status:statusFilter.value,component_kind:setupKindFilter.value||undefined})
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
        photoPreviewBase(row, member) + '/thumbnail'
      )
      const url = URL.createObjectURL(blob)
      if (generation !== loadGeneration) URL.revokeObjectURL(url)
      else {
        if (previewUrls.value[row.id]) URL.revokeObjectURL(previewUrls.value[row.id]!)
        previewUrls.value[row.id] = url
      }
    } catch {
      // Unsupported or missing previews remain unavailable in the row.
    }
  }
}

function photoPreviewBase(row: RecordData, member: {asset: Asset; version: RecordData}) {
  return row.project_id && row.asset_version_id
    ? '/astrophotoflow/api/v1/projects/' + row.project_id + '/asset-references/' + row.id + '/previews'
    : '/astrophotoflow/api/v1/library/assets/' + member.asset.id + '/versions/' + member.version.id + '/previews'
}
async function openPhotoPreview(row: RecordData) {
  const current = ++photoPreviewRequest
  if (!await waitForInlineSave() || current !== photoPreviewRequest) return
  try {
    const member = await previewMember(row)
    if (current === photoPreviewRequest && member) photoPreview.value = {
      assetId: member.asset.id, versionId: member.version.id, title: member.asset.name,
      basePath: photoPreviewBase(row, member)
    }
  } catch (cause) { if (current === photoPreviewRequest) error.value = presentError(cause) }
}
function closePhotoPreview() { photoPreviewRequest++; photoPreview.value = undefined }
async function refreshPhotoThumbnails(photo: PreviewPhoto) {
  const generation = loadGeneration
  try {
    for (const row of rows.value) {
      const member = await previewMember(row)
      if (generation !== loadGeneration) return
      if (member?.version.id === photo.versionId) await loadThumbnails([row], generation)
    }
  } catch (cause) { if (generation === loadGeneration) error.value = presentError(cause) }
}
watch(() => JSON.stringify([
  activeArea.value, store.section, libraryCategory.value, activeDataset.value?.id, activeDataset.value?.current_version_id,
  store.activeProjectId, viewingProjectAssets.value, viewingProjectDatasets.value, addingProjectAssets.value, addingProjectDatasets.value,
  store.query, store.offset, store.pageSize, librarySort.value, libraryViewMode.value, activeFilters.value, selected.value?.id
]), closePhotoPreview, {flush:'sync'})

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

function managementEntryType(section:WorkspaceSection){
  if(section==='projects')return 'project' as const
  if(section==='equipment')return 'equipment' as const
  if(section==='equipment-setups')return 'equipment_setup' as const
  return undefined
}
function requestManagementArchive(row:RecordData,entryType?:'capture_preset') {
  if (!['projects','equipment','equipment-setups'].includes(store.section)) return
  pendingManagementArchive.value = {section:store.section,row,entry_type:entryType??managementEntryType(store.section)}
}

async function updateManagementStatus(row:RecordData,status:'active'|'archived',section:WorkspaceSection=store.section) {
  if (!await waitForInlineSave()) return
  let path:string
  let schema:ZodType<any>
  let payload:RecordData={base_revision:row.revision,status}
  if (section==='projects') {path='/projects/'+row.id;schema=projectSchema}
  else if (section==='equipment') {path='/equipment/'+row.id;schema=equipmentSchema;payload.kind=row.kind}
  else if (section==='equipment-setups') {path='/equipment-setups/'+row.id;schema=equipmentSetupSchema}
  else return
  error.value=undefined
  managementArchiveBusy.value=true
  try {
    await assetApi.send('/astrophotoflow/api/v1'+path,schema,'PATCH',payload)
    managementChangeToken.value++
    pendingManagementArchive.value=undefined
    await loadRecords()
  } catch (cause) {error.value=presentError(cause)}
  finally {managementArchiveBusy.value=false}
}

async function confirmManagementArchive() {
  const pending=pendingManagementArchive.value
  if (!pending||managementArchiveBusy.value) return
  if(managementSelectMode.value){await confirmSelectedManagementArchive();return}
  if (!await waitForInlineSave()) return
  const body={items:[{entry_type:pending.entry_type??managementEntryType(pending.section),id:pending.row.id,revision:pending.row.revision}]}
  managementArchiveBusy.value=true;error.value=undefined
  try{
    await assetApi.send('/astrophotoflow/api/v1/settings/trash/archive',z.object({archived_count:z.number().int()}).strict(),'POST',body)
    pendingManagementArchive.value=undefined;selected.value=undefined;managementChangeToken.value++;await loadRecords()
  }catch(cause){error.value=presentError(cause)}
  finally{managementArchiveBusy.value=false}
}

function managementSelectionKey(section:WorkspaceSection,row:RecordData){return section+':'+row.id}
function toggleManagementSelection(row:RecordData){
  const key=managementSelectionKey(store.section,row),next=new Map(managementSelection.value)
  if(next.has(key))next.delete(key);else next.set(key,{section:store.section,row})
  managementSelection.value=next
}
function toggleManagementPage(event:Event){
  const checked=(event.target as HTMLInputElement).checked,next=new Map(managementSelection.value)
  for(const row of rows.value){const key=managementSelectionKey(store.section,row);if(checked)next.set(key,{section:store.section,row});else next.delete(key)}
  managementSelection.value=next
}
const managementPageAllSelected=computed(()=>rows.value.length>0&&rows.value.every(row=>managementSelection.value.has(managementSelectionKey(store.section,row))))
const managementPagePartiallySelected=computed(()=>rows.value.some(row=>managementSelection.value.has(managementSelectionKey(store.section,row)))&&!managementPageAllSelected.value)
async function enterManagementSelectMode(){
  if(!await waitForInlineSave())return
  managementSelection.value=new Map();managementSelectMode.value=true;selected.value=undefined
}
function leaveManagementSelectMode(){managementSelectMode.value=false;managementSelection.value=new Map();pendingManagementArchive.value=undefined}
function requestSelectedManagementArchive(){
  if(!managementSelection.value.size)return
  const first=managementSelection.value.values().next().value as {section:WorkspaceSection;row:RecordData}
  if([...managementSelection.value.values()].some(item=>item.section!==first.section))return
  pendingManagementArchive.value={section:first.section,row:{...first.row,name:`${managementSelection.value.size} 条设置`}}
}
async function confirmSelectedManagementArchive(){
  if(!managementSelection.value.size||managementArchiveBusy.value)return
  if(!await waitForInlineSave())return
  const items=[...managementSelection.value.values()].map(({section,row})=>({entry_type:managementEntryType(section),id:row.id,revision:row.revision}))
  managementArchiveBusy.value=true;error.value=undefined
  try{
    await assetApi.send('/astrophotoflow/api/v1/settings/trash/archive',z.object({archived_count:z.number().int()}).strict(),'POST',{items})
    pendingManagementArchive.value=undefined;managementSelection.value=new Map();managementSelectMode.value=false;selected.value=undefined;managementChangeToken.value++;await loadRecords()
  }catch(cause){error.value=presentError(cause)}
  finally{managementArchiveBusy.value=false}
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
  leaveDatasetContext()
  editorType.value = undefined
  editingId.value = undefined
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = false
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  managementFilterOpen.value=false
  managementSelectMode.value=false
  managementSelection.value=new Map()
  equipmentKindFilter.value='';projectTargetFilter.value='';setupKindFilter.value=''
  store.selectSection(section)
  if (section === 'projects' || section === 'equipment' || section === 'equipment-setups') {
    lastManagementSection.value = section
  }
  selected.value = undefined
  loadRecords()
}

async function selectLibraryCategory(category:'all'|'light'|'calibration'){
  if(category===libraryCategory.value)return
  if(dirty.value&&!window.confirm('当前表单有未保存修改。放弃修改并切换吗？'))return
  if(!await waitForInlineSave())return
  leaveDatasetContext();selected.value=undefined
  store.query='';store.offset=0;activeFilters.value=emptyFilters()
  libraryCategory.value=category
  await loadRecords()
}

async function selectArea(area: WorkspaceArea, managementSection: WorkspaceSection = 'projects') {
  if (dirty.value && !window.confirm('当前表单有未保存修改。放弃修改并切换吗？')) return false
  if(!await waitForInlineSave())return false
  leaveDatasetContext()
  editorType.value = undefined
  editingId.value = undefined
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = false
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  selected.value = undefined
  filterPanelOpen.value = false
  managementFilterOpen.value=false
  managementSelectMode.value=false
  managementSelection.value=new Map()
  store.query = ''
  store.offset = 0
  store.activeProjectId = null
  store.activeProjectRevision = null
  statusFilter.value = 'active'
  roleFilter.value = ''
  frameTypeFilter.value = ''
  equipmentKindFilter.value='';projectTargetFilter.value='';setupKindFilter.value=''
  activeFilters.value = emptyFilters()
  activeArea.value = area
  if (area === 'library') {
    store.selectSection('library')
    void loadRelatedEquipment(true)
    loadRecords()
  } else if (area === 'settings') {
    lastManagementSection.value = managementSection
    store.selectSection(managementSection)
    loadRecords()
  } else {
    loadGeneration++
    loading.value = false
    error.value = undefined
  }
  return true
}

async function leavePage() {
  return dirty.value ? selectArea(activeArea.value, store.section) : waitForInlineSave()
}

defineExpose({ selectArea, activeArea, leavePage })

function startImport(kind:'files'|'folder') {
  importMenuOpen.value=false
  if(kind==='folder')folderPicker.value?.click()
  else filePicker.value?.click()
}

function applyFilters(filters: LibraryFilters) {
  if (!isLibraryItemsView.value) return
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

const registeredImportTaskIds = new Set<string>()
function importRegistrationCompleted(taskId: string) {
  if (registeredImportTaskIds.has(taskId)) return
  registeredImportTaskIds.add(taskId)
  clearBulkSelection()
  void loadRecords()
}

function importTaskCompleted(taskId: string) {
  watchedTaskIds.value=watchedTaskIds.value.filter(id=>id!==taskId)
  clearBulkSelection()
  void loadRecords()
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
  const registration = report.registration
  return registration ? (registration.total ? Math.round(registration.registered * 100 / registration.total) : 100) : task.items_total ? Math.min(100, Math.round(task.items_completed * 100 / task.items_total)) : 0
}

function uploadTaskLabel(task: ImportTask) {
  const report = task.report as Record<string, any>
  if (task.status === 'failed') return String(task.error?.message ?? '导入失败。')
  if (report.upload_manifest && !report.upload_complete) return '上传中 · ' + task.items_total + ' 个文件'
  if (report.registration) return (task.status === 'interrupted' ? '已暂停，进度已保存 · ' : '登记中 · ') + report.registration.registered + ' / ' + report.registration.total + ' 项已登记'
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
  } else {
    path='/equipment/'+row.id;schema=equipmentSchema
    const spec=field.startsWith('specs.')?specFields[row.kind]?.find(item=>item.key===field.slice(6)):undefined
    const fieldValue=spec?.type==='number'?(value==null||value===''?null:Number(value)):value
    payload=field==='specs.pixel_size_um'
      ? {base_revision:row.revision,kind:row.kind,specs:{pixel_size_x_um:fieldValue,pixel_size_y_um:fieldValue}}
      : field.startsWith('specs.')
      ? {base_revision:row.revision,kind:row.kind,specs:{[field.slice(6)]:fieldValue}}
      : {base_revision:row.revision,kind:row.kind,[field]:value}
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

    throw new Error('当前记录不支持拍摄参数编辑。')
  }catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:'参数保存失败。');throw cause}
  finally{finishInlineSave()}
}

async function updateDatasetMembers(row:RecordData,changes:RecordData){
  const members:RecordData[]=row.version?.members??[]
  if(!activeDataset.value&&row.matching_member_count<members.length)throw new Error('此筛选结果包含组内其他用途或条件的成员。请先打开图像组，在完整成员范围内编辑。')
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
  }else if(row.entry_type==='dataset'){
    await saveDatasetParameters(row,{binning_x:number,binning_y:number})
  }
}

async function openDataset(row:RecordData){
  const context={query:store.query,offset:store.offset,pageSize:store.pageSize,sort:{...librarySort.value},view:libraryViewMode.value}
  if(!await waitForInlineSave())return
  if(!isLibraryItemsView.value||store.query!==context.query||store.offset!==context.offset||store.pageSize!==context.pageSize||librarySort.value.by!==context.sort.by||librarySort.value.order!==context.sort.order||libraryViewMode.value!==context.view)return
  const currentRow=rows.value.find(item=>item.id===row.id&&item.entry_type==='dataset')
  if(!currentRow)return
  datasetRefreshGeneration++
  outerLibraryState.value={query:store.query,offset:store.offset,pageSize:store.pageSize,sort:{...librarySort.value},view:libraryViewMode.value}
  activeDataset.value={...(currentRow.dataset??currentRow),id:currentRow.dataset?.id??currentRow.id,current_version_id:currentRow.version?.id??currentRow.dataset?.current_version_id??currentRow.current_version_id,name:currentRow.dataset?.name??currentRow.name}
  store.query='';store.offset=0;store.pageSize=50;librarySort.value={by:'member_position',order:'asc'};libraryViewMode.value='detail'
  filterPanelOpen.value=false
  void loadRecords()
}
function leaveDatasetContext(){
  if(!activeDataset.value)return
  datasetRefreshGeneration++
  loadGeneration++
  activeDataset.value=undefined
  if(outerLibraryState.value){
    store.query=outerLibraryState.value.query;store.offset=outerLibraryState.value.offset;store.pageSize=outerLibraryState.value.pageSize
    librarySort.value=outerLibraryState.value.sort;libraryViewMode.value=outerLibraryState.value.view
  }else if(librarySort.value.by==='member_position'){
    librarySort.value={by:'created_at',order:'desc'}
  }
  outerLibraryState.value=undefined
  filterPanelOpen.value=false
  loading.value=false
  error.value=undefined
}
async function closeDataset(){
  if(calibrationDirty.value&&!window.confirm('图像组说明或校准关联有未保存修改。放弃修改吗？'))return
  if (dirty.value && !window.confirm('当前表单有未保存修改。放弃修改并返回吗？')) return
  if(!await waitForInlineSave())return
  datasetRefreshGeneration++
  loadGeneration++
  activeDataset.value=undefined
  if(outerLibraryState.value){
    restoringOuterLibraryState.value=true
    store.query=outerLibraryState.value.query;store.offset=outerLibraryState.value.offset;store.pageSize=outerLibraryState.value.pageSize
    librarySort.value=outerLibraryState.value.sort;libraryViewMode.value=outerLibraryState.value.view
    await nextTick()
    restoringOuterLibraryState.value=false
  }
  outerLibraryState.value=undefined
  await loadRecords()
}

async function calibrationUpdated(dataset:RecordData){
  if(activeDataset.value?.id===dataset.id){
    activeDataset.value={...dataset}
    await loadRecords()
  }
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

function openManagementFilter(){
  if(managementFilterBlocked.value)return
  equipmentKindFilterDraft.value=equipmentKindFilter.value
  projectTargetFilterDraft.value=projectTargetFilter.value
  setupKindFilterDraft.value=setupKindFilter.value
  managementFilterOpen.value=true
}
function applyManagementFilter(){
  if(managementFilterBlocked.value)return
  equipmentKindFilter.value=equipmentKindFilterDraft.value
  projectTargetFilter.value=projectTargetFilterDraft.value.trim()
  setupKindFilter.value=setupKindFilterDraft.value
  store.offset=0
  managementFilterOpen.value=false
}
function clearManagementFilter(){
  equipmentKindFilterDraft.value='';projectTargetFilterDraft.value='';setupKindFilterDraft.value=''
}
async function managementTrashChanged(){managementChangeToken.value++;await loadRecords()}

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
function removeSelectedLibraryEntries(){
  if(bulkDeleteBusy.value||!bulkSelection.value.size)return
  const selectedRows=rows.value.filter(row=>bulkSelection.value.has(bulkKey(row)))
  if(!selectedRows.length)return
  bulkConfirmRows.value=selectedRows.map(row=>({...row,asset:row.asset?{...row.asset}:undefined,dataset:row.dataset?{...row.dataset}:undefined}))
  bulkConfirmOpen.value=true
}
async function confirmRemoveSelectedLibraryEntries(){
  if(bulkDeleteBusy.value||!bulkConfirmRows.value.length)return
  const items=libraryEntriesRemoveRequestSchema.parse({items:bulkConfirmRows.value.map(row=>({
    entry_type:row.entry_type as 'asset'|'dataset',id:row.id,revision:row.revision,
    current_version_id:row.dataset?.current_version_id??row.asset?.current_version_id??row.current_version_id??null,
  }))}).items
  if(!items.length)return
  bulkConfirmOpen.value=false
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
    bulkConfirmRows.value=[]
    bulkDeleteBusy.value=false
    await loadRecords()
  }catch(cause){
    error.value=presentError(cause)
  }finally{bulkDeleteBusy.value=false}
}

function onLibraryRowClick(row:RecordData,event:MouseEvent){
  if(bulkSelectMode.value){toggleBulkSelection(row);return}
  if(row.entry_type==='dataset'&&isLibraryItemsView.value&&!(event.target instanceof Element&&event.target.closest('.apf-inline-field'))){
    openDataset(row)
    return
  }
  void selectRow(row)
}

async function selectRow(row: RecordData) {
  if(selected.value?.id===row.id)return
  if(setupDirty.value&&!window.confirm('当前组合或预设有未保存修改。放弃修改吗？'))return
  if(!await waitForInlineSave())return
  selected.value = row
  if(row.asset||row.scope==='shared'||row.entry_type==='dataset')
    void loadRelatedEquipment(true)
  if (store.section === 'projects' && !viewingProjectAssets.value && !viewingProjectDatasets.value) {
    store.activeProjectId = row.id
    store.activeProjectRevision = row.revision
  }
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
  if (type === 'project') draft.value = { name: '', target_name: '', notes: '' }
  if (type === 'equipment') draft.value = { kind: 'camera', name: '', model: '', serial_number: '', notes: '', specs: emptySpecs('camera') }

  originalDraft.value = JSON.stringify(draft.value)
  selected.value = undefined
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
  const specs = Object.fromEntries(specFields[row.kind].map(field => [field.key, textInput(specValue(field,row.specs))]))
  draft.value = {
    name: row.name, kind: row.kind, model: textInput(row.model), serial_number: textInput(row.serial_number),
    notes: textInput(row.notes), status: row.status, revision: row.revision, specs
  }
  beginEdit('equipment', row.id)
}

function editProject(row: RecordData) {
  draft.value = {
    name: row.name, target_name: textInput(row.target_name), notes: textInput(row.notes),
    status: row.status, revision: row.revision
  }
  beginEdit('project', row.id)
}



function beginEdit(type: EditorType, id: string) {
  editorType.value = type
  editingId.value = id
  originalDraft.value = JSON.stringify(draft.value)
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
      notes: nullableString(draft.value.notes)
    }
    if (editingId.value) Object.assign(payload, { base_revision: draft.value.revision, status: draft.value.status })
    return payload
  }
  if (editorType.value === 'equipment') {
    const specs = equipmentSpecsPayload(draft.value.kind,Object.fromEntries(specFields[draft.value.kind].map(field => [
      field.key, field.type ? inputNumber(draft.value.specs[field.key]) : nullableString(draft.value.specs[field.key])
    ])))
    const payload: RecordData = {
      kind: draft.value.kind, name: draft.value.name, model: nullableString(draft.value.model),
      serial_number: nullableString(draft.value.serial_number), notes: nullableString(draft.value.notes), specs
    }
    if (editingId.value) Object.assign(payload, { base_revision: draft.value.revision, status: draft.value.status })
    return payload
  }

}

async function saveEditor() {
  if (!editorType.value||editingId.value) return
  saving.value = true
  error.value = undefined
  const paths: Record<EditorType, string> = {
    project: '/projects', equipment: '/equipment'
  }
  const schemas: Record<EditorType, any> = {
    project: projectSchema, equipment: equipmentSchema
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
  if ('target_name' in row) return row.target_name || ''
  if (row.entry_type === 'dataset') return (row.member_count ?? 0) + ' 个成员'
  if (row.version) return '固定版本 · ' + (row.version.frame_type ?? '未分类')
  if (row.current_version) return row.current_version.frame_type ?? '未分类'
  if (row.kind) return equipmentKindLabels[row.kind] + (row.model ? ' · ' + row.model : '')
  if (row.components) return row.components.length + ' 个设备'
  if (row.camera_id) return row.frame_type + ' · 相机 ' + row.camera_id
  return ''
}
const rowAsset = (row: RecordData) => row.asset ?? row
const rowParameters = (row: RecordData) => rowAsset(row).parameters ?? {}
const rowClassification = (row: RecordData) => rowAsset(row).classification ?? {}
function equipmentName(id: string | null | undefined) {
  if (!id) return '未指定'
  return relatedEquipment.value.find(item => item.id === id)?.name ?? id.slice(0, 8)
}
function materialEquipmentValue(row:RecordData,key:string,fixed=false):string|undefined {
  const snapshot=fixed||row.project_id?row.version?.capture_snapshot?.equipment_snapshot:rowAsset(row).equipment_snapshot
  return snapshot?.[key]?.name
}
function materialEquipmentName(row:RecordData,key:string) {
  return materialEquipmentValue(row,key)??'未指定'
}
function historicalEquipmentSnapshots():RecordData[]{
  const snapshots:RecordData[]=[]
  for(const row of rows.value){
    const assets=[row.asset??row,...(row.version?.members??[]).map((member:RecordData)=>member.asset).filter(Boolean)]
    for(const asset of assets)for(const snapshot of Object.values(asset.equipment_snapshot??{})){
      if(snapshot&&typeof snapshot==='object')snapshots.push(snapshot as RecordData)
    }
  }
  return snapshots
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
  [() => store.query, () => store.offset, () => store.pageSize, statusFilter, roleFilter, frameTypeFilter, equipmentKindFilter, projectTargetFilter, setupKindFilter],
  ([query, offset, pageSize, status, role, frameType, kind, target, componentKind], [previousQuery, previousOffset, previousPageSize, previousStatus, previousRole, previousFrameType, previousKind, previousTarget, previousComponentKind]) => {
    if(restoringOuterLibraryState.value)return
    const queryChanged = query !== previousQuery
    const filtersChanged = pageSize !== previousPageSize || status !== previousStatus || role !== previousRole || frameType !== previousFrameType || kind !== previousKind || target !== previousTarget || componentKind !== previousComponentKind
    if(offset!==previousOffset||queryChanged||filtersChanged)clearBulkSelection()
    if(offset!==previousOffset||queryChanged||filtersChanged)managementSelection.value=new Map()
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
const workspaceContext = {
  store, activeArea, lastManagementSection, capabilities, rows,
  selected, total, loading, error, capabilityError,
  statusFilter, equipmentKindFilter, setupDirty, setupSaving, calibrationDirty, libraryCategory, selectLibraryCategory, roleFilter, frameTypeFilter, emptyFilters, activeFilters,
  filterPanelOpen, filterButton, activeFilterCount, viewingProjectAssets, viewingProjectDatasets,
  addingProjectAssets, addingProjectDatasets, importDialogOpen, importFiles, filePicker,
  folderPicker, importMenuOpen, importCreatesDataset, importDatasetName, libraryViewMode,
  librarySort, bulkSelectMode, bulkSelection, bulkDeleteBusy, bulkDeleteNotice,
  bulkConfirmOpen, bulkConfirmRows, trashOpen, managementTrashOpen, progressRefreshToken, uploadProgress,
  watchedTaskIds, activeDataset, outerLibraryState,
  restoringOuterLibraryState, previewUrls, editorType, editingId, draft,
  originalDraft, saving, savingInline, inlineSaveFailures, inlineSaveFailure,
  relatedEquipment, relatedEquipmentLoading, relatedEquipmentError, relatedEquipmentReady,
     dirty, isAssetSection,
  isAssetTable, isDatasetTable, isLibraryItemsView, isLibraryTableView, isDatasetMembersView,
  pageSelectionKeys, pageAllSelected, pagePartiallySelected, areaTitles, areaMessages,
  specFields, frameTypes, frameClasses, cfaChoices, equipmentKinds, equipmentKindLabels,
  specKind, specChoices, specDisplay, specValue, equipmentSpecsPayload, apiPath, loadWorkspacePage,
  libraryFilterParams, formListPath, loadAll, loadRelatedEquipment, equipmentChoiceMessage,
  equipmentChoices,    loadCapabilities,
  loadRecords, loadThumbnails, previewMember, openPhotoPreview, presentError, errorText,
  waitForInlineSave, selectSection, selectArea, startImport, applyFilters,
  filesChosen, foldersChosen, importSubmitted, importTaskCompleted, importRegistrationCompleted,
  updateUploadProgress, uploadTaskProgress, uploadTaskLabel, refreshLibrary,
  saveInlineField, selectedFieldSave, selectedParameterSave, selectedBinSave,
  syncEditingDraft, editorRow, saveEditorInline, saveEditorBin, saveEditorParameterGroup,
   performInlineFieldSave, saveRowField, saveDatasetParameter, saveDatasetClassification,
  saveDatasetParameters, saveParameterGroup, updateDatasetMembers, binValue, binEditValue,
  binEditChoices, datasetBinChoices, datasetRawValue, datasetParameterRaw, parameterModeValue,
  parameterModeDisplay,  displayTemperature, datasetTemperature, inlineFailureKey,
  editorInlineFailureKey, setInlineSaveFailure, clearInlineSaveFailure, finishInlineSave, saveBin,
  performBinSave, openDataset, leaveDatasetContext, closeDataset,
  calibrationUpdated, addSelectedAsset, removeSelectedAssetReference,
  addSelectedDataset, removeSelectedDatasetReference, setQuery, bulkKey, clearBulkSelection,
  toggleLibrarySort, sortAria, sortArrow, toggleBulkSelection, togglePageSelection,
  enterBulkSelectMode, leaveBulkSelectMode, removeSelectedLibraryEntries, confirmRemoveSelectedLibraryEntries, onLibraryRowClick,
  selectRow,  openProjectAssets, openProjectDatasets, openAvailableAssets,
  toggleProjectAssetMode, openAvailableDatasets, toggleProjectDatasetMode, leaveProjectAssets, emptySpecs,
  openCreate, textInput, inputNumber,  nullableString, requestManagementArchive, updateManagementStatus, managementArchiveBusy,
  managementSelectMode, managementSelection, managementPageAllSelected, managementPagePartiallySelected, managementChangeToken,
  toggleManagementSelection, toggleManagementPage, leaveManagementSelectMode,
  editEquipment, editProject,  beginEdit,
  closeEditor, onEquipmentKindChange, buildPayload, saveEditor, itemTitle,
  itemSubtitle, rowAsset, rowParameters, rowClassification, equipmentName, materialEquipmentName, materialEquipmentValue,
  captureValue, modeValue, datasetParameterMode, cfaLabel, frameClassLabel,
  frameTypeLabel, rowFrame, datasetMembers, datasetValue, datasetClassification
}
export type WorkspaceContext = typeof workspaceContext
provide('workspace', workspaceContext)

onMounted(async () => {
  void loadRelatedEquipment()
  await loadCapabilities()
  await loadRecords()
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  for (const url of Object.values(previewUrls.value)) URL.revokeObjectURL(url)
})
</script>

<template>
  <section class="apf-workspace" aria-label="AstroPhotoFlow 天文资产工作台"
    @pointerdown.stop @pointerup.stop @mousedown.stop @mouseup.stop
    @click.stop @contextmenu.stop @keydown.stop @keyup.stop>
      <nav v-if="!props.native" class="apf-nav" aria-label="AstroPhotoFlow 模块">
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
              <button v-if="activeDataset" type="button" @click="closeDataset">← 返回素材库</button>
              <button v-else-if="viewingProjectAssets || viewingProjectDatasets" type="button" @click="leaveProjectAssets">← 返回项目</button>
              <button v-else-if="props.native && activeArea === 'settings'" type="button" @click="emit('back-to-library')">← 返回素材库</button>
              <h1 v-if="!props.sidebar || activeDataset || activeArea !== 'library'">{{ activeDataset ? '素材库 / '+activeDataset.name : activeArea === 'library' ? '素材库' : (viewingProjectAssets ? '项目资产' : viewingProjectDatasets ? '项目数据集' : props.native ? '设备管理' : '设置') }}</h1>
              <span v-if="activeDataset" class="apf-state">图像组 · {{activeDataset.version?.members?.length??activeDataset.member_count??0}} 张</span>
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
                <button v-if="props.native" type="button" class="apf-equipment" @click="emit('manage-equipment')">设备管理</button>
                <button type="button" aria-label="刷新" @click="refreshLibrary"><i class="pi pi-refresh" aria-hidden="true"></i><span>刷新</span></button>
                <button type="button" :disabled="savingInline>0||Boolean(inlineSaveFailure)" @click="enterBulkSelectMode">批量删除</button>
                <button type="button" aria-label="打开回收站" title="回收站" @click="trashOpen=true">回收站</button>
                <div v-if="importMenuOpen" class="apf-import-menu">
                  <button type="button" @click="startImport('files')">选择文件</button>
                  <button type="button" @click="startImport('folder')">选择文件夹</button>
                </div>
                </template>
              </div>
            </div>
            <nav v-if="activeArea==='library'&&!activeDataset" class="apf-library-categories" aria-label="素材用途">
              <button v-for="(label,category) in {all:'全部素材',light:'亮场',calibration:'校准库'}" :key="category" type="button" :aria-current="libraryCategory===category?'page':undefined" @click="selectLibraryCategory(category)">{{label}}</button>
            </nav>
            <div v-if="activeArea === 'settings' && !viewingProjectAssets && !viewingProjectDatasets" class="apf-management-tabs" :aria-label="props.native ? '设备与资料类别' : '设置类别'">
              <button v-for="(title, section) in (props.native ? {equipment: '设备', 'equipment-setups': '使用组合', projects: '项目'} : { projects: '项目', equipment: '设备', 'equipment-setups': '使用组合' })"
                :key="section" type="button" :aria-current="store.section === section ? 'page' : undefined"
                @click="selectSection(section as WorkspaceSection)">{{ title }}</button>
            </div>
            <label class="apf-search">
              <i class="pi pi-search" aria-hidden="true"></i>
              <input :value="store.query" aria-label="搜索" placeholder="搜索名称" :disabled="bulkDeleteBusy||setupDirty" @input="setQuery" />
            </label>
            <select v-if="activeArea !== 'settings' && (store.section === 'projects' || store.section === 'equipment' || store.section === 'equipment-setups')"
              v-model="statusFilter" :disabled="setupDirty" aria-label="状态筛选">
              <option value="active">启用</option><option value="archived">已归档</option><option value="all">全部</option>
            </select>
            <div v-if="activeArea==='settings' && ['projects','equipment','equipment-setups'].includes(store.section) && !viewingProjectAssets && !viewingProjectDatasets" class="apf-management-filter-control">
              <button ref="managementFilterButton" type="button" :disabled="managementFilterBlocked" :aria-expanded="managementFilterOpen" @click="managementFilterOpen?managementFilterOpen=false:openManagementFilter()">筛选<span v-if="managementFilterCount">（{{managementFilterCount}}）</span></button>
              <div v-if="managementFilterOpen" class="apf-management-filter-panel">
                <label v-if="store.section==='projects'">拍摄目标<input v-model="projectTargetFilterDraft" placeholder="按目标筛选" /></label>
                <label v-if="store.section==='equipment'">设备类别<select v-model="equipmentKindFilterDraft"><option value="">全部设备</option><option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{equipmentKindLabels[kind]}}</option></select></label>
                <label v-if="store.section==='equipment-setups'">组合设备类别<select v-model="setupKindFilterDraft"><option value="">全部类别</option><option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{equipmentKindLabels[kind]}}</option></select></label>
                <div><button type="button" @click="clearManagementFilter">清除</button><button type="button" @click="applyManagementFilter" :disabled="managementFilterBlocked">应用</button></div>
              </div>
            </div>
            <button v-if="isLibraryItemsView" ref="filterButton" type="button" :disabled="bulkDeleteBusy" :aria-expanded="filterPanelOpen" @click="filterPanelOpen=!filterPanelOpen">
              筛选<span v-if="activeFilterCount">（{{activeFilterCount}}）</span>
            </button>
            <div v-if="isLibraryTableView" class="apf-library-view" aria-label="素材显示方式">
              <button type="button" :aria-pressed="libraryViewMode==='simple'" @click="libraryViewMode='simple'">简约</button>
              <button type="button" :aria-pressed="libraryViewMode==='detail'" @click="libraryViewMode='detail'">细节</button>
            </div>
            <button v-if="activeArea !== 'library' || viewingProjectAssets || viewingProjectDatasets" type="button" :disabled="setupDirty" @click="loadRecords"><i class="pi pi-refresh" aria-hidden="true"></i><span>刷新</span></button>
            <template v-if="activeArea==='settings' && ['projects','equipment','equipment-setups'].includes(store.section) && !viewingProjectAssets && !viewingProjectDatasets">
              <template v-if="managementSelectMode">
                <button type="button" :disabled="!managementSelection.size||managementArchiveBusy" @click="requestSelectedManagementArchive">移入回收站（{{managementSelection.size}}）</button>
                <button type="button" :disabled="managementArchiveBusy" @click="leaveManagementSelectMode">取消</button>
              </template>
              <template v-else>
                <button type="button" :disabled="loading||savingInline>0||Boolean(inlineSaveFailure)" @click="enterManagementSelectMode">批量删除</button>
                <button type="button" :disabled="setupDirty||dirty||savingInline>0||Boolean(inlineSaveFailure)" @click="managementTrashOpen=true">回收站</button>
              </template>
            </template>
            <button v-if="store.section === 'projects' && statusFilter!=='archived' && !managementSelectMode && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openCreate('project')">新建项目</button>
            <button v-if="store.section === 'equipment' && statusFilter!=='archived' && !managementSelectMode" type="button" @click="openCreate('equipment')">添加设备</button>
            <button v-if="store.section==='projects' && viewingProjectAssets" type="button" @click="toggleProjectAssetMode">{{addingProjectAssets?'查看已选资产':'添加素材'}}</button>
            <button v-if="store.section==='projects' && viewingProjectDatasets" type="button" @click="toggleProjectDatasetMode">{{addingProjectDatasets?'查看已选数据集':'添加数据集'}}</button>
          </div>
        <LibraryPage v-if="activeArea === 'library'" />
        <SettingsPage v-else />
      </template>
        <section v-else class="apf-placeholder" :aria-label="areaTitles[activeArea]">
          <h1>{{ areaTitles[activeArea] }}</h1>
          <p>{{ areaMessages[activeArea] }}</p>
        </section>
    </main>
      <PhotoPreviewDialog :photo="photoPreview" @close="closePhotoPreview" @updated="refreshPhotoThumbnails" />
      <LibraryTrashDialog :open="trashOpen" @close="trashOpen=false" @changed="refreshLibrary" />
      <SettingsTrashDialog :open="managementTrashOpen" @close="managementTrashOpen=false" @changed="managementTrashChanged" />
      <div v-if="bulkConfirmOpen" class="apf-trash-confirm-backdrop" role="presentation" @click.self="bulkConfirmOpen=false">
        <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="bulk-trash-confirm-title">
          <h2 id="bulk-trash-confirm-title">确认移入垃圾桶</h2>
          <p>将移入垃圾桶 {{bulkConfirmRows.length}} 条素材库记录。原文件保留，可恢复。</p>
          <ul><li v-for="row in bulkConfirmRows" :key="row.entry_type+':'+row.id">{{itemTitle(row)}}<span v-if="row.entry_type==='dataset'">（数据集，{{row.version?.members?.length??row.dataset?.member_count??0}} 张照片）</span><span v-else>（照片）</span></li></ul>
          <button type="button" @click="bulkConfirmOpen=false">取消</button><button type="button" @click="confirmRemoveSelectedLibraryEntries">移入垃圾桶</button>
        </section>
      </div>
      <div v-if="pendingManagementArchive" class="apf-trash-confirm-backdrop" role="presentation" @click.self="pendingManagementArchive=undefined">
        <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="management-archive-title">
          <h2 id="management-archive-title">移入回收站</h2>
          <p v-if="managementSelectMode">将 {{managementSelection.size}} 条设置移入回收站。关联素材及其设备快照会保留，可在回收站恢复。</p>
          <p v-else>将“{{itemTitle(pendingManagementArchive.row)}}”移入回收站。记录、关联素材和历史预设会保留，可随时恢复。</p>
          <button type="button" :disabled="managementArchiveBusy" @click="pendingManagementArchive=undefined">取消</button>
          <button type="button" :disabled="managementArchiveBusy" @click="confirmManagementArchive">{{managementArchiveBusy?'处理中…':'确认移入回收站'}}</button>
        </section>
      </div>
      <ImportDialog :open="importDialogOpen" :files="importFiles" :create-dataset="importCreatesDataset" :dataset-name="importDatasetName" @close="importDialogOpen=false" @submitted="importSubmitted" @upload-progress="updateUploadProgress" @upload-failed="progressRefreshToken++" />
  </section>
</template>

<style>
.apf-library-categories{display:flex;gap:8px;flex-wrap:wrap}
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
.apf-assets-table .apf-thumb { display:flex; align-items:center; justify-content:center; width:100px; height:64px; overflow:hidden; border-radius:8px; background:var(--comfy-menu-secondary-bg,#292929); cursor:pointer; border:0; padding:0; color:inherit; }
.apf-assets-table .apf-thumb img { width:100%; height:100%; object-fit:contain; }
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
.apf-heading { position:relative; display:flex; flex-wrap:wrap; flex:1 0 100%; align-items:center; gap:8px; min-width:0; }
.apf-heading h1 { flex:0 0 auto; margin:4px 0; color:var(--input-text,#ddd); font-size:16px; font-weight:600; line-height:1.25; white-space:nowrap; }
.apf-heading-actions { position:relative; display:flex; flex:0 1 auto; flex-wrap:wrap; min-width:0; align-items:center; gap:5px; margin-left:auto; }
.apf-trash-confirm-backdrop { position:fixed; inset:0; z-index:30; display:grid; place-items:center; padding:16px; background:#000a; }
.apf-trash-confirm { max-width:560px; max-height:80vh; overflow:auto; padding:18px; border:1px solid var(--border-color,#555); border-radius:10px; background:var(--comfy-menu-bg,#292929); box-shadow:0 8px 40px #0009; }
.apf-trash-confirm h2 { margin:0 0 10px; font-size:16px; }
.apf-trash-confirm li { margin:4px 0; }
.apf-trash-confirm button+button { margin-left:8px; }
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
.apf-toolbar-filter { display:flex; flex:0 0 auto; align-items:center; gap:6px; white-space:nowrap; }
.apf-management-filter-control { position:relative; }
.apf-management-filter-panel { position:absolute; z-index:12; top:calc(100% + 6px); left:0; display:grid; min-width:230px; gap:10px; padding:12px; border:1px solid var(--border-color,#555); border-radius:8px; background:var(--comfy-menu-bg,#292929); box-shadow:0 6px 24px #0008; }
.apf-management-filter-panel label { display:flex; flex-direction:column; gap:5px; color:var(--descrip-text,#aaa); font-size:12px; }
.apf-management-filter-panel input { height:30px; padding:0 8px; border:1px solid var(--border-color,#555); border-radius:7px; color:var(--input-text,#ddd); background:var(--comfy-input-bg,#222); font:inherit; }
.apf-management-filter-panel>div { display:flex; justify-content:flex-end; gap:6px; }
.apf-search { display:flex; flex:1 1 145px; min-width:0; height:36px; align-items:center; gap:8px; padding:0 10px; border:1px solid var(--border-color,#4e4e4e); border-radius:9px; color:var(--descrip-text,#999); background:var(--comfy-input-bg,#222); }
.apf-search:focus-within { border-color:var(--input-text,#ddd); }
.apf-search input { width:100%; min-width:0; border:0; outline:0; color:var(--input-text,#ddd); background:transparent; font:inherit; font-size:12px; }
.apf-search input::placeholder { color:var(--descrip-text,#999); }
.apf-workspace button.apf-inline-value { min-height:25px; justify-content:flex-start; padding:2px 4px; background:transparent; white-space:pre-wrap; }
.apf-workspace .apf-member-open { min-height:22px; padding:2px 4px; background:transparent; color:var(--descrip-text,#999); }
.apf-records.grid { display:grid; grid-template-columns:1fr; gap:8px; }
.apf-records.list { display:flex; flex-direction:column; gap:6px; }
.apf-management-select-page,.apf-management-record-select { display:flex; align-items:center; gap:12px; padding:10px; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-secondary-bg,#292929); }
.apf-management-select-page { width:max-content; padding:6px 10px; }
.apf-management-record-select span:last-child { display:flex; min-width:0; flex-direction:column; gap:4px; }
.apf-management-record-select small { color:var(--descrip-text,#999); }
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

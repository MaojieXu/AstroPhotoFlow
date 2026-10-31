<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { z } from 'zod'
import {
  assetSchema, capabilitiesSchema, datasetReferenceSchema, datasetSchema, libraryEntriesRemoveRequestSchema,
  libraryEntriesRemoveSchema,
  datasetVersionSchema, datasetMemberParametersUpdateSchema, equipmentSchema, pageSchema, projectAssetReferenceSchema,
  projectSchema, libraryItemSchema, equipmentSetupSchema, type Asset
} from '../api/contracts'
import { ApiClientError } from '../api/client'
import type { Equipment } from '../api/contracts'
import type { EquipmentDraft } from './EquipmentFields.vue'
import { assetApi } from '../api/index'
import type { ZodType } from 'zod'
import { useWorkspaceStore, type WorkspaceSection } from './store'
import PhotoPreviewDialog, { type PreviewPhoto } from './PhotoPreviewDialog.vue'
import type { MediaViewerRequest } from '../api/media'
import ImportDialog from './ImportDialog.vue'
import LibraryTrashDialog from './LibraryTrashDialog.vue'
import EquipmentDeleteDialog, { type EquipmentDeleteItem } from './EquipmentDeleteDialog.vue'
import LocalImportPicker from './LocalImportPicker.vue'
import ImportIssueDialog from './ImportIssueDialog.vue'
import type { LocalImportFile } from '../api/contracts'
import type { ImportNotice } from './libraryControls'
import { canvasDataRequestSchema } from '../api/canvas'
import type { CanvasDataRequest } from '../api/canvas'
import LibraryPage from './LibraryPage.vue'
import SettingsPage from './SettingsPage.vue'
import EquipmentSetupManager from './EquipmentSetupManager.vue'
import LibraryButton from './LibraryButton.vue'
import LibrarySelect from './LibrarySelect.vue'
import LibraryMenu from './LibraryMenu.vue'
import LibraryTabs from './LibraryTabs.vue'
import { libraryControlsKey } from './libraryControls'
import type { LibraryControls, LibraryMenuItem } from './libraryControls'
import { displayLabel, parameterSummary } from './presentation'
import './equipmentCompact.css'

type RecordData = Record<string, any>
type EditorType = 'project' | 'equipment'
type InputField = { key: string; label: string; type?: string; options?: string[]; integer?: boolean }
type WorkspaceArea = 'library' | 'nodes' | 'software' | 'agent' | 'settings'
type SetupSortField = 'created_at' | 'name' | 'camera' | 'telescope' | 'mount' | 'filter' | 'accessory'

const store = useWorkspaceStore()
const props = defineProps<{ native?: boolean; sidebar?: boolean; controls?: LibraryControls }>()
provide(libraryControlsKey, props.controls)
const emit = defineEmits<{ 'manage-equipment': []; 'back-to-library': []; 'notify-success': [message: string]; 'notify-import': [notice: ImportNotice]; 'open-workbench-settings': [] }>()

function canvasSource(row: RecordData): CanvasDataRequest | undefined {
  if (row.project_id || bulkSelectMode.value || savingInline.value || inlineSaveFailure.value) return
  const version = row.version ?? row.current_version
  if (!version) return
  if (row.entry_type === 'dataset') {
    if (!version.members?.length || version.members.some((member: { version: { availability: string } }) => member.version.availability !== 'available')) return
  } else if (version.availability !== 'available') return
  const source = canvasDataRequestSchema.safeParse({
    entry_type: row.entry_type === 'dataset' ? 'dataset' : 'asset',
    id: row.dataset?.id ?? row.asset?.id ?? row.id,
    version_id: version.id
  })
  return source.success ? source.data : undefined
}

if (props.sidebar) {
  store.selectSection('library')
  store.setQuery('')
  store.activeProjectId = null
  store.activeProjectRevision = null
}
const activeArea = ref<WorkspaceArea>('library')
const isEquipmentManagement = computed(() => activeArea.value === 'settings' && ['equipment', 'equipment-setups'].includes(store.section))
const recordPageSize = computed(() => isEquipmentManagement.value ? 50 : store.pageSize)
const setupManager = ref<InstanceType<typeof EquipmentSetupManager>>()
const equipmentMenu = ref<InstanceType<typeof LibraryMenu>>()
const libraryMenu = ref<InstanceType<typeof LibraryMenu>>()
const lastManagementSection = ref<WorkspaceSection>('equipment-setups')
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
const projectTargetFilterDraft = ref('')
const managementFilterOpen = ref(false)
const managementFilterCount = computed(()=>Number(Boolean(projectTargetFilter.value)))
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
const filterButton = ref<HTMLElement>()
const activeFilterCount = computed(() => Object.values(activeFilters.value).filter(value =>
  Array.isArray(value) ? value.length > 0 : value !== ''
).length)
const viewingProjectAssets = ref(false)
const viewingProjectDatasets = ref(false)
const addingProjectAssets = ref(false)
const addingProjectDatasets = ref(false)
const importDialogOpen = ref(false)
const importFiles = ref<LocalImportFile[]>([])
const localPickerMode = ref<'files'|'folder'>()
const importWorkspace = ref('')
const importIssue = ref<{taskId:string;category:'content'|'preview'}>()
function showImportIssue(taskId:string,category:'content'|'preview'){importIssue.value={taskId,category}}
function notifyImport(notice:ImportNotice){emit('notify-import',notice)}
const importMenuOpen = ref(false)
const importCreatesDataset = ref(false)
const importDatasetName = ref('')
const libraryViewMode = ref<'simple' | 'detail'>('simple')
const librarySort = ref({by: 'created_at', order: 'desc' as 'asc' | 'desc'})
const setupSort = ref({by: 'created_at' as SetupSortField, order: 'desc' as 'asc' | 'desc'})
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
const equipmentDeleteItems = ref<EquipmentDeleteItem[]>()
function requestEquipmentDeleteSelection(items:EquipmentDeleteItem[]){equipmentDeleteItems.value=items}
function requestEquipmentDelete(row:RecordData,entryType:'equipment'|'equipment_setup'|'capture_preset'=store.section==='equipment'?'equipment':'equipment_setup') {
  equipmentDeleteItems.value=[{entry_type:entryType,id:row.id,revision:row.revision}]
}
function requestSelectedEquipmentDelete(){
  equipmentDeleteItems.value=[...managementSelection.value.values()].map(({section,row})=>({entry_type:section==='equipment'?'equipment':'equipment_setup',id:row.id,revision:row.revision}))
}
async function equipmentDeleted(){
  selected.value=undefined;managementSelection.value=new Map();managementSelectMode.value=false
  managementChangeToken.value++;await loadRelatedEquipment(true);await loadRecords()
}
const managementChangeToken = ref(0)
const progressRefreshToken = ref(0)
const watchedTaskIds = ref<string[]>([])
const activeDataset = ref<RecordData>()
const outerLibraryState = ref<{query:string;offset:number;pageSize:10|20|50|'all';sort:{by:string;order:'asc'|'desc'};view:'simple'|'detail'}>()
const restoringOuterLibraryState = ref(false)
const previewUrls = ref<Record<string,string>>({})
const photoPreview = ref<PreviewPhoto>()
const mediaPreview = ref<MediaViewerRequest>()
let photoPreviewRequest = 0
const editorType = ref<EditorType>()
const editingId = ref<string>()
const draft = ref<RecordData>({})
const originalDraft = ref('')
const saving = ref(false)
const savingInline = ref(0)
const inlineSaveFailures = ref<Record<string,string>>({})
const inlineSaveFailure = computed(() => Object.values(inlineSaveFailures.value).at(-1) ?? '')
const relatedEquipment = ref<Equipment[]>([])
const relatedEquipmentLoading = ref(false)
const relatedEquipmentError = ref('')
const relatedEquipmentReady = ref(false)




let searchTimer: ReturnType<typeof setTimeout> | undefined
let recordsLoadPending = false

const managementFilterBlocked = computed(() => dirty.value || setupSaving.value || saving.value || savingInline.value > 0)
function closeEquipmentMenu(restoreFocus = false) {
  equipmentMenu.value?.close(restoreFocus)
}
function dismissEquipmentMenu(event: PointerEvent) {
  equipmentMenu.value?.dismiss(event)
  libraryMenu.value?.dismiss(event)
}
function filterEquipmentKind(value: string | number | null | undefined) {
  if (managementFilterBlocked.value) return
  store.offset = 0
  equipmentKindFilter.value = String(value ?? '')
}
async function refreshEquipment() {
  closeEquipmentMenu()
  await loadRelatedEquipment(true)
  await loadRecords()
}
const dirty = computed(() => setupDirty.value || calibrationDirty.value || (editorType.value !== undefined && JSON.stringify(draft.value) !== originalDraft.value))
const equipmentMenuItems = computed(() => {
  const current=selected.value
  return [
  {get label() { return uiT('apfUi.refresh') },disabled:managementFilterBlocked.value||loading.value,command:refreshEquipment},
  ...(!managementSelectMode.value?[{get label() { return uiT('apfUi.manage_in_bulk') },disabled:managementFilterBlocked.value||loading.value,command:enterManagementSelectMode}]:[]),
  ...(store.section==='equipment-setups'&&current?[{get label() { return uiT('apfUi.delete_setup') },disabled:managementFilterBlocked.value||loading.value,command:()=>requestEquipmentDelete(current)}]:[])
  ]
})
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
const libraryToolbarBlocked = computed(() => bulkDeleteBusy.value || savingInline.value > 0 || Boolean(inlineSaveFailure.value) || setupDirty.value)
const libraryMenuItems = computed<LibraryMenuItem[]>(() => [
  { get label() { return uiT('apfUi.refresh') }, disabled: libraryToolbarBlocked.value || loading.value, command: refreshLibrary },
  ...(isLibraryItemsView.value ? [
    { get label() { return uiT('apfUi.manage_in_bulk') }, disabled: libraryToolbarBlocked.value || loading.value, command: enterBulkSelectMode },
    { get label() { return uiT('apfUi.trash_ba35dc') }, disabled: libraryToolbarBlocked.value, command: () => { trashOpen.value = true } }
  ] : []),
  { get label() { return uiT('apfUi.display_mode') }, disabled: libraryToolbarBlocked.value, radioGroup: {
    value: libraryViewMode.value,
    options: ([['simple', uiT('apfUi.compact')], ['detail', uiT('apfUi.details')]] as const).map(([value, label]) => ({ value, label, command: () => { libraryViewMode.value = value } }))
  } },
  { get label() { return uiT('apfUi.items_per_page') }, disabled: libraryToolbarBlocked.value || loading.value, radioGroup: {
    value: String(store.pageSize),
    options: ([10, 20, 50, 'all'] as const).map(value => ({ value: String(value), label: value === 'all' ? uiT('apfUi.all') : String(value), command: () => store.setPageSize(value) }))
  } }
])
function notifyImportSuccess(message: string) { emit('notify-success', message) }

const pageSelectionKeys = computed(() => rows.value.map(row => bulkKey(row)))
const pageAllSelected = computed(() => pageSelectionKeys.value.length > 0 && pageSelectionKeys.value.every(key => bulkSelection.value.has(key)))
const pagePartiallySelected = computed(() => pageSelectionKeys.value.some(key => bulkSelection.value.has(key)) && !pageAllSelected.value)
const areaTitles: Record<WorkspaceArea, string> = {
  get library() { return uiT('apfUi.library') },
  get nodes() { return uiT('apfUi.node_repository') },
  get software() { return uiT('apfUi.available_software') },
  get agent() { return uiT('apfUi.agent_chat') },
  get settings() { return uiT('apfUi.equipment_manager') }
}
const areaMessages: Partial<Record<WorkspaceArea, string>> = {
  get nodes() { return uiT('apfUi.this_area_is_reserved_for_the_node_repository_the_catalog_is_not_conne') },
  get software() { return uiT('apfUi.this_area_is_reserved_for_available_software_catalog_and_installation_') },
  get agent() { return uiT('apfUi.this_area_is_reserved_for_agent_chat_chat_is_not_connected_yet') }
}
let loadGeneration = 0
let datasetRefreshGeneration = 0

const specFields: Record<string, InputField[]> = {
  camera: [
    { key: 'sensor_mode', get label() { return uiT('apfUi.sensor_type') }, options: ['mono', 'color'] },
    { key: 'sensor_width_px', get label() { return uiT('apfUi.width_px') }, type: 'number', integer: true },
    { key: 'sensor_height_px', get label() { return uiT('apfUi.height_px') }, type: 'number', integer: true },
    { key: 'pixel_size_um', get label() { return uiT('apfUi.pixel_size_m') }, type: 'number' },
    { key: 'cfa_pattern', get label() { return uiT('apfUi.cfa_pattern') } }
  ],
  optical_system: [
    { key: 'aperture_mm', get label() { return uiT('apfUi.aperture_mm') }, type: 'number' },
    { key: 'native_focal_length_mm', get label() { return uiT('apfUi.base_focal_length_mm') }, type: 'number' },
    { key: 'effective_focal_length_mm', get label() { return uiT('apfUi.focal_length_with_reducer_barlow_mm') }, type: 'number' },
    { key: 'focal_adjustment_note', get label() { return uiT('apfUi.reducer_barlow_description_optional') } }
  ],
  filter: [
    { key: 'bandwidth_nm', get label() { return uiT('apfUi.bandwidth_nm') }, type: 'number' },
  ],
  mount: [
    {key:'mount_type',get label() { return uiT('apfUi.mount_type') }},
    {key:'payload_kg',get label() { return uiT('apfUi.payload_kg') },type:'number'},
    {key:'connection_note',get label() { return uiT('apfUi.connection_description') }}
  ],
  accessory: [
    {key:'accessory_type',get label() { return uiT('apfUi.accessory_type') }},
    {key:'connection_note',get label() { return uiT('apfUi.connection_description') }}
  ]
}
specFields.telescope = specFields.optical_system
const frameTypes = ['light', 'bias', 'dark', 'flat', 'dark_flat']
const frameClasses = ['subframe', 'masterframe', 'video']
const cfaChoices=[
  {value:'',get label() { return uiT('apfUi.not_specified') }},{value:'MONO',get label() { return uiT('apfUi.no_cfa_monochrome') }},
  {value:'RGGB',label:'RGGB'},{value:'BGGR',label:'BGGR'},{value:'GRBG',label:'GRBG'},{value:'GBRG',label:'GBRG'},
  {value:'XTRANS',label:'X-Trans 6×6'},{value:'QUAD_BAYER',label:'Quad Bayer'}
]
const equipmentKinds = ['camera', 'telescope', 'filter', 'mount', 'accessory'] as const
const equipmentKindLabels:Record<string,string> = {get camera() { return uiT('apfUi.camera_dacf07') },get telescope() { return uiT('apfUi.telescope') },get filter() { return uiT('apfUi.filter') },get mount() { return uiT('apfUi.mount') },get accessory() { return uiT('apfUi.accessory') },get optical_system() { return uiT('apfUi.imaging_system_existing') }}
const equipmentKindIcons:Record<string,string> = {camera:'icon-[lucide--camera]',telescope:'icon-[lucide--telescope]',filter:'icon-[lucide--filter]',mount:'icon-[lucide--compass]',accessory:'icon-[lucide--wrench]',optical_system:'icon-[lucide--telescope]'}
function specKind(field:InputField):'number'|'select'|'text'{
  return field.key==='cfa_pattern'||field.options?'select':field.type==='number'?'number':'text'
}
function specChoices(field:InputField){
  if(field.key==='cfa_pattern')return cfaChoices
  if(field.options)return [{value:'',get label() { return uiT('apfUi.not_specified') }},...field.options.map(value=>({value,label:field.key==='sensor_mode'?({get mono() { return uiT('apfUi.monochrome') },get color() { return uiT('apfUi.color') }} as Record<string,string>)[value]??value:value}))]
  return []
}
function specDisplay(field:InputField,value:unknown){
  if(value===null||value===undefined||value==='')return uiT('apfUi.not_specified')
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
  const pageSize = recordPageSize.value
  const limit = pageSize === 'all' ? 200 : pageSize
  const getPage = (offset: number) => assetApi.get(
    apiPath(path, {...params, limit, offset}), pageSchema(schema)
  )
  const first = await getPage(pageSize === 'all' ? 0 : store.offset)
  if (pageSize !== 'all') return first
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
  if(relatedEquipmentLoading.value)return uiT('apfUi.reading_equipment_list')
  if(relatedEquipmentError.value)return relatedEquipmentError.value
  const names:Record<string,string>={get camera() { return uiT('apfUi.camera_dacf07') },get optical_system() { return uiT('apfUi.imaging_system') },get filter() { return uiT('apfUi.filter') }}
  return relatedEquipment.value.some(item=>item.kind===kind)?'':uiT('apfUi.not_registered_yet')+(names[kind]??uiT('apfUi.equipment'))+uiT('apfUi.add_it_in_settings_equipment_first')
}

function equipmentChoices(kind:string){
  const current=relatedEquipment.value.filter(item=>item.kind===kind).map(item=>({
    value:item.id,label:item.name+(item.status==='archived'?uiT('apfUi.trash'):''),disabled:item.status==='archived'||relatedEquipmentLoading.value||Boolean(relatedEquipmentError.value)
  }))
  const ids=new Set(current.map(item=>item.value))
  for(const snapshot of historicalEquipmentSnapshots()){
    if(snapshot.kind===kind&&typeof snapshot.id==='string'&&!ids.has(snapshot.id)){
      current.push({value:snapshot.id,label:String(snapshot.name)+uiT('apfUi.removed_from_equipment_library'),disabled:true})
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
      loadedRows = isAdding ? page.items.map(row => ({...row, dataset: row, entry_type: 'dataset'})) : page.items
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
      const page = await loadWorkspacePage('/equipment-setups', equipmentSetupSchema, {
        status:statusFilter.value, sort_by:setupSort.value.by, order:setupSort.value.order
      })
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
    if (isEquipmentManagement.value && store.offset > 0 && store.offset >= loadedTotal) {
      store.offset = loadedTotal ? Math.floor((loadedTotal - 1) / 50) * 50 : 0
      return
    }
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
    if (props.controls?.mediaViewer) {
      const group = row.version?.members ? row.version : row.current_version_id && row.member_count != null
        ? await assetApi.get('/astrophotoflow/api/v1/datasets/' + row.id + '/versions/' + row.current_version_id, datasetVersionSchema)
        : undefined
      const single = group ? undefined : await previewMember(row)
      const members = group ? group.members.map((member: {asset: Asset; version: RecordData}) => ({
        title: member.asset.name,
        basePath: photoPreviewBase(row, member)
      })) : single ? [{ title: single.asset.name, basePath: photoPreviewBase(row, single) }] : []
      if (current === photoPreviewRequest && members.length) mediaPreview.value = {
        index: 0, total: members.length,
        member: async (index, signal) => {
          if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
          const member = members[index]
          if (!member) throw new ApiClientError(uiT('apfUi.group_member_is_outside_the_fixed_selection'), 'contract')
          return member
        }
      }
      return
    }
    const member = await previewMember(row)
    if (current === photoPreviewRequest && member) photoPreview.value = {
      assetId: member.asset.id, versionId: member.version.id, title: member.asset.name,
      basePath: photoPreviewBase(row, member)
    }
  } catch (cause) { if (current === photoPreviewRequest) error.value = presentError(cause) }
}
function closePhotoPreview() { photoPreviewRequest++; photoPreview.value = undefined; mediaPreview.value = undefined }
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
  return new ApiClientError(uiT('apfUi.request_failed'), 'contract')
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
  if(isEquipmentManagement.value)selected.value=undefined
}
function toggleManagementPage(checked:boolean){
  const next=new Map(managementSelection.value)
  for(const row of rows.value){const key=managementSelectionKey(store.section,row);if(checked)next.set(key,{section:store.section,row});else next.delete(key)}
  managementSelection.value=next
  if(isEquipmentManagement.value)selected.value=undefined
}
const managementPageAllSelected=computed(()=>rows.value.length>0&&rows.value.every(row=>managementSelection.value.has(managementSelectionKey(store.section,row))))
const managementPagePartiallySelected=computed(()=>rows.value.some(row=>managementSelection.value.has(managementSelectionKey(store.section,row)))&&!managementPageAllSelected.value)
async function enterManagementSelectMode(){
  if(managementFilterBlocked.value||managementArchiveBusy.value)return
  if(!await waitForInlineSave())return
  managementSelection.value=new Map();managementSelectMode.value=true;selected.value=undefined
}
function leaveManagementSelectMode(){managementSelectMode.value=false;managementSelection.value=new Map();pendingManagementArchive.value=undefined}
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
  if (value.kind === 'network') return uiT('apfUi.asset_service_is_disconnected_check_whether_it_is_running')
  if (value.kind === 'contract') return value.message
  if (value.code === 'SERVICE_NOT_CONFIGURED') return uiT('apfUi.local_service_credentials_are_not_configured')
  if (value.code === 'SERVICE_UNAVAILABLE') return uiT('apfUi.asset_service_is_currently_unavailable')
  if (value.code === 'SERVICE_TIMEOUT') return uiT('apfUi.asset_service_timed_out')
  if (value.code === 'AUTHENTICATION_REQUIRED') return uiT('apfUi.local_service_authentication_failed')
  if (value.code === 'REVISION_CONFLICT') return uiT('apfUi.another_window_modified_this_record_your_draft_is_retained_read_the_cu')
  return value.message + (value.requestId ? uiT('apfUi.request') + value.requestId + '）' : '')
}

async function waitForInlineSave(){
  while(savingInline.value)await new Promise(resolve=>setTimeout(resolve,25))
  return !inlineSaveFailure.value
}

async function selectSection(section: WorkspaceSection) {
  if (dirty.value && !window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_switch'))) return
  if(!await waitForInlineSave())return
  closeEquipmentMenu()
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
  equipmentKindFilter.value='';projectTargetFilter.value=''
  rows.value = []
  total.value = 0
  store.selectSection(section)
  if (section === 'projects' || section === 'equipment' || section === 'equipment-setups') {
    lastManagementSection.value = section
  }
  selected.value = undefined
  if (section === 'equipment-setups') void loadRelatedEquipment(true)
  loadRecords()
}

async function selectLibraryCategory(category:'all'|'light'|'calibration'){
  if(category===libraryCategory.value)return
  if(dirty.value&&!window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_switch')))return
  if(!await waitForInlineSave())return
  leaveDatasetContext();selected.value=undefined
  store.query='';store.offset=0;activeFilters.value=emptyFilters()
  libraryCategory.value=category
  await loadRecords()
}

async function selectArea(area: WorkspaceArea, managementSection: WorkspaceSection = 'equipment-setups') {
  if (dirty.value && !window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_switch'))) return false
  if(!await waitForInlineSave())return false
  closeEquipmentMenu()
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
  equipmentKindFilter.value='';projectTargetFilter.value=''
  activeFilters.value = emptyFilters()
  rows.value = []
  total.value = 0
  activeArea.value = area
  if (area === 'library') {
    store.selectSection('library')
    void loadRelatedEquipment(true)
    loadRecords()
  } else if (area === 'settings') {
    lastManagementSection.value = managementSection
    store.selectSection(managementSection)
    if (managementSection === 'equipment-setups') void loadRelatedEquipment(true)
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

defineExpose({ selectArea, activeArea, leavePage, showImportIssue })

function startImport(kind:'files'|'folder') {
  importMenuOpen.value=false
  localPickerMode.value=kind
}
function localFilesSelected(files:LocalImportFile[],name:string,folder:boolean){
  localPickerMode.value=undefined
  importFiles.value=files
  importCreatesDataset.value=folder
  importDatasetName.value=folder?name:''
  importDialogOpen.value=true
}

function applyFilters(filters: LibraryFilters) {
  if (!isLibraryItemsView.value) return
  activeFilters.value=Object.fromEntries(Object.entries(filters).filter(([,value])=>Array.isArray(value)?value.length>0:value!==''))
  clearBulkSelection()
  store.offset = 0
  void loadRecords()
}

function importSubmitted(taskId: string) {
  importDialogOpen.value = false
  watchedTaskIds.value = [...watchedTaskIds.value, taskId]
  progressRefreshToken.value++
  clearBulkSelection()
  void loadRecords()
}

function importRegistrationCompleted() {
  clearBulkSelection()
  void loadRecords()
}

function importTaskCompleted(taskId: string) {
  watchedTaskIds.value=watchedTaskIds.value.filter(id=>id!==taskId)
  clearBulkSelection()
  void loadRecords()
}
function materialReadiness(row:RecordData){
  const versions=row.entry_type==='dataset'?(row.version?.members??[]).map((member:RecordData)=>member.version):[row.current_version??row.version]
  if(!versions.length||versions.some((version:RecordData)=>!version))return uiT('apfUi.no_original_yet')
  if(versions.some((version:RecordData)=>['changed','missing','unavailable'].includes(version.availability)))return uiT('apfUi.original_error')
  if(versions.some((version:RecordData)=>version.availability!=='available'))return row.import_issue?uiT('apfUi.original_error'):uiT('apfUi.importing_originals')
  return previewUrls.value[row.id]?uiT('apfUi.original_ready_preview_ready'):uiT('apfUi.original_ready')
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
  catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:uiT('apfUi.could_not_save_the_field'));throw cause}
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
  if(!row)throw new Error(uiT('apfUi.the_record_being_edited_no_longer_exists'))
  await saveInlineField(row,field,value)
}

async function saveEditorBin(value:string|number|null){
  const row=editorRow()
  if(!row)throw new Error(uiT('apfUi.the_record_being_edited_no_longer_exists'))
  await saveBin(row,value)
}

async function saveEditorParameterGroup(changes:RecordData){
  const row=editorRow()
  if(!row)throw new Error(uiT('apfUi.the_record_being_edited_no_longer_exists'))
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

    throw new Error(uiT('apfUi.capture_parameters_cannot_be_edited_for_this_record'))
  }catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:uiT('apfUi.could_not_save_parameters'));throw cause}
  finally{finishInlineSave()}
}

async function updateDatasetMembers(row:RecordData,changes:RecordData){
  const members:RecordData[]=row.version?.members??[]
  if(!activeDataset.value&&row.matching_member_count<members.length)throw new Error(uiT('apfUi.these_results_include_group_members_with_other_frame_uses_or_propertie'))
  const dataset=row.dataset
  if(!dataset?.id||!row.version?.id||!members.length)throw new Error(uiT('apfUi.this_image_group_has_no_editable_members'))
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
  return [{value:'',get label() { return uiT('apfUi.not_specified') }},...Array.from({length:16},(_,i)=>({value:'Bin'+(i+1),label:'Bin'+(i+1)})),
    ...(current.startsWith('legacy:')?[{value:current,label:binValue(parameters)+uiT('apfUi.current_value')}]:[])]
}
function datasetBinChoices(row:RecordData){
  const current=datasetRawValue(row,member=>binEditValue(member.asset?.parameters??{}))
  return [{value:'',get label() { return uiT('apfUi.not_specified') }},...(current==='mixed'?[{value:'mixed',get label() { return uiT('apfUi.mixed') },disabled:true}]:[]),...Array.from({length:16},(_,i)=>({value:'Bin'+(i+1),label:'Bin'+(i+1)})),
    ...(current.startsWith('legacy:')?[{value:current,label:current.replace(/^legacy:/,'Bin').replace('x','×')+uiT('apfUi.current_value')}]:[])]
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
  return parameterSummary(parameterModeValue(row))
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
  if(!known.length)return uiT('apfUi.not_specified')
  const displayed=[...new Set(known.map(displayTemperature))]
  if(displayed.length>1)return uiT('apfUi.mixed')
  return displayed[0]+(known.length<members.length?uiT('apfUi.partially_missing_262385'):'')+' °C'
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
  catch(cause){setInlineSaveFailure(failureKey,cause instanceof Error?cause.message:uiT('apfUi.could_not_save_binning'));throw cause}
  finally { finishInlineSave() }
}
async function performBinSave(row: RecordData, value: string | number | null) {
  const number=value==null||value===''?null:Number(String(value).replace(/^Bin/i,''))
  if(number!==null&&(!Number.isInteger(number)||number<1||number>16))throw new Error(uiT('apfUi.binning_must_be_between_bin1_and_bin16'))
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
  if(calibrationDirty.value&&!window.confirm(uiT('apfUi.the_group_description_or_calibration_bindings_have_unsaved_changes_dis')))return
  if (dirty.value && !window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_go_back'))) return
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
  projectTargetFilterDraft.value=projectTargetFilter.value
  managementFilterOpen.value=true
}
function applyManagementFilter(){
  if(managementFilterBlocked.value)return
  projectTargetFilter.value=projectTargetFilterDraft.value.trim()
  store.offset=0
  managementFilterOpen.value=false
}
function clearManagementFilter(){
  projectTargetFilterDraft.value=''
}

function bulkKey(row:RecordData){return row.entry_type+':'+row.id}
function clearBulkSelection(){bulkSelection.value=new Set()}
function toggleSetupSort(by: Exclude<SetupSortField, 'created_at'>) {
  if (managementFilterBlocked.value || loading.value) return
  setupSort.value = setupSort.value.by === by
    ? { by, order: setupSort.value.order === 'asc' ? 'desc' : 'asc' }
    : { by, order: 'asc' }
  managementSelection.value = new Map()
  managementSelectMode.value = false
  if (store.offset !== 0) store.offset = 0
  else void loadRecords()
}
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
function togglePageSelection(checked:boolean){
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
    bulkDeleteNotice.value=uiT('apfUi.removed')+result.removed_count+uiT('apfUi.library_entries_original_data_retained')
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
  if(setupDirty.value&&!window.confirm(uiT('apfUi.this_setup_or_preset_has_unsaved_changes_discard_them')))return
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
  if (managementFilterBlocked.value || editorType.value) return
  draft.value = {
    name: row.name, kind: row.kind, model: textInput(row.model), serial_number: textInput(row.serial_number),
    notes: textInput(row.notes), status: row.status, revision: row.revision, specs:{...row.specs}
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
  if (dirty.value && !window.confirm(uiT('apfUi.discard_unsaved_changes'))) return
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
    if (editingId.value) {
      const original:EquipmentDraft = JSON.parse(originalDraft.value)
      const payload:Record<string,unknown> = {kind:draft.value.kind,base_revision:draft.value.revision}
      for (const key of ['name','model','serial_number','notes'] as const) {
        if (draft.value[key] !== original[key]) payload[key] = key === 'name' ? draft.value[key] : nullableString(draft.value[key])
      }
      const specs = Object.fromEntries(Object.entries(draft.value.specs).filter(([key,value]) => value !== original.specs[key]))
      if (Object.keys(specs).length) payload.specs = specs
      return payload
    }
    const specs = equipmentSpecsPayload(draft.value.kind,Object.fromEntries(specFields[draft.value.kind].map(field => [
      field.key, field.type ? inputNumber(specValue(field,draft.value.specs)) : nullableString(draft.value.specs[field.key])
    ])))
    const payload: RecordData = {
      kind: draft.value.kind, name: draft.value.name, model: nullableString(draft.value.model),
      serial_number: nullableString(draft.value.serial_number), notes: nullableString(draft.value.notes), specs
    }
    return payload
  }

}

async function saveEditor() {
  if (!editorType.value||(editingId.value&&editorType.value!=='equipment')||saving.value) return
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

const itemTitle = (row: RecordData) => row.asset?.name ?? row.dataset?.name ?? row.name ?? uiT('apfUi.unnamed_record')
const itemSubtitle = (row: RecordData) => {
  if ('target_name' in row) return row.target_name || ''
  if (row.dataset || row.entry_type === 'dataset') return datasetClassification(row) + ' · ' + (row.version?.members?.length ?? row.member_count ?? row.dataset?.member_count ?? 0) + uiT('apfUi.members')
  if (row.version) return uiT('apfUi.fixed_version_f7e42b') + frameTypeLabel(rowClassification(row).frame_type)
  if (row.current_version) return frameTypeLabel(rowClassification(row).frame_type)
  if (row.kind) {
    const model = row.model?.trim()
    return equipmentKindLabels[row.kind] + (model && model.toLocaleLowerCase() !== row.name.trim().toLocaleLowerCase() ? ' · ' + model : '')
  }
  if (row.components) return row.components.length + uiT('apfUi.devices')
  if (row.camera_id) return row.frame_type + uiT('apfUi.camera') + row.camera_id
  return ''
}
const rowAsset = (row: RecordData) => row.asset ?? row
const rowParameters = (row: RecordData) => rowAsset(row).parameters ?? {}
const rowClassification = (row: RecordData) => rowAsset(row).classification ?? {}
function equipmentName(id: string | null | undefined) {
  if (!id) return uiT('apfUi.not_specified')
  return relatedEquipment.value.find(item => item.id === id)?.name ?? id.slice(0, 8)
}
function materialEquipmentValue(row:RecordData,key:string,fixed=false):string|undefined {
  const snapshot=fixed||row.project_id?row.version?.capture_snapshot?.equipment_snapshot:rowAsset(row).equipment_snapshot
  return snapshot?.[key]?.name
}
function materialEquipmentName(row:RecordData,key:string) {
  return materialEquipmentValue(row,key)??uiT('apfUi.not_specified')
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
  if(value===null||value===undefined||value==='')return uiT('apfUi.not_specified')
  return ({get MONO() { return uiT('apfUi.no_cfa_monochrome') },XTRANS:'X-Trans 6×6',QUAD_BAYER:'Quad Bayer'} as Record<string,string>)[String(value)]??String(value??uiT('apfUi.not_specified'))
}
function frameClassLabel(value:unknown){return displayLabel(value)}
function frameTypeLabel(value:unknown){return displayLabel(value)}
function rowFrame(row: RecordData) {
  if (row.version?.members) return row.version.members.length + uiT('apfUi.members')
  if (row.member_count != null || row.dataset_id) return row.member_count == null ? uiT('apfUi.image_group') : row.member_count + uiT('apfUi.members')
  const classification = rowClassification(row)
  return [classification.frame_class, classification.frame_type].filter(Boolean).map(displayLabel).join(' / ') || uiT('apfUi.unclassified')
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
  if (distinct.size > 1) return uiT('apfUi.mixed')
  const displayed = format(distinct.values().next().value)
  return known.length < values.length ? displayed + uiT('apfUi.partially_missing_262385') : displayed
}
function datasetClassification(row: RecordData) {
  return datasetValue(row, member => {
    const classification = member.asset?.classification
    return classification
      ? [classification.frame_class, classification.frame_type].filter(Boolean).map(displayLabel).join(' / ') || null
      : null
  }, value => String(value))
}

watch(
  [() => store.query, () => store.offset, () => store.pageSize, statusFilter, roleFilter, frameTypeFilter, equipmentKindFilter, projectTargetFilter],
  ([query, offset, pageSize, status, role, frameType, kind, target], [previousQuery, previousOffset, previousPageSize, previousStatus, previousRole, previousFrameType, previousKind, previousTarget]) => {
    if(restoringOuterLibraryState.value)return
    const queryChanged = query !== previousQuery
    const filtersChanged = pageSize !== previousPageSize || status !== previousStatus || role !== previousRole || frameType !== previousFrameType || kind !== previousKind || target !== previousTarget
    if(offset!==previousOffset||queryChanged||filtersChanged)clearBulkSelection()
    if(offset!==previousOffset||queryChanged||filtersChanged){
      managementSelection.value=new Map()
      if(isEquipmentManagement.value)managementSelectMode.value=false
    }
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
  canvasSource,
  requestEquipmentDelete, requestEquipmentDeleteSelection,
  store, activeArea, isEquipmentManagement, recordPageSize, managementFilterBlocked, lastManagementSection, capabilities, rows,
  selected, total, loading, error, capabilityError,
  statusFilter, equipmentKindFilter, setupDirty, setupSaving, calibrationDirty, libraryCategory, selectLibraryCategory, roleFilter, frameTypeFilter, emptyFilters, activeFilters,
  filterPanelOpen, filterButton, activeFilterCount, viewingProjectAssets, viewingProjectDatasets,
  addingProjectAssets, addingProjectDatasets, importDialogOpen, importFiles,
  importMenuOpen, importCreatesDataset, importDatasetName, libraryViewMode,
  librarySort, setupSort, toggleSetupSort, bulkSelectMode, bulkSelection, bulkDeleteBusy, bulkDeleteNotice,
  bulkConfirmOpen, bulkConfirmRows, trashOpen, managementTrashOpen, progressRefreshToken, importWorkspace,
  watchedTaskIds, activeDataset, outerLibraryState,
  restoringOuterLibraryState, previewUrls, editorType, editingId, draft,
  originalDraft, saving, savingInline, inlineSaveFailures, inlineSaveFailure,
  relatedEquipment, relatedEquipmentLoading, relatedEquipmentError, relatedEquipmentReady,
     dirty, isAssetSection,
  isAssetTable, isDatasetTable, isLibraryItemsView, isLibraryTableView, isDatasetMembersView,
  pageSelectionKeys, pageAllSelected, pagePartiallySelected, areaTitles, areaMessages,
  specFields, frameTypes, frameClasses, cfaChoices, equipmentKinds, equipmentKindLabels, equipmentKindIcons,
  specKind, specChoices, specDisplay, specValue, equipmentSpecsPayload, apiPath, loadWorkspacePage,
  libraryFilterParams, formListPath, loadAll, loadRelatedEquipment, equipmentChoiceMessage,
  equipmentChoices,    loadCapabilities,
  loadRecords, loadThumbnails, previewMember, openPhotoPreview, presentError, errorText,
  waitForInlineSave, selectSection, selectArea, startImport, applyFilters,
  importSubmitted, importTaskCompleted, importRegistrationCompleted,
  refreshLibrary, notifyImportSuccess, notifyImport, materialReadiness,
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
  displayLabel, itemSubtitle, rowAsset, rowParameters, rowClassification, equipmentName, materialEquipmentName, materialEquipmentValue,
  captureValue, modeValue, datasetParameterMode, cfaLabel, frameClassLabel,
  frameTypeLabel, rowFrame, datasetMembers, datasetValue, datasetClassification
}
export type WorkspaceContext = typeof workspaceContext
provide('workspace', workspaceContext)

onMounted(async () => {
  document.addEventListener('pointerdown', dismissEquipmentMenu, true)
  void loadRelatedEquipment()
  try {
    const health=await assetApi.get('/astrophotoflow/api/v1/health',z.object({workspace:z.string()}).passthrough())
    importWorkspace.value=health.workspace
  } catch(cause) {error.value=presentError(cause)}
  await loadCapabilities()
  await loadRecords()
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', dismissEquipmentMenu, true)
  clearTimeout(searchTimer)
  for (const url of Object.values(previewUrls.value)) URL.revokeObjectURL(url)
})
</script>

<template>
  <section class="apf-workspace" :aria-label="$t('apfUi.astrophotoflow_astronomy_library')"
    @pointerdown.stop @pointerup.stop @mousedown.stop @mouseup.stop
    @click.stop @contextmenu.stop @keydown.stop @keyup.stop>
      <nav v-if="!props.native" class="apf-nav" :aria-label="$t('apfUi.astrophotoflow_modules')">
        <button v-for="(title, area) in areaTitles" :key="area" type="button"
          :aria-label="title" :title="title" :aria-current="activeArea === area ? 'page' : undefined"
          @click="selectArea(area as WorkspaceArea)">
          <i :class="['pi', ({ library: 'pi-images', nodes: 'pi-sitemap', software: 'pi-box', agent: 'pi-comments', settings: 'pi-cog' } as Record<WorkspaceArea, string>)[area]]" aria-hidden="true"></i>
        </button>
      </nav>
    <main class="apf-main" :class="{'apf-equipment-management':isEquipmentManagement,'apf-library-workspace':activeArea==='library'}">
      <template v-if="activeArea === 'library' || activeArea === 'settings'">
          <div class="apf-toolbar">
            <div class="apf-heading">
              <button v-if="activeDataset" type="button" @click="closeDataset">{{ $t('apfUi.back_to_library') }}</button>
              <button v-else-if="viewingProjectAssets || viewingProjectDatasets" type="button" @click="leaveProjectAssets">{{ $t('apfUi.back_to_project') }}</button>
              <LibraryButton v-else-if="props.native && activeArea === 'settings'" type="button" class="apf-equipment-back" :aria-label="$t('apfUi.back_to_library_8979db')" :tooltip="$t('apfUi.back_to_library_8979db')" @click="emit('back-to-library')"><i class="pi pi-arrow-left" aria-hidden="true"></i></LibraryButton>
              <h1 v-if="!props.sidebar || activeDataset || activeArea !== 'library'">{{ activeDataset ? $t('apfUi.library_968e00')+activeDataset.name : activeArea === 'library' ? $t('apfUi.library') : (viewingProjectAssets ? $t('apfUi.project_assets') : viewingProjectDatasets ? $t('apfUi.project_image_groups') : $t('apfUi.equipment_manager')) }}</h1>
              <span v-if="activeDataset" class="apf-state">{{ $t('apfUi.image_group_photos_value', { p0: (activeDataset.version?.members?.length??activeDataset.member_count??0) }) }}</span>
              <div v-if="isLibraryTableView" class="apf-heading-actions">
                <template v-if="bulkSelectMode">
                  <span role="status">{{ $t('apfUi.selected_value', { p0: (bulkSelection.size) }) }}</span>
                  <LibraryButton :disabled="bulkDeleteBusy||bulkSelection.size===0||savingInline>0||Boolean(inlineSaveFailure)" @click="removeSelectedLibraryEntries">{{bulkDeleteBusy?$t('apfUi.deleting'):$t('apfUi.delete')}}</LibraryButton>
                  <LibraryButton :disabled="bulkDeleteBusy" @click="leaveBulkSelectMode">{{ $t('apfUi.done') }}</LibraryButton>
                </template>
                <template v-else>
                  <LibraryButton v-if="isLibraryItemsView" class="apf-import" variant="primary" :disabled="!capabilities?.asset_import" :aria-expanded="importMenuOpen" @click="importMenuOpen=!importMenuOpen" :tooltip="$t('apfUi.select_files_or_folder')"><i class="icon-[lucide--upload] size-4" aria-hidden="true" /><span>{{ $t('apfUi.import') }}</span></LibraryButton>
                  <LibraryButton v-if="props.native&&isLibraryItemsView" class="apf-equipment" @click="emit('manage-equipment')">{{ $t('apfUi.equipment_manager') }}</LibraryButton>
                  <LibraryMenu ref="libraryMenu" :items="libraryMenuItems" />
                  <div v-if="importMenuOpen&&isLibraryItemsView" class="apf-import-menu">
                    <LibraryButton @click="startImport('files')">{{ $t('apfUi.select_files') }}</LibraryButton>
                    <LibraryButton @click="startImport('folder')">{{ $t('apfUi.select_folder') }}</LibraryButton>
                  </div>
                </template>
              </div>
            </div>
            <LibraryTabs v-if="activeArea==='library'&&!activeDataset" class="apf-library-categories" :value="libraryCategory" :options="[{value:'all',label:$t('apfUi.all_assets')},{value:'light',label:$t('apfUi.light')},{value:'calibration',label:$t('apfUi.calibration_library')}]" :label="$t('apfUi.asset_use')" @change="selectLibraryCategory($event as 'all'|'light'|'calibration')" />
            <LibraryTabs v-if="activeArea === 'settings' && !viewingProjectAssets && !viewingProjectDatasets" class="apf-management-tabs" :value="store.section" :options="[{value:'equipment-setups',label:$t('apfUi.equipment_setup')},{value:'equipment',label:$t('apfUi.my_equipment')}]" :label="props.native?$t('apfUi.equipment_and_metadata_categories'):$t('apfUi.settings_category')" @change="selectSection($event as WorkspaceSection)" />
            <label class="apf-search">
              <i class="pi pi-search" aria-hidden="true"></i>
              <input :value="store.query" :aria-label="$t('apfUi.search')" :placeholder="$t('apfUi.search_names')" :disabled="bulkDeleteBusy||setupDirty" @input="setQuery" />
            </label>
            <select v-if="activeArea !== 'settings' && (store.section === 'projects' || store.section === 'equipment' || store.section === 'equipment-setups')"
              v-model="statusFilter" :disabled="setupDirty" :aria-label="$t('apfUi.status_filter')">
              <option value="active">{{ $t('apfUi.active') }}</option><option value="archived">{{ $t('apfUi.archived') }}</option><option value="all">{{ $t('apfUi.all') }}</option>
            </select>
            <LibrarySelect v-if="isEquipmentManagement&&store.section==='equipment'" class="apf-equipment-kind-filter" :model-value="equipmentKindFilter" :label="$t('apfUi.equipment_category')" :options="[{value:'',name:$t('apfUi.all_equipment')},...equipmentKinds.map(kind=>({value:kind,name:equipmentKindLabels[kind]}))]" :disabled="managementFilterBlocked" @update:model-value="filterEquipmentKind" />
            <div v-if="activeArea==='settings' && store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets" class="apf-management-filter-control">
              <button ref="managementFilterButton" type="button" :disabled="managementFilterBlocked" :aria-expanded="managementFilterOpen" @click="managementFilterOpen?managementFilterOpen=false:openManagementFilter()">{{ $t('apfUi.filter_b5f154') }}<span v-if="managementFilterCount">（{{managementFilterCount}}）</span></button>
              <div v-if="managementFilterOpen" class="apf-management-filter-panel">
                <label v-if="store.section==='projects'">{{ $t('apfUi.target') }}<input v-model="projectTargetFilterDraft" :placeholder="$t('apfUi.filter_by_target')" /></label>
                <div><button type="button" @click="clearManagementFilter">{{ $t('apfUi.clear') }}</button><button type="button" @click="applyManagementFilter" :disabled="managementFilterBlocked">{{ $t('apfUi.apply') }}</button></div>
              </div>
            </div>
            <span v-if="isLibraryItemsView" ref="filterButton"><LibraryButton :disabled="bulkDeleteBusy" :aria-expanded="filterPanelOpen" @click="filterPanelOpen=!filterPanelOpen">{{ $t('apfUi.filter_b5f154') }}<span v-if="activeFilterCount">（{{activeFilterCount}}）</span>
            </LibraryButton></span>
            <button v-if="!isEquipmentManagement&&(activeArea !== 'library' || viewingProjectAssets || viewingProjectDatasets)" type="button" :disabled="setupDirty" @click="loadRecords"><i class="pi pi-refresh" aria-hidden="true"></i><span>{{ $t('apfUi.refresh') }}</span></button>
            <template v-if="isEquipmentManagement">
              <template v-if="managementSelectMode">
                <span role="status">{{ $t('apfUi.selected_value', { p0: (managementSelection.size) }) }}</span>
                <LibraryButton type="button" :disabled="!managementSelection.size||managementArchiveBusy||managementFilterBlocked" @click="requestSelectedEquipmentDelete">{{ $t('apfUi.delete_selected_value', { p0: (managementSelection.size) }) }}</LibraryButton>
                <LibraryButton type="button" :disabled="managementArchiveBusy" @click="leaveManagementSelectMode">{{ $t('apfUi.done') }}</LibraryButton>
              </template>
              <LibraryButton v-else-if="statusFilter!=='archived'" type="button" variant="primary" :disabled="managementFilterBlocked||loading" @click="store.section==='equipment-setups'?setupManager?.beginSetup(null):openCreate('equipment')"><i class="pi pi-plus" aria-hidden="true"></i>{{store.section==='equipment-setups'?$t('apfUi.new_equipment_setup'):$t('apfUi.new_equipment')}}</LibraryButton>
              <LibraryMenu ref="equipmentMenu" :items="equipmentMenuItems" />
            </template>
            <template v-if="activeArea==='settings' && store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets">
              <template v-if="managementSelectMode">
                <button type="button" :disabled="!managementSelection.size||managementArchiveBusy" @click="requestSelectedEquipmentDelete">{{ $t('apfUi.delete_value', { p0: (managementSelection.size) }) }}</button>
                <button type="button" :disabled="managementArchiveBusy" @click="leaveManagementSelectMode">{{ $t('apfUi.cancel') }}</button>
              </template>
              <template v-else>
                <button type="button" :disabled="loading||savingInline>0||Boolean(inlineSaveFailure)" @click="enterManagementSelectMode">{{ $t('apfUi.delete_in_bulk') }}</button>
              </template>
            </template>
            <button v-if="store.section === 'projects' && statusFilter!=='archived' && !managementSelectMode && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openCreate('project')">{{ $t('apfUi.new_project') }}</button>
            <button v-if="store.section==='projects' && viewingProjectAssets" type="button" @click="toggleProjectAssetMode">{{addingProjectAssets?$t('apfUi.view_selected_asset'):$t('apfUi.add_asset')}}</button>
            <button v-if="store.section==='projects' && viewingProjectDatasets" type="button" @click="toggleProjectDatasetMode">{{addingProjectDatasets?$t('apfUi.view_selected_image_group'):$t('apfUi.add_image_group')}}</button>
          </div>
        <LibraryPage v-if="activeArea === 'library'" />
        <EquipmentSetupManager v-else-if="store.section==='equipment-setups'" ref="setupManager" />
        <SettingsPage v-else />
      </template>
        <section v-else class="apf-placeholder" :aria-label="areaTitles[activeArea]">
          <h1>{{ areaTitles[activeArea] }}</h1>
          <p>{{ areaMessages[activeArea] }}</p>
        </section>
    </main>
      <component :is="props.controls.mediaViewer" v-if="props.controls?.mediaViewer && mediaPreview" :request="mediaPreview" @close="closePhotoPreview" />
      <PhotoPreviewDialog v-else :photo="photoPreview" @close="closePhotoPreview" @updated="refreshPhotoThumbnails" />
      <LibraryTrashDialog :open="trashOpen" @close="trashOpen=false" @changed="refreshLibrary" />
      <EquipmentDeleteDialog :items="equipmentDeleteItems" @close="equipmentDeleteItems=undefined" @deleted="equipmentDeleted" />
      <div v-if="bulkConfirmOpen" class="apf-trash-confirm-backdrop" role="presentation" @click.self="bulkConfirmOpen=false">
        <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="bulk-trash-confirm-title">
          <h2 id="bulk-trash-confirm-title">{{ $t('apfUi.confirm_move_to_trash') }}</h2>
          <p>{{ $t('apfUi.move_value_library_entries_to_trash_original_files_are_retained_and_en', { p0: (bulkConfirmRows.length) }) }}</p>
          <ul><li v-for="row in bulkConfirmRows" :key="row.entry_type+':'+row.id">{{itemTitle(row)}}<span v-if="row.entry_type==='dataset'">{{ $t('apfUi.image_group_value_photos', { p0: (row.version?.members?.length??row.dataset?.member_count??0) }) }}</span><span v-else>{{ $t('apfUi.photo_95be49') }}</span></li></ul>
          <button type="button" @click="bulkConfirmOpen=false">{{ $t('apfUi.cancel') }}</button><button type="button" @click="confirmRemoveSelectedLibraryEntries">{{ $t('apfUi.move_to_trash') }}</button>
        </section>
      </div>
      <div v-if="pendingManagementArchive" class="apf-trash-confirm-backdrop" role="presentation" @click.self="pendingManagementArchive=undefined">
        <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="management-archive-title">
          <h2 id="management-archive-title">{{ $t('apfUi.move_to_trash') }}</h2>
          <p v-if="managementSelectMode">{{ $t('apfUi.move_value_settings_to_trash_linked_assets_and_equipment_snapshots_are', { p0: (managementSelection.size) }) }}</p>
          <p v-else>{{ $t('apfUi.move_value_to_trash_records_linked_assets_and_historical_presets_are_r', { p0: (itemTitle(pendingManagementArchive.row)) }) }}</p>
          <button type="button" :disabled="managementArchiveBusy" @click="pendingManagementArchive=undefined">{{ $t('apfUi.cancel') }}</button>
          <button type="button" :disabled="managementArchiveBusy" @click="confirmManagementArchive">{{managementArchiveBusy?$t('apfUi.processing'):$t('apfUi.confirm_move_to_trash')}}</button>
        </section>
      </div>
      <LocalImportPicker :open="!!localPickerMode" :mode="localPickerMode??'files'" @close="localPickerMode=undefined" @selected="localFilesSelected" />
      <ImportIssueDialog :issue="importIssue" @close="importIssue=undefined" @retried="importSubmitted" />
      <ImportDialog :open="importDialogOpen" :files="importFiles" :create-dataset="importCreatesDataset" :dataset-name="importDatasetName" @close="importDialogOpen=false" @submitted="importSubmitted" />
  </section>
</template>

<style>
.apf-library-categories{display:flex;gap:8px;flex-wrap:wrap}
.apf-workspace { position:relative; display:flex; flex:1 1 auto; width:100%; height:100%; min-height:0; font:inherit; color:var(--input-text,inherit); }
.apf-workspace button { display:inline-flex; min-height:32px; align-items:center; justify-content:center; gap:8px; padding:8px; border:0; border-radius:8px; color:var(--input-text,#ddd); background:var(--comfy-menu-secondary-bg,#292929); font:inherit; font-size:12px; font-weight:500; line-height:1; white-space:nowrap; cursor:pointer; transition:background-color .1s ease; }
.apf-workspace button:hover:not(:disabled) { background:var(--comfy-menu-bg,#353535); }
.apf-workspace button:focus-visible, .apf-workspace input:focus-visible, .apf-workspace select:focus-visible, .apf-workspace textarea:focus-visible { outline:1px solid var(--border-color,#4e4e4e); outline-offset:1px; }
.apf-workspace button:disabled { opacity:.5; cursor:not-allowed; }
.apf-table-scroll { margin:0 10px; min-width:0; min-height:160px; max-height:45vh; flex:0 0 auto; overflow:auto; }
.apf-assets-table { border-collapse:collapse; min-width:1120px; width:100%; font-size:12px; }
.apf-table-scroll.simple .apf-assets-table { min-width:0; table-layout:fixed; }
.apf-table-scroll.simple .apf-column-classification,.apf-table-scroll.simple .apf-column-camera,.apf-table-scroll.simple .apf-column-parameter,.apf-table-scroll.simple .apf-column-exposure,.apf-table-scroll.simple .apf-column-temperature{display:none}
.apf-table-scroll.simple th.apf-column-preview{width:72px}
.apf-table-scroll.simple .apf-column-name{min-width:0;overflow:hidden}
.apf-table-scroll.simple .apf-thumb{width:60px;height:52px}
.apf-table-scroll.simple .apf-inline-field{min-width:0;width:100%}
.apf-table-scroll.simple .apf-material-name .apf-inline-value{display:block;min-width:0;width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;overflow-wrap:normal}
.apf-table-scroll.simple .apf-column-name>.apf-member-open{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.apf-table-scroll.simple .apf-column-name>small{display:none}
.apf-table-scroll.simple .apf-classification-separator{display:none}
.apf-compact-meta{display:none}
.apf-table-scroll.simple .apf-assets-table.is-selecting th:first-child{width:28px}
.apf-processing-issue{color:var(--destructive-foreground,#faa)!important;white-space:normal}
.apf-workspace .apf-info{display:inline-flex;min-width:24px;min-height:24px;width:24px;height:24px;padding:0;margin-left:4px;background:transparent;color:var(--descrip-text,#999);vertical-align:middle}
.apf-info i{font-size:14px}
.apf-hint-content{display:block;max-width:min(360px,calc(100vw - 32px));white-space:pre-wrap;overflow-wrap:anywhere;font-weight:400;text-align:left}
.apf-workspace h2{font-size:16px;line-height:1.4;margin:8px 0;font-weight:600}
.apf-workspace h3{font-size:14px;line-height:1.4;font-weight:600}
.apf-workspace input:not([type=checkbox]):not([type=range]),.apf-workspace select,.apf-workspace textarea{max-width:100%;min-width:0;border-radius:8px;color:var(--input-text,#ddd);background:var(--comfy-input-bg,#222);font:inherit}
.apf-calibration-editor select,.apf-calibration-editor input,.apf-calibration-editor textarea{padding:8px;border:1px solid var(--border-color,#555)}
.apf-preset-picker label{display:flex;flex-direction:column;gap:4px;margin:8px 0}.apf-preset-picker select{min-height:36px;padding:6px 8px;border:1px solid var(--border-color,#555)}
.apf-workspace button[data-variant]{font-size:14px;min-height:36px}
.apf-workspace button.apf-info{min-height:24px}
.apf-workspace button[data-variant=primary]{background:var(--primary-bg,#236692);color:var(--primary-fg,#fff)}
.apf-edit-icon{font-size:11px;opacity:0}
.apf-inline-value:hover .apf-edit-icon,.apf-inline-value:focus-visible .apf-edit-icon{opacity:.7}
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
.apf-toolbar { flex:none; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.apf-heading { display:flex; align-items:center; gap:8px; flex:0 0 100%; min-width:0; white-space:nowrap; }
.apf-heading h1 { flex:0 0 auto; white-space:nowrap; }
.apf-heading-actions { display:flex; flex:0 0 auto; align-items:center; gap:6px; }
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
.apf-records.list { flex:none; max-height:32vh; overflow:auto; display:flex; flex-direction:column; gap:6px; }
.apf-management-select-page,.apf-management-record-select { display:flex; align-items:center; gap:12px; padding:10px; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-secondary-bg,#292929); }
.apf-management-select-page { width:max-content; padding:6px 10px; }
.apf-management-record-select span:last-child { display:flex; min-width:0; flex-direction:column; gap:4px; }
.apf-management-record-select small { color:var(--descrip-text,#999); }
.apf-workspace .apf-record { display:flex; width:100%; min-height:68px; justify-content:flex-start; gap:12px; padding:10px; border:1px solid var(--border-color,#4e4e4e); text-align:left; white-space:normal; background:var(--comfy-menu-secondary-bg,#292929); }
.apf-record span:last-child { display:flex; flex-direction:column; gap:4px; min-width:0; }
.apf-record small { color:var(--descrip-text,#999); }
.apf-record-icon { font-size:22px; }
.apf-pagination { flex:none; flex-wrap:wrap; display:flex; gap:8px; align-items:center; margin-top:0; }
.apf-pagination span { margin-right:auto; }
.apf-pagination label { display:flex; align-items:center; gap:6px; color:var(--descrip-text,#999); font-size:12px; }
.apf-pagination select { height:28px; padding:0 8px; border:1px solid var(--border-color,#4e4e4e); border-radius:7px; color:var(--input-text,#ddd); background:var(--comfy-input-bg,#222); font:inherit; }
.apf-classification-separator { margin:0 5px; color:var(--descrip-text,#999); font-size:.8em; opacity:.6; }
.apf-details { flex:none; min-width:0; padding:10px; overflow:visible; border:1px solid var(--border-color,#4e4e4e); border-radius:8px; background:var(--comfy-menu-bg,#353535); }
.apf-details pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:11px; }
.apf-project-intro{flex:none;margin:0 10px}.apf-project-intro h2,.apf-project-intro p{margin:4px 0}.apf-binding-select{display:flex;min-width:0;align-items:center}.apf-binding-select select{min-width:0;max-width:100%;flex:1}
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

.apf-library-workspace .apf-workspace-more{position:relative;flex:none}
.apf-library-workspace .apf-workspace-more>summary{display:grid;place-items:center;min-width:28px;height:28px;border-radius:8px;background:var(--color-secondary-background);cursor:pointer;list-style:none}
.apf-library-workspace .apf-workspace-more>div{position:absolute;z-index:12;right:0;top:calc(100% + 4px);display:flex;flex-direction:column;gap:4px;min-width:180px;padding:8px;border:1px solid var(--color-border-default);border-radius:8px;background:var(--color-base-background)}
.apf-library-workspace .apf-workspace-more label{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12px}
.apf-library-workspace .apf-library-categories button{background:transparent;color:var(--color-muted-foreground)}
.apf-library-workspace .apf-library-categories button:hover:not(:disabled),.apf-library-workspace .apf-library-categories button[aria-current=page]{background:var(--color-secondary-background);color:var(--color-base-foreground)}
.apf-workspace .apf-library-workspace .apf-import-progress button{min-height:28px;height:28px;padding:4px 8px;font-size:12px}
.apf-workspace .apf-library-workspace .apf-sort-button{min-height:28px;height:auto;padding:2px 4px;border:0;background:transparent;color:var(--color-muted-foreground);font:inherit;text-align:left}
.apf-workspace .apf-library-workspace .apf-sort-button:hover:not(:disabled){background:var(--color-secondary-background);color:var(--color-base-foreground)}
.apf-library-workspace .apf-sort-button:focus-visible{outline:1px solid var(--color-border-default);outline-offset:2px}
.apf-workspace .apf-library-workspace button[data-slot=checkbox]{min-height:16px;height:16px;width:16px;padding:0;background:transparent;border:1px solid var(--color-border-default);border-radius:3px}
.apf-workspace .apf-library-workspace button[data-slot=checkbox][data-state=checked],.apf-workspace .apf-library-workspace button[data-slot=checkbox][data-state=indeterminate]{background:var(--color-primary-background);border-color:var(--color-primary-background)}
.apf-workspace .apf-library-workspace .apf-heading-actions button[data-variant=primary]{background:var(--color-primary-background);color:var(--color-base-foreground)}
</style>

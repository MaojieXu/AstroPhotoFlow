<script setup lang="ts">
import { useLibrarySelection } from '../library/useLibrarySelection'
import { useLibraryRemoval } from '../trash/useLibraryRemoval'
import { createLibraryTableRow } from '../library/tableRows'
import { rowCalibration } from '../library/inlineCalibration'
import { useQueryClient } from '@tanstack/vue-query'
import { invalidateLibraryData } from '../library/invalidation'
import { useRecordFieldEditing } from '../library/useRecordFieldEditing'
import { rowClassification, parameterModeDisplay, displayTemperature, captureValue, frameTypeLabel, datasetFieldDisplay, datasetClassification } from '../library/metadataPresentation'
import { useProjectReferenceActions } from '../projects/useProjectReferenceActions'
import { useInlineSaveState } from '../library/useInlineSaveState'
import { validatedInput } from '../../../core/api/input'
import { zPatchProjectApiV1ProjectsProjectIdPatchBody, zArchiveManagementEntriesApiV1SettingsTrashArchivePostBody } from '../../../generated/api/zod.gen'
import { type WorkspaceRecord, type AssetRecord, type DatasetRecord, isMemberRecord, isAssetRecord, isDatasetRecord, isProjectAssetReference, isProjectDatasetReference, isEquipmentRecord, isSetupRecord, isProjectRecord, assetRecord, datasetRecord, recordEntity, recordIssue, recordVersion } from './recordTypes'
import { uiT } from '../../../core/i18n'
import { managementSelectionEntry, managementArchiveItems, equipmentDeletionItems, type ManagementSelectionEntry, type ManagementArchiveConfirmation } from '../trash/selection'
import type { ProjectOut, DatasetOut, ServiceCapabilities } from '../../../generated/api/types.gen'
import { useThumbnailUrls } from '../media/useThumbnailUrls'
import { equipmentKinds, equipmentKindLabels, equipmentSubtitle } from '../equipment/fields'

import { computed, h, nextTick, onBeforeUnmount, onMounted, provide, ref, toRef, watch } from 'vue'
import { type EquipmentSetup, equipmentSetupSchema } from '../api/contracts'
import { ApiClientError } from '../api/client'
import { useEquipmentChoices } from '../equipment/queries'
import { useEquipmentManagementView } from '../equipment/useEquipmentManagementView'
import { useDatasetMembersView } from '../datasets/useDatasetMembersView'
import { assetApi, datasetApi } from '../api/index'
import { libraryError as presentError, libraryErrorText as errorText } from '../library/errors'
import { useLibraryView, type LibraryFilters } from '../library/useLibraryView'
import { useRecordSearch } from './useRecordSearch'
import { useImportFlow } from '../imports/useImportFlow'
import { useUpdateProject } from '../projects/mutations'
import { useArchiveManagement } from '../trash/mutations'
import { useProjectRecordsView } from '../projects/useProjectRecordsView'
import { useMaterialSelectionView } from '../library/useMaterialSelectionView'
import { useWorkspaceStore, type WorkspaceSection } from './store'
import PhotoPreviewDialog from '../media/PhotoPreviewDialog.vue'
import type { PreviewPhoto } from '../media/previewTypes'
import { useLibraryPreview } from '../media/useLibraryPreview'
import ImportDialog from '../imports/ImportDialog.vue'
import LibraryTrashDialog from '../trash/LibraryTrashDialog.vue'
import EquipmentDeleteDialog, { type EquipmentDeleteItem } from '../equipment/EquipmentDeleteDialog.vue'
import LocalImportPicker from '../imports/LocalImportPicker.vue'
import ImportIssueDialog from '../imports/ImportIssueDialog.vue'
import type { ImportNotice } from './libraryControls'
import { resolveMaterialRecord, fixedAssetPreview, fixedAssetContent, materialCanvasSource, materialPreviewBase, materialThumbnailKey, type MaterialRecord } from '../library/materialRecords'
import type { CanvasDataRequest } from '../api/canvas'
import LibraryPage from '../library/LibraryPage.vue'
import WorkspaceRecords from '../library/WorkspaceRecords.vue'
import type { RecordsPresentation, RecordsBody } from './recordsTypes'
import type { DatasetReferenceRow } from '../datasets/DatasetReferenceTable.vue'
import { zEquipmentPage, zEquipmentSetupPage, zProjectPage } from '../../../generated/api/zod.gen'
import SettingsPage, { type SettingsProjectMode, type SettingsRecordDetails } from '../library/SettingsPage.vue'
import AssetDetails from '../assets/AssetDetails.vue'
import DatasetDetails from '../datasets/DatasetDetails.vue'
import type { AssetDetailField, AssetDetailBindings } from '../assets/detailTypes'
import { zAssetOut, zDatasetOut } from '../../../generated/api/zod.gen'
import RecordEditorForm from './RecordEditorForm.vue'
import ProjectDetails, { type ProjectDetailsAction } from '../projects/ProjectDetails.vue'
import { zProjectOut } from '../../../generated/api/zod.gen'
import { useRecordEditor } from './useRecordEditor'
import { useDatasetView } from '../datasets/useDatasetView'
import { observedEquipmentChoices, summaryEquipmentChoices, type EquipmentChoiceSnapshot } from '../equipment/snapshots'
import { binValue, binEditValue, binEditChoices } from '../assets/binning'
import EquipmentSetupManager from '../equipment/EquipmentSetupManager.vue'
import LibraryButton from '../components/LibraryButton.vue'
import LibrarySelect from '../components/LibrarySelect.vue'
import LibraryMenu from '../components/LibraryMenu.vue'
import LibraryTabs from '../components/LibraryTabs.vue'
import { libraryControlsKey } from './libraryControls'
import { useQueryAvailability } from '../../../core/query/availability'
import type { LibraryControls, LibraryMenuItem } from './libraryControls'
import { displayLabel } from '../library/presentation'
import { isLibrarySummary, hasSummary, summaryEquipment } from '../library/summary'
import './equipmentCompact.css'


type EditorType = 'project' | 'equipment'
type WorkspaceArea = 'library' | 'settings'
type SetupSortField = 'created_at' | 'name' | 'camera' | 'telescope' | 'mount' | 'filter'

type ToolbarPopup = 'import' | 'library-filter' | 'project-filter' | 'equipment-category' | 'library-more' | 'equipment-more' | 'toolbar-search' | 'toolbar-view'

const connectionReady = useQueryAvailability()
const store = useWorkspaceStore()
const calibrationCache = useQueryClient()
const props = defineProps<{ native?: boolean; sidebar?: boolean; initialSection?: 'library' | 'projects'; controls?: LibraryControls; workspaceId:string; capabilities:ServiceCapabilities }>()
provide(libraryControlsKey, props.controls)
const emit = defineEmits<{ 'manage-equipment': []; 'back-to-library': []; 'notify-success': [message: string]; 'notify-import': [notice: ImportNotice] }>()

function canvasSource(row: unknown): CanvasDataRequest | undefined {
  if (bulkSelectMode.value || savingInline.value || inlineSaveFailure.value) return
  const record=resolveMaterialRecord(row)
  return record ? materialCanvasSource(record) : undefined
}

if (props.sidebar) {
  store.selectSection(props.initialSection ?? 'library')
  store.setQuery('')
  store.activeProjectId = null
  store.activeProjectRevision = null
}
const activeArea = ref<WorkspaceArea>(props.initialSection === 'projects' ? 'settings' : 'library')
const isEquipmentManagement = computed(() => activeArea.value === 'settings' && ['equipment', 'equipment-setups'].includes(store.section))
const recordPageSize = computed(() => isEquipmentManagement.value ? 50 : store.pageSize)
const setupManager = ref<InstanceType<typeof EquipmentSetupManager>>()
const setupViewKey = computed(() => JSON.stringify([importWorkspace.value, store.section, store.query, store.offset, statusFilter.value, setupSort.value]))
const selectedEquipmentSetup = computed(() => isEquipmentManagement.value && store.section === 'equipment-setups' && selected.value ? equipmentSetupSchema.parse(selected.value) : undefined)
async function setupSaved(setup: EquipmentSetup, viewKey: string) {
  if (setupViewKey.value !== viewKey) return
  await nextTick()
  if (setupViewKey.value === viewKey) selected.value = setup
}

const workspaceRoot = ref<HTMLElement>()
const toolbar = ref<HTMLElement>()
const toolbarWidth = ref(Infinity)
const foldSecondaryActions = computed(() => toolbarWidth.value < 660)
const foldSearch = computed(() => toolbarWidth.value < 500)
const foldViewTabs = computed(() => toolbarWidth.value < 420)
const toolbarSearchInput = ref<HTMLInputElement>()
const toolbarPopup = ref<ToolbarPopup>()
const toolbarFocusHandoffs = new Set<ToolbarPopup>()
const importMenuOpen = popupOpen('import')
const filterPanelOpen = popupOpen('library-filter')
const managementFilterOpen = popupOpen('project-filter')
const equipmentCategoryOpen = popupOpen('equipment-category')
const libraryMenuOpen = popupOpen('library-more')
const equipmentMenuOpen = popupOpen('equipment-more')
const toolbarSearchOpen = popupOpen('toolbar-search')
const toolbarViewOpen = popupOpen('toolbar-view')

watch(toolbar, (element, _, onCleanup) => {
  if (!element || typeof ResizeObserver === 'undefined') return
  const observer = new ResizeObserver(([entry]) => { toolbarWidth.value = entry.contentRect.width })
  observer.observe(element)
  onCleanup(() => observer.disconnect())
})

watch(foldSearch, () => { toolbarSearchOpen.value = false })
watch(foldViewTabs, () => { toolbarViewOpen.value = false })
watch(foldSecondaryActions, () => { equipmentCategoryOpen.value = false })

async function toggleToolbarSearch() {
  toolbarSearchOpen.value = !toolbarSearchOpen.value
  if (!toolbarSearchOpen.value) return
  await nextTick()
  toolbarSearchInput.value?.focus()
}

function popupOpen(popup: ToolbarPopup) {
  return computed({
    get: () => toolbarPopup.value === popup,
    set(open: boolean) {
      if (open) {
        if (toolbarPopup.value !== popup) closeToolbarPopup()
        toolbarFocusHandoffs.delete(popup)
        toolbarPopup.value = popup
      } else if (toolbarPopup.value === popup) {
        toolbarPopup.value = undefined
      }
    }
  })
}

function closeToolbarPopup() {
  const popup = toolbarPopup.value
  if (popup && isPortaledPopup(popup)) toolbarFocusHandoffs.add(popup)
  toolbarPopup.value = undefined
}

function isPortaledPopup(popup: ToolbarPopup) {
  if (popup === 'equipment-category' || popup === 'toolbar-view') return Boolean(props.controls?.select)
  return (popup === 'library-more' || popup === 'equipment-more') && Boolean(props.controls?.menu)
}

function dismissToolbarOnPointerDown(event: PointerEvent) {
  const popup = toolbarPopup.value
  const root = workspaceRoot.value
  if (!popup || !root) return
  const path = event.composedPath()
  if (isPortaledPopup(popup) && !path.includes(root)) return
  if (path.some(node => node instanceof HTMLElement && root.contains(node) && node.dataset.apfPopup === popup)) return
  closeToolbarPopup()
}

function dismissToolbarOnEscape(event: KeyboardEvent) {
  const popup = toolbarPopup.value
  if (!popup) return
  toolbarPopup.value = undefined
  event.preventDefault()
  workspaceRoot.value?.querySelector<HTMLElement>(
    `button[data-apf-popup="${popup}"], [data-apf-popup="${popup}"] button[aria-expanded], [data-apf-popup="${popup}"] summary`
  )?.focus()
}

function preserveToolbarFocus(popup: ToolbarPopup, event: Event) {
  if (toolbarFocusHandoffs.delete(popup) || toolbarPopup.value) event.preventDefault()
}

const lastManagementSection = ref<WorkspaceSection>('equipment-setups')
const capabilities=computed(()=>props.capabilities)
const libraryRows = computed(() => isLibrarySummaryView.value && libraryRequest.value ? libraryQuery.data.value?.items ?? [] : [])
const rows = computed<WorkspaceRecord[]>({
  get: () => {
    if (isDatasetMembersView.value) return memberRequest.value ? membersQuery.rows.value : []
    if (isLibrarySummaryView.value) return libraryRows.value
    if (isEquipmentManagement.value) return managementRequest.value ? managementQuery.data.value?.items ?? [] : []
    if (isSelectionRecordsView.value) return selectionRequest.value ? selectionQuery.rows.value : []
    return projectRequest.value ? projectQuery.rows.value : []
  },
  set: value => {
    if (isDatasetMembersView.value) membersQuery.updateRows(value.map(row => {if(!isMemberRecord(row))throw new ApiClientError('Member update requires a member record','contract');return row}))
    else if (isLibrarySummaryView.value) libraryQuery.updateItems(value)
    else if (isEquipmentManagement.value) managementQuery.updateItems(value)
    else if (isSelectionRecordsView.value) selectionQuery.updateItems(value)
    else projectQuery.updateItems(value)
  }
})
const selected = ref<WorkspaceRecord>()
const projectDetails = computed(() => {
  const row = selected.value
  if (!row || store.section !== 'projects' || viewingProjectAssets.value || viewingProjectDatasets.value || addingProjectAssets.value || addingProjectDatasets.value) return undefined
  return { project: zProjectOut.parse(row),
    saveName: (value: string | number | null) => saveRowField(row, 'name', value),
    saveTarget: (value: string | number | null) => saveRowField(row, 'target_name', value),
    saveNotes: (value: string | number | null) => saveRowField(row, 'notes', value) }
})
async function projectDetailsAction(action: ProjectDetailsAction, projectId: string) {
  const row = selected.value
  if (!row || row.id !== projectId || !projectDetails.value) return
  switch (action) {
    case 'assets': return openProjectAssets()
    case 'datasets': return openProjectDatasets()
    case 'add-asset': return openAvailableAssets()
    case 'add-dataset': return openAvailableDatasets()
    case 'edit': return editProject(row)
    case 'archive': return requestManagementArchive(projectDetails.value.project)
    case 'restore': return restoreProject(projectDetails.value.project)
  }
}
function cancelProjectField(field: 'name' | 'target_name' | 'notes', projectId: string) {
  if (selected.value?.id === projectId) clearInlineSaveFailure(inlineFailureKey(selected.value, field))
}
const settingsProjectMode = computed<SettingsProjectMode | undefined>(() => store.section === 'projects'
  ? viewingProjectAssets.value ? 'asset-references' : viewingProjectDatasets.value ? 'dataset-references' : 'projects' : undefined)
const choosingProjectVersion = computed(() => addingProjectAssets.value || addingProjectDatasets.value)
const settingsRecordDetails = computed<SettingsRecordDetails | undefined>(() => {
  const row = selected.value
  if (!row || activeArea.value === 'library' || isEquipmentManagement.value) return undefined
  const asset = rowAsset(row)
  return { recordId: row.id, title: itemTitle(row), subtitle: itemSubtitle(row),
    content: asset ? { assetId: asset.id, hasVersion: Boolean(asset.current_version_id) } : undefined,
    version: settingsProjectMode.value && settingsProjectMode.value !== 'projects' ? {
      number: recordVersion(row)?.number ?? '—',
      id: recordVersion(row)?.id ?? ''
    } : undefined }
})
const assetDetails = computed(() => {
  const row = selected.value
  if (!row || !settingsRecordDetails.value || !(assetRecord(row))) return undefined
  const asset = zAssetOut.parse(rowAsset(row))
  const save = (field: AssetDetailField) => (value: string | number | null) => saveRowField(row, field, value)
  const bindings: AssetDetailBindings = {
    name: save('name'), frame_class: save('frame_class'), frame_type: save('frame_type'),
    camera_id: save('camera_id'), optical_system_id: save('optical_system_id'), filter_id: save('filter_id'),
    exposure_seconds: save('exposure_seconds'), integration_seconds: save('integration_seconds'), sensor_temperature_c: save('sensor_temperature_c'),
    cfa_pattern: save('cfa_pattern'), status: save('status'), notes: save('notes'),
    parameters: changes => saveParameterGroup(row, changes), binning: value => saveBin(row, value)
  }
  return { asset, recordId: row.id, title: itemTitle(row), bindings,
    equipment: {
      camera_id: {display: materialEquipmentName(row,'camera_id'), choices: equipmentChoices('camera'), message: equipmentChoiceMessage('camera')},
      optical_system_id: {display: materialEquipmentName(row,'optical_system_id'), choices: equipmentChoices('optical_system'), message: equipmentChoiceMessage('optical_system')},
      filter_id: {display: materialEquipmentName(row,'filter_id'), choices: equipmentChoices('filter'), message: equipmentChoiceMessage('filter')}
    },
    binning: { value: binEditValue(asset.parameters), display: binValue(asset.parameters) ?? uiT('apfUi.not_specified'), choices: binEditChoices(asset.parameters) },
    temperatureDisplay: asset.parameters.sensor_temperature_c == null ? uiT('apfUi.not_specified') : displayTemperature(asset.parameters.sensor_temperature_c) + ' °C'
  }
})
const datasetDetails = computed(() => {
  const row = selected.value
  if (!row || !settingsRecordDetails.value || !isDatasetRecord(row)) return undefined
  return { dataset: zDatasetOut.parse(datasetRecord(row)), recordId: row.id,
    saveName: (value: string | number | null) => saveRowField(row,'name',value),
    saveStatus: (value: string | number | null) => saveRowField(row,'status',value),
    saveNotes: (value: string | number | null) => saveRowField(row,'notes',value) }
})
function cancelRecordField(field: string, recordId: string) {
  if (selected.value?.id === recordId) clearInlineSaveFailure(inlineFailureKey(selected.value, field))
}

function projectReferenceAction(recordId: string, mode: 'asset-references' | 'dataset-references', choosing: boolean) {
  if (projectReferences.pending.value || settingsRecordDetails.value?.recordId !== recordId || settingsProjectMode.value !== mode || choosingProjectVersion.value !== choosing) return
  if (mode === 'asset-references') return choosing ? addSelectedAsset() : removeSelectedAssetReference()
  return choosing ? addSelectedDataset() : removeSelectedDatasetReference()
}
const selectedAssetDetails = computed(() => {
  const row = selected.value
  if (!row || !isAssetRecord(row)) return undefined
  const asset=assetRecord(row)
  const versionId = recordVersion(row)?.id ?? undefined
  return {id:asset?.id??row.id,title:itemTitle(row),hasVersion:Boolean(versionId),versionId}
})
const total = computed(() => {
  if (isDatasetMembersView.value) return memberRequest.value ? membersQuery.data.value?.total ?? 0 : 0
  if (isLibrarySummaryView.value) return libraryRequest.value ? libraryQuery.data.value?.total ?? 0 : 0
  if (isEquipmentManagement.value) return managementRequest.value ? managementQuery.data.value?.total ?? 0 : 0
  if (isSelectionRecordsView.value) return selectionRequest.value ? selectionQuery.data.value?.page.total ?? 0 : 0
  return projectRequest.value ? projectQuery.data.value?.page.total ?? 0 : 0
})
const loading = computed(() => {
    if (isDatasetMembersView.value) return membersQuery.isPending.value || search.pending.value
    if (isLibrarySummaryView.value) return libraryQuery.isPending.value || search.pending.value
    if (isEquipmentManagement.value) return managementQuery.isPending.value || search.pending.value
    if (isSelectionRecordsView.value) return selectionQuery.isPending.value || search.pending.value
    return projectQuery.isPending.value || search.pending.value
  })
const operationError = ref<ApiClientError>()
const error = computed({
  get: () => {
    if (operationError.value) return operationError.value
    if (isDatasetMembersView.value && membersQuery.error.value) return presentError(membersQuery.error.value)
    if (isLibrarySummaryView.value && libraryQuery.error.value) return presentError(libraryQuery.error.value)
    if (isEquipmentManagement.value && managementQuery.error.value) return presentError(managementQuery.error.value)
    if (isSelectionRecordsView.value && selectionQuery.error.value) return presentError(selectionQuery.error.value)
    if (isProjectRecordsView.value && projectQuery.error.value) return presentError(projectQuery.error.value)
    return undefined
  },
  set: value => { operationError.value = value }
})
const statusFilter = ref<'active' | 'archived' | 'all'>('active')
const equipmentKindFilter = ref('')
const projectTargetFilter = ref('')
const projectTargetFilterDraft = ref('')
const projectReferences = useProjectReferenceActions({
  workspaceId: () => importWorkspace.value, projectId: toRef(store, 'activeProjectId'),
  revision: toRef(store, 'activeProjectRevision'), selected, mode: settingsProjectMode,
  choosing: choosingProjectVersion, error,
  onAdded: kind => { if (kind === 'asset') addingProjectAssets.value = false; else addingProjectDatasets.value = false }
})
const { addSelectedAsset, removeSelectedAssetReference, addSelectedDataset, removeSelectedDatasetReference } = projectReferences
const projectWrite=useUpdateProject()
const archiveWrite=useArchiveManagement()
let writeViewActive=true
const inlineState = useInlineSaveState(() => writeViewActive)
const { savingInline, inlineSaveFailure, waitForInlineSave, clearInlineSaveFailure } = inlineState
onBeforeUnmount(()=>{writeViewActive=false})
function writeViewKey(){
  return writeViewActive?JSON.stringify([importWorkspace.value,store.section,store.query,store.offset,store.activeProjectId,
    activeDataset.value?.id,viewingProjectAssets.value,viewingProjectDatasets.value,addingProjectAssets.value,addingProjectDatasets.value,
    libraryRequest.value,memberRequest.value,managementRequest.value,selectionRequest.value,projectRequest.value]):undefined
}
const managementFilterCount = computed(()=>Number(Boolean(projectTargetFilter.value)))
const setupDirty = ref(false)
const setupSaving = ref(false)
const calibrationDirty = ref(false)
const libraryCategory = ref<'all'|'light'|'calibration'>('all')
const roleFilter = ref('')
const frameTypeFilter = ref('')
function emptyFilters(): LibraryFilters { return {} }
const activeFilters = ref<LibraryFilters>(emptyFilters())
const filterButton = ref<HTMLElement>()
const activeFilterCount = computed(() => Object.values(activeFilters.value).filter(value =>
  Array.isArray(value) ? value.length > 0 : value !== ''
).length)
const viewingProjectAssets = ref(false)
const viewingProjectDatasets = ref(false)
const addingProjectAssets = ref(false)
const addingProjectDatasets = ref(false)
const importWorkspace = computed(()=>props.workspaceId)
const selection = useLibrarySelection(() => libraryRows.value)
const { bulkSelectMode, bulkSelection, bulkKey, clearBulkSelection, toggleBulkSelection,
  togglePageSelection, pageAllSelected, pagePartiallySelected } = selection
const removal = useLibraryRemoval({
  workspaceId: importWorkspace, enabled: () => isLibrarySummaryView.value,
  items: () => libraryRows.value, selection: bulkSelection, contextKey: writeViewKey, error,
  onRemoved(count) {
    if (isLibrarySummaryView.value) libraryQuery.updateTotal(Math.max(0,total.value-count))
    else if (isSelectionRecordsView.value) selectionQuery.updateTotal(Math.max(0,total.value-count))
    else projectQuery.updateTotal(Math.max(0,total.value-count))
    const pageSize=store.pageSize==='all'?total.value:store.pageSize
    if(store.offset>=total.value&&store.offset>0&&pageSize>0)store.offset=Math.max(0,Math.floor((total.value-1)/pageSize)*pageSize)
    selection.leaveSelection()
  }
})
const { bulkDeleteBusy, removalBlocksCurrentView, bulkDeleteNotice, bulkConfirmOpen, bulkConfirmRows,
  removeSelectedLibraryEntries, confirmRemoveSelectedLibraryEntries } = removal
const importFlow=useImportFlow({workspace:importWorkspace,clearSelection:clearBulkSelection,notify:notice=>emit('notify-import',notice)})
const {dialogOpen:importDialogOpen,files:importFiles,pickerMode:localPickerMode,issue:importIssue,
  createsDataset:importCreatesDataset,datasetName:importDatasetName,
  watchedTaskIds,refreshToken:progressRefreshToken,start:startImport,selected:localFilesSelected,
  submitted:importSubmitted,registered:importRegistrationCompleted,completed:importTaskCompleted,
  showIssue:showImportIssue,notify:notifyImport}=importFlow
const libraryViewMode = ref<'simple' | 'detail'>('simple')
const librarySort = ref({by: 'created_at', order: 'desc' as 'asc' | 'desc'})
const setupSort = ref({by: 'created_at' as SetupSortField, order: 'desc' as 'asc' | 'desc'})
const trashOpen = ref(false)
const pendingManagementArchive = ref<ManagementArchiveConfirmation>()
const managementArchiveBusy = ref(false)
const managementSelectMode = ref(false)
const managementSelection = ref(new Map<string,ManagementSelectionEntry>())
const equipmentDeleteItems = ref<EquipmentDeleteItem[]>()
function requestEquipmentDeleteSelection(items:EquipmentDeleteItem[]){equipmentDeleteItems.value=items}
function requestEquipmentDelete(row:Pick<EquipmentDeleteItem,'id'|'revision'>,entryType:'equipment'|'equipment_setup'=store.section==='equipment'?'equipment':'equipment_setup') {
  equipmentDeleteItems.value=[{entry_type:entryType,id:row.id,revision:row.revision}]
}
function requestSelectedEquipmentDelete(){
  equipmentDeleteItems.value=equipmentDeletionItems([...managementSelection.value.values()])
}
async function equipmentDeleted(){
  selected.value=undefined;managementSelection.value=new Map();managementSelectMode.value=false
  managementChangeToken.value++;await loadRelatedEquipment(true)
}
const managementChangeToken = ref(0)
const datasetView = useDatasetView({
  workspaceId: () => importWorkspace.value, paused: () => savingInline.value > 0 || Boolean(inlineSaveFailure.value),
  navigation: store, sort: librarySort, mode: libraryViewMode, filterOpen: filterPanelOpen,
  records: rows, libraryActive: () => isLibraryItemsView.value, dirty: () => dirty.value, calibrationDirty, waitForInlineSave, error
})
const { activeDataset, restoringOuterLibraryState, openDataset, closeDataset, leaveDatasetContext, calibrationUpdated } = datasetView
function thumbnailKey(record: MaterialRecord) {
  const group = activeDataset.value
  return 'member_position' in record && group
    ? `${group.id}:${group.current_version_id}:${materialThumbnailKey(record)}`
    : materialThumbnailKey(record)
}
const { urls: previewUrls, load: loadThumbnailRecords, loadMissing: loadMissingThumbnails, prioritize: prioritizeThumbnails, refresh: refreshThumbnailRecord, clear: clearThumbnails, cancel: cancelThumbnails } = useThumbnailUrls<MaterialRecord>(thumbnailKey, readThumbnail)
function loadThumbnails(values: readonly unknown[]) {
  if(!connectionReady.value)return
  return loadThumbnailRecords(values.flatMap(value => {const record=resolveMaterialRecord(value);return record?[record]:[]}))
}
function thumbnailUrl(value: unknown) {
  const record=resolveMaterialRecord(value)
  return record ? previewUrls.value[thumbnailKey(record)] : undefined
}
const {photo:photoPreview,media:mediaPreview,open:openPhotoPreview,close:closePhotoPreview}=useLibraryPreview({
  nativeViewer:()=>Boolean(props.controls?.mediaViewer),waitForEdits:waitForInlineSave,
  onError:cause=>{error.value=presentError(cause)}
})
const recordEditorOwner = useRecordEditor(importWorkspace)
const recordEditor = recordEditorOwner.model
const editorType = computed(() => recordEditor.value?.kind)
const editingId = computed(() => recordEditor.value?.id)
const saving = ref(false)
const equipmentChoicesQuery = useEquipmentChoices(() => importWorkspace.value)
const relatedEquipment = computed(() => equipmentChoicesQuery.data.value ?? [])
const relatedEquipmentLoading = equipmentChoicesQuery.isFetching
const relatedEquipmentError = computed(() => equipmentChoicesQuery.error.value ? errorText(presentError(equipmentChoicesQuery.error.value)) : '')
const relatedEquipmentReady = equipmentChoicesQuery.isSuccess
const loadRelatedEquipment = equipmentChoicesQuery.refresh





const managementFilterBlocked = computed(() => dirty.value || setupSaving.value || saving.value || savingInline.value > 0)
function filterEquipmentKind(value: string | number | null | undefined) {
  if (managementFilterBlocked.value) return
  store.offset = 0
  equipmentKindFilter.value = String(value ?? '')
}
async function refreshEquipment() {
  closeToolbarPopup()
  await loadRelatedEquipment(true)
  await refreshRecords()
}
const dirty = computed(() => setupDirty.value || calibrationDirty.value || recordEditorOwner.dirty.value)
const equipmentCategoryOptions = computed(() => [
  { value: '', name: uiT('apfUi.all_equipment') },
  ...equipmentKinds.map(kind => ({ value: kind, name: equipmentKindLabels[kind] }))
])
const equipmentMenuItems = computed<LibraryMenuItem[]>(() => {
  const current=selected.value
  return [
  ...(foldSecondaryActions.value && store.section === 'equipment' ? [{
    label: uiT('apfUi.equipment_category'),
    disabled: managementFilterBlocked.value,
    radioGroup: {
      value: equipmentKindFilter.value,
      options: equipmentCategoryOptions.value.map(({ value, name }) => ({
        value, label: name, command: () => filterEquipmentKind(value)
      }))
    }
  }] : []),
  {get label() { return uiT('apfUi.refresh') },disabled:managementFilterBlocked.value||loading.value,command:refreshEquipment},
  ...(!managementSelectMode.value?[{get label() { return uiT('apfUi.manage_in_bulk') },disabled:managementFilterBlocked.value||loading.value,command:enterManagementSelectMode}]:[]),
  ...(store.section==='equipment-setups'&&current?[{get label() { return uiT('apfUi.delete_setup') },disabled:managementFilterBlocked.value||loading.value,command:()=>requestEquipmentDelete(managementSelectionEntry(store.section,current).reference)}]:[])
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
const compactToolbar = computed(() => isLibraryItemsView.value || isEquipmentManagement.value)
const toolbarViewValue = computed(() => isEquipmentManagement.value ? store.section : libraryCategory.value)
const newEquipmentLabel = computed(() => uiT(store.section === 'equipment-setups' ? 'apfUi.new_equipment_setup' : 'apfUi.new_equipment'))
const toolbarViewLabel = computed(() => isEquipmentManagement.value
  ? uiT(props.native ? 'apfUi.equipment_and_metadata_categories' : 'apfUi.settings_category')
  : uiT('apfUi.asset_use'))
const toolbarViews = computed(() => isEquipmentManagement.value ? [
  { value: 'equipment-setups', label: uiT('apfUi.equipment_setup') },
  { value: 'equipment', label: uiT('apfUi.my_equipment') }
] : [
  { value: 'all', label: uiT('apfUi.all_assets') },
  { value: 'light', label: uiT('apfUi.light') },
  { value: 'calibration', label: uiT('apfUi.calibration_library') }
])
const toolbarViewOptions = computed(() => toolbarViews.value.map(({ value, label }) => ({ value, name: label })))
function switchToolbarView(value: string | number | null | undefined) {
  if (value === 'equipment' || value === 'equipment-setups') return selectSection(value)
  if (value === 'all' || value === 'light' || value === 'calibration') return selectLibraryCategory(value)
}
const isDatasetMembersView = computed(() => activeArea.value === 'library' && store.section === 'library' && Boolean(activeDataset.value) && !viewingProjectAssets.value && !viewingProjectDatasets.value)
const isLibrarySummaryView = computed(() => isLibraryItemsView.value && store.section === 'library')
const isSelectionRecordsView = computed(() => store.section === 'calibration' || addingProjectAssets.value || (store.section === 'projects' && viewingProjectDatasets.value && addingProjectDatasets.value))
const isProjectRecordsView = computed(() => !isSelectionRecordsView.value && (store.section === 'projects' || viewingProjectAssets.value))

const libraryToolbarBlocked = computed(() => bulkDeleteBusy.value || savingInline.value > 0 || Boolean(inlineSaveFailure.value) || setupDirty.value)
const libraryMenuItems = computed<LibraryMenuItem[]>(() => [
  ...(foldSecondaryActions.value && props.native && isLibraryItemsView.value ? [
    { label: uiT('apfUi.equipment_manager'), command: () => emit('manage-equipment') }
  ] : []),
  { get label() { return uiT('apfUi.refresh') }, disabled: libraryToolbarBlocked.value || loading.value, command: refreshLibrary },
  ...(isLibrarySummaryView.value ? [
    { get label() { return uiT('apfUi.manage_in_bulk') }, disabled: libraryToolbarBlocked.value || loading.value, command: enterBulkSelectMode }
  ] : []),
  ...(isLibraryItemsView.value ? [
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

const areaTitles: Record<WorkspaceArea, string> = {
  get library() { return uiT('apfUi.library') },
  get settings() { return uiT('apfUi.equipment_manager') }
}
const search = useRecordSearch(()=>store.query,()=>JSON.stringify([activeArea.value,store.section,activeDataset.value?.id,activeDataset.value?.current_version_id,
  store.activeProjectId,viewingProjectAssets.value,viewingProjectDatasets.value,addingProjectAssets.value,addingProjectDatasets.value,
  store.offset,store.pageSize,statusFilter.value,roleFilter.value,frameTypeFilter.value,equipmentKindFilter.value,projectTargetFilter.value,
  libraryCategory.value,activeFilters.value,librarySort.value,setupSort.value]))
const listInput = () => ({workspaceId:importWorkspace.value,pageSize:recordPageSize.value,offset:store.offset,search:search.query.value})
const editorReadPaused = () => dirty.value || savingInline.value>0 || Boolean(inlineSaveFailure.value) || removalBlocksCurrentView.value
const {request:projectRequest,query:projectQuery} = useProjectRecordsView(()=>({...listInput(),active:isProjectRecordsView.value,
  kind:viewingProjectAssets.value?'assets':viewingProjectDatasets.value?'datasets':'projects',projectId:store.activeProjectId,
  status:statusFilter.value,targetName:projectTargetFilter.value,role:roleFilter.value,frameType:frameTypeFilter.value}),
  ()=>!isProjectRecordsView.value||editorReadPaused())
const {request:selectionRequest,query:selectionQuery} = useMaterialSelectionView(()=>({...listInput(),active:isSelectionRecordsView.value,
  kind:addingProjectDatasets.value?'datasets':'assets',status:statusFilter.value,role:store.section==='calibration'?'calibration':roleFilter.value,frameType:frameTypeFilter.value}),
  ()=>!isSelectionRecordsView.value||editorReadPaused())
watch([projectQuery.data, projectQuery.fetchStatus], ([page, status]) => {
  if (!page || status !== 'idle' || projectQuery.isError.value || !isProjectRecordsView.value) return
  selected.value = rows.value.find(row => row.id === selected.value?.id)
  void loadThumbnails(rows.value)
})
watch([selectionQuery.data, selectionQuery.fetchStatus], ([page, status]) => {
  if (!page || status !== 'idle' || selectionQuery.isError.value || !isSelectionRecordsView.value) return
  selected.value = rows.value.find(row => row.id === selected.value?.id)
  void loadThumbnails(rows.value)
})
const {request:managementRequest,query:managementQuery} = useEquipmentManagementView(()=>({...listInput(),active:isEquipmentManagement.value,
  kind:store.section==='equipment'?'equipment':'setups',status:statusFilter.value,equipmentKind:equipmentKindFilter.value,sort:setupSort.value}),
  ()=>!isEquipmentManagement.value||editorReadPaused())
watch([managementQuery.data, managementQuery.fetchStatus], ([page, status]) => {
  if (!page || status !== 'idle' || managementQuery.isError.value || !isEquipmentManagement.value) return
  if (store.offset > 0 && store.offset >= page.total) {
    store.offset = page.total ? Math.floor((page.total - 1) / 50) * 50 : 0
    return
  }
  const latest=rows.value.find(row=>row.id===selected.value?.id)
  // A read begun before a confirmed save must not lower the selected revision.
  if(!latest||!selected.value||recordEntity(latest).revision>=recordEntity(selected.value).revision)selected.value=latest
})
const libraryReadPaused = () => savingInline.value>0 || Boolean(inlineSaveFailure.value) || removalBlocksCurrentView.value
const {request:libraryRequest,query:libraryQuery} = useLibraryView(()=>({...listInput(),active:isLibrarySummaryView.value,
  category:libraryCategory.value,filters:activeFilters.value,sort:librarySort.value}),()=>!isLibrarySummaryView.value||libraryReadPaused())
watch([libraryQuery.data, libraryQuery.fetchStatus], ([page, status]) => {
  if (!page || status !== 'idle' || libraryQuery.isError.value || !isLibrarySummaryView.value) return
  selected.value = rows.value.find(row => row.id === selected.value?.id)
  void loadThumbnails(rows.value)
})
const {request:memberRequest,query:membersQuery} = useDatasetMembersView(()=>({...listInput(),active:isDatasetMembersView.value,
  dataset:activeDataset.value?{id:activeDataset.value.id,versionId:activeDataset.value.current_version_id}:undefined,sort:librarySort.value}),
  ()=>!isDatasetMembersView.value||libraryReadPaused())
watch([membersQuery.data, membersQuery.fetchStatus], ([page, status]) => {
  if (!page || status !== 'idle' || membersQuery.isError.value || !isDatasetMembersView.value) return
  selected.value = rows.value.find(row => row.id === selected.value?.id)
  void loadThumbnails(rows.value)
})




function equipmentChoiceMessage(kind:string){
  if(relatedEquipmentLoading.value)return uiT('apfUi.reading_equipment_list')
  if(relatedEquipmentError.value)return relatedEquipmentError.value
  const names:Record<string,string>={get camera() { return uiT('apfUi.camera_dacf07') },get optical_system() { return uiT('apfUi.imaging_system') },get filter() { return uiT('apfUi.filter') }}
  return relatedEquipment.value.some(item=>item.kind===kind)?'':uiT('apfUi.not_registered_yet')+(names[kind]??uiT('apfUi.equipment'))+uiT('apfUi.add_it_in_settings_equipment_first')
}

function equipmentChoices(kind:string){
  const current=relatedEquipment.value.filter(item=>kind==='optical_system'?item.kind==='telescope':item.kind===kind).map(item=>({
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







const currentRead = computed(()=>isDatasetMembersView.value?membersQuery:isLibrarySummaryView.value?libraryQuery:
  isEquipmentManagement.value?managementQuery:isSelectionRecordsView.value?selectionQuery:isProjectRecordsView.value?projectQuery:undefined)
// Action diagnostics belong to the originating view, independently of Query errors.
watch(writeViewKey,()=>{operationError.value=undefined})
async function refreshRecords() {
  if(!connectionReady.value||savingInline.value||inlineSaveFailure.value||removalBlocksCurrentView.value)return
  cancelThumbnails()
  error.value=undefined
  await currentRead.value?.refresh()
}

async function readThumbnail(record: MaterialRecord, signal: AbortSignal): Promise<Blob | undefined> {
  if ('thumbnail_status' in record && (record.thumbnail_status === 'failed' || record.thumbnail_status === 'unsupported')) return
  if ('member_position' in record && 'dataset_id' in record) {
    return assetApi.getBlob(`/astrophotoflow/api/v1/datasets/${record.dataset_id}/versions/${record.dataset_version_id}/members/${record.version_id}/thumbnail`, signal)
  }
  let base: string
  if ('version_id' in record) {
    const thumbnail=record.thumbnail
    if (record.entry_type === 'dataset') {
      if (!thumbnail || !record.version_id) return
      return assetApi.getBlob(`/astrophotoflow/api/v1/datasets/${record.id}/versions/${record.version_id}/members/${thumbnail.asset_version_id}/thumbnail`, signal)
    }
    if (!record.view_base) return
    base=record.view_base
  } else if ('summary' in record) return
  else {
    const member=fixedAssetPreview(record)
    if (!member) return
    if ('member_position' in record && activeDataset.value) {
      const group=activeDataset.value
      return assetApi.getBlob(`/astrophotoflow/api/v1/datasets/${group.id}/versions/${group.current_version_id}/members/${member.version.id}/thumbnail`, signal)
    }
    base=materialPreviewBase(record,member)
  }
  return assetApi.getBlob(base+'/thumbnail',signal)
}
async function refreshPhotoThumbnails(photo: PreviewPhoto) {
  const aliases=rows.value.flatMap(value=>{const record=resolveMaterialRecord(value);return record?[record]:[]}).filter(record=>{
    if('version_id' in record)return record.thumbnail?.asset_id===photo.assetId&&record.thumbnail.asset_version_id===photo.versionId
    const fixed=fixedAssetPreview(record)
    return fixed?.asset.id===photo.assetId&&fixed.version.id===photo.versionId
  })
  try {if(aliases[0])await refreshThumbnailRecord(aliases[0],aliases)}
  catch(cause){error.value=presentError(cause)}
}
watch(() => JSON.stringify([
  activeArea.value, store.section, libraryCategory.value, activeDataset.value?.id, activeDataset.value?.current_version_id,
  store.activeProjectId, viewingProjectAssets.value, viewingProjectDatasets.value, addingProjectAssets.value, addingProjectDatasets.value,
  store.query, store.offset, store.pageSize, librarySort.value, libraryViewMode.value, activeFilters.value, selected.value?.id
]), closePhotoPreview, {flush:'sync'})


function requestManagementArchive(row:ProjectOut) {
  pendingManagementArchive.value = {kind:'single',entry:managementSelectionEntry('projects',row)}
}
function requestSelectedManagementArchive() {
  if (!managementSelection.value.size || managementArchiveBusy.value) return
  pendingManagementArchive.value = {kind:'selection',entries:[...managementSelection.value.values()]}
}

async function restoreProject(row:ProjectOut) {
  const origin=writeViewKey()
  const workspaceId=importWorkspace.value
  if (!await waitForInlineSave()) return
  if(origin!==writeViewKey())return
  error.value=undefined
  managementArchiveBusy.value=true
  try {
    await projectWrite.mutateAsync({workspaceId,projectId:row.id,body:validatedInput(zPatchProjectApiV1ProjectsProjectIdPatchBody,{base_revision:row.revision,status:'active'})})
    if(origin!==writeViewKey())return
    managementChangeToken.value++
    pendingManagementArchive.value=undefined
    } catch (cause) {if(origin===writeViewKey())error.value=presentError(cause)}
  finally {managementArchiveBusy.value=false}
}

async function confirmManagementArchive() {
  const origin=writeViewKey()
  const workspaceId=importWorkspace.value
  const pending=pendingManagementArchive.value
  if (!pending||managementArchiveBusy.value) return
  const entries=pending.kind==='selection'?pending.entries:[pending.entry]
  managementArchiveBusy.value=true
  try {
    if (!await waitForInlineSave()) return
    if(origin!==writeViewKey())return
    error.value=undefined
    await archiveWrite.mutateAsync({workspaceId,body:validatedInput(zArchiveManagementEntriesApiV1SettingsTrashArchivePostBody,{items:managementArchiveItems(entries)})})
    if(origin!==writeViewKey())return
    if (pending.kind==='selection') {
      managementSelection.value=new Map()
      managementSelectMode.value=false
    }
    pendingManagementArchive.value=undefined
    selected.value=undefined
    managementChangeToken.value++
    } catch (cause) {if(origin===writeViewKey())error.value=presentError(cause)}
  finally {managementArchiveBusy.value=false}
}

function managementSelectionKey(section:WorkspaceSection,id:string){return section+':'+id}
function toggleManagementSelection(row:unknown){
  const entry=managementSelectionEntry(store.section,row)
  const key=managementSelectionKey(store.section,entry.reference.id),next=new Map(managementSelection.value)
  if(next.has(key))next.delete(key);else next.set(key,entry)
  managementSelection.value=next
  if(isEquipmentManagement.value)selected.value=undefined
}
function toggleManagementPage(checked:boolean){
  const next=new Map(managementSelection.value)
  for(const row of rows.value){const key=managementSelectionKey(store.section,row.id);if(checked)next.set(key,managementSelectionEntry(store.section,row));else next.delete(key)}
  managementSelection.value=next
  if(isEquipmentManagement.value)selected.value=undefined
}
const managementPageAllSelected=computed(()=>rows.value.length>0&&rows.value.every(row=>managementSelection.value.has(managementSelectionKey(store.section,row.id))))
const managementPagePartiallySelected=computed(()=>rows.value.some(row=>managementSelection.value.has(managementSelectionKey(store.section,row.id)))&&!managementPageAllSelected.value)
async function enterManagementSelectMode(){
  if(managementFilterBlocked.value||managementArchiveBusy.value)return
  if(!await waitForInlineSave())return
  managementSelection.value=new Map();managementSelectMode.value=true;selected.value=undefined
}
function leaveManagementSelectMode(){managementSelectMode.value=false;managementSelection.value=new Map();pendingManagementArchive.value=undefined}

async function selectSection(section: WorkspaceSection) {
  if (dirty.value && !window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_switch'))) return
  if(!await waitForInlineSave())return
  closeToolbarPopup()
  leaveDatasetContext()
  recordEditorOwner.close()
  viewingProjectAssets.value = false
  viewingProjectDatasets.value = false
  addingProjectAssets.value = false
  addingProjectDatasets.value = false
  managementFilterOpen.value=false
  managementSelectMode.value=false
  managementSelection.value=new Map()
  equipmentKindFilter.value='';projectTargetFilter.value=''
  clearThumbnails()
  store.selectSection(section)
  if (section === 'projects' || section === 'equipment' || section === 'equipment-setups') {
    lastManagementSection.value = section
  }
  selected.value = undefined
  if (section === 'equipment-setups') void loadRelatedEquipment(true)
}

async function selectLibraryCategory(category:'all'|'light'|'calibration'){
  if(category===libraryCategory.value)return
  if(dirty.value&&!window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_switch')))return
  if(!await waitForInlineSave())return
  closeToolbarPopup()
  leaveDatasetContext();selected.value=undefined
  store.query='';store.offset=0;activeFilters.value=emptyFilters()
  libraryCategory.value=category
}

async function selectArea(area: WorkspaceArea, managementSection: WorkspaceSection = 'equipment-setups') {
  if (dirty.value && !window.confirm(uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_switch'))) return false
  if(!await waitForInlineSave())return false
  closeToolbarPopup()
  leaveDatasetContext()
  recordEditorOwner.close()
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
  clearThumbnails()
  activeArea.value = area
  if (area === 'library') {
    store.selectSection('library')
    void loadRelatedEquipment(true)
    } else if (area === 'settings') {
    lastManagementSection.value = managementSection
    store.selectSection(managementSection)
    if (managementSection === 'equipment-setups') void loadRelatedEquipment(true)
    }
  return true
}

async function leavePage() {
  closeToolbarPopup()
  return dirty.value ? selectArea(activeArea.value, store.section) : waitForInlineSave()
}

defineExpose({ selectArea, activeArea, leavePage, showImportIssue })

function applyFilters(filters: LibraryFilters) {
  if (!isLibraryItemsView.value) return
  activeFilters.value=Object.fromEntries(Object.entries(filters).filter(([,value])=>Array.isArray(value)?value.length>0:value!==''))
  clearBulkSelection()
  store.offset = 0
}

function materialReadiness(value: unknown) {
  const row=resolveMaterialRecord(value)
  if(!row)return uiT('apfUi.no_original_yet')
  const issue='import_issue' in row&&recordIssue(row)
  if (hasSummary(row)) {
    const availability = row.summary.availability
    if (availability.value === 'changed' || availability.value === 'missing') return uiT('apfUi.original_error')
    if (!row.input_ready) return issue ? uiT('apfUi.original_error') : uiT('apfUi.importing_originals')
    return uiT('apfUi.original_ready')
  }
  const version = fixedAssetContent(row)?.version
  if (!version) return uiT('apfUi.no_original_yet')
  if (version.availability === 'changed' || version.availability === 'missing') return uiT('apfUi.original_error')
  if (version.availability !== 'available') return issue ? uiT('apfUi.original_error') : uiT('apfUi.importing_originals')
  return uiT('apfUi.original_ready')
}
function refreshLibrary() {
  if(savingInline.value||inlineSaveFailure.value)return
  clearBulkSelection()
  void loadRelatedEquipment(true)
  importFlow.refresh()
  void refreshRecords()
}

async function calibrationCreated(dataset: DatasetOut) {
  await nextTick()
  if (activeArea.value !== 'library' || libraryCategory.value !== 'calibration' || activeDataset.value || calibrationDirty.value) return
  const row = rows.value.find(item => item.id === dataset.id)
  if (row) await openDataset(row)
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

function toggleSetupSort(by: Exclude<SetupSortField, 'created_at'>) {
  if (managementFilterBlocked.value || loading.value) return
  setupSort.value = setupSort.value.by === by
    ? { by, order: setupSort.value.order === 'asc' ? 'desc' : 'asc' }
    : { by, order: 'asc' }
  managementSelection.value = new Map()
  managementSelectMode.value = false
  if (store.offset !== 0) store.offset = 0
}
function toggleLibrarySort(by:string){
  librarySort.value=librarySort.value.by===by
    ?{by,order:librarySort.value.order==='asc'?'desc':'asc'}
    :{by,order:'asc'}
  store.offset=0
  clearBulkSelection()
  bulkDeleteNotice.value=''
}
async function enterBulkSelectMode(){
  if(!await waitForInlineSave())return
  selection.enterSelection()
  bulkDeleteNotice.value=''
  error.value=undefined
  filterPanelOpen.value=false
}
function leaveBulkSelectMode(){
  selection.leaveSelection()
  bulkDeleteNotice.value=''
  error.value=undefined
}

function onLibraryRowClick(row:WorkspaceRecord,event:MouseEvent){
  if(bulkSelectMode.value){if(isLibrarySummary(row))toggleBulkSelection(row);return}
  if(isDatasetRecord(row)&&isLibraryItemsView.value&&!(event.target instanceof Element&&event.target.closest('.apf-inline-field'))){
    openDataset(row)
    return
  }
  void selectRow(row)
}

async function selectRow(row: WorkspaceRecord) {
  if(selected.value?.id===row.id)return
  if(setupDirty.value&&!window.confirm(uiT('apfUi.this_setup_has_unsaved_changes_discard_them')))return
  if(!await waitForInlineSave())return
  selected.value = row
  if(assetRecord(row)||isDatasetRecord(row))
    void loadRelatedEquipment(true)
  if (isProjectRecord(row) && store.section === 'projects' && !viewingProjectAssets.value && !viewingProjectDatasets.value) {
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
}

async function openAvailableAssets() {
  if(!await waitForInlineSave())return
  viewingProjectAssets.value = true
  addingProjectAssets.value = true
  addingProjectDatasets.value = false
  store.offset = 0
  selected.value = undefined
}

async function toggleProjectAssetMode(){
  if(!await waitForInlineSave())return
  if(addingProjectAssets.value)addingProjectAssets.value=false
  else await openAvailableAssets()
}

async function openAvailableDatasets() {
  if(!await waitForInlineSave())return
  viewingProjectDatasets.value = true
  addingProjectDatasets.value = true
  addingProjectAssets.value = false
  store.offset = 0
  selected.value = undefined
}

async function toggleProjectDatasetMode(){
  if(!await waitForInlineSave())return
  if(addingProjectDatasets.value)addingProjectDatasets.value=false
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
}

async function openCreate(type: EditorType) {
  if (!await waitForInlineSave()) return
  if (type === 'project') recordEditorOwner.project()
  else recordEditorOwner.equipment()
  selected.value = undefined
}

function editEquipment(row: WorkspaceRecord) {
  if (managementFilterBlocked.value || editorType.value) return
  recordEditorOwner.equipment(zEquipmentPage.shape.items.element.parse(row))
}
function editProject(row: WorkspaceRecord) {
  recordEditorOwner.project(zProjectOut.parse(row))
}

function closeEditor() {
  if(saving.value||savingInline.value||inlineSaveFailure.value)return
  if (dirty.value && !window.confirm(uiT('apfUi.discard_unsaved_changes'))) return
  recordEditorOwner.close()
}

async function saveEditor() {
  if (!editorType.value||(editingId.value&&editorType.value!=='equipment')||saving.value) return
  saving.value = true
  error.value = undefined
  try {
    await recordEditorOwner.submit()
    recordEditorOwner.close()
    } catch (cause) {
    error.value = presentError(cause)
  } finally {
    saving.value = false
  }
}

const fieldEditing = useRecordFieldEditing({
  workspaceId: () => importWorkspace.value, contextKey: writeViewKey, records: rows, selected,
  editorSource: () => recordEditorOwner.source.value,
  synchronizeDraft: (id, updated) => recordEditorOwner.synchronize(id, updated),
  datasetOpen: () => Boolean(activeDataset.value), saveState: inlineState,
  projectSaved: (id, revision) => { if (store.activeProjectId === id) store.activeProjectRevision = revision }
})
const { saveEditorInline, saveRowField, saveParameterGroup, inlineFailureKey, editorInlineFailureKey, saveBin } = fieldEditing

const itemTitle = (row: WorkspaceRecord) => recordEntity(row).name ?? uiT('apfUi.unnamed_record')
const itemSubtitle = (row: WorkspaceRecord) => {
  if (isProjectRecord(row)) return row.target_name || ''
  if (isDatasetRecord(row)) return datasetClassification(row) + ' · ' + (isDatasetRecord(row)?datasetRecord(row).member_count:0) + uiT('apfUi.members')
  if ('version' in row) return uiT('apfUi.fixed_version_f7e42b') + frameTypeLabel(rowClassification(row).frame_type)
  if ('current_version' in row && row.current_version) return frameTypeLabel(rowClassification(row).frame_type)
  if (isEquipmentRecord(row)) {
    return equipmentSubtitle({kind:row.kind,name:row.name,model:row.model})
  }
  if (isSetupRecord(row)) return row.components.length + uiT('apfUi.devices')
  return ''
}
const rowAsset = assetRecord


function materialEquipmentValue(row: WorkspaceRecord, key: 'camera_id' | 'optical_system_id' | 'filter_id', fixed = false): string | undefined {
  if (hasSummary(row)) return summaryEquipment(row, key)
  const material=resolveMaterialRecord(row)
  const snapshot = fixed || isProjectAssetReference(row) ? material&&fixedAssetContent(material)?.version.capture_snapshot?.equipment_snapshot : rowAsset(row)?.equipment_snapshot
  return snapshot?.[key]?.name
}
function materialEquipmentName(row:WorkspaceRecord,key:'camera_id'|'optical_system_id'|'filter_id') {
  return materialEquipmentValue(row,key)??uiT('apfUi.not_specified')
}
function historicalEquipmentSnapshots(): EquipmentChoiceSnapshot[] {
  return rows.value.flatMap(row => hasSummary(row)
    ? summaryEquipmentChoices(row.summary)
    : observedEquipmentChoices(assetRecord(row)?.equipment_snapshot ?? {}))
}

watch(
  [() => store.query, () => store.offset, () => store.pageSize, statusFilter, roleFilter, frameTypeFilter, equipmentKindFilter, projectTargetFilter],
  ([query, offset, pageSize, status, role, frameType, kind, target], [previousQuery, previousOffset, previousPageSize, previousStatus, previousRole, previousFrameType, previousKind, previousTarget]) => {
    if(restoringOuterLibraryState.value)return
    const filtersChanged=pageSize!==previousPageSize||status!==previousStatus||role!==previousRole||frameType!==previousFrameType||kind!==previousKind||target!==previousTarget
    if(offset!==previousOffset||query!==previousQuery||filtersChanged){
      clearBulkSelection();managementSelection.value=new Map()
      if(isEquipmentManagement.value)managementSelectMode.value=false
    }
    if((query!==previousQuery||filtersChanged)&&offset!==0)store.offset=0
  }
)

const recordsPresentation = (() => {
function selectRecord(id: string) {
  const row = rows.value.find(item => item.id === id)
  if (row) return selectRow(row)
}
function toggleRecordSelection(id: string) {
  const row = rows.value.find(item => item.id === id)
  if (row) return toggleManagementSelection(row)
}

function libraryRowKey(row: (typeof rows.value)[number]) {
  return (isDatasetRecord(row)?'dataset':'asset')+':'+row.id+':'+(isMemberRecord(row)?row.member_position:'')
}
const libraryRows = computed(() => isAssetTable.value ? rows.value
  .filter((row): row is AssetRecord | DatasetRecord => isAssetRecord(row) || isDatasetRecord(row))
  .map(row => ({...createLibraryTableRow(row, {
    key: libraryRowKey(row), title: itemTitle(row), subtitle: itemSubtitle(row),
    selected: bulkSelectMode.value ? isLibrarySummary(row) && bulkSelection.value.has(bulkKey(row)) : selected.value?.id === row.id,
    source: canvasSource(row), readiness: materialReadiness(row)
  }, { name: materialEquipmentName, choices: equipmentChoices, message: equipmentChoiceMessage }, {
    saveRowField, saveParameterGroup, saveBin,
    cancelField: (record, field) => clearInlineSaveFailure(inlineFailureKey(record, field))
  }), thumbnailUrl: () => thumbnailUrl(row), prioritizeThumbnail: () => {
    const record = resolveMaterialRecord(row)
    if (record) prioritizeThumbnails([record])
  }, calibration: rowCalibration(row, {workspaceId:importWorkspace.value,dataset:activeDataset.value,
    cancel:clearInlineSaveFailure,
    runSave:async(key,operation)=>{inlineState.beginInlineSave();try{await operation();clearInlineSaveFailure(key)}catch(cause){inlineState.setInlineSaveFailure(key,errorText(presentError(cause)));throw cause}finally{inlineState.finishInlineSave()}},
    saved:async(datasetId)=>{if(datasetId)await calibrationUpdated(await datasetApi.get(datasetId));await invalidateLibraryData(calibrationCache,importWorkspace.value,
      datasetId?{datasetIds:[datasetId]}:{assetIds:[recordEntity(row).id]})}
  })})) : [])
function libraryClick(key:string,event:MouseEvent) { const row=rows.value.find(item=>libraryRowKey(item)===key); if(row)return onLibraryRowClick(row,event) }
function libraryPreview(key:string) { const row=rows.value.find(item=>libraryRowKey(item)===key); if(row)return openPhotoPreview(row) }
function libraryOpen(key:string) { const row=rows.value.find(item=>libraryRowKey(item)===key); if(row)return openDataset(row) }
function libraryToggle(key:string) { const row=rows.value.find(item=>libraryRowKey(item)===key); if(row&&isLibrarySummary(row))return toggleBulkSelection(row) }
const projects = computed(() => store.section === 'projects' && !isAssetTable.value && !isDatasetTable.value
  ? zProjectPage.shape.items.parse(rows.value) : [])
const selectedProjectIds = computed(() => new Set([...managementSelection.value.values()]
  .filter(item => item.section === 'projects').map(item => item.reference.id)))
function previewDatasetReference(id: string) {
  const row = rows.value.find(item => item.id === id)
  if (row) return openPhotoPreview(row)
}
const datasetReferenceRows = computed<DatasetReferenceRow[]>(() => isDatasetTable.value ? rows.value.filter(isDatasetRecord).map(row => {
  const entity=datasetRecord(row)
  return { recordId:row.id,title:entity.name,projectFixed:isProjectDatasetReference(row),thumbnail:thumbnailUrl(row),
    classification:datasetClassification(row),count:row.member_count,camera:materialEquipmentName(row,'camera_id'),
    parameters:parameterModeDisplay(row),exposure:datasetFieldDisplay(row,'exposure_seconds',value=>captureValue(value)+' s'),
    temperature:datasetFieldDisplay(row,'sensor_temperature_c',value=>captureValue(value)+' °C'),
    opticalSystem:materialEquipmentName(row,'optical_system_id'),filter:materialEquipmentName(row,'filter_id'),
    storage:datasetFieldDisplay(row,'storage_mode',displayLabel),status:displayLabel(entity.status),notes:entity.notes??'—',
    datasetId:entity.id,versionId:recordVersion(row)?.id??null,memberCount:row.member_count }
}) : [])
const equipmentRows = computed(() => store.section === 'equipment' ? zEquipmentPage.shape.items.parse(rows.value) : [])
const selectedEquipmentIds = computed(() => new Set([...managementSelection.value.values()]
  .filter(item => item.section === 'equipment').map(item => item.reference.id)))
function editEquipmentById(id: string) {
  const row = rows.value.find(item => item.id === id)
  if (row) return editEquipment(row)
}
const setupRows = computed(() => store.section === 'equipment-setups'
  ? zEquipmentSetupPage.shape.items.parse(rows.value) : [])
const selectedSetupIds = computed(() => new Set([...managementSelection.value.values()]
  .filter(item => item.section === 'equipment-setups').map(item => item.reference.id)))
const emptyMessage = computed(() => {
  if (loading.value || error.value || rows.value.length) return undefined
  if (activeDataset.value) return uiT('apfUi.this_image_group_has_no_members')
  if (isEquipmentManagement.value) {
    if (store.query || equipmentKindFilter.value) return uiT('apfUi.no_matching_records_adjust_the_search_or_equipment_category')
    return store.section === 'equipment-setups' ? uiT('apfUi.no_equipment_setups_yet') : uiT('apfUi.no_equipment_yet')
  }
  if (store.query || activeFilterCount.value) return uiT('apfUi.no_matching_records_adjust_the_search_or_filters')
  if (activeArea.value === 'library') return libraryCategory.value !== 'all'
    ? uiT('apfUi.no_assets_in_this_category_check_all_assets_or_import_files_for_this_f')
    : uiT('apfUi.your_library_is_empty_click_import_to_select_files_or_a_folder')
  return uiT('apfUi.no_records_here_yet_use_the_create_action_above')
})
const recordsError = computed(() => error.value ? { message: errorText(error.value), requestId: error.value.requestId } : undefined)

return computed<RecordsPresentation>(() => {
  let body: RecordsBody = { kind: 'none' }
  if (activeArea.value==='settings'&&store.section==='equipment-setups') {
    body = { kind:'setups', props:{ setups:setupRows.value, selectedId:selected.value?.id, loading:loading.value,
      equipment:relatedEquipment.value, equipmentReady:relatedEquipmentReady.value, equipmentLoading:relatedEquipmentLoading.value, equipmentError:relatedEquipmentError.value,
      sort:setupSort.value, blocked:managementFilterBlocked.value, selectMode:managementSelectMode.value, selectedIds:selectedSetupIds.value,
      allSelected:managementPageAllSelected.value, partiallySelected:managementPagePartiallySelected.value,
      onSort:toggleSetupSort, onSelect:selectRecord, 'onToggle-row':toggleRecordSelection, 'onToggle-page':toggleManagementPage, 'onRetry-equipment':()=>loadRelatedEquipment(true) } }
  } else if ((rows.value.length||activeArea.value==='library')&&isAssetTable.value) {
    body = { kind:'library', props:{ rows:libraryRows.value, library:activeArea.value==='library', viewMode:libraryViewMode.value,
      sortable:isLibraryTableView.value, sort:librarySort.value, selectMode:bulkSelectMode.value, selectionAllowed:isLibraryItemsView.value,
      deleting:bulkDeleteBusy.value, allSelected:pageAllSelected.value, partiallySelected:pagePartiallySelected.value,
      onSort:toggleLibrarySort, 'onRow-click':libraryClick, onPreview:libraryPreview, 'onOpen-dataset':libraryOpen, onToggle:libraryToggle, 'onToggle-page':togglePageSelection } }
  } else if (!loading.value&&rows.value.length&&isDatasetTable.value) {
    body = { kind:'datasets', props:{ workspaceId:importWorkspace.value, rows:datasetReferenceRows.value, selectedId:selected.value?.id, onSelect:selectRecord, onPreview:previewDatasetReference } }
  } else if (!loading.value&&rows.value.length&&isEquipmentManagement.value) {
    body = { kind:'equipment', props:{ equipment:equipmentRows.value, selectedId:selected.value?.id, selectedIds:selectedEquipmentIds.value,
      selectMode:managementSelectMode.value, allSelected:managementPageAllSelected.value, partiallySelected:managementPagePartiallySelected.value,
      blocked:managementFilterBlocked.value, loading:loading.value, layout:store.layout,
      onSelect:selectRecord, onEdit:editEquipmentById, 'onToggle-row':toggleRecordSelection, 'onToggle-page':toggleManagementPage } }
  } else if (!loading.value&&rows.value.length&&!isAssetTable.value&&!isDatasetTable.value) {
    body = { kind:'projects', props:{ projects:projects.value, selectedId:selected.value?.id, selectedIds:selectedProjectIds.value,
      selectMode:managementSelectMode.value, allSelected:managementPageAllSelected.value, partiallySelected:managementPagePartiallySelected.value, layout:store.layout,
      onSelect:selectRecord, 'onToggle-row':toggleRecordSelection, 'onToggle-page':toggleManagementPage } }
  }
  return {
    imports:isLibraryItemsView.value ? {refreshToken:progressRefreshToken.value, watchTaskIds:watchedTaskIds.value, workspace:importWorkspace.value,
      onCompleted:importTaskCompleted, onRegistered:importRegistrationCompleted, onSucceeded:notifyImportSuccess, onNotice:notifyImport} : undefined,
    feedback:{ inlineError:inlineSaveFailure.value,
      librarySelecting:bulkSelectMode.value, projectSelecting:managementSelectMode.value&&!isEquipmentManagement.value,
      notice:bulkDeleteNotice.value, readError:recordsError.value, loading:loading.value, emptyMessage:emptyMessage.value },
    body,
    pagination:{ total:total.value, offset:store.offset, pageSize:recordPageSize.value, pageLength:rows.value.length, library:activeArea.value==='library',
      equipmentManagement:isEquipmentManagement.value, loading:loading.value, error:Boolean(error.value), blocked:bulkDeleteBusy.value||setupDirty.value,
      onMove:store.movePage, 'onPage-size':store.setPageSize },
    previewUnavailable:Boolean(isAssetSection.value&&capabilities.value&&!capabilities.value.asset_preview)
  }
})
})()
const RecordsPanel = () => h(WorkspaceRecords, { view: recordsPresentation.value })

watch([
  () => activeDataset.value?.id, settingsProjectMode, bulkSelectMode, managementSelectMode,
  editorType, localPickerMode, importDialogOpen, importIssue, trashOpen, equipmentDeleteItems,
  bulkConfirmOpen, pendingManagementArchive, photoPreview, mediaPreview
], closeToolbarPopup, {flush:'sync'})
watch(connectionReady,async available=>{
  if(!available){closeToolbarPopup();closePhotoPreview();cancelThumbnails();return}
  await nextTick()
  if(writeViewActive&&connectionReady.value)void loadThumbnails(rows.value)
})
let thumbnailRefreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  document.addEventListener('pointerdown',dismissToolbarOnPointerDown,true)
  thumbnailRefreshTimer = setInterval(() => {
    if (!connectionReady.value || document.hidden || !(isLibraryItemsView.value || isDatasetMembersView.value)) return
    const visible=rows.value.flatMap(value=>{const record=resolveMaterialRecord(value);return record?[record]:[]})
    void loadMissingThumbnails(visible)
  }, 3000)
})
onBeforeUnmount(() => {
  if (thumbnailRefreshTimer) clearInterval(thumbnailRefreshTimer)
  cancelThumbnails()
  document.removeEventListener('pointerdown', dismissToolbarOnPointerDown, true)
})
</script>

<template>
  <section
    ref="workspaceRoot" class="apf-workspace" :aria-label="$t('apfUi.astrophotoflow_astronomy_library')"
    @pointerdown.stop @pointerup.stop @mousedown.stop @mouseup.stop
    @click.stop @contextmenu.stop @keydown.stop @keydown.esc="dismissToolbarOnEscape" @keyup.stop>
      <nav v-if="!props.native" class="apf-nav" :aria-label="$t('apfUi.astrophotoflow_modules')">
        <button
v-for="(title, area) in areaTitles" :key="area" type="button"
          :aria-label="title" :title="title" :aria-current="activeArea === area ? 'page' : undefined"
          @click="selectArea(area as WorkspaceArea)">
          <i :class="['pi', ({ library: 'pi-images', settings: 'pi-cog' } as Record<WorkspaceArea, string>)[area]]" aria-hidden="true"></i>
        </button>
      </nav>
    <main class="apf-main" :class="{'apf-equipment-management':isEquipmentManagement,'apf-library-workspace':activeArea==='library'}">
            <div v-if="(!props.sidebar || activeDataset || activeArea !== 'library') && (!props.sidebar || activeArea !== 'settings' || settingsProjectMode !== 'projects')" class="apf-heading">
              <button v-if="activeDataset" type="button" @click="closeDataset">{{ $t('apfUi.back_to_library') }}</button>
              <button v-else-if="viewingProjectAssets || viewingProjectDatasets" type="button" @click="leaveProjectAssets">{{ $t('apfUi.back_to_project') }}</button>
              <LibraryButton v-else-if="props.native && activeArea === 'settings' && store.section !== 'projects'" type="button" class="apf-equipment-back" :aria-label="$t('apfUi.back_to_library_8979db')" :tooltip="$t('apfUi.back_to_library_8979db')" @click="emit('back-to-library')"><i class="pi pi-arrow-left" aria-hidden="true"></i></LibraryButton>
              <h1 v-if="!props.sidebar || activeDataset || activeArea !== 'library'">{{ activeDataset ? $t('apfUi.library_968e00')+activeDataset.name : activeArea === 'library' ? $t('apfUi.library') : (viewingProjectAssets ? $t('apfUi.project_assets') : viewingProjectDatasets ? $t('apfUi.project_image_groups') : store.section === 'projects' ? $t('apfUi.project') : $t('apfUi.equipment_manager')) }}</h1>
              <span v-if="activeDataset" class="apf-state">{{ $t('apfUi.image_group_photos_value', { p0: (activeDataset.member_count??0) }) }}</span>
            </div>
          <div ref="toolbar" class="apf-toolbar" :class="{
            'apf-compact-toolbar': compactToolbar,
            'apf-toolbar-icons': compactToolbar && foldSearch
          }">
            <LibraryTabs v-if="compactToolbar && !foldViewTabs" :class="isEquipmentManagement ? 'apf-management-tabs' : 'apf-library-categories'" :value="toolbarViewValue" :options="toolbarViews" :label="toolbarViewLabel" @change="switchToolbarView" />
            <LibrarySelect v-else-if="compactToolbar" v-model:open="toolbarViewOpen" class="apf-toolbar-view" data-apf-popup="toolbar-view" :model-value="toolbarViewValue" :options="toolbarViewOptions" :label="toolbarViewLabel" :modal="false" :searchable="false" density="compact" @update:model-value="switchToolbarView" @close-auto-focus="preserveToolbarFocus('toolbar-view', $event)" />
            <div class="apf-toolbar-search" data-apf-popup="toolbar-search">
              <LibraryButton v-if="compactToolbar && foldSearch" class="apf-toolbar-icon" :class="{ 'apf-toolbar-active': store.query }" :aria-label="$t('apfUi.search')" :aria-description="store.query || undefined" :tooltip="$t('apfUi.search')" :aria-expanded="toolbarSearchOpen" :disabled="bulkDeleteBusy||setupDirty" @click="toggleToolbarSearch">
                <i class="pi pi-search" aria-hidden="true"></i>
              </LibraryButton>
              <label v-if="!compactToolbar || !foldSearch || toolbarSearchOpen" class="apf-search" :class="{ 'apf-search-popup': compactToolbar && foldSearch }">
                <i class="pi pi-search" aria-hidden="true"></i>
                <input ref="toolbarSearchInput" :value="store.query" :aria-label="$t('apfUi.search')" :placeholder="$t('apfUi.search_names')" :disabled="bulkDeleteBusy||setupDirty" @input="setQuery" />
              </label>
            </div>
            <span v-if="isLibraryItemsView" ref="filterButton" data-apf-popup="library-filter">
              <LibraryButton :disabled="bulkDeleteBusy" :aria-expanded="filterPanelOpen" :aria-label="$t('apfUi.filter_b5f154') + (activeFilterCount ? `（${activeFilterCount}）` : '')" :tooltip="foldSearch ? $t('apfUi.filter_b5f154') : undefined" @click="filterPanelOpen=!filterPanelOpen">
                <i v-if="foldSearch" class="pi pi-filter" aria-hidden="true"></i>
                <span v-else>{{ $t('apfUi.filter_b5f154') }}</span>
                <span v-if="activeFilterCount">{{ foldSearch ? activeFilterCount : `（${activeFilterCount}）` }}</span>
              </LibraryButton>
            </span>
              <div v-if="isLibraryTableView" class="apf-toolbar-actions">
                <template v-if="bulkSelectMode">
                  <span role="status" class="apf-toolbar-selection">{{ $t('apfUi.selected_value', { p0: (bulkSelection.size) }) }}</span>
                  <LibraryButton :aria-label="$t('apfUi.delete_selected_value', { p0: bulkSelection.size })" :tooltip="foldSearch ? $t('apfUi.delete') : undefined" :disabled="bulkDeleteBusy||bulkSelection.size===0||savingInline>0||Boolean(inlineSaveFailure)" @click="removeSelectedLibraryEntries">
                    <i v-if="compactToolbar && foldSearch" class="pi pi-trash" aria-hidden="true"></i>
                    <span v-if="compactToolbar && foldSearch" aria-hidden="true">{{ bulkSelection.size }}</span>
                    <span v-else>{{bulkDeleteBusy?$t('apfUi.deleting'):$t('apfUi.delete')}}</span>
                  </LibraryButton>
                  <LibraryButton :disabled="bulkDeleteBusy" @click="leaveBulkSelectMode">{{ $t('apfUi.done') }}</LibraryButton>
                </template>
                <template v-else>
                  <div v-if="isLibraryItemsView" class="apf-import-control" data-apf-popup="import">
                    <LibraryButton class="apf-import" :class="{ 'apf-toolbar-icon': foldViewTabs }" variant="primary" :disabled="!capabilities?.asset_import" :aria-label="$t('apfUi.import')" :aria-expanded="importMenuOpen" :tooltip="$t('apfUi.select_files_or_folder')" @click="importMenuOpen=!importMenuOpen">
                      <i class="icon-[lucide--upload] size-4" aria-hidden="true" /><span v-if="!foldViewTabs">{{ $t('apfUi.import') }}</span>
                    </LibraryButton>
                    <div v-if="importMenuOpen" class="apf-import-menu">
                      <LibraryButton @click="startImport('files')">{{ $t('apfUi.select_files') }}</LibraryButton>
                      <LibraryButton @click="startImport('folder')">{{ $t('apfUi.select_folder') }}</LibraryButton>
                    </div>
                  </div>
                  <LibraryButton v-if="props.native&&isLibraryItemsView&&!foldSecondaryActions" class="apf-equipment" @click="emit('manage-equipment')">{{ $t('apfUi.equipment_manager') }}</LibraryButton>
                  <LibraryMenu v-model:open="libraryMenuOpen" data-apf-popup="library-more" :items="libraryMenuItems" @close-auto-focus="preserveToolbarFocus('library-more', $event)" />
                </template>
              </div>
            <select
v-if="activeArea !== 'settings' && (store.section === 'projects' || store.section === 'equipment' || store.section === 'equipment-setups')"
              v-model="statusFilter" :disabled="setupDirty" :aria-label="$t('apfUi.status_filter')">
              <option value="active">{{ $t('apfUi.active') }}</option><option value="archived">{{ $t('apfUi.archived') }}</option><option value="all">{{ $t('apfUi.all') }}</option>
            </select>
            <LibrarySelect v-if="isEquipmentManagement&&store.section==='equipment'&&!foldSecondaryActions" v-model:open="equipmentCategoryOpen" class="apf-equipment-kind-filter" data-apf-popup="equipment-category" :modal="false" :searchable="false" density="compact" :model-value="equipmentKindFilter" :label="$t('apfUi.equipment_category')" :options="equipmentCategoryOptions" :disabled="managementFilterBlocked" @update:model-value="filterEquipmentKind" @close-auto-focus="preserveToolbarFocus('equipment-category', $event)" />
            <div v-if="activeArea==='settings' && store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets" class="apf-management-filter-control" data-apf-popup="project-filter">
              <button type="button" :disabled="managementFilterBlocked" :aria-expanded="managementFilterOpen" @click="managementFilterOpen?managementFilterOpen=false:openManagementFilter()">{{ $t('apfUi.filter_b5f154') }}<span v-if="managementFilterCount">（{{managementFilterCount}}）</span></button>
              <div v-if="managementFilterOpen" class="apf-management-filter-panel">
                <label v-if="store.section==='projects'">{{ $t('apfUi.target') }}<input v-model="projectTargetFilterDraft" :placeholder="$t('apfUi.filter_by_target')" /></label>
                <div><button type="button" @click="clearManagementFilter">{{ $t('apfUi.clear') }}</button><button type="button" :disabled="managementFilterBlocked" @click="applyManagementFilter">{{ $t('apfUi.apply') }}</button></div>
              </div>
            </div>
            <button v-if="!isEquipmentManagement&&(activeArea !== 'library' || viewingProjectAssets || viewingProjectDatasets)" type="button" :disabled="setupDirty" @click="refreshRecords"><i class="pi pi-refresh" aria-hidden="true"></i><span>{{ $t('apfUi.refresh') }}</span></button>
            <div v-if="isEquipmentManagement" class="apf-toolbar-actions">
              <template v-if="managementSelectMode">
                <span role="status" class="apf-toolbar-selection">{{ $t('apfUi.selected_value', { p0: (managementSelection.size) }) }}</span>
                <LibraryButton type="button" :aria-label="$t('apfUi.delete_selected_value', { p0: managementSelection.size })" :tooltip="foldSearch ? $t('apfUi.delete') : undefined" :disabled="!managementSelection.size||managementArchiveBusy||managementFilterBlocked" @click="requestSelectedEquipmentDelete">
                  <i v-if="foldSearch" class="pi pi-trash" aria-hidden="true"></i>
                  <span v-if="foldSearch" aria-hidden="true">{{ managementSelection.size }}</span>
                  <span v-else>{{ $t('apfUi.delete_selected_value', { p0: managementSelection.size }) }}</span>
                </LibraryButton>
                <LibraryButton type="button" :disabled="managementArchiveBusy" @click="leaveManagementSelectMode">{{ $t('apfUi.done') }}</LibraryButton>
              </template>
              <LibraryButton v-else-if="statusFilter!=='archived'" type="button" variant="primary" :class="{ 'apf-toolbar-icon': foldViewTabs }" :aria-label="newEquipmentLabel" :tooltip="foldViewTabs ? newEquipmentLabel : undefined" :disabled="managementFilterBlocked||loading" @click="store.section==='equipment-setups'?setupManager?.beginSetup(null):openCreate('equipment')">
                <i class="pi pi-plus" aria-hidden="true"></i><span v-if="!foldViewTabs">{{ newEquipmentLabel }}</span>
              </LibraryButton>
              <LibraryMenu v-model:open="equipmentMenuOpen" data-apf-popup="equipment-more" :class="{ 'apf-toolbar-active': foldSecondaryActions && store.section==='equipment' && equipmentKindFilter }" :aria-description="foldSecondaryActions && store.section==='equipment' ? equipmentCategoryOptions.find(option => option.value === equipmentKindFilter && equipmentKindFilter)?.name : undefined" :items="equipmentMenuItems" @close-auto-focus="preserveToolbarFocus('equipment-more', $event)" />
            </div>
            <template v-if="activeArea==='settings' && store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets">
              <template v-if="managementSelectMode">
                <button type="button" :disabled="!managementSelection.size||managementArchiveBusy" @click="requestSelectedManagementArchive">{{ $t('apfUi.move_to_trash') }}</button>
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
        <LibraryPage
v-if="activeArea === 'library'" :workspace="importWorkspace" :records-loading="loading" :filters="activeFilters"
          :filter-open="filterPanelOpen && isLibraryItemsView" :filter-anchor="filterButton"
          :calibration-library="libraryCategory === 'calibration' && !activeDataset" :dataset-id="activeDataset?.id" :dataset-version-id="activeDataset?.current_version_id" :dataset-name="activeDataset?.name" :selected-asset="selectedAssetDetails"
          @apply-filters="applyFilters" @close-filters="filterPanelOpen=false"
          @calibration-updated="calibrationUpdated" @calibration-dirty="calibrationDirty=$event" @calibration-created="calibrationCreated">
          <template #records><RecordsPanel /></template>
        </LibraryPage>
        <EquipmentSetupManager
v-else-if="store.section==='equipment-setups'" ref="setupManager"
          :workspace="importWorkspace" :selected-setup="selectedEquipmentSetup" :records-loading="loading" :view-key="setupViewKey" :change-token="managementChangeToken"
          @dirty="setupDirty=$event" @saving="setupSaving=$event" @saved="setupSaved" @delete="requestEquipmentDeleteSelection">
          <template #records><RecordsPanel /></template>
        </EquipmentSetupManager>
        <SettingsPage
v-else :workspace-id="importWorkspace" :reference-busy="projectReferences.pending.value" :project-mode="settingsProjectMode" :choosing="choosingProjectVersion" :details="settingsRecordDetails"
          @reference-action="projectReferenceAction">
          <template #records><RecordsPanel /></template>
          <template #asset-details>
            <AssetDetails v-if="assetDetails" :key="assetDetails.recordId" v-bind="assetDetails" @cancel-field="cancelRecordField" />
          </template>
          <template #dataset-details>
            <DatasetDetails v-if="datasetDetails" :key="datasetDetails.recordId" v-bind="datasetDetails" @cancel-field="cancelRecordField" />
          </template>
          <template #project-details>
            <ProjectDetails
v-if="projectDetails" :key="projectDetails.project.id" :project="projectDetails.project"
              :blocked="managementArchiveBusy||dirty||savingInline>0" :save-name="projectDetails.saveName" :save-target="projectDetails.saveTarget" :save-notes="projectDetails.saveNotes"
              @action="projectDetailsAction" @cancel-field="cancelProjectField" />
          </template>
          <template #editor>
        <RecordEditorForm
v-if="recordEditor" v-model="recordEditor" :saving="saving" :saving-inline="savingInline"
          :error="error?errorText(error):undefined" :inline-error="inlineSaveFailure" :save-field="saveEditorInline"
          @submit="saveEditor" @close="closeEditor" @cancel-field="clearInlineSaveFailure(editorInlineFailureKey($event))" />
          </template>
        </SettingsPage>
    </main>
      <component :is="props.controls.mediaViewer" v-if="connectionReady && props.controls?.mediaViewer && mediaPreview" :request="mediaPreview" @close="closePhotoPreview" />
      <PhotoPreviewDialog v-else :workspace-id="importWorkspace" :photo="photoPreview" @close="closePhotoPreview" @updated="refreshPhotoThumbnails" />
      <LibraryTrashDialog :open="trashOpen" :workspace-id="importWorkspace" @close="trashOpen=false" />
      <EquipmentDeleteDialog :workspace-id="importWorkspace" :view-key="setupViewKey" :items="equipmentDeleteItems" @close="equipmentDeleteItems=undefined" @deleted="equipmentDeleted" />
      <div v-if="bulkConfirmOpen" class="apf-trash-confirm-backdrop" role="presentation" @click.self="bulkConfirmOpen=false">
        <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="bulk-trash-confirm-title">
          <h2 id="bulk-trash-confirm-title">{{ $t('apfUi.confirm_move_to_trash') }}</h2>
          <p>{{ $t('apfUi.move_value_library_entries_to_trash_original_files_are_retained_and_en', { p0: (bulkConfirmRows.length) }) }}</p>
          <ul><li v-for="review in bulkConfirmRows" :key="review.request.entry_type+':'+review.request.id">{{review.title}}<span v-if="review.kind==='dataset'">{{ $t('apfUi.image_group_value_photos', { p0: review.memberCount }) }}</span><span v-else>{{ $t('apfUi.photo_95be49') }}</span></li></ul>
          <button type="button" @click="bulkConfirmOpen=false">{{ $t('apfUi.cancel') }}</button><button type="button" @click="confirmRemoveSelectedLibraryEntries">{{ $t('apfUi.move_to_trash') }}</button>
        </section>
      </div>
      <div v-if="pendingManagementArchive" class="apf-trash-confirm-backdrop" role="presentation" @click.self="pendingManagementArchive=undefined">
        <section class="apf-trash-confirm" role="alertdialog" aria-modal="true" aria-labelledby="management-archive-title">
          <h2 id="management-archive-title">{{ $t('apfUi.move_to_trash') }}</h2>
          <p v-if="pendingManagementArchive.kind==='selection'">{{ $t('apfUi.move_value_settings_to_trash_linked_assets_and_equipment_snapshots_are', { p0: pendingManagementArchive.entries.length }) }}</p>
          <p v-else>{{ $t('apfUi.move_value_to_trash_records_and_linked_assets_are_retained', { p0: (pendingManagementArchive.entry.reference.name) }) }}</p>
          <button type="button" :disabled="managementArchiveBusy" @click="pendingManagementArchive=undefined">{{ $t('apfUi.cancel') }}</button>
          <button type="button" :disabled="managementArchiveBusy" @click="confirmManagementArchive">{{managementArchiveBusy?$t('apfUi.processing'):$t('apfUi.confirm_move_to_trash')}}</button>
        </section>
      </div>
      <LocalImportPicker :open="!!localPickerMode" :mode="localPickerMode??'files'" @close="localPickerMode=undefined" @selected="localFilesSelected" />
      <ImportIssueDialog :workspace-id="importWorkspace" :issue="importIssue" @close="importIssue=undefined" @retried="importSubmitted" />
      <ImportDialog :workspace-id="importWorkspace" :open="importDialogOpen" :files="importFiles" :create-dataset="importCreatesDataset" :dataset-name="importDatasetName" @close="importDialogOpen=false" @submitted="importSubmitted" />
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
.apf-table-scroll.simple .apf-column-name>.apf-group-total{display:block;color:var(--descrip-text,#999);font-size:12px;line-height:18px}
.apf-assets-table .apf-column-calibration{min-width:112px;max-width:180px;vertical-align:middle}
.apf-table-scroll.simple .apf-assets-table:has(.apf-column-calibration){min-width:640px}
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
.apf-heading, .apf-toolbar, .apf-error, .apf-state, .apf-disabled, .apf-records, .apf-pagination, .apf-details { margin-left:10px; margin-right:10px; }
.apf-heading { display:flex; flex:none; flex-wrap:wrap; align-items:center; gap:8px; min-width:0; }
.apf-heading h1 { flex:0 0 auto; margin:4px 0; color:var(--input-text,#ddd); font-size:16px; font-weight:600; line-height:1.25; white-space:nowrap; }
.apf-toolbar-actions { display:flex; flex:0 1 auto; flex-wrap:wrap; min-width:0; align-items:center; gap:6px; margin-inline-start:auto; }
.apf-toolbar-search { flex:1 1 145px; min-width:0; }
.apf-compact-toolbar { position:relative; flex-wrap:nowrap; gap:6px; white-space:nowrap; }
.apf-compact-toolbar .apf-toolbar-actions { flex:none; flex-wrap:nowrap; }
.apf-compact-toolbar .apf-toolbar-search { flex:1 1 160px; max-width:220px; }
.apf-compact-toolbar .apf-library-categories,
.apf-compact-toolbar .apf-management-tabs { flex:none; flex-wrap:nowrap; gap:4px; padding:0; border:0; }
.apf-compact-toolbar .apf-toolbar-view { flex:0 1 152px; min-width:0; max-width:152px; }
.apf-workspace .apf-compact-toolbar .apf-search { box-sizing:border-box; min-width:0; height:32px; }
.apf-toolbar-icons .apf-toolbar-search { flex:none; }
.apf-workspace .apf-compact-toolbar .apf-toolbar-icon { width:32px; min-width:32px; padding-inline:0; }
.apf-workspace .apf-compact-toolbar .apf-toolbar-actions > button,
.apf-workspace .apf-compact-toolbar .apf-import,
.apf-workspace .apf-compact-toolbar [data-apf-popup="library-filter"] > button,
.apf-workspace .apf-compact-toolbar .apf-toolbar-icon { height:32px; min-height:32px; }
.apf-toolbar-icons .apf-toolbar-selection { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
.apf-toolbar-active { position:relative; }
.apf-toolbar-active::after { content:''; position:absolute; inset-block-start:3px; inset-inline-end:3px; width:5px; height:5px; border-radius:50%; background:var(--color-primary-background); pointer-events:none; }
.apf-workspace .apf-search-popup { position:absolute; z-index:9; inset-block-start:calc(100% + 4px); inset-inline-start:0; width:min(220px, 100%); box-shadow:0 6px 18px #0008; }
.apf-trash-confirm-backdrop { position:fixed; inset:0; z-index:30; display:grid; place-items:center; padding:16px; background:#000a; }
.apf-trash-confirm { max-width:560px; max-height:80vh; overflow:auto; padding:18px; border:1px solid var(--border-color,#555); border-radius:10px; background:var(--comfy-menu-bg,#292929); box-shadow:0 8px 40px #0009; }
.apf-trash-confirm h2 { margin:0 0 10px; font-size:16px; }
.apf-trash-confirm li { margin:4px 0; }
.apf-trash-confirm button+button { margin-left:8px; }
.apf-import-control { position:relative; }
.apf-import-menu { position:absolute; z-index:8; top:calc(100% + 4px); inset-inline-end:0; display:flex; min-width:120px; flex-direction:column; gap:4px; padding:5px; border:1px solid var(--border-color,#555); border-radius:7px; background:var(--comfy-menu-bg,#272727); box-shadow:0 6px 18px #0008; }
.apf-workspace .apf-import-menu button { justify-content:flex-start; }
.apf-import { display:flex; align-items:center; }
.apf-management-tabs { display:flex; }
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
.apf-workspace .apf-library-workspace .apf-toolbar-actions button[data-variant=primary]{background:var(--color-primary-background);color:var(--color-base-foreground)}
</style>

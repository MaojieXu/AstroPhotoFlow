import { computed, nextTick, ref, toValue } from 'vue'
import type { MaybeRefOrGetter, Ref } from 'vue'
import type { DatasetOut } from '../../../generated/api/types.gen'
import type { ApiClientError as ApiError } from '../api/client'
import { ApiClientError } from '../api/client'
import { uiT } from '../../../core/i18n'
import type { WorkspaceRecord } from '../workspace/recordTypes'
import { isDatasetRecord } from '../workspace/recordTypes'
import type { WorkspacePageSize } from '../workspace/store'
import { isLibrarySummary } from '../library/summary'
import {
  datasetViewFromSummary,
  datasetViewFromAcknowledgement,
  type DatasetViewIdentity
} from './viewIdentity'

interface LibraryNavigation {
  query: string
  offset: number
  pageSize: WorkspacePageSize
}
interface DatasetViewOptions {
  navigation: LibraryNavigation
  sort: Ref<{ by: string; order: 'asc' | 'desc' }>
  mode: Ref<'simple' | 'detail'>
  filterOpen: Ref<boolean>
  records: Ref<WorkspaceRecord[]>
  libraryActive: MaybeRefOrGetter<boolean>
  dirty: MaybeRefOrGetter<boolean>
  calibrationDirty: MaybeRefOrGetter<boolean>
  waitForInlineSave: () => Promise<boolean>
  error: Ref<ApiError | undefined>
}

/** Owns the fixed group identity and restoration of the outer library view. */
export function useDatasetView(options: DatasetViewOptions) {
  const {
    navigation: store,
    sort: librarySort,
    mode: libraryViewMode,
    filterOpen: filterPanelOpen,
    records: rows,
    waitForInlineSave,
    error
  } = options
  const isLibraryItemsView = computed(() => toValue(options.libraryActive))
  const dirty = computed(() => toValue(options.dirty))
  const calibrationDirty = computed(() => toValue(options.calibrationDirty))
  const activeDataset = ref<DatasetViewIdentity>()
  const outerLibraryState = ref<
    LibraryNavigation & {
      sort: { by: string; order: 'asc' | 'desc' }
      view: 'simple' | 'detail'
    }
  >()
  const restoringOuterLibraryState = ref(false)

  async function openDataset(row: WorkspaceRecord) {
    const context = {
      query: store.query,
      offset: store.offset,
      pageSize: store.pageSize,
      sort: { ...librarySort.value },
      view: libraryViewMode.value
    }
    if (!(await waitForInlineSave())) return
    if (
      !isLibraryItemsView.value ||
      store.query !== context.query ||
      store.offset !== context.offset ||
      store.pageSize !== context.pageSize ||
      librarySort.value.by !== context.sort.by ||
      librarySort.value.order !== context.sort.order ||
      libraryViewMode.value !== context.view
    )
      return
    const currentRow = rows.value.find(
      (item) => item.id === row.id && isDatasetRecord(item)
    )
    if (
      !currentRow ||
      !isLibrarySummary(currentRow) ||
      currentRow.entry_type !== 'dataset'
    )
      return
    const identity = datasetViewFromSummary(currentRow)
    if (!identity) {
      error.value = new ApiClientError(
        'Dataset has no fixed version to open',
        'contract'
      )
      return
    }
    outerLibraryState.value = {
      query: store.query,
      offset: store.offset,
      pageSize: store.pageSize,
      sort: { ...librarySort.value },
      view: libraryViewMode.value
    }
    activeDataset.value = identity
    store.query = ''
    store.offset = 0
    store.pageSize = 50
    librarySort.value = { by: 'member_position', order: 'asc' }
    libraryViewMode.value = 'detail'
    filterPanelOpen.value = false
  }

  function leaveDatasetContext() {
    if (!activeDataset.value) return
    activeDataset.value = undefined
    if (outerLibraryState.value) {
      store.query = outerLibraryState.value.query
      store.offset = outerLibraryState.value.offset
      store.pageSize = outerLibraryState.value.pageSize
      librarySort.value = outerLibraryState.value.sort
      libraryViewMode.value = outerLibraryState.value.view
    } else if (librarySort.value.by === 'member_position') {
      librarySort.value = { by: 'created_at', order: 'desc' }
    }
    outerLibraryState.value = undefined
    filterPanelOpen.value = false
    error.value = undefined
  }

  async function closeDataset() {
    if (
      calibrationDirty.value &&
      !window.confirm(
        uiT(
          'apfUi.the_group_description_or_calibration_bindings_have_unsaved_changes_dis'
        )
      )
    )
      return
    if (
      dirty.value &&
      !window.confirm(
        uiT('apfUi.this_form_has_unsaved_changes_discard_them_and_go_back')
      )
    )
      return
    if (!(await waitForInlineSave())) return
    activeDataset.value = undefined
    if (outerLibraryState.value) {
      restoringOuterLibraryState.value = true
      store.query = outerLibraryState.value.query
      store.offset = outerLibraryState.value.offset
      store.pageSize = outerLibraryState.value.pageSize
      librarySort.value = outerLibraryState.value.sort
      libraryViewMode.value = outerLibraryState.value.view
      await nextTick()
      restoringOuterLibraryState.value = false
    }
    outerLibraryState.value = undefined
  }

  async function calibrationUpdated(dataset: DatasetOut) {
    if (activeDataset.value?.id === dataset.id) {
      const identity = datasetViewFromAcknowledgement(dataset)
      if (!identity) {
        error.value = new ApiClientError(
          'Acknowledged dataset has no fixed version',
          'contract'
        )
        return
      }
      activeDataset.value = identity
    }
  }

  return {
    activeDataset,
    restoringOuterLibraryState,
    openDataset,
    closeDataset,
    leaveDatasetContext,
    calibrationUpdated
  }
}

import { computed, ref, toValue } from 'vue'
import type { MaybeRefOrGetter, Ref } from 'vue'
import type { LibraryItemPage } from '../../../generated/api/types.gen'
import { zRemoveLibraryEntriesApiV1LibraryItemsDeleteBody } from '../../../generated/api/zod.gen'
import { validatedInput } from '../../../core/api/input'
import { uiT } from '../../../core/i18n'
import type { ApiClientError } from '../api/client'
import { libraryError as presentError } from '../library/errors'
import {
  reviewLibraryRemoval,
  type LibraryRemovalReview
} from './librarySelection'
import { useRemoveLibraryEntries } from './mutations'

interface LibraryRemovalOptions {
  workspaceId: MaybeRefOrGetter<string>
  enabled: MaybeRefOrGetter<boolean>
  items: MaybeRefOrGetter<readonly LibraryItemPage['items'][number][]>
  selection: Ref<Set<string>>
  contextKey: () => string | undefined
  error: Ref<ApiClientError | undefined>
  onRemoved: (count: number) => void
}

/** Review and submit a finite revision-checked removal, then acknowledge only its origin view. */
export function useLibraryRemoval(options: LibraryRemovalOptions) {
  const libraryRemoval = useRemoveLibraryEntries()
  const bulkDeleteBusy = ref(false)
  const libraryRemovalView = ref<string>()
  const removalBlocksCurrentView = computed(
    () =>
      bulkDeleteBusy.value && libraryRemovalView.value === options.contextKey()
  )
  const bulkDeleteNotice = ref('')
  const bulkConfirmOpen = ref(false)
  const bulkConfirmRows = ref<LibraryRemovalReview[]>([])
  const { selection: bulkSelection, error } = options

  function removeSelectedLibraryEntries() {
    if (
      !toValue(options.enabled) ||
      bulkDeleteBusy.value ||
      !bulkSelection.value.size
    )
      return
    const selectedRows = toValue(options.items).filter((row) =>
      bulkSelection.value.has(row.entry_type + ':' + row.id)
    )
    if (!selectedRows.length) return
    bulkConfirmRows.value = selectedRows.map(reviewLibraryRemoval)
    bulkConfirmOpen.value = true
  }

  async function confirmRemoveSelectedLibraryEntries() {
    const origin = options.contextKey()
    if (bulkDeleteBusy.value || !bulkConfirmRows.value.length) return
    const items = bulkConfirmRows.value.map((review) => review.request)
    if (!items.length) return
    bulkConfirmOpen.value = false
    libraryRemovalView.value = origin
    bulkDeleteBusy.value = true
    bulkDeleteNotice.value = ''
    error.value = undefined
    try {
      const result = await libraryRemoval.mutateAsync({
        workspaceId: toValue(options.workspaceId),
        body: validatedInput(zRemoveLibraryEntriesApiV1LibraryItemsDeleteBody, {
          items
        })
      })
      if (origin !== options.contextKey()) return
      options.onRemoved(result.removed_count)
      bulkDeleteNotice.value =
        uiT('apfUi.removed') +
        result.removed_count +
        uiT('apfUi.library_entries_original_data_retained')
      bulkConfirmRows.value = []
      bulkDeleteBusy.value = false
    } catch (cause) {
      if (origin === options.contextKey()) error.value = presentError(cause)
    } finally {
      bulkDeleteBusy.value = false
      libraryRemovalView.value = undefined
    }
  }

  return {
    bulkDeleteBusy,
    removalBlocksCurrentView,
    bulkDeleteNotice,
    bulkConfirmOpen,
    bulkConfirmRows,
    removeSelectedLibraryEntries,
    confirmRemoveSelectedLibraryEntries
  }
}

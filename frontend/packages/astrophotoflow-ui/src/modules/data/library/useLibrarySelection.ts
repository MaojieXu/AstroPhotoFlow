import { computed, ref, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { LibraryItemPage } from '../../../generated/api/types.gen'

/** Selection identities belong to the visible library, never to mutable row objects. */
export function useLibrarySelection(
  items: MaybeRefOrGetter<readonly LibraryItemPage['items'][number][]>
) {
  const bulkSelectMode = ref(false)
  const bulkSelection = ref(new Set<string>())
  const pageSelectionKeys = computed(() => toValue(items).map(bulkKey))
  const pageAllSelected = computed(
    () =>
      pageSelectionKeys.value.length > 0 &&
      pageSelectionKeys.value.every((key) => bulkSelection.value.has(key))
  )
  const pagePartiallySelected = computed(
    () =>
      pageSelectionKeys.value.some((key) => bulkSelection.value.has(key)) &&
      !pageAllSelected.value
  )

  function bulkKey(row: LibraryItemPage['items'][number]) {
    return row.entry_type + ':' + row.id
  }

  function clearBulkSelection() {
    bulkSelection.value = new Set()
  }

  function toggleBulkSelection(row: LibraryItemPage['items'][number]) {
    const key = bulkKey(row)
    const next = new Set(bulkSelection.value)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    bulkSelection.value = next
  }

  function togglePageSelection(checked: boolean) {
    const next = new Set(bulkSelection.value)
    for (const key of pageSelectionKeys.value) {
      if (checked) next.add(key)
      else next.delete(key)
    }
    bulkSelection.value = next
  }

  function enterSelection() {
    clearBulkSelection()
    bulkSelectMode.value = true
  }
  function leaveSelection() {
    clearBulkSelection()
    bulkSelectMode.value = false
  }
  return {
    bulkSelectMode,
    bulkSelection,
    bulkKey,
    clearBulkSelection,
    toggleBulkSelection,
    togglePageSelection,
    pageAllSelected,
    pagePartiallySelected,
    enterSelection,
    leaveSelection
  }
}

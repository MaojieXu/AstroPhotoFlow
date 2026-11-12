import { computed, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

/** UI parameters, not a second copy of server records. */
export interface ListViewInput {
  workspaceId: string
  active: boolean
  pageSize: number | 'all'
  offset: number
  search: string
}

/** Freeze parameters while editing, never carry them across resource identities. */
export function useStableQueryInput<T>(
  desired: MaybeRefOrGetter<T | undefined>,
  paused: MaybeRefOrGetter<boolean>,
  identity: (request: T) => string
) {
  const applied = shallowRef<T | undefined>(toValue(desired))
  watch([() => toValue(desired), () => toValue(paused)], ([next, hold]) => {
    if (
      !next ||
      !applied.value ||
      identity(next) !== identity(applied.value) ||
      !hold
    )
      applied.value = next
  })
  return computed(() => applied.value)
}

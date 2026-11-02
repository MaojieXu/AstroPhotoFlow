import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { trashApi } from '../api'

export type TrashPageRequest = { workspaceId: string; query: Parameters<typeof trashApi.list>[0] }

export function trashQueryKey(workspaceId: string) {
  return [...workspaceQueryKey(workspaceId), 'trash'] as const
}

export function useTrashQuery(request: MaybeRefOrGetter<TrashPageRequest | undefined>, paused: MaybeRefOrGetter<boolean>) {
  const client = useQueryClient()
  const queryKey = computed(() => {
    const current = toValue(request)
    return current ? [...trashQueryKey(current.workspaceId), current.query] as const : ['trash-idle'] as const
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: ({ signal }) => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('Trash query requires a workspace identity')
      return trashApi.list(current.query, signal)
    },
    // A reopened destructive-action dialog must refresh before enabling selection.
    staleTime: 0,
    refetchInterval: 10_000
  })
  watch(() => toValue(paused), value => {
    if (value) void client.cancelQueries({ queryKey: queryKey.value })
  }, { flush: 'sync' })
  return query
}

import { readPages } from './pagination'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { libraryApi, catalogApi } from '../api'
import type { LibraryQuery } from './client'
import type { LibraryItemPage } from '../../../generated/api/types.gen'
import { zLibraryItemPage } from '../../../generated/api/zod.gen'

export function libraryQueryKey(workspaceId: string) {
  return [...workspaceQueryKey(workspaceId), 'library'] as const
}

export function readLibraryChanges(cache: QueryClient, workspaceId: string) {
  return cache.fetchQuery({
    queryKey: [...libraryQueryKey(workspaceId), 'change-state'],
    queryFn: ({ signal }) => libraryApi.changeState(signal),
    staleTime: 500
  })
}

export function useLibraryBootstrap(connectionEpoch: MaybeRefOrGetter<number> = 0, connected: MaybeRefOrGetter<boolean> = true) {
  const cache = useQueryClient()
  const queryKey = computed(()=>['library-bootstrap',toValue(connectionEpoch)] as const)
  const query = useQuery({
    queryKey,
    enabled:computed(()=>toValue(connected)),
    staleTime:0,
    refetchOnMount:'always',
    queryFn:async({signal})=>{
      const [health,capabilities]=await Promise.all([catalogApi.health(signal),catalogApi.capabilities(signal)])
      signal.throwIfAborted()
      return {health,capabilities}
    }
  })
  watch(()=>toValue(connected),available=>{
    if(!available)void cache.cancelQueries({queryKey:queryKey.value})
  },{flush:'sync'})
  return query
}

export function useLibraryFilterOptions(workspace: MaybeRefOrGetter<string>) {
  const cache = useQueryClient()
  let checkpoint: string | undefined
  const connectionReady = useQueryAvailability()
  return useQuery({
    queryKey: computed(() => [...libraryQueryKey(toValue(workspace)), 'filters'] as const),
    enabled: computed(() => connectionReady.value && Boolean(toValue(workspace))),
    queryFn: async ({ signal, queryKey }) => {
      const change = await readLibraryChanges(cache, toValue(workspace))
      signal.throwIfAborted()
      const previous = cache.getQueryData<Awaited<ReturnType<typeof libraryApi.filters>>>(queryKey)
      if (previous && !cache.getQueryState(queryKey)?.isInvalidated && checkpoint === change.revision_token) return previous
      const filters = await libraryApi.filters(signal)
      checkpoint = change.revision_token
      return filters
    },
    refetchInterval: 10_000
  })
}

export interface LibraryPageRequest {
  workspaceId: string
  query: LibraryQuery & { limit: number; offset: number }
  all: boolean
  empty: boolean
}

export function useLibraryQuery(
  request: MaybeRefOrGetter<LibraryPageRequest | undefined>,
  paused: MaybeRefOrGetter<boolean>
) {
  const client = useQueryClient()
  let checkpoint: { key: string; token: string } | undefined
  const queryKey = computed(() => {
    const current = toValue(request)
    return current ? [...libraryQueryKey(current.workspaceId), 'items', current.query, current.all, current.empty] as const : ['library-items-idle'] as const
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: async ({ signal, queryKey: activeKey }): Promise<LibraryItemPage> => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('A library request requires a workspace identity')
      if (current.empty) return { items: [], total: 0, limit: current.query.limit, offset: current.query.offset }
      const change = await readLibraryChanges(client, current.workspaceId)
      signal.throwIfAborted()
      const identity = JSON.stringify(activeKey), token = change.revision_token + ':' + change.thumbnail_token
      const previous = client.getQueryData<LibraryItemPage>(activeKey)
      if (previous && !client.getQueryState(activeKey)?.isInvalidated && checkpoint?.key === identity && checkpoint.token === token) return previous
      const read = (offset: number) => libraryApi.search({ ...current.query, offset }, signal)
      const page = await readPages(offset => read(offset ?? current.query.offset ?? 0), current.all, signal)
      signal.throwIfAborted()
      checkpoint = { key: identity, token }
      return page
    },
    refetchInterval: 10_000
  })
  watch(() => toValue(paused), value => {
    if (value) void client.cancelQueries({ queryKey: queryKey.value })
  }, { flush: 'sync' })

  function updateItems(items: unknown[]) {
    const validated = zLibraryItemPage.shape.items.parse(items)
    client.setQueryData<LibraryItemPage>(queryKey.value, previous => previous && ({ ...previous, items: validated }))
    void client.invalidateQueries({queryKey:queryKey.value})
  }
  function updateTotal(total: number) {
    client.setQueryData<LibraryItemPage>(queryKey.value, previous => previous && ({ ...previous, total }))
    void client.invalidateQueries({queryKey:queryKey.value})
  }
  async function refresh() {
    checkpoint = undefined
    const current=toValue(request)
    if(!current)return
    await client.invalidateQueries({queryKey:libraryQueryKey(current.workspaceId),refetchType:'none'})
    return query.refetch({cancelRefetch:false})
  }
  return { ...query, refresh, updateItems, updateTotal }
}

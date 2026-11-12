import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { zAssetPage } from '../../../generated/api/zod.gen'
import { catalogApi } from '../api'
import { readPages } from './pagination'
import { datasetChoiceToRecord } from './materialRecords'

export type LibrarySelectionRequest = { workspaceId: string; all: boolean } & (
  | { kind: 'assets'; query: Parameters<typeof catalogApi.assets>[0] }
  | { kind: 'datasets'; query: Parameters<typeof catalogApi.datasets>[0] }
)
// A UI discriminator is removed before canonical dataset DTOs enter the cache.
const datasetChoiceItems = datasetChoiceToRecord.array()

export function useLibrarySelectionQuery(request: MaybeRefOrGetter<LibrarySelectionRequest | undefined>, paused: MaybeRefOrGetter<boolean>, refetchInterval: number | false = 10_000) {
  const client = useQueryClient()
  const queryKey = computed(() => {
    const current = toValue(request)
    return current ? [...workspaceQueryKey(current.workspaceId), 'library-selection', current] as const : ['library-selection-idle'] as const
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('Library selection requires a workspace identity')
      switch (current.kind) {
        case 'assets': return { kind: current.kind, page: await readPages(offset => catalogApi.assets({ ...current.query, offset: offset ?? current.query.offset }, signal), current.all, signal) }
        case 'datasets': return { kind: current.kind, page: await readPages(offset => catalogApi.datasets({ ...current.query, offset: offset ?? current.query.offset }, signal), current.all, signal) }
      }
    },
    refetchInterval
  })
  watch(() => toValue(paused), value => { if (value) void client.cancelQueries({ queryKey: queryKey.value }) }, { flush: 'sync' })
  type Result = NonNullable<typeof query.data.value>
  const rows = computed(() => {
    const current = query.data.value
    return current?.kind === 'datasets' ? current.page.items.map(dataset => ({ ...dataset, entry_type: 'dataset' as const })) : current?.page.items ?? []
  })
  function updateItems(items: unknown[]) {
    client.setQueryData<Result>(queryKey.value, previous => {
      if (!previous) return previous
      return previous.kind === 'assets'
        ? { ...previous, page: { ...previous.page, items: zAssetPage.shape.items.parse(items) } }
        : { ...previous, page: { ...previous.page, items: datasetChoiceItems.parse(items) } }
    })
    void client.invalidateQueries({queryKey:queryKey.value})
  }
  function updateTotal(total: number) {
    client.setQueryData<Result>(queryKey.value, previous => {
      if (!previous) return previous
      switch (previous.kind) {
        case 'assets': return { ...previous, page: { ...previous.page, total } }
        case 'datasets': return { ...previous, page: { ...previous.page, total } }
      }
    })
    void client.invalidateQueries({queryKey:queryKey.value})
  }
  async function refresh() {
    const current=toValue(request)
    if(!current)return
    await client.invalidateQueries({queryKey:[...workspaceQueryKey(current.workspaceId),'library-selection'],refetchType:'none'})
    return query.refetch({cancelRefetch:false})
  }
  return { ...query, refresh, rows, updateItems, updateTotal }
}

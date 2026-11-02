import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { zProjectPage, zProjectAssetReferencePage, zProjectDatasetReferencePage } from '../../../generated/api/zod.gen'
import { catalogApi } from '../api'
import { readPages } from '../library/pagination'

type RequestBody =
  | { kind: 'projects'; query: Parameters<typeof catalogApi.projects>[0] }
  | { kind: 'assets'; projectId: string; query: Parameters<typeof catalogApi.projectAssets>[1] }
  | { kind: 'datasets'; projectId: string; query: Parameters<typeof catalogApi.projectDatasets>[1] }
export type ProjectRecordsRequest = { workspaceId: string; all: boolean } & RequestBody
export const projectQueryKey = (workspaceId: string) => [...workspaceQueryKey(workspaceId), 'projects'] as const

export function useProjectRecordsQuery(request: MaybeRefOrGetter<ProjectRecordsRequest | undefined>, paused: MaybeRefOrGetter<boolean>) {
  const client = useQueryClient()
  const queryKey = computed(() => {
    const current = toValue(request)
    return current ? [...projectQueryKey(current.workspaceId), current] as const : ['projects-idle'] as const
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('Project reads require a workspace identity')
      switch (current.kind) {
        case 'projects': return { kind: current.kind, page: await readPages(offset => catalogApi.projects({ ...current.query, offset: offset ?? current.query.offset }, signal), current.all, signal) }
        case 'assets': return { kind: current.kind, page: await readPages(offset => catalogApi.projectAssets(current.projectId, { ...current.query, offset: offset ?? current.query.offset }, signal), current.all, signal) }
        case 'datasets': return { kind: current.kind, page: await readPages(offset => catalogApi.projectDatasets(current.projectId, { ...current.query, offset: offset ?? current.query.offset }, signal), current.all, signal) }
      }
    },
    refetchInterval: 10_000
  })
  watch(() => toValue(paused), value => { if (value) void client.cancelQueries({ queryKey: queryKey.value }) }, { flush: 'sync' })
  type Result = NonNullable<typeof query.data.value>
  function updateItems(items: unknown[]) {
    client.setQueryData<Result>(queryKey.value, previous => {
      if (!previous) return previous
      switch (previous.kind) {
        case 'projects': return { ...previous, page: { ...previous.page, items: zProjectPage.shape.items.parse(items) } }
        case 'assets': return { ...previous, page: { ...previous.page, items: zProjectAssetReferencePage.shape.items.parse(items) } }
        case 'datasets': return { ...previous, page: { ...previous.page, items: zProjectDatasetReferencePage.shape.items.parse(items) } }
      }
    })
    void client.invalidateQueries({queryKey:queryKey.value})
  }
  function updateTotal(total: number) {
    client.setQueryData<Result>(queryKey.value, previous => {
      if (!previous) return previous
      switch (previous.kind) {
        case 'projects': return { ...previous, page: { ...previous.page, total } }
        case 'assets': return { ...previous, page: { ...previous.page, total } }
        case 'datasets': return { ...previous, page: { ...previous.page, total } }
      }
    })
    void client.invalidateQueries({queryKey:queryKey.value})
  }
  async function refresh() {
    const current=toValue(request)
    if(!current)return
    await client.invalidateQueries({queryKey:projectQueryKey(current.workspaceId),refetchType:'none'})
    return query.refetch({cancelRefetch:false})
  }
  return { ...query, refresh, rows: computed(() => query.data.value?.page.items ?? []), updateItems, updateTotal }
}

import { readPages } from '../library/pagination'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

import type { DatasetMemberSummaryPage, DatasetMemberSummary } from '../../../generated/api/types.gen'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { libraryApi } from '../api'
import type { MemberQuery } from '../library/client'
import { libraryQueryKey, readLibraryChanges } from '../library/queries'

export interface DatasetMembersRequest {
  workspaceId: string
  datasetId: string
  versionId: string
  query: MemberQuery
  all: boolean
}

export function useDatasetMembersQuery(
  request: MaybeRefOrGetter<DatasetMembersRequest | undefined>,
  paused: MaybeRefOrGetter<boolean>
) {
  const client = useQueryClient()
  let checkpoint: { key: string; token: string } | undefined
  const queryKey = computed(() => {
    const current = toValue(request)
    return current
      ? [...workspaceQueryKey(current.workspaceId), 'datasets', current.datasetId, 'versions', current.versionId, 'members', current.query, current.all] as const
      : ['dataset-members-idle'] as const
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: async ({ signal, queryKey: activeKey }): Promise<DatasetMemberSummaryPage> => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('A dataset member request requires a workspace identity')
      const change = await readLibraryChanges(client, current.workspaceId)
      signal.throwIfAborted()
      const identity = JSON.stringify(activeKey), token = change.revision_token + ':' + change.thumbnail_token
      const previous = client.getQueryData<DatasetMemberSummaryPage>(activeKey)
      if (previous && !client.getQueryState(activeKey)?.isInvalidated && checkpoint?.key === identity && checkpoint.token === token) return previous
      const read = (offset: number) => libraryApi.memberSummaries(current.datasetId, current.versionId, { ...current.query, offset }, signal)
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

  const rows = computed(() => query.data.value?.items ?? [])

  function updateRows(updates: readonly DatasetMemberSummary[]) {
    const current = toValue(request)
    if (!current) return
    const byPosition = new Map(updates.map(row => [row.member_position, row]))
    client.setQueryData<DatasetMemberSummaryPage>(queryKey.value, previous => previous && ({
      ...previous,
      items: previous.items.map(member => {
        return byPosition.get(member.member_position) ?? member
      })
    }))
    void client.invalidateQueries({queryKey:queryKey.value})
    void client.invalidateQueries({ queryKey: libraryQueryKey(current.workspaceId) })
  }

  async function refresh() {
    checkpoint = undefined
    const current=toValue(request)
    if(!current)return
    await client.invalidateQueries({queryKey:[...workspaceQueryKey(current.workspaceId),'datasets',current.datasetId,'versions',current.versionId,'members'],refetchType:'none'})
    return query.refetch({cancelRefetch:false})
  }
  return { ...query, refresh, rows, updateRows }
}

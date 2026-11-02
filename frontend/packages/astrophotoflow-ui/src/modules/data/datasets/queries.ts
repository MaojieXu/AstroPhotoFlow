import { readPages } from '../library/pagination'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

import type { DatasetMemberPage } from '../../../generated/api/types.gen'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { libraryApi } from '../api'
import type { MemberQuery } from '../library/client'
import { libraryQueryKey } from '../library/queries'

export interface DatasetMembersRequest {
  workspaceId: string
  datasetId: string
  versionId: string
  query: MemberQuery
  all: boolean
}

type Member = DatasetMemberPage['items'][number]

export function useDatasetMembersQuery(
  request: MaybeRefOrGetter<DatasetMembersRequest | undefined>,
  paused: MaybeRefOrGetter<boolean>
) {
  const client = useQueryClient()
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
    queryFn: async ({ signal }): Promise<DatasetMemberPage> => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('A dataset member request requires a workspace identity')
      const read = (offset: number) => libraryApi.members(current.datasetId, current.versionId, { ...current.query, offset }, signal)
      return readPages(offset => read(offset ?? current.query.offset ?? 0), current.all, signal)
    },
    refetchInterval: 10_000
  })

  watch(() => toValue(paused), value => {
    if (value) void client.cancelQueries({ queryKey: queryKey.value })
  }, { flush: 'sync' })

  const rows = computed(() => query.data.value?.items.map(member => ({
    ...member.asset, asset: member.asset, version: member.version,
    entry_type: 'asset' as const, member_position: member.position
  })) ?? [])

  function updateRows(updates: readonly { position: number; asset: Member['asset']; version: Member['version'] }[]) {
    const current = toValue(request)
    if (!current) return
    const byPosition = new Map(updates.map(row => [row.position, row]))
    client.setQueryData<DatasetMemberPage>(queryKey.value, previous => previous && ({
      ...previous,
      items: previous.items.map(member => {
        const update = byPosition.get(member.position)
        return update ? { ...member, asset: update.asset, version: update.version } : member
      })
    }))
    void client.invalidateQueries({queryKey:queryKey.value})
    void client.invalidateQueries({ queryKey: libraryQueryKey(current.workspaceId) })
  }

  async function refresh() {
    const current=toValue(request)
    if(!current)return
    await client.invalidateQueries({queryKey:[...workspaceQueryKey(current.workspaceId),'datasets',current.datasetId,'versions',current.versionId,'members'],refetchType:'none'})
    return query.refetch({cancelRefetch:false})
  }
  return { ...query, refresh, rows, updateRows }
}

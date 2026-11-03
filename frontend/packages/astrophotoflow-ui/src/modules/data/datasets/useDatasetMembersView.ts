import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useStableQueryInput } from '../../../core/query/viewInput'
import type { ListViewInput } from '../../../core/query/viewInput'
import { zListDatasetMemberSummariesQuery } from '../../../generated/api/zod.gen'
import { useDatasetMembersQuery } from './queries'
import type { DatasetMembersRequest } from './queries'

export interface DatasetMembersViewInput extends ListViewInput {
  dataset?: { id: string; versionId: string }
  sort: { by: string; order: 'asc' | 'desc' }
}
export function useDatasetMembersView(
  input: MaybeRefOrGetter<DatasetMembersViewInput>,
  paused: MaybeRefOrGetter<boolean>
) {
  const desired = computed<DatasetMembersRequest | undefined>(() => {
    const state = toValue(input)
    if (!state.active || !state.workspaceId || !state.dataset) return
    return {
      workspaceId: state.workspaceId,
      datasetId: state.dataset.id,
      versionId: state.dataset.versionId,
      query: zListDatasetMemberSummariesQuery.parse({
        limit: state.pageSize === 'all' ? 200 : state.pageSize,
        offset: state.pageSize === 'all' ? 0 : state.offset,
        q: state.search || undefined,
        sort_by:
          state.sort.by === 'member_position' ? 'position' : state.sort.by,
        order: state.sort.order
      }),
      all: state.pageSize === 'all'
    }
  })
  const request = useStableQueryInput(desired, paused, (state) =>
    JSON.stringify([state.workspaceId, state.datasetId, state.versionId])
  )
  return { request, query: useDatasetMembersQuery(request, paused) }
}
